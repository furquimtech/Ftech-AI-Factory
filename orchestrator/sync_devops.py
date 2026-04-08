"""
Azure DevOps sync – imports new backlog items as tasks in the local DB.
Called periodically by the scheduler (or manually via the API).
"""
from __future__ import annotations

from config.logging_config import get_logger
from database.session import AsyncSessionLocal
from database.task_repository import TaskRepository
from integrations.azure_devops import AzureDevOpsIntegration

logger = get_logger("orchestrator.sync_devops")


async def sync_backlog() -> dict:
    """Pull new items from Azure DevOps and create local tasks for them."""
    devops = AzureDevOpsIntegration()
    items = devops.get_backlog_items(state="New")
    created = []
    skipped = []

    async with AsyncSessionLocal() as session:
        repo = TaskRepository(session)
        for item in items:
            external_id = item["external_id"]
            # Avoid duplicates: check if external_id already exists
            from sqlalchemy import select
            from database.models import Task
            result = await session.execute(
                select(Task).where(Task.external_id == external_id)
            )
            existing = result.scalar_one_or_none()
            if existing:
                skipped.append(external_id)
                continue

            task = await repo.create(
                title=item["title"],
                description=item.get("description", ""),
                acceptance_criteria=item.get("acceptance_criteria", ""),
                external_id=external_id,
            )
            created.append(str(task.id))
            logger.info(f"Imported work item {external_id} → task {task.id}")

            # Mark as Active in DevOps
            devops.update_work_item_state(external_id, "Active")

    logger.info(f"Sync complete: {len(created)} created, {len(skipped)} skipped")
    return {"created": created, "skipped": skipped}
