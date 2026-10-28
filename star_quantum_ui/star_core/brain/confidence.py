"""Confidence Scoring System (Section A).

Calculates a 0-100 confidence score before task execution based on:
- Prior task type experience (+20)
- Prior success rate on same type (+15)
- Tool availability (+15)
- Instruction clarity (+15)
- Past errors (-20)
- Multi-step complexity (-10)
- External API dependence (-10)
- 3B model heavy reasoning limit (-15)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ConfidenceReport:
    score: int
    risk: str
    reasons: list[str]
    can_proceed: bool
    warning_message: str | None = None


class ConfidenceCalculator:
    def __init__(self, task_tracker, tool_registry):
        self.tracker = task_tracker
        self.registry = tool_registry

    def calculate(self, command: str, task_type: str, plan_steps: list[Any], intent: str) -> ConfidenceReport:
        score = 50  # Baseline
        reasons = []

        history = self.tracker.data.get("task_history", [])
        same_type_tasks = [t for t in history if t.get("task_type") == task_type]

        # 1. Prior task type experience (+20) - only for known classified task types
        if task_type != "other" and same_type_tasks:
            score += 20
            reasons.append("Task type previously executed (+20)")
        elif task_type == "other":
            reasons.append("Unclassified/general task type (+0)")
        else:
            reasons.append("First time executing this task type (+0)")

        # 2. Prior success rate (+15) - only for known classified task types
        successful_same = [t for t in same_type_tasks if t.get("status") in ("SUCCESS", "AUTO_FIXED")]
        if task_type != "other" and same_type_tasks and (len(successful_same) / len(same_type_tasks)) >= 0.7:
            score += 15
            reasons.append("High past success rate in this task type (+15)")

        # 3. Required tools available (+15)
        tools_needed = [getattr(s, "tool", s.get("tool") if isinstance(s, dict) else "") for s in plan_steps]
        all_tools_avail = all(self.registry.get(t) is not None for t in tools_needed if t)
        if all_tools_avail and tools_needed:
            score += 15
            reasons.append("All required tools registered & verified (+15)")
        elif not all_tools_avail:
            score -= 15
            reasons.append("Missing one or more required tools (-15)")

        # 4. Instruction clarity (+15) or Ambiguity/Contradiction Penalties
        words = command.strip().split()
        cmd_low = command.lower()
        has_ambiguity = any(amb in cmd_low for amb in ("oita", "sheta", "kisu ekta", "something", "oi ta"))
        is_contradictory = ("save" in cmd_low and ("delete" in cmd_low or "muche" in cmd_low)) or \
                           ("create" in cmd_low and ("delete" in cmd_low or "remove" in cmd_low))

        if is_contradictory:
            score -= 25
            reasons.append("Contradictory operations detected in instruction (-25)")
        elif len(words) >= 4 and not has_ambiguity:
            score += 15
            reasons.append("Instruction is clear and specific (+15)")
        elif has_ambiguity:
            score -= 15
            reasons.append("Instruction contains ambiguous pronoun/reference (-15)")
        else:
            reasons.append("Instruction contains ambiguity (-0)")

        # 5. Past errors on same task type (-20)
        past_errors = [t for t in same_type_tasks if t.get("status") == "FAILED"]
        if task_type != "other" and past_errors:
            score -= 20
            reasons.append(f"Previously encountered {len(past_errors)} failure(s) in this task type (-20)")

        # 6. Multi-step complexity (-10)
        if len(plan_steps) >= 3:
            score -= 10
            reasons.append(f"Multi-step complexity ({len(plan_steps)} steps) (-10)")

        # 7. External API dependence (-10)
        if any(t in ("web_search", "open_url", "serve_website") for t in tools_needed):
            score -= 10
            reasons.append("Dependent on external network/API (-10)")

        # 8. Model limitation on heavy reasoning (-15)
        heavy_terms = ("deep analysis", "machine learning", "compile", "heavy", "complex", "cryptography")
        if any(term in command.lower() for term in heavy_terms):
            score -= 15
            reasons.append("High reasoning load for 3B parameter model (-15)")

        # Clamp between 0 and 100
        score = max(5, min(100, score))

        # Risk categorization
        if score >= 75:
            risk = "Low"
        elif score >= 50:
            risk = "Medium"
        else:
            risk = "High"

        can_proceed = score >= 40
        warning_msg = None
        if not can_proceed:
            warning_msg = (
                f"Ami ei task e confident na (Confidence: {score}/100).\n"
                f"Reason: {'; '.join(reasons[-2:])}.\n"
                f"Tumi ki confirm korbe naki ami alternative suggest korbo?"
            )

        return ConfidenceReport(score=score, risk=risk, reasons=reasons, can_proceed=can_proceed, warning_message=warning_msg)
