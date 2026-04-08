"""
Azure DevOps integration.
Covers:
  • Reading work items from a Kanban board
  • Updating work item state
  • Updating Wiki pages

Uses the Azure DevOps REST API with a Personal Access Token (PAT).
Set AZURE_DEVOPS_ORG, AZURE_DEVOPS_PROJECT, AZURE_DEVOPS_PAT in .env.
"""
from __future__ import annotations

import base64
from typing import Any

import httpx

from config.logging_config import get_logger
from config.settings import AZURE_DEVOPS_ORG, AZURE_DEVOPS_PAT, AZURE_DEVOPS_PROJECT

logger = get_logger("integration.azure_devops")

_API_VERSION = "7.1"
_BASE = "https://dev.azure.com"
_WIKI_BASE = "https://dev.azure.com"


def _auth_header(pat: str) -> dict[str, str]:
    token = base64.b64encode(f":{pat}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


class AzureDevOpsIntegration:
    """Wraps the Azure DevOps REST API."""

    def __init__(
        self,
        org: str = AZURE_DEVOPS_ORG,
        project: str = AZURE_DEVOPS_PROJECT,
        pat: str = AZURE_DEVOPS_PAT,
    ) -> None:
        self.org = org
        self.project = project
        self._headers = {
            **_auth_header(pat),
            "Content-Type": "application/json",
        }
        self._client = httpx.Client(timeout=30)
        self._simulated = not (org and project and pat)
        if self._simulated:
            logger.warning("Azure DevOps credentials not set – running in simulation mode")

    # ── Work Items ─────────────────────────────────────────────────────────────

    def get_backlog_items(self, state: str = "New", top: int = 20) -> list[dict]:
        """Return work items in the given state from the project backlog."""
        if self._simulated:
            return self._mock_work_items()

        # WIQL query
        wiql_url = (
            f"{_BASE}/{self.org}/{self.project}/_apis/wit/wiql"
            f"?api-version={_API_VERSION}"
        )
        wiql = {
            "query": (
                f"SELECT [System.Id],[System.Title],[System.Description],"
                f"[Microsoft.VSTS.Common.AcceptanceCriteria]"
                f" FROM WorkItems"
                f" WHERE [System.TeamProject]='{self.project}'"
                f" AND [System.State]='{state}'"
                f" ORDER BY [System.CreatedDate] ASC"
            )
        }
        resp = self._client.post(wiql_url, json=wiql, headers=self._headers)
        resp.raise_for_status()
        ids = [wi["id"] for wi in resp.json().get("workItems", [])[:top]]

        if not ids:
            return []

        # Batch fetch details
        ids_str = ",".join(map(str, ids))
        fields = (
            "System.Id,System.Title,System.Description,"
            "Microsoft.VSTS.Common.AcceptanceCriteria,System.State"
        )
        detail_url = (
            f"{_BASE}/{self.org}/{self.project}/_apis/wit/workitems"
            f"?ids={ids_str}&fields={fields}&api-version={_API_VERSION}"
        )
        resp = self._client.get(detail_url, headers=self._headers)
        resp.raise_for_status()

        items = []
        for wi in resp.json().get("value", []):
            f = wi.get("fields", {})
            items.append({
                "id": str(wi["id"]),
                "external_id": str(wi["id"]),
                "title": f.get("System.Title", ""),
                "description": f.get("System.Description", ""),
                "acceptance_criteria": f.get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
                "state": f.get("System.State", ""),
            })
        return items

    def update_work_item_state(self, work_item_id: str, state: str) -> dict:
        """Transition a work item to a new state."""
        if self._simulated:
            logger.info(f"[SIM] Update work item {work_item_id} → {state}")
            return {"simulated": True, "id": work_item_id, "state": state}

        url = (
            f"{_BASE}/{self.org}/{self.project}/_apis/wit/workitems/{work_item_id}"
            f"?api-version={_API_VERSION}"
        )
        patch = [{"op": "add", "path": "/fields/System.State", "value": state}]
        headers = {**self._headers, "Content-Type": "application/json-patch+json"}
        resp = self._client.patch(url, json=patch, headers=headers)
        resp.raise_for_status()
        logger.info(f"Work item {work_item_id} updated to state '{state}'")
        return resp.json()

    # ── Wiki ───────────────────────────────────────────────────────────────────

    def update_wiki(self, page_path: str, content: str) -> dict[str, Any]:
        """Create or update a Wiki page with Markdown content."""
        if self._simulated:
            logger.info(f"[SIM] Update wiki page '{page_path}' ({len(content)} chars)")
            return {"simulated": True, "page_path": page_path}

        # Get wiki id first
        wikis_url = (
            f"{_BASE}/{self.org}/{self.project}/_apis/wiki/wikis"
            f"?api-version={_API_VERSION}"
        )
        resp = self._client.get(wikis_url, headers=self._headers)
        resp.raise_for_status()
        wikis = resp.json().get("value", [])
        if not wikis:
            raise RuntimeError("No wikis found in the project")
        wiki_id = wikis[0]["id"]

        # Upsert page
        page_url = (
            f"{_BASE}/{self.org}/{self.project}/_apis/wiki/wikis/{wiki_id}/pages"
            f"?path={page_path}&api-version={_API_VERSION}"
        )
        resp = self._client.get(page_url, headers=self._headers)
        etag = resp.headers.get("ETag", "") if resp.status_code == 200 else ""

        put_headers = {**self._headers, "Content-Type": "application/json"}
        if etag:
            put_headers["If-Match"] = etag

        resp = self._client.put(
            page_url,
            json={"content": content},
            headers=put_headers,
        )
        resp.raise_for_status()
        logger.info(f"Wiki page '{page_path}' updated")
        return resp.json()

    # ── simulation helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _mock_work_items() -> list[dict]:
        return [
            {
                "id": "sim-001",
                "external_id": "sim-001",
                "title": "Create user authentication module",
                "description": "Implement JWT-based authentication for the API.",
                "acceptance_criteria": "- POST /auth/login returns JWT\n- Token expires in 1h",
                "state": "New",
            }
        ]

    def __del__(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
