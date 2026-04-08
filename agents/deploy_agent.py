"""
Deploy Agent
────────────
Local simulation of a deploy pipeline:
  1. Pulls the branch from GitHub
  2. Runs build/test scripts (subprocess)
  3. Reports status back

For production migration: replace subprocess calls with real CI/CD triggers.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from agents.base_agent import BaseAgent


class DeployAgent(BaseAgent):
    name = "deploy"

    def _run(self, cmd: list[str], cwd: Path) -> tuple[int, str, str]:
        result = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=300
        )
        return result.returncode, result.stdout, result.stderr

    def execute(self, task: dict) -> dict:
        branch = task.get("branch", "main")
        repo_url = task.get("repo_url", "")
        task_id = str(task.get("id", "unknown"))

        self.logger.info(f"Starting local deploy simulation for task {task_id} branch={branch}")

        steps: list[dict] = []

        with tempfile.TemporaryDirectory(prefix="ftechai_deploy_") as tmpdir:
            work = Path(tmpdir)

            # Step 1 – clone
            if repo_url:
                code, out, err = self._run(
                    ["git", "clone", "--branch", branch, "--depth", "1", repo_url, str(work / "repo")],
                    cwd=work,
                )
                steps.append({"step": "clone", "code": code, "stdout": out[:500], "stderr": err[:500]})
                if code != 0:
                    raise RuntimeError(f"Git clone failed: {err[:200]}")
                work = work / "repo"

            # Step 2 – backend build (dotnet build if present)
            backend_dir = work / "backend"
            if backend_dir.exists():
                code, out, err = self._run(["dotnet", "build", "--configuration", "Release"], cwd=backend_dir)
                steps.append({"step": "dotnet_build", "code": code, "stdout": out[:500]})
                if code != 0:
                    raise RuntimeError(f"dotnet build failed: {err[:200]}")

            # Step 3 – frontend build (npm ci + build if present)
            frontend_dir = work / "frontend"
            if frontend_dir.exists():
                code, out, err = self._run(["npm", "ci"], cwd=frontend_dir)
                steps.append({"step": "npm_ci", "code": code, "stdout": out[:300]})
                if code == 0:
                    code, out, err = self._run(["npm", "run", "build"], cwd=frontend_dir)
                    steps.append({"step": "npm_build", "code": code, "stdout": out[:300]})
                if code != 0:
                    raise RuntimeError(f"Frontend build failed: {err[:200]}")

        self.logger.info(f"Deploy simulation completed for task {task_id}")
        return {"task_id": task_id, "branch": branch, "steps": steps, "status": "success"}
