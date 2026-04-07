"""
Base agent interface.  Every concrete agent must inherit from BaseAgent
and implement execute(task) -> AgentResult.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from config.logging_config import get_logger
from config.settings import MAX_RETRIES


@dataclass
class AgentResult:
    success: bool
    agent: str
    task_id: str
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


class BaseAgent(ABC):
    """Common contract for all FTech AI Factory agents."""

    name: str = "base"

    def __init__(self) -> None:
        self.logger = get_logger(f"agent.{self.name}")

    # ── public entry-point ────────────────────────────────────────────────────

    def run(self, task: dict) -> AgentResult:
        """Execute with automatic retry and timing."""
        task_id = str(task.get("id", "unknown"))
        self.logger.info("Starting task", extra={"task_id": task_id})

        for attempt in range(1, MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                output = self.execute(task)
                duration_ms = (time.monotonic() - t0) * 1000
                self.logger.info(
                    f"Task completed (attempt {attempt})",
                    extra={"task_id": task_id, "duration_ms": duration_ms},
                )
                return AgentResult(
                    success=True,
                    agent=self.name,
                    task_id=task_id,
                    output=output,
                    duration_ms=duration_ms,
                )
            except Exception as exc:  # noqa: BLE001
                duration_ms = (time.monotonic() - t0) * 1000
                self.logger.warning(
                    f"Attempt {attempt} failed: {exc}",
                    extra={"task_id": task_id},
                    exc_info=True,
                )
                if attempt == MAX_RETRIES:
                    return AgentResult(
                        success=False,
                        agent=self.name,
                        task_id=task_id,
                        error=str(exc),
                        duration_ms=duration_ms,
                    )

        # unreachable, but makes mypy happy
        return AgentResult(success=False, agent=self.name, task_id=task_id)

    # ── abstract ──────────────────────────────────────────────────────────────

    @abstractmethod
    def execute(self, task: dict) -> dict:
        """
        Core agent logic.  Receives a task dict and returns a result dict.
        Raise any exception to trigger the retry mechanism.
        """
