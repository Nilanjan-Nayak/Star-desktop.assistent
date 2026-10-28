from __future__ import annotations
import logging
from typing import Any
from .protocol import HiveTask, HiveResult

log = logging.getLogger("star.hive.commander")


class CommanderAgent:
    """Central Hive Commander agent that decomposes queries and delegates to specialists."""

    def __init__(self, router=None):
        self.router = router

    def decompose(self, query: str) -> list[HiveTask]:
        low = query.lower()
        tasks = []

        if any(w in low for w in ("research", "khujo", "search", "verify")):
            tasks.append(HiveTask(
                task_id="task_research",
                task_type="research",
                instructions=f"Investigate topic: {query}",
                assigned_to="researcher",
            ))

        if any(w in low for w in ("code", "python", "script", "website", "html", "banai", "banao")):
            tasks.append(HiveTask(
                task_id="task_coder",
                task_type="coding",
                instructions=f"Synthesize verified code for: {query}",
                assigned_to="coder",
                dependencies=["task_research"] if tasks else [],
            ))

        if not tasks:
            tasks.append(HiveTask(
                task_id="task_general",
                task_type="writing",
                instructions=query,
                assigned_to="writer",
            ))

        return tasks
