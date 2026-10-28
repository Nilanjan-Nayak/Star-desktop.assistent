from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Any


@dataclass
class HiveMessage:
    sender: str
    recipient: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class HiveTask:
    task_id: str
    task_type: str  # research, coding, writing, evaluation
    instructions: str
    assigned_to: str
    dependencies: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class HiveResult:
    task_id: str
    agent: str
    status: str  # success, failure, retry
    output: Any
    quality_score: int = 80
    error: str | None = None
