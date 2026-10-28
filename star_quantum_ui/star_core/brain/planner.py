"""Planner: analysis -> validated step list. The model proposes; this code decides what is acceptable."""
from __future__ import annotations

import json
import os
import re

from ..llm import LLMError, ModelRouter
from ..models import Analysis, Plan, Step
from ..tools import ToolRegistry
from .prompts import PLAN_SYSTEM, REPLAN_SYSTEM, user_message

REF_ANY = re.compile(r"\$\{(\w+)\.(\w+)\}")
_DUMMY = {"str": "x", "int": 0, "bool": False, "list": [], "dict": {}}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def validate_plan_dict(data: dict, registry: ToolRegistry, known_ids: set[str] | None = None) -> str | None:
    steps = data.get("steps")
    if not isinstance(steps, list):
        return "'steps' must be a list"
    # Filter out hallucinated open_url steps with empty/invalid URLs when actual tools exist
    if len(steps) > 1:
        data["steps"] = [s for s in steps if not (
            isinstance(s, dict) and s.get("tool") == "open_url" and
            not str(s.get("args", {}).get("url", "")).startswith(("http://", "https://"))
        )]
        steps = data["steps"]
    seen = set(known_ids or ())
    for i, s in enumerate(steps, 1):
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or not isinstance(s.get("args"), dict):
            return f"step {i} needs string 'id', 'tool' and object 'args'"
        sid, tool = s["id"], registry.get(str(s.get("tool", "")))
        if tool is None:
            return f"step {sid}: unknown tool '{s.get('tool')}'. Allowed: {', '.join(registry.names())}"
        if sid in seen:
            return f"duplicate step id '{sid}'"
        probe = {}
        for k, v in s["args"].items():
            refs = REF_ANY.findall(v) if isinstance(v, str) else []
            for ref_id, field in refs:
                src_tool = next((registry.get(x["tool"]) for x in steps if x.get("id") == ref_id), None) \
                    if ref_id not in (known_ids or ()) else None
                if ref_id not in seen:
                    return f"step {sid}: '${{{ref_id}.{field}}}' refers to a step that does not come earlier"
                if src_tool is not None and field not in src_tool.outputs:
                    return f"step {sid}: tool '{src_tool.name}' has no output '{field}' (has: {', '.join(src_tool.outputs)})"
            if refs and re.fullmatch(REF_ANY, v) and k in tool.params:
                # References are resolved only during execution. Use a type-valid probe value
                # so downstream validators can still check the rest of the proposed plan.
                probe[k] = "http://127.0.0.1:8765/" if k == "url" else _DUMMY[tool.params[k].type]
            else:
                probe[k] = v if not refs else "x"
        errs = tool.validate(probe)
        if errs:
            return f"step {sid} ({tool.name}): " + "; ".join(errs)
        seen.add(sid)
    return None


def to_plan(data: dict, fallback_goal: str = "") -> Plan:
    steps = [Step(s["id"], s["tool"], dict(s["args"]), str(s.get("description", ""))) for s in data.get("steps", [])]
    return Plan(str(data.get("goal") or fallback_goal), steps, [str(u) for u in data.get("unsupported", []) if u])


def plan_risk(plan: Plan, registry: ToolRegistry) -> str:
    worst = "low"
    for s in plan.steps:
        tool = registry.get(s.tool)
        r = tool.risk_for(tool.with_defaults(s.args)) if tool else "high"
        if RISK_ORDER[r] > RISK_ORDER[worst]:
            worst = r
    return worst


class Planner:
    def __init__(self, router: ModelRouter, registry: ToolRegistry, allowed_roots=()):
        self.router, self.registry = router, registry
        self.allowed_roots = tuple(str(root) for root in allowed_roots)

    def _outputs_text(self) -> str:
        return "\n".join(f"- {n} -> {', '.join(self.registry.get(n).outputs) or '(none)'}" for n in self.registry.names())

    def plan(self, analysis: Analysis, text: str, memory: str = "", hints: str = "", cloud_ok: bool = True) -> Plan:
        runtime = (
            f"\nRuntime platform: {os.name} (Windows). Allowed roots: "
            f"{', '.join(self.allowed_roots)}. "
            "If the user did not provide a save location, use the first allowed root plus "
            "the folder STAR_tasks (create it first). "
            "Use only the absolute Windows paths already present in Analysis JSON. "
            "Never invent Linux paths such as /var/www or /home, shell variables such as $1.path, "
            "or substitute paths. Step references must use the exact form ${{s1.field}}."
        )
        system = PLAN_SYSTEM.format(catalog=self.registry.catalog(), outputs=self._outputs_text(),
                                    hints=f"\nSaved knowledge that may help:\n{hints}" if hints else "") + runtime
        a = {"intent": analysis.intent, "summary": analysis.summary, "entities": analysis.entities,
             "language": analysis.language}
        user = f"Analysis JSON:\n{json.dumps(a, ensure_ascii=False)}\n\n" + user_message(text, "", memory)
        data = self.router.json_chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                     task="planning", required=["steps"], cloud_ok=cloud_ok,
                                     retries=self._json_retries(), check=lambda d: validate_plan_dict(d, self.registry))
        return to_plan(data, analysis.summary)

    def _json_retries(self) -> int:
        return getattr(self.router.config, "llm_json_retries", 1)

    def replan(self, goal: str, done: list[str], failed: str, error: str, used_ids: set[str],
               cloud_ok: bool = True) -> Plan | None:
        system = REPLAN_SYSTEM.format(catalog=self.registry.catalog())
        user = (f"Goal: {goal}\nAlready completed and verified: {json.dumps(done, ensure_ascii=False)}\n"
                f"Failed step: {failed}\nError: {error}\nIds already used: {sorted(used_ids)}")
        try:
            data = self.router.json_chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                         task="replan", required=["steps"], cloud_ok=cloud_ok, retries=1,
                                         check=lambda d: validate_plan_dict(d, self.registry, set(used_ids)))
        except LLMError:
            return None
        if data.get("give_up") or not data.get("steps"):
            return None
        return to_plan(data, goal)
