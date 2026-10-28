"""Evaluator: runs a skill's tests in a throw-away folder and guards against regressions."""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ..config import Config
from ..executor import Executor
from ..models import Plan
from ..security import PermissionPolicy
from ..tools import CommandRunner, ToolContext, ToolRegistry
from .registry import Skill
from .sandbox import run_code
from .workflow import bind

TESTABLE_RISK = ("low", "medium")


@dataclass
class CaseResult:
    name: str
    passed: bool
    detail: str = ""
    false_success: bool = False     # we would have reported success, but reality disagrees


@dataclass
class EvalResult:
    cases: list = field(default_factory=list)
    blocked: str = ""

    @property
    def pass_rate(self) -> float:
        return (sum(c.passed for c in self.cases) / len(self.cases)) if self.cases else 0.0

    @property
    def false_success(self) -> int:
        return sum(c.false_success for c in self.cases)

    @property
    def passed(self) -> bool:
        return not self.blocked and bool(self.cases) and all(c.passed for c in self.cases)

    def summary(self) -> str:
        if self.blocked:
            return f"blocked: {self.blocked}"
        ok = sum(c.passed for c in self.cases)
        return f"{ok}/{len(self.cases)} tests passed, {self.false_success} false successes"

    def to_dict(self) -> dict:
        return {"pass_rate": self.pass_rate, "false_success": self.false_success, "blocked": self.blocked,
                "cases": {c.name: c.passed for c in self.cases}}


class Evaluator:
    def __init__(self, registry: ToolRegistry, config: Config):
        self.registry, self.config = registry, config

    def run(self, skill: Skill, extra_tests: list | None = None) -> EvalResult:
        tests = list(skill.tests)
        names = {t["name"] for t in tests}
        tests += [t for t in (extra_tests or []) if t["name"] not in names]
        if skill.kind == "code":
            return EvalResult([self._code_case(skill, t) for t in tests])
        for st in skill.steps:
            tool = self.registry.get(st["tool"])
            if tool is None or tool.risk not in TESTABLE_RISK:
                return EvalResult(blocked=f"step uses '{st['tool']}', which cannot be tested safely")
        return EvalResult([self._workflow_case(skill, t) for t in tests])

    def compare(self, new: EvalResult, old: EvalResult | None) -> list[str]:
        reasons = []
        if not new.passed:
            reasons.append("the new version fails its own tests")
        if new.false_success:
            reasons.append("the new version would report a false success")
        if old is not None:
            before, after = {c.name: c.passed for c in old.cases}, {c.name: c.passed for c in new.cases}
            reasons += [f"regression: '{n}' passed before and fails now" for n, ok in before.items() if ok and after.get(n) is False]
            if new.pass_rate < old.pass_rate:
                reasons.append(f"pass rate dropped from {old.pass_rate:.0%} to {new.pass_rate:.0%}")
        return reasons

    # cases ---------------------------------------------------------------------------------
    def _code_case(self, skill: Skill, case: dict) -> CaseResult:
        r = run_code(skill.code, case["input"])
        if not r.ok:
            return CaseResult(case["name"] if "name" in case else str(case["input"])[:30], False, r.error)
        ok = r.result == case["expect"]
        return CaseResult(case.get("name", str(case["input"])[:30]), ok, "" if ok else f"got {r.result!r}")

    def _workflow_case(self, skill: Skill, case: dict) -> CaseResult:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td).resolve()
            fx = case.get("fixture", {})
            for rel, content in fx.get("files", {}).items():
                p = tmp / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
            for rel in fx.get("dirs", []):
                (tmp / rel).mkdir(parents=True, exist_ok=True)
            params = {k: (v.replace("{tmp}", str(tmp)) if isinstance(v, str) else v) for k, v in case["params"].items()}
            try:
                steps = bind(skill.steps, params)
            except KeyError as e:
                return CaseResult(case["name"], False, f"cannot bind: {e}")
            policy = PermissionPolicy([tmp])
            ex = Executor(self.registry, self.config, lambda log: ToolContext(policy, self.config, log, lambda: False, CommandRunner(), None))
            outcomes: list = []
            for _ in range(case.get("runs", 1)):
                outcomes = ex.run_plan(Plan("test", steps), {}, lambda _m: None, lambda: False)
            all_verified = bool(outcomes) and all(o.verified for o in outcomes)
            exp = case["expect"]
            problems = []
            if all_verified != exp.get("all_verified", True):
                problems.append(f"expected all_verified={exp.get('all_verified', True)}, got {all_verified}")
            files_bad = [f for f in exp.get("files_exist", []) if not (tmp / f.replace("{tmp}/", "")).exists()]
            files_bad += [f for f in exp.get("files_absent", []) if (tmp / f.replace("{tmp}/", "")).exists()]
            if files_bad:
                problems.append("file expectations broken: " + ", ".join(files_bad[:3]))
            false_success = all_verified and bool(files_bad)
            return CaseResult(case["name"], not problems, "; ".join(problems), false_success)
