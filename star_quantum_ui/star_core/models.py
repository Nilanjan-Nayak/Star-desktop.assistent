"""Plain data types shared by every backend module."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Analysis:
    intent: str = "chat"
    summary: str = ""
    language: str = "en"                # bn | banglish | en
    entities: dict = field(default_factory=dict)
    missing_info: list = field(default_factory=list)
    questions: list = field(default_factory=list)
    risk: str = "low"                   # low | medium | high
    needs_plan: bool = False
    direct_answer: str | None = None
    remember: list = field(default_factory=list)   # [{kind,key,content}] only when the user asked


@dataclass
class Step:
    id: str
    tool: str
    args: dict
    description: str = ""


@dataclass
class Plan:
    goal: str
    steps: list = field(default_factory=list)       # list[Step]
    unsupported: list = field(default_factory=list)  # things the tools cannot do
    skill: str | None = None                          # "name@version" when a skill produced the plan


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class Verdict:
    passed: bool
    checks: list = field(default_factory=list)      # list[Check]
    reason: str = ""

    @classmethod
    def of(cls, checks: list) -> "Verdict":
        failed = [c for c in checks if not c.passed]
        return cls(not failed, checks, "; ".join(f"{c.name}: {c.detail}" for c in failed))


@dataclass
class ToolResult:
    ok: bool
    output: dict = field(default_factory=dict)
    error: str | None = None
    error_kind: str | None = None       # see recovery.classify


@dataclass
class StepOutcome:
    step: Step
    result: ToolResult | None = None
    verdict: Verdict | None = None
    attempts: int = 0
    skipped: bool = False

    @property
    def verified(self) -> bool:
        return bool(self.result and self.result.ok and self.verdict and self.verdict.passed)


@dataclass
class TaskReport:
    ok: bool                              # True only when EVERY step was independently verified
    summary: str
    outcomes: list = field(default_factory=list)
    plan: Plan | None = None
    analysis: Analysis | None = None
    skill_used: str | None = None
    partial: bool = False
    meta: dict[str, Any] = field(default_factory=dict)
