"""
QA Agent
─────────
Validates generated code against the original requirements.
Returns a structured report with pass/fail and observations.
"""
from __future__ import annotations

from agents.base_agent import BaseAgent
from config.settings import LLM_QA
from llm import get_provider


class QAAgent(BaseAgent):
    name = "qa"

    def __init__(self) -> None:
        super().__init__()
        self.llm = get_provider(LLM_QA)

    def _review_prompt(self, task: dict, code: str, language: str) -> str:
        return (
            f"You are a senior QA engineer and {language} code reviewer.\n"
            f"Evaluate the code below against the acceptance criteria.\n\n"
            f"## Acceptance Criteria\n{task.get('acceptance_criteria', 'N/A')}\n\n"
            f"## Code to Review\n{code}\n\n"
            f"Respond with a JSON object:\n"
            f'{{"passed": true|false, "score": 0-10, "issues": ["..."], "suggestions": ["..."]}}\n'
            f"Output ONLY valid JSON."
        )

    def execute(self, task: dict) -> dict:
        import json

        artifacts = task.get("artifacts", {})
        backend_code = artifacts.get("backend_code", "")
        frontend_code = artifacts.get("frontend_code", "")

        reports = {}
        overall_passed = True

        for lang, code in [("C#", backend_code), ("TypeScript/React", frontend_code)]:
            if not code:
                continue
            raw = self.llm.generate(self._review_prompt(task, code, lang))
            try:
                report = json.loads(raw)
            except json.JSONDecodeError:
                report = {"passed": False, "score": 0, "raw": raw, "parse_error": True}

            reports[lang] = report
            if not report.get("passed", False):
                overall_passed = False

        self.logger.info(
            f"QA result for task {task.get('id')}: passed={overall_passed}"
        )
        return {"passed": overall_passed, "reports": reports}
