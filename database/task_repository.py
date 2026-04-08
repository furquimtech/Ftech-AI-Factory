"""
Task queue operations (CRUD + status transitions).
"""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AgentName, Task, TaskExecution, TaskStatus


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── create ─────────────────────────────────────────────────────────────────

    async def create(
        self,
        title: str,
        description: str = "",
        acceptance_criteria: str = "",
        external_id: str | None = None,
        payload: dict | None = None,
    ) -> Task:
        task = Task(
            title=title,
            description=description,
            acceptance_criteria=acceptance_criteria,
            external_id=external_id,
            payload=payload or {},
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    # ── read ───────────────────────────────────────────────────────────────────

    async def get(self, task_id: uuid.UUID) -> Task | None:
        return await self.session.get(Task, task_id)

    async def list_by_status(self, status: TaskStatus) -> Sequence[Task]:
        result = await self.session.execute(
            select(Task).where(Task.status == status).order_by(Task.created_at)
        )
        return result.scalars().all()

    async def next_pending(self, status: TaskStatus) -> Task | None:
        result = await self.session.execute(
            select(Task)
            .where(Task.status == status)
            .order_by(Task.created_at)
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ── update ─────────────────────────────────────────────────────────────────

    async def update_status(self, task_id: uuid.UUID, status: TaskStatus) -> None:
        await self.session.execute(
            update(Task).where(Task.id == task_id).values(status=status)
        )
        await self.session.commit()

    async def save_result(
        self, task_id: uuid.UUID, result: dict, status: TaskStatus
    ) -> None:
        await self.session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(result=result, status=status)
        )
        await self.session.commit()

    async def increment_retry(self, task_id: uuid.UUID) -> None:
        task = await self.get(task_id)
        if task:
            task.retries += 1
            await self.session.commit()

    # ── execution log ──────────────────────────────────────────────────────────

    async def log_execution(
        self,
        task_id: uuid.UUID,
        agent: AgentName,
        success: bool,
        output: dict | None = None,
        error: str | None = None,
        duration_ms: float = 0.0,
    ) -> None:
        execution = TaskExecution(
            task_id=task_id,
            agent=agent,
            success=success,
            output=output,
            error=error,
            duration_ms=duration_ms,
        )
        self.session.add(execution)
        await self.session.commit()
