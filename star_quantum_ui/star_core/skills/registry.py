"""Skill registry: versioned skills on disk, approved ones indexed into memory and matched at planning time."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..memory import MemoryStore
from ..models import Analysis, Plan
from ..text import tokens
from .workflow import bind

STATUSES = ("draft", "tested", "approved", "retired", "needs_review")


@dataclass
class Skill:
    name: str
    version: int
    kind: str                         # workflow | code
    intent: str = ""
    description: str = ""
    triggers: list = field(default_factory=list)
    params: list = field(default_factory=list)
    entity_keys: list = field(default_factory=list)   # every entity key seen when it was learned
    steps: list = field(default_factory=list)         # workflow template
    code: str = ""                                    # code skills
    tests: list = field(default_factory=list)
    status: str = "draft"
    created: float = 0.0
    uses: int = 0
    failures: int = 0
    last_eval: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.name}@v{self.version}"


class SkillRegistry:
    def __init__(self, root: Path, store: MemoryStore):
        self.root, self.store = Path(root), store
        self.root.mkdir(parents=True, exist_ok=True)

    # storage -------------------------------------------------------------------------------
    def _path(self, name: str, version: int) -> Path:
        return self.root / name / f"v{version}.json"

    def save(self, skill: Skill) -> Skill:
        p = self._path(skill.name, skill.version)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(skill), indent=2, ensure_ascii=False), encoding="utf-8")
        return skill

    def versions(self, name: str) -> list[Skill]:
        d = self.root / name
        if not d.is_dir():
            return []
        out = [Skill(**json.loads(p.read_text(encoding="utf-8"))) for p in d.glob("v*.json")]
        return sorted(out, key=lambda s: s.version)

    def all(self) -> list[Skill]:
        return [s for d in sorted(self.root.iterdir()) if d.is_dir() for s in self.versions(d.name)]

    def get(self, name: str, version: int) -> Skill | None:
        p = self._path(name, version)
        return Skill(**json.loads(p.read_text(encoding="utf-8"))) if p.exists() else None

    def active(self, name: str) -> Skill | None:
        approved = [s for s in self.versions(name) if s.status == "approved"]
        return approved[-1] if approved else None

    def active_skills(self) -> list[Skill]:
        names = [d.name for d in self.root.iterdir() if d.is_dir()]
        return [s for n in names if (s := self.active(n))]

    def next_version(self, name: str) -> int:
        v = self.versions(name)
        return (v[-1].version + 1) if v else 1

    def count_approved(self) -> int:
        return len(self.active_skills())

    # lifecycle -----------------------------------------------------------------------------
    def new_draft(self, **kw) -> Skill:
        name = kw["name"]
        return self.save(Skill(version=self.next_version(name), created=time.time(), status="draft", **kw))

    def set_status(self, skill: Skill, status: str) -> Skill:
        skill.status = status
        return self.save(skill)

    def approve(self, skill: Skill) -> Skill:
        for old in self.versions(skill.name):
            if old.version != skill.version and old.status == "approved":
                self.set_status(old, "retired")
        self.set_status(skill, "approved")
        self._index(skill)
        return skill

    def retire(self, skill: Skill) -> None:
        self.set_status(skill, "retired")
        for m in self.store.all("skill"):
            if m.key == skill.name:
                self.store.forget(m.id)

    def _index(self, skill: Skill) -> None:
        for m in self.store.all("skill"):
            if m.key == skill.name:
                self.store.forget(m.id)
        self.store.add("skill", skill.name, f"{skill.description} (triggers: {', '.join(skill.triggers)})",
                       meta={"version": skill.version, "kind": skill.kind, "params": skill.params},
                       confidence=0.9, source="star")

    def record_use(self, label: str, ok: bool) -> None:
        name, ver = label.split("@v")
        s = self.get(name, int(ver))
        if s is None:
            return
        s.uses += 1
        s.failures = 0 if ok else s.failures + 1
        if s.failures >= 2:           # two failures in a row: stop trusting it until reviewed
            s.status = "needs_review"
        self.save(s)

    # use at planning time ---------------------------------------------------------------------
    def plan_for(self, analysis: Analysis, tool_registry) -> tuple[Plan, str] | None:
        best = None
        for s in self.active_skills():
            if s.kind != "workflow" or not s.params:
                continue
            same_intent = s.intent and s.intent == analysis.intent
            overlap = self._overlap(analysis.summary, s)
            if not (same_intent or overlap >= 0.6):
                continue
            if not set(s.params) <= set(analysis.entities):
                continue                                   # a required value is missing: let the planner ask/decide
            if not set(analysis.entities) <= set(s.entity_keys):
                continue                                   # the request has parts this skill never handled
            if best is None or overlap > best[0]:
                best = (overlap, s)
        if best is None:
            return None
        s = best[1]
        try:
            steps = bind(s.steps, {k: analysis.entities[k] for k in s.params})
        except KeyError:
            return None
        return Plan(analysis.summary or s.description, steps, [], s.label), s.label

    @staticmethod
    def _overlap(text: str, s: Skill) -> float:
        q = set(tokens(text))
        d = set(tokens(s.description + " " + " ".join(s.triggers)))
        return len(q & d) / len(q) if q and d else 0.0

    def hints(self, analysis: Analysis) -> str:
        lines = []
        for s in self.active_skills():
            if self._overlap(analysis.summary + " " + analysis.intent, s) >= 0.3 or s.intent == analysis.intent:
                tools = " -> ".join(st["tool"] for st in s.steps) if s.kind == "workflow" else "code skill"
                lines.append(f"- skill {s.label}: {s.description} (steps: {tools})")
        return "\n".join(lines)
