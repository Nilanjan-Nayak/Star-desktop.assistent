"""Run accounting. The number that matters is *verified* success and how many false successes were caught."""
from __future__ import annotations

import json
import time

from .memory import MemoryStore
from .models import TaskReport


class Metrics:
    def __init__(self, store: MemoryStore):
        self.store = store

    def record(self, report: TaskReport, intent: str, seconds: float) -> None:
        executed = [o for o in report.outcomes if not o.skipped]
        # a step whose tool said "ok" but whose independent verification disagreed = a false success we caught
        claimed = any(o.result and o.result.error_kind == "verification_failed" for o in executed)
        with self.store.lock:
            self.store.db.execute(
                "INSERT INTO runs(ts,intent,claimed_ok,verified_ok,partial,steps,seconds,skill,detail) VALUES(?,?,?,?,?,?,?,?,?)",
                (time.time(), intent, int(claimed), int(report.ok), int(report.partial), len(report.outcomes), seconds,
                 report.skill_used, json.dumps(report.meta, default=str)[:500]))
            self.store.db.commit()

    def summary(self) -> dict:
        with self.store.lock:
            rows = self.store.db.execute("SELECT claimed_ok, verified_ok, partial FROM runs").fetchall()
        total = len(rows)
        verified = sum(r["verified_ok"] for r in rows)
        return {"total": total, "verified_ok": verified, "partial": sum(r["partial"] for r in rows),
                "verified_rate": (verified / total) if total else None,
                "false_success_prevented": sum(1 for r in rows if r["claimed_ok"] and not r["verified_ok"])}
