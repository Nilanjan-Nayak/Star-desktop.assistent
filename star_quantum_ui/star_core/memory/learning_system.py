"""Agent Self-Learning System with learning_log.json.

Maintains permanent learning logs, tracks recurring mistakes, user preferences,
and generates self-improvement insights.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("star.learning")


class AgentLearningSystem:
    def __init__(self, log_path: Path | str = "learning_log.json", agent_name: str = "STAR"):
        self.log_path = Path(log_path)
        self.agent_name = agent_name
        self._lock = threading.RLock()
        self.log = self._load_log()

    def _load_log(self) -> dict[str, Any]:
        """Load log file, or initialize with clean structure if missing."""
        with self._lock:
            if self.log_path.exists():
                try:
                    return json.loads(self.log_path.read_text(encoding="utf-8"))
                except Exception as e:
                    log.warning("Could not read learning_log.json (%s), creating new structure", e)

            initial = {
                "agent_name": self.agent_name,
                "version": "1.0",
                "total_tasks_completed": 0,
                "total_errors": 0,
                "learning_entries": [],
                "user_preferences": {
                    "language": "Banglish / Bengali / English",
                    "response_style": "detailed, conversational, crisp",
                    "preferred_format": "markdown with tables",
                    "theme": "dark",
                    "design_style": "minimal, clean",
                    "save_location": "Desktop / STAR_tasks / Documents",
                    "voice_enabled": True
                },
                "recurring_patterns": {
                    "most_common_tasks": [],
                    "peak_usage_time": "10:00-20:00",
                    "common_mistakes": [],
                    "user_satisfaction_trend": "improving"
                }
            }
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                self.log_path.write_text(json.dumps(initial, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
            return initial

    def _save_log(self) -> None:
        """Persist log to disk safely."""
        with self._lock:
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                self.log_path.write_text(json.dumps(self.log, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                log.error("Failed saving learning_log.json: %s", e)

    def check_past_mistakes(self, task_type: str) -> list[str]:
        """Retrieve past mistakes for this task type so the agent never repeats them."""
        with self._lock:
            mistakes = []
            for entry in self.log.get("learning_entries", []):
                if entry.get("task_type") == task_type and entry.get("mistakes_made"):
                    mistakes.extend(entry["mistakes_made"])
            # Add common mistakes from recurring patterns
            for cm in self.log.get("recurring_patterns", {}).get("common_mistakes", []):
                mistakes.append(cm)
            return list(dict.fromkeys(mistakes))

    def get_user_preferences(self) -> dict[str, Any]:
        """Return user preferences dictionary."""
        with self._lock:
            return dict(self.log.get("user_preferences", {}))

    def update_user_preference(self, key: str, value: Any) -> None:
        """Dynamically update a user preference."""
        with self._lock:
            self.log.setdefault("user_preferences", {})[key] = value
            self._save_log()

    def log_task(self, task_type: str, user_command: str, steps: list[str],
                 result: str, time_taken_seconds: float, learned: list[str] | None = None,
                 mistakes: list[str] | None = None, feedback: str = "",
                 improvement_plan: str = "") -> int:
        """Log a completed or failed task entry."""
        with self._lock:
            entries = self.log.setdefault("learning_entries", [])
            new_id = len(entries) + 1
            learned_list = [l for l in (learned or []) if l]
            mistakes_list = [m for m in (mistakes or []) if m]

            new_entry = {
                "id": new_id,
                "timestamp": datetime.now().isoformat(),
                "task_type": task_type,
                "user_command": user_command,
                "steps_taken": steps,
                "result": result,  # success | partial_success | failed
                "time_taken_seconds": round(time_taken_seconds, 2),
                "what_learned": learned_list,
                "mistakes_made": mistakes_list,
                "user_feedback": feedback,
                "improvement_plan": improvement_plan or ("Avoid mistakes: " + "; ".join(mistakes_list) if mistakes_list else "Performance verified."),
                "tags": [task_type]
            }

            entries.append(new_entry)
            self.log["total_tasks_completed"] = self.log.get("total_tasks_completed", 0) + 1

            if result in ("failed", "partial_success") or mistakes_list:
                self.log["total_errors"] = self.log.get("total_errors", 0) + 1
                for m in mistakes_list:
                    cm = self.log.setdefault("recurring_patterns", {}).setdefault("common_mistakes", [])
                    if m not in cm:
                        cm.append(m)

            # Update most common tasks
            tasks = self.log.setdefault("recurring_patterns", {}).setdefault("most_common_tasks", [])
            if task_type not in tasks:
                tasks.append(task_type)

            self._save_log()
            return new_id

    def should_self_improve(self) -> tuple[bool, str]:
        """Check if self-improvement should be triggered based on recent failure patterns."""
        with self._lock:
            recent = self.log.get("learning_entries", [])[-5:]
            if not recent:
                return False, "No tasks logged yet."
            mistake_count = sum(1 for e in recent if e.get("mistakes_made"))
            if mistake_count >= 2:
                return True, f"⚠️ Recent error rate elevated ({mistake_count}/5 tasks had issues) — self-optimization recommended."
            return False, "✅ System healthy and operating smoothly."

    def generate_improvement_report(self) -> str:
        """Generate human-readable self-improvement markdown report."""
        with self._lock:
            total = self.log.get("total_tasks_completed", 0)
            errors = self.log.get("total_errors", 0)
            success_rate = ((total - errors) / total * 100) if total > 0 else 100.0

            lines = [
                "📊 **AGENT SELF-IMPROVEMENT REPORT**",
                f"- **Agent:** {self.log.get('agent_name', self.agent_name)} (v{self.log.get('version', '1.0')})",
                f"- **Total Tasks:** {total}",
                f"- **Total Errors:** {errors}",
                f"- **Success Rate:** {success_rate:.1f}%",
                "",
                "🔴 **Recurring Mistakes to Avoid:**"
            ]
            common_m = self.log.get("recurring_patterns", {}).get("common_mistakes", [])
            if common_m:
                for m in common_m:
                    lines.append(f"  - {m}")
            else:
                lines.append("  - (None recorded yet)")

            lines.append("\n🟢 **Key Learnings (Recent):**")
            recent = self.log.get("learning_entries", [])[-5:]
            found_any = False
            for entry in recent:
                for l in entry.get("what_learned", []):
                    lines.append(f"  - [{entry.get('task_type', 'task')}] {l}")
                    found_any = True
            if not found_any:
                lines.append("  - All workflows functioning according to design standards.")

            lines.append("\n👤 **Active User Preferences:**")
            for k, v in self.log.get("user_preferences", {}).items():
                lines.append(f"  - **{k}:** {v}")

            return "\n".join(lines)
