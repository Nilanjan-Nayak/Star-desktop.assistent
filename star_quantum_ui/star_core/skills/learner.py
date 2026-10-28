"""Learning: turn verified successes into skills (with approval + tests) and failures into lessons."""
from __future__ import annotations

import logging

from ..brain.resolver import is_dest_key, is_location_key
from ..config import Config
from ..llm import LLMError, ModelRouter
from ..models import Analysis, TaskReport
from ..reporter import _t
from .evaluator import Evaluator, EvalResult
from .registry import Skill, SkillRegistry
from .sandbox import GuardError, check_code
from .workflow import generalize

log = logging.getLogger("star")
BANNED_TOOLS = {"install_package", "run_command"}


class SkillLearner:
    def __init__(self, registry: SkillRegistry, router: ModelRouter, config: Config):
        self.registry, self.router, self.config = registry, router, config
        self._offered: set[str] = set()

    # entry from the orchestrator ------------------------------------------------------------
    def after_task(self, report: TaskReport, analysis: Analysis, orch) -> None:
        if not report.ok:
            self._lesson(report, analysis, orch)
            if report.skill_used:
                self.registry.record_use(report.skill_used, False)
            return
        if report.skill_used:
            self.registry.record_use(report.skill_used, True)
            return
        if analysis.intent in self._offered or self._declined(analysis.intent, orch):
            return
        reason = self._ineligible(report, analysis, orch)
        if reason:
            log.info("not learning a skill: %s", reason)
            return
        self._offered.add(analysis.intent)
        self._offer(report, analysis, orch)

    # eligibility -----------------------------------------------------------------------------
    def _ineligible(self, report: TaskReport, analysis: Analysis, orch) -> str | None:
        steps = [o.step for o in report.outcomes]
        if len(steps) < 2:
            return "a single step is not worth a skill"
        if report.plan and report.plan.unsupported:
            return "part of the request was unsupported"
        if any(s.tool in BANNED_TOOLS for s in steps):
            return "contains high-risk tools"
        if any(orch.registry.get(s.tool) is None or orch.registry.get(s.tool).risk == "high" for s in steps):
            return "contains high-risk tools"
        _, params = generalize(steps, analysis.entities)
        if not params:
            return "nothing in the plan came from the user's request, so there is nothing to parameterise"
        return None

    def _declined(self, intent: str, orch) -> bool:
        return any(m.key == f"skill_declined:{intent}" for m in orch.store.all("learning"))

    # learning a workflow skill ------------------------------------------------------------------
    def _offer(self, report: TaskReport, analysis: Analysis, orch) -> None:
        ui, lang = orch.ui, analysis.language
        steps = [o.step for o in report.outcomes]
        template, params = generalize(steps, analysis.entities)
        name = analysis.intent or "workflow"
        ok = ui.request_approval(
            _t(lang, "এটাকে reusable skill হিসেবে সেভ করব?", "Eta ke reusable skill hisebe save korbo?", "Save this as a reusable skill?"),
            _t(lang, "একই ধরনের কাজ পরে আরও দ্রুত ও নির্ভরযোগ্যভাবে হবে। আগে sandbox-এ test করব; পাস না করলে সেভ হবে না।",
               "Ekoi dhoroner kaj pore aro druto o nirbhorjogyo bhabe hobe. Age sandbox e test korbo; pass na korle save hobe na.",
               "Next time the same kind of task will be faster and safer. I'll test it in a sandbox first; it is not saved unless it passes."),
            {"Skill": name, "Parameters": ", ".join(params), "Steps": str(len(steps))},
            [s.description or s.tool for s in steps], self.config.approval_timeout_s)
        if not ok:
            orch.store.add("learning", f"skill_declined:{analysis.intent}", "user declined creating this skill", source="star", confidence=0.9)
            return
        skill = self.registry.new_draft(
            name=name, kind="workflow", intent=analysis.intent, description=analysis.summary or name,
            triggers=[analysis.intent, analysis.summary][:2], params=params, entity_keys=sorted(analysis.entities),
            steps=template)
        skill.tests = self._workflow_tests(skill, report, analysis)
        self._finish(skill, orch, lang)

    def _workflow_tests(self, skill: Skill, report: TaskReport, analysis: Analysis) -> list[dict]:
        source = next((p for p in skill.params if is_location_key(p) and not is_dest_key(p)), None)
        dest = next((p for p in skill.params if is_location_key(p) and is_dest_key(p)), None)
        params = {p: ("{tmp}/" + p if is_location_key(p) else analysis.entities[p]) for p in skill.params}
        made = {st["args"].get("path") for st in skill.steps if st["tool"] == "make_dir"}
        dirs = [p for p in skill.params if is_location_key(p) and f"<<{p}>>" not in made]
        found = []
        for o in report.outcomes:
            if o.step.tool == "find_files" and o.result:
                found = [f.replace("\\", "/").split("/")[-1] for f in o.result.output.get("files", [])][:3]
        found = found or ["sample_1.txt", "sample_2.txt"]
        copies = any(st["tool"] == "copy_files" for st in skill.steps)
        files = {f"{source}/{n}": f"data {n}" for n in found} if source else {}
        files[f"{source}/decoy_not_matching.zzz"] = "decoy" if source else ""
        files = {k: v for k, v in files.items() if source}
        exp = {"all_verified": True}
        if dest and copies and source:
            exp["files_exist"] = [f"{dest}/{n}" for n in found]
            exp["files_absent"] = [f"{dest}/decoy_not_matching.zzz"]
        tests = [{"name": "normal run", "fixture": {"files": files, "dirs": dirs}, "params": params, "expect": exp},
                 {"name": "second run is harmless", "fixture": {"files": files, "dirs": dirs}, "params": params,
                  "expect": exp, "runs": 2},
                 {"name": "nothing to do", "fixture": {"files": {}, "dirs": dirs}, "params": params,
                  "expect": {"all_verified": True}}]
        finds_recursive = any(st["tool"] == "find_files" and st["args"].get("recursive", True) for st in skill.steps)
        if source and copies and finds_recursive:
            tests.append({"name": "same name in two folders is never reported as success",
                          "fixture": {"files": {f"{source}/x/{found[0]}": "one", f"{source}/y/{found[0]}": "two"}, "dirs": dirs},
                          "params": params, "expect": {"all_verified": False}})
        return tests

    def _finish(self, skill: Skill, orch, lang: str) -> None:
        ev = Evaluator(orch.registry, self.config)
        previous = self.registry.active(skill.name)
        result = ev.run(skill, previous.tests if previous else None)
        old = ev.run(previous) if previous else None
        reasons = ev.compare(result, old)
        skill.last_eval = result.to_dict()
        if reasons:
            self.registry.save(skill)
            orch.store.add("learning", f"skill_rejected:{skill.name}", "; ".join(reasons), source="star", confidence=0.8)
            orch.ui.say(_t(lang, f"skill সেভ করিনি, test পাস করেনি: {'; '.join(reasons)}",
                           f"skill save kori ni, test pass kore ni: {'; '.join(reasons)}", f"Skill not saved, it failed testing: {'; '.join(reasons)}"))
            return
        self.registry.set_status(skill, "tested")
        activate = True
        if self.config.skill_activation_requires_approval:
            activate = orch.ui.request_approval(
                _t(lang, "skill চালু করব?", "Skill chalu korbo?", "Activate this skill?"),
                _t(lang, f"সব test পাস করেছে ({result.summary()}). চালু করলে একই ধরনের কাজে এটি ব্যবহার হবে।",
                   f"Sob test pass korechi ({result.summary()}). Chalu korle ekoi dhoroner kaje eti byabohar hobe.",
                   f"All tests passed ({result.summary()}). Once active it will be used for similar tasks."),
                {"Skill": skill.label, "Tests": result.summary()}, [c.name for c in result.cases], self.config.approval_timeout_s)
        if activate:
            self.registry.approve(skill)
            orch.ui.say(_t(lang, f"skill '{skill.label}' সেভ ও চালু হয়েছে।", f"skill '{skill.label}' save o chalu hoyeche.",
                           f"Skill '{skill.label}' saved and active."))
            orch.store.add("learning", f"skill_created:{skill.name}", f"created {skill.label}: {result.summary()}", source="star", confidence=0.9)
            if orch.skills is not None:
                orch.ui.metric("Skills", orch.skills.count_approved())

    # code skills (LLM-proposed, sandboxed) ---------------------------------------------------------
    def propose_code_skill(self, request: str, orch) -> tuple[Skill | None, EvalResult | None, str]:
        """Ask the model for a pure-function skill, guard-check it, test it in the sandbox. Never activates it."""
        try:
            d = self.router.json_chat(
                [{"role": "system", "content": "[[TASK:skill_code]]\nWrite a pure Python skill. Reply with ONE JSON object: "
                  '{"name": "snake_case", "description": "...", "code": "def run(inputs): ...", '
                  '"tests": [{"input": {}, "expect": {}}]}. Only re, math, json, itertools, functools, collections, datetime, '
                  "string, textwrap, unicodedata, statistics, decimal, fractions, hashlib, base64 may be imported. No file, "
                  "network or process access."}, {"role": "user", "content": f"User request:\n{request}"}],
                task="skill_code", required=["name", "code", "tests"])
        except LLMError as e:
            return None, None, f"the model could not propose a skill: {e}"
        try:
            check_code(d["code"])
        except GuardError as e:
            return None, None, f"proposal rejected by the safety guard: {e}"
        tests = [dict(t, name=t.get("name") or f"case {i + 1}") for i, t in enumerate(d["tests"])]
        skill = self.registry.new_draft(name=str(d["name"]), kind="code", intent=str(d["name"]),
                                        description=str(d.get("description", d["name"])), triggers=[str(d["name"])],
                                        params=["inputs"], code=d["code"], tests=tests)
        result = Evaluator(orch.registry, self.config).run(skill, None)
        skill.last_eval = result.to_dict()
        self.registry.set_status(skill, "tested" if result.passed else "draft")
        return skill, result, result.summary()

    # lessons -----------------------------------------------------------------------------------
    def _lesson(self, report: TaskReport, analysis: Analysis, orch) -> None:
        failed = next((o for o in report.outcomes if not o.skipped and not o.verified), None)
        if failed is None or failed.result is None:
            return
        key = f"failure:{analysis.intent}"
        content = f"{failed.step.tool} failed ({failed.result.error_kind}): {failed.result.error}"[:300]
        if any(m.key == key and m.content == content for m in orch.store.all("learning")):
            return
        orch.store.add("learning", key, content, meta={"tool": failed.step.tool, "kind": failed.result.error_kind},
                       source="star", confidence=0.6)
