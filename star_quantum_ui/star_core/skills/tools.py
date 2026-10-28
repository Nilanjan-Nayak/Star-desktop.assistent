"""run_skill: lets plans call an approved CODE skill. Verified by re-running it and comparing."""
from __future__ import annotations

from ..models import Check, ToolResult, Verdict
from ..tools import Param, Tool, ToolRegistry
from .registry import SkillRegistry
from .sandbox import run_code


class RunSkill(Tool):
    name = "run_skill"
    description = "Run an approved pure-function skill by name with an inputs object. Returns its result."
    risk = "low"
    outputs = ("result",)
    params = {"name": Param("str", desc="skill name"), "inputs": Param("dict", desc="inputs for the skill")}

    def __init__(self, skills: SkillRegistry):
        self.skills = skills

    def run(self, args, ctx):
        s = self.skills.active(args["name"])
        if s is None or s.kind != "code":
            return ToolResult(False, {}, f"no approved code skill named '{args['name']}'", "not_found")
        r = run_code(s.code, args["inputs"])
        if not r.ok:
            return ToolResult(False, {}, r.error, "skill_error")
        return ToolResult(True, {"result": r.result})

    def verify(self, args, result, ctx):
        s = self.skills.active(args["name"])
        again = run_code(s.code, args["inputs"]) if s else None
        return Verdict.of([Check("skill exists", s is not None),
                           Check("second run gives the same output", bool(again and again.ok and again.result == result.output.get("result")))])


def register_skill_tool(tools: ToolRegistry, skills: SkillRegistry) -> None:
    tools.register(RunSkill(skills))
