"""
GitHub integration.
Covers:
  • Creating a branch from main
  • Committing a file (create or update)
  • Opening a Pull Request

Uses the GitHub REST API v3 with a Personal Access Token.
Set GITHUB_TOKEN and GITHUB_REPO (owner/repo) in .env.
"""
from __future__ import annotations

import base64
from typing import Any

import httpx

from config.logging_config import get_logger
from config.settings import GITHUB_REPO, GITHUB_TOKEN

logger = get_logger("integration.github")

_API = "https://api.github.com"
_DEFAULT_BRANCH = "main"


class GitHubIntegration:
    """Thin wrapper around the GitHub REST API."""

    def __init__(
        self,
        token: str = GITHUB_TOKEN,
        repo: str = GITHUB_REPO,
    ) -> None:
        self.repo = repo
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self._client = httpx.Client(timeout=30)
        self._simulated = not (token and repo)
        if self._simulated:
            logger.warning("GitHub credentials not set – running in simulation mode")

    # ── Branch ─────────────────────────────────────────────────────────────────

    def ensure_branch(self, branch: str, base: str = _DEFAULT_BRANCH) -> None:
        """Create branch from base if it doesn't already exist."""
        if self._simulated:
            logger.info(f"[SIM] Ensure branch '{branch}' from '{base}'")
            return

        # Get base SHA
        ref_url = f"{_API}/repos/{self.repo}/git/ref/heads/{base}"
        resp = self._client.get(ref_url, headers=self._headers)
        resp.raise_for_status()
        sha = resp.json()["object"]["sha"]

        # Check if branch exists
        check = self._client.get(
            f"{_API}/repos/{self.repo}/git/ref/heads/{branch}",
            headers=self._headers,
        )
        if check.status_code == 200:
            logger.debug(f"Branch '{branch}' already exists")
            return

        # Create branch
        create = self._client.post(
            f"{_API}/repos/{self.repo}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": sha},
            headers=self._headers,
        )
        create.raise_for_status()
        logger.info(f"Branch '{branch}' created from '{base}' ({sha[:7]})")

    # ── Commit ─────────────────────────────────────────────────────────────────

    def commit_file(
        self,
        branch: str,
        file_path: str,
        content: str,
        message: str,
        base: str = _DEFAULT_BRANCH,
    ) -> dict[str, Any]:
        """Create or update a file in the repository and return the commit."""
        self.ensure_branch(branch, base)

        if self._simulated:
            logger.info(f"[SIM] Commit '{file_path}' to branch '{branch}'")
            return {"simulated": True, "file": file_path, "branch": branch}

        encoded = base64.b64encode(content.encode()).decode()
        url = f"{_API}/repos/{self.repo}/contents/{file_path}"

        # Check existing file for SHA (needed for updates)
        existing = self._client.get(url, params={"ref": branch}, headers=self._headers)
        body: dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        if existing.status_code == 200:
            body["sha"] = existing.json()["sha"]

        resp = self._client.put(url, json=body, headers=self._headers)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Committed '{file_path}' to '{branch}'")
        return {
            "file": file_path,
            "branch": branch,
            "commit_sha": data.get("commit", {}).get("sha", ""),
        }

    # ── Pull Request ───────────────────────────────────────────────────────────

    def create_pull_request(
        self,
        branch: str,
        title: str,
        body: str,
        base: str = _DEFAULT_BRANCH,
    ) -> dict[str, Any]:
        """Open a PR from branch → base. Returns PR data including html_url."""
        if self._simulated:
            logger.info(f"[SIM] Create PR '{title}' ({branch} → {base})")
            return {
                "simulated": True,
                "html_url": f"https://github.com/{self.repo}/pull/0",
                "number": 0,
            }

        resp = self._client.post(
            f"{_API}/repos/{self.repo}/pulls",
            json={"title": title, "body": body, "head": branch, "base": base},
            headers=self._headers,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"PR #{data['number']} created: {data['html_url']}")
        return data

    def __del__(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
