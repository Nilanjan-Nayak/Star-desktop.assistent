"""Multi-tier Memory Engine for STAR.

Organizes memories across four physiological tiers:
  1. Working Memory (RAM/Session state, short-term conversational context)
  2. Episodic Memory (JSONL chronological logs of tasks, successes, and failed patterns for learning)
  3. Semantic Memory (Structured knowledge graph, user preferences, PC environment facts)
  4. Procedural Memory (Verified dynamic skills and workflows)

All stored in human-readable and agent-inspectable format under `star_memory/`.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("star.memory")


class MultiTierMemory:
    """Manages the star_memory folder hierarchy and synchronizes structured memories."""

    def __init__(self, base_dir: Path | str | None = None):
        if base_dir is None:
            # Default to star_memory inside workspace or ~/.star/star_memory
            workspace_candidate = Path.cwd() / "star_memory"
            if (Path.cwd() / "star_core").exists():
                self.base_dir = workspace_candidate
            else:
                self.base_dir = Path.home() / ".star" / "star_memory"
        else:
            self.base_dir = Path(base_dir)

        self._lock = threading.RLock()
        self.working_dir = self.base_dir / "working"
        self.episodic_dir = self.base_dir / "episodic"
        self.semantic_dir = self.base_dir / "semantic"
        self.skills_dir = self.base_dir / "skills_catalog"
        self.procedural_dir = self.base_dir / "procedural"
        self.training_dir = self.base_dir / "training"
        self.manifests_dir = self.base_dir / "manifests"

        self._init_dirs()

    def _atomic_write(self, path: Path, text: str) -> None:
        """Atomic write using temporary file and atomic replace to prevent corruption."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".tmp_{time.time_ns()}")
        try:
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)
        except Exception:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            # Fallback direct write
            path.write_text(text, encoding="utf-8")

    def _init_dirs(self) -> None:
        """Create directory structure and default templates if they do not exist."""
        # Core physiological directories (Blueprint Section 8)
        subdirs = [
            self.working_dir,
            self.episodic_dir,
            self.semantic_dir,
            self.skills_dir,
            self.procedural_dir / "drafts",
            self.procedural_dir / "tested",
            self.procedural_dir / "active",
            self.procedural_dir / "quarantine",
            self.training_dir / "exports",
            self.manifests_dir,
        ]
        for d in subdirs:
            d.mkdir(parents=True, exist_ok=True)

        user_prof = self.semantic_dir / "user_profile.json"
        if not user_prof.exists():
            self._atomic_write(user_prof, json.dumps({
                "schema_version": 1,
                "language_preference": "bn",
                "interaction_style": "conversational",
                "custom_notes": []
            }, indent=2, ensure_ascii=False))

        sys_kn = self.semantic_dir / "system_knowledge.json"
        if not sys_kn.exists():
            self._atomic_write(sys_kn, json.dumps({
                "schema_version": 1,
                "os": os.name,
                "verified_paths": [],
                "installed_tools": ["python", "git"]
            }, indent=2, ensure_ascii=False))

        mem_schema = self.manifests_dir / "memory_schema.json"
        if not mem_schema.exists():
            self._atomic_write(mem_schema, json.dumps({
                "schema_version": 1,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tiers": ["working", "episodic", "semantic", "procedural", "training"]
            }, indent=2))

    # ------------------------------------------------------------------
    # 1. Working Memory
    # ------------------------------------------------------------------
    def set_working_context(self, task_id: str, context: dict[str, Any]) -> None:
        with self._lock:
            path = self.working_dir / f"{task_id}.json"
            self._atomic_write(path, json.dumps(context, indent=2, ensure_ascii=False))

            # Maintain context_index.json pointers
            idx_path = self.working_dir / "context_index.json"
            try:
                curr = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {}
            except Exception:
                curr = {}
            curr[task_id] = {"updated": time.time(), "file": f"{task_id}.json"}
            self._atomic_write(idx_path, json.dumps(curr, indent=2))

    def clear_working_context(self, task_id: str) -> None:
        with self._lock:
            path = self.working_dir / f"{task_id}.json"
            if path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # 2. Episodic Memory (Task Logs & Error Feedback Patterns)
    # ------------------------------------------------------------------
    def log_task_run(self, intent: str, summary: str, ok: bool, duration_s: float, details: dict | None = None) -> None:
        """Record an episodic memory event in chronological jsonl."""
        event = {
            "timestamp": time.time(),
            "iso_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "intent": intent,
            "summary": summary,
            "ok": ok,
            "duration_s": round(duration_s, 2),
            "details": details or {}
        }
        with self._lock:
            path = self.episodic_dir / "tasks_timeline.jsonl"
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def record_failed_pattern(self, intent: str, tool: str, error: str, context: str) -> None:
        """Record a failure pattern so the Brain learns never to repeat the same error."""
        entry = {
            "timestamp": time.time(),
            "intent": intent,
            "tool": tool,
            "error": error,
            "context": context[:300]
        }
        with self._lock:
            path = self.episodic_dir / "failed_patterns.jsonl"
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_recent_failed_patterns(self, limit: int = 5) -> list[dict]:
        """Retrieve recent failure patterns for planner negative prompting."""
        path = self.episodic_dir / "failed_patterns.jsonl"
        if not path.exists():
            return []
        patterns = []
        with self._lock:
            try:
                lines = path.read_text(encoding="utf-8").strip().splitlines()
                for line in lines[-limit:]:
                    if line.strip():
                        patterns.append(json.loads(line))
            except Exception as e:
                log.warning("failed reading failed_patterns.jsonl: %s", e)
        return patterns

    def log_latency_event(self, stage: str, duration_ms: float, details: dict | None = None) -> None:
        """Record fine-grained latency breakdown event in latency_events.jsonl (Blueprint 7.1)."""
        evt = {
            "timestamp": time.time(),
            "stage": stage,
            "duration_ms": round(duration_ms, 2),
            "details": details or {}
        }
        with self._lock:
            path = self.episodic_dir / "latency_events.jsonl"
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(evt, ensure_ascii=False) + "\n")

    def record_correction(self, original_plan: list[str], corrected_plan: list[str], reason: str, error_class: str = "general") -> None:
        """Record user or model correction pairs for safe training dataset generation (Blueprint 9.1)."""
        corr = {
            "timestamp": time.time(),
            "schema_version": 1,
            "error_class": error_class,
            "original_plan": original_plan,
            "corrected_plan": corrected_plan,
            "reason": reason,
        }
        with self._lock:
            path = self.episodic_dir / "corrections.jsonl"
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(corr, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # 3. Semantic Memory
    # ------------------------------------------------------------------
    def update_user_profile(self, key: str, value: Any) -> None:
        with self._lock:
            path = self.semantic_dir / "user_profile.json"
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            data[key] = value
            self._atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False))

    def get_semantic_facts(self) -> str:
        """Summarize semantic knowledge for inclusion in the brain context."""
        facts = []
        with self._lock:
            p_path = self.semantic_dir / "user_profile.json"
            if p_path.exists():
                try:
                    p = json.loads(p_path.read_text(encoding="utf-8"))
                    facts.append(f"User preferences: {json.dumps(p, ensure_ascii=False)}")
                except Exception:
                    pass
            k_path = self.semantic_dir / "system_knowledge.json"
            if k_path.exists():
                try:
                    k = json.loads(k_path.read_text(encoding="utf-8"))
                    facts.append(f"System facts: {json.dumps(k, ensure_ascii=False)}")
                except Exception:
                    pass
        return "\n".join(facts)
