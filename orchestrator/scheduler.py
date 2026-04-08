"""
Local scheduler – polls the task queue at a fixed interval and dispatches
pending tasks to the appropriate agents, up to MAX_PARALLEL_AGENTS at a time.
"""
from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

from config.logging_config import get_logger
from config.settings import MAX_PARALLEL_AGENTS, MAX_RETRIES, SCHEDULER_INTERVAL
from database.models import AgentName, TaskStatus
from database.session import AsyncSessionLocal
from database.task_repository import TaskRepository
from orchestrator.pipeline import STAGE_MAP

logger = get_logger("orchestrator.scheduler")
_executor = ThreadPoolExecutor(max_workers=MAX_PARALLEL_AGENTS)


async def _run_agent_for_task(task_id: uuid.UUID, status: TaskStatus) -> None:
    """Pick the right agent for the task's current status and execute it."""
    stage = STAGE_MAP.get(status)
    if stage is None:
        logger.debug(f"No stage configured for status '{status}' (task {task_id})")
        return

    agent_cls, agent_name_enum, next_status = stage

    async with AsyncSessionLocal() as session:
        repo = TaskRepository(session)
        task = await repo.get(task_id)
        if task is None:
            return

        # Build the task dict passed to the agent
        task_dict: dict = {
            "id": str(task.id),
            "title": task.title,
            "description": task.description or "",
            "acceptance_criteria": task.acceptance_criteria or "",
            **(task.payload or {}),
        }

        # Carry QA report into downstream agents
        if task.result:
            task_dict.update(task.result)

    # Run the (sync) agent in a thread so we don't block the event loop
    loop = asyncio.get_running_loop()
    agent_instance = agent_cls()
    result = await loop.run_in_executor(_executor, agent_instance.run, task_dict)

    async with AsyncSessionLocal() as session:
        repo = TaskRepository(session)
        if result.success:
            await repo.save_result(task_id, result.output, next_status)
        else:
            task = await repo.get(task_id)
            retries = task.retries if task else 0
            if retries >= MAX_RETRIES:
                await repo.save_result(task_id, {"error": result.error}, TaskStatus.FAILED)
                logger.error(f"Task {task_id} permanently failed after {retries} retries")
            else:
                await repo.increment_retry(task_id)
                logger.warning(f"Task {task_id} failed (attempt {retries + 1}), will retry")

        await repo.log_execution(
            task_id=task_id,
            agent=agent_name_enum,
            success=result.success,
            output=result.output if result.success else None,
            error=result.error,
            duration_ms=result.duration_ms,
        )

    logger.info(
        f"Task {task_id}: agent={agent_name_enum.value} "
        f"success={result.success} → {next_status.value if result.success else 'retry/failed'}"
    )


async def _poll_once() -> None:
    """Single scheduler tick – dispatch one task per active pipeline stage."""
    semaphore = asyncio.Semaphore(MAX_PARALLEL_AGENTS)
    tasks_dispatched: list[asyncio.Task] = []

    for status in STAGE_MAP:
        async with AsyncSessionLocal() as session:
            repo = TaskRepository(session)
            task = await repo.next_pending(status)
            if task is None:
                continue
            task_id = task.id

        async def _guarded(tid=task_id, st=status) -> None:
            async with semaphore:
                await _run_agent_for_task(tid, st)

        tasks_dispatched.append(asyncio.create_task(_guarded()))

    if tasks_dispatched:
        await asyncio.gather(*tasks_dispatched, return_exceptions=True)


async def start_scheduler() -> None:
    """Run indefinitely, polling every SCHEDULER_INTERVAL seconds."""
    logger.info(f"Scheduler started (interval={SCHEDULER_INTERVAL}s, max_parallel={MAX_PARALLEL_AGENTS})")
    while True:
        try:
            await _poll_once()
        except Exception:
            logger.exception("Unexpected error in scheduler tick")
        await asyncio.sleep(SCHEDULER_INTERVAL)
