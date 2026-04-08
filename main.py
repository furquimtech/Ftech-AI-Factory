"""
FTech AI Factory – FastAPI entry point.

Run locally:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config.logging_config import get_logger
from config.settings import API_HOST, API_PORT
from database.models import Task, TaskStatus
from database.session import engine, get_session, Base
from database.task_repository import TaskRepository
from orchestrator.scheduler import start_scheduler
from orchestrator.sync_devops import sync_backlog

logger = get_logger("orchestrator.api")


# ── Startup / shutdown ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist (dev convenience; use Alembic in prod)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Start background scheduler
    task = asyncio.create_task(start_scheduler())
    logger.info("FTech AI Factory started")
    yield
    task.cancel()
    await engine.dispose()


app = FastAPI(
    title="FTech AI Factory",
    description="Multi-agent software development automation system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str
    description: str = ""
    acceptance_criteria: str = ""
    external_id: str | None = None
    payload: dict[str, Any] = {}


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str | None
    acceptance_criteria: str | None
    status: str
    retries: int
    result: dict | None
    external_id: str | None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, task: Task) -> "TaskResponse":
        return cls(
            id=str(task.id),
            title=task.title,
            description=task.description,
            acceptance_criteria=task.acceptance_criteria,
            status=task.status.value,
            retries=task.retries,
            result=task.result,
            external_id=task.external_id,
        )


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "FTech AI Factory"}


# Tasks CRUD + queue
@app.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    body: TaskCreate,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    repo = TaskRepository(session)
    task = await repo.create(
        title=body.title,
        description=body.description,
        acceptance_criteria=body.acceptance_criteria,
        external_id=body.external_id,
        payload=body.payload,
    )
    return TaskResponse.from_orm(task)


@app.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[TaskResponse]:
    repo = TaskRepository(session)
    if status:
        try:
            ts = TaskStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status '{status}'")
        tasks = await repo.list_by_status(ts)
    else:
        from sqlalchemy import select
        result = await session.execute(select(Task).order_by(Task.created_at))
        tasks = result.scalars().all()
    return [TaskResponse.from_orm(t) for t in tasks]


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    repo = TaskRepository(session)
    task = await repo.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return TaskResponse.from_orm(task)


@app.patch("/tasks/{task_id}/status")
async def update_task_status(
    task_id: uuid.UUID,
    status: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        ts = TaskStatus(status)
    except ValueError:
        raise HTTPException(400, f"Invalid status '{status}'")
    repo = TaskRepository(session)
    task = await repo.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    await repo.update_status(task_id, ts)
    return {"id": str(task_id), "status": ts.value}


# Trigger a single agent manually (useful for testing)
@app.post("/tasks/{task_id}/run")
async def run_task_now(
    task_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    repo = TaskRepository(session)
    task = await repo.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")

    from orchestrator.scheduler import _run_agent_for_task
    background_tasks.add_task(_run_agent_for_task, task_id, task.status)
    return {"message": f"Task {task_id} dispatched", "current_status": task.status.value}


# Azure DevOps sync
@app.post("/sync/devops")
async def trigger_devops_sync(background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(sync_backlog)
    return {"message": "DevOps sync started in background"}


# Knowledge search
@app.get("/knowledge/search")
async def knowledge_search(q: str, top_k: int = 5) -> list[dict]:
    from agents.knowledge_agent import KnowledgeAgent
    agent = KnowledgeAgent()
    results = await agent.search(q, top_k=top_k)
    return results


# Pipeline status overview
@app.get("/pipeline/status")
async def pipeline_status(session: AsyncSession = Depends(get_session)) -> dict:
    repo = TaskRepository(session)
    counts: dict[str, int] = {}
    for status in TaskStatus:
        tasks = await repo.list_by_status(status)
        counts[status.value] = len(tasks)
    return {"pipeline": counts}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)
