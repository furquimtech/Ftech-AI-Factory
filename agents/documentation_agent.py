"""
Documentation Agent
────────────────────
• Generates a markdown section for the feature
• Updates Azure DevOps Wiki
• Updates repository README (via GitHub commit)
"""
from __future__ import annotations

from agents.base_agent import BaseAgent
from config.settings import LLM_DOC
from integrations.azure_devops import AzureDevOpsIntegration
from integrations.github_integration import GitHubIntegration
from llm import get_provider


class DocumentationAgent(BaseAgent):
    name = "documentation"

    def __init__(self) -> None:
        super().__init__()
        self.llm = get_provider(LLM_DOC)
        self.devops = AzureDevOpsIntegration()
        self.github = GitHubIntegration()

    def _doc_prompt(self, task: dict, qa_report: dict) -> str:
        return (
            f"You are a technical writer.\n"
            f"Write clear, concise developer documentation in Markdown for the following feature:\n\n"
            f"## Feature\n"
            f"**Title:** {task.get('title', '')}\n"
            f"**Description:** {task.get('description', '')}\n"
            f"**Acceptance Criteria:** {task.get('acceptance_criteria', 'N/A')}\n\n"
            f"## QA Summary\n"
            f"Passed: {qa_report.get('passed', 'unknown')}\n\n"
            f"Include: Overview, API endpoints (if any), component usage, and known limitations.\n"
            f"Output only the Markdown text."
        )

    def execute(self, task: dict) -> dict:
        qa_report = task.get("qa_report", {})
        self.logger.info(f"Generating docs for task {task.get('id')}")

        markdown = self.llm.generate(self._doc_prompt(task, qa_report))

        # Update Azure DevOps Wiki
        wiki_result = self.devops.update_wiki(
            page_path=f"AI-Generated/{task.get('id')}-{task.get('title', 'feature')}",
            content=markdown,
        )

        # Commit docs to GitHub (docs/ folder)
        title_slug = task.get("title", "feature").lower().replace(" ", "-")[:40]
        doc_path = f"docs/{task.get('id', 'unknown')}-{title_slug}.md"
        commit_result = self.github.commit_file(
            branch="main",
            file_path=doc_path,
            content=markdown,
            message=f"docs({task.get('id')}): add feature documentation",
        )

        return {
            "doc_path": doc_path,
            "wiki_result": wiki_result,
            "commit_result": commit_result,
            "markdown_preview": markdown[:500],
        }
