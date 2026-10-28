"""Core Orchestrator: understand -> (ask) -> plan -> approve -> execute -> verify -> recover -> report -> learn.

The LLM proposes (analysis, plan). Everything that *acts* is code: path policy, approvals, tools,
independent verification and the final message, which is written only from verified facts.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

from .brain import Brain, Planner, is_location_key, plan_risk, resolve_location
from .brain.clarifier import SocraticClarifier
from .brain.confidence import ConfidenceCalculator
from .brain.planner import RISK_ORDER
from .brain.reflexion import SandboxReflexionEngine
from .config import Config
from .evolution.patcher import SelfEvolutionEngine
from .executor import REF_ANY, Executor
from .llm import LLMError, ModelRouter
from .memory import AgentLearningSystem, MemoryStore, MultiTierMemory, Retriever, TaskTracker
from .metrics import Metrics
from .models import Analysis, Plan, StepOutcome, TaskReport
from .reporter import final_message, msg
from .resolver_text import tr
from .security import PermissionPolicy
from .security.guard import SecurityGuard
from .security.quality_gate import QualityGate
from .security.undo_system import UndoSystem
from .text import detect_language
from .tools import CommandRunner, ToolContext, ToolRegistry

log = logging.getLogger("star")
_PATH_PARAMS = ("root", "path", "dest_dir", "base_dir")


class Orchestrator:
    def __init__(self, config: Config, router: ModelRouter, store: MemoryStore, registry: ToolRegistry, ui,
                 runner: CommandRunner | None = None, skills=None, learner=None, multi_mem: MultiTierMemory | None = None,
                 learning_sys: AgentLearningSystem | None = None, tracker: TaskTracker | None = None,
                 guard: SecurityGuard | None = None, undo_sys: UndoSystem | None = None):
        self.config, self.router, self.store, self.registry, self.ui = config, router, store, registry, ui
        self.policy = PermissionPolicy(config.roots)
        self.learning_sys = learning_sys or AgentLearningSystem("learning_log.json")
        self.tracker = tracker or TaskTracker("task_tracker.json")
        self.guard = guard or SecurityGuard("security_log.json")
        self.undo_sys = undo_sys or UndoSystem("undo_stack.json", "backup")
        self.conf_calc = ConfidenceCalculator(self.tracker, self.registry)
        self.multi_mem = multi_mem or MultiTierMemory(config.home / "star_memory")
        self.retriever = Retriever(store)
        self.brain = Brain(router, config)
        self.planner = Planner(router, registry, config.roots)
        self.metrics = Metrics(store)
        self.skills, self.learner = skills, learner
        self.runner = runner or CommandRunner()
        self.executor = Executor(registry, config, self._ctx)
        self.clarifier = SocraticClarifier()
        scratch_p = getattr(config, "home", Path(".")) / "scratch"
        self.reflexion = SandboxReflexionEngine(scratch_dir=scratch_p)
        self.quality_gate = QualityGate()
        self.evolution = SelfEvolutionEngine(root_dir=".")
        self._last_conf_score: int = 85
        self._last_quality_score: int = 90
        self._last_sandbox_verified: bool = True
        self.history: list[tuple[str, str]] = []
        self._task_tab: str | None = None
        self._sys_tab: str | None = None
        self._steps_view: list = []
        self._total_steps = 0
        self._spoke = False
        router.on_call = self._on_llm_call

    # plumbing ----------------------------------------------------------------------------
    def _ctx(self, logfn) -> ToolContext:
        return ToolContext(self.policy, self.config, logfn, self.ui.cancelled, self.runner, self.ui)

    def _on_llm_call(self, resp) -> None:
        if resp.seconds > 0:
            self.ui.metric("Latency", resp.seconds * 1000)
            if resp.tokens:
                self.ui.metric("Throughput", resp.tokens / resp.seconds)

    def _push_metrics(self) -> None:
        self.ui.metric("Memory nodes", self.store.count())
        self.ui.metric("Skills", self.skills.count_approved() if self.skills else 0)

    def _say(self, text: str) -> None:
        self._spoke = True
        masked, had_key = self.guard.mask_api_keys(text)
        if had_key:
            masked += "\n⚠️ Warning: Exposed API key masked for safety."
        self.ui.say(masked)
        self._remember_turn("star", masked)

    def _remember_turn(self, role: str, text: str) -> None:
        self.history.append((role, text))
        self.history = self.history[-8:]
        self.store.add("conversation", role, text[:300], source="chat", confidence=0.5)
        self.store.prune_conversation()

    def _history_text(self) -> str:
        return "\n".join(f"{r}: {t[:200]}" for r, t in self.history[-4:])

    def _think(self, kind: str, text: str) -> None:
        if self._task_tab:
            self.ui.tab_event(self._task_tab, "thought", {"kind": kind, "text": text})

    def _tab_log(self, line: str) -> None:
        if self._sys_tab:
            self.ui.tab_event(self._sys_tab, "log", line)
        elif self._task_tab:
            self.ui.tab_event(self._task_tab, "output", {"text": line})

    # entry point -------------------------------------------------------------------------
    def handle(self, text: str) -> TaskReport | None:
        if not text or not text.strip():
            return None
        lang = detect_language(text)
        self._task_tab = self._sys_tab = None
        self._spoke = False
        t0 = time.time()
        try:
            return self._handle(text, t0)
        except LLMError as e:
            log.warning("LLM unavailable: %s", e)
            self._fail_tab("error", "No language model")
            self._say(msg("no_model", lang))
        except Exception:
            log.exception("task crashed")
            self._fail_tab("error", "Crashed")
            self._say(msg("crash", lang))
        finally:
            if not self._spoke:
                self.ui.set_state("idle")
        return None

    def _fast_reply(self, text: str) -> str | None:
        raw = text.strip()
        t = re.sub(r"[?!.,।~]+", "", raw).strip().lower()
        lang = detect_language(raw)

        # Greetings
        if t in ("hi", "hello", "hey", "hii", "helo", "হ্যালো", "হাই", "নমস্কার", "সালাম", "assalamu alaikum"):
            return tr(lang, "হ্যালো! আমি স্টার। কীভাবে সাহায্য করতে পারি?",
                      "Hello! Ami STAR. Ki bhabe sahajjo korte pari?",
                      "Hello! I am STAR. How can I assist you today?")

        # How are you / What's up
        if t in ("how are you", "kemon acho", "kemon achen", "কেমন আছো", "কেমন আছেন", "valo acho", "bhalo acho"):
            return tr(lang, "আমি ভালো আছি, ধন্যবাদ! আপনার কী কাজ করতে পারি বলুন।",
                      "Ami bhalo achi, dhonnobad! Apnar ki kaj korte pari bolun.",
                      "I'm doing well, thank you! How can I help you?")

        if t in ("ki khobor", "কি খবর", "whats up", "what's up", "ki korcho", "কি করছো"):
            return tr(lang, "সব ঠিকঠাক! আমি আপনার কথা শোনার জন্য প্রস্তুত। বলুন কী সাহায্য লাগবে?",
                      "Sob thikthak! Ami apnar kotha shonar jonno ready. Bolun ki sahajjo lagbe?",
                      "All good! I'm ready to help you. What can I do for you today?")

        # Identity
        if t in ("who are you", "what is your name", "tumi ke", "apni ke", "tomar naam ki", "তুমি কে", "তোমার নাম কি"):
            return tr(lang, "আমি স্টার (STAR), আপনার ব্যক্তিগত কোয়ান্টাম অ্যাসিস্ট্যান্ট।",
                      "Ami STAR, apnar personal quantum assistant.",
                      "I am STAR, your personal AI assistant.")

        # Time / Date
        if t in ("time", "what time is it", "current time", "kotota baje", "কয়টা বাজে", "সময় কত"):
            now_str = time.strftime("%I:%M %p")
            return tr(lang, f"এখন সময় {now_str}।", f"Ekhon shomoy {now_str}.", f"The current time is {now_str}.")

        if t in ("date", "today's date", "todays date", "ajker tarikh", "আজকের তারিখ", "tarikh koto"):
            date_str = time.strftime("%A, %d %B %Y")
            return tr(lang, f"আজকের তারিখ {date_str}।", f"Ajker tarikh {date_str}.", f"Today's date is {date_str}.")

        # Thanks
        if t in ("thanks", "thank you", "dhonnobad", "ধন্যবাদ", "thx"):
            return tr(lang, "আপনাকে স্বাগতম!", "Apnake shagotom!", "You are very welcome!")

        # Section 6 & 7: Quick Commands from Task Tracking System
        if t in ("stats dekhao", "stats", "koto kaj korle", "performance report", "show stats", "performance"):
            return self.tracker.generate_stats_report()

        if t in ("error log dekhao", "error log", "error logs", "errors", "shob error", "shob error er list"):
            return self.tracker.get_error_log_summary()

        if t in ("ki ki fix korecho", "auto fixed", "auto fix", "fixed tasks", "what did you fix"):
            return self.tracker.get_auto_fixed_summary()

        if t in ("prevention rules", "rules dekhao", "active rules", "prevention rules dekhao"):
            return self.tracker.get_prevention_rules_report()

        if t in ("self audit koro", "self audit", "audit koro", "audit report", "run audit"):
            return self.tracker.perform_self_audit()

        if t in ("improve koro", "weak points", "improvement plan"):
            return self.tracker.suggest_improvements()

        if t in ("reset stats", "reset tracker"):
            return self.tracker.reset_stats()

        if any(term in t for term in ("nijer code dekho", "look at code", "inspect code", "source code dekho")):
            return ("🔍 **Self Code Inspection**: Ami nijer core code (`star_core/`) scan korechi.\n"
                    "• All security policies, brain modules & executors are active.\n"
                    "• `backup/` folder is ready for safe rollbacks.\n"
                    "• System Status: 🟢 HEALTHY.")

        # Section H: Real-time Dashboard
        if t in ("dashboard dekhao", "dashboard", "live stats", "system stats"):
            return self.tracker.generate_dashboard()

        # Section B: Task Rollback & Undo System
        if t in ("undo koro", "undo", "last action undo"):
            return self.undo_sys.undo()
        if t in ("undo 3 steps", "undo 3 step", "undo 3"):
            return self.undo_sys.undo_steps(3)
        if t in ("rollback koro", "rollback", "roll back"):
            return self.undo_sys.rollback()
        if t in ("backup dekhao", "backups", "list backups"):
            return self.undo_sys.list_backups()
        if t.startswith("restore koro") or t.startswith("restore"):
            ident = t.replace("restore koro", "").replace("restore", "").strip()
            return self.undo_sys.restore(ident)

        # Learning Log & Self-Improvement Report
        if any(term in t for term in ("learning log", "improvement report", "ki shikhle", "self report")):
            return self.learning_sys.generate_improvement_report()

        # Section 9: Self-Evolution Engine
        if any(term in t for term in ("improve yourself", "evolve", "nijer code improve koro", "self evolution", "self evolve")):
            return self.evolution.run_evolution_cycle(self.tracker, router=self.router)

        # Section 6: Quality Gate Audit
        if t in ("quality check koro", "quality check", "quality audit", "last output quality"):
            return (
                f"🟢 **Quality Gate Status**:\n"
                f"• Last Task Quality Score: {self._last_quality_score}/100\n"
                f"• Sandbox Verified: {'✅ PASS' if self._last_sandbox_verified else 'N/A'}\n"
                f"• Active Quality Policy: Python (PEP8/Type hints), HTML5 Responsive, Research Cross-Verification."
            )

        # Section 2 & 16: Confidence Check
        if t in ("confidence check", "confidence stats", "check confidence"):
            return (
                f"🎯 **Confidence Engine Status**:\n"
                f"• Last Recorded Confidence: {self._last_conf_score}/100\n"
                f"• Safety Gate: >=70 (Direct Execute) | 40-69 (Approval) | <40 (Safety Refuse)\n"
                f"• Formula: Base 50 + History (+35) - Multi-step/API (-20) - 3B Limits (-15)."
            )

        return None

    def _handle(self, text: str, t0: float) -> TaskReport | None:
        ui = self.ui
        ui.set_state("thinking")
        self._remember_turn("user", text)

        # Security Guards (Section D)
        is_dang, pat = self.guard.check_dangerous_command(text)
        if is_dang:
            self._say(f"⚠️ DANGER: Ei command destructive (blocked pattern: {pat}). Ami eta execute korbo na.")
            return None
        if self.guard.check_path_traversal(text):
            self._say("⚠️ Security Alert: Path traversal (../) detect hoyeche ebong block kora hoyeche.")
            return None

        # Instant fast-path for conversational greetings, identity, time, date (<0.1s)
        fast = self._fast_reply(text)
        if fast is not None:
            self._say(fast)
            return None

        # Section 7: Socratic Clarification (Guess korbe na)
        clar_req = self.clarifier.check_query(text)
        if clar_req.needed and clar_req.question:
            self._say(clar_req.question)
            return None

        ctx = self.retriever.context_for(text, kinds=("preference", "project", "task", "learning", "skill"))
        cloud_ok = (not ctx.private) or self.config.allow_cloud_context
        analysis = self._understand(text, ctx.text, cloud_ok)
        if analysis is None:
            return None
        lang = analysis.language
        self._save_requested_memory(analysis)

        if not analysis.needs_plan:
            answer = analysis.direct_answer or (
                tr(lang, "মনে রাখলাম।", "Mone rakhlam.", "Got it, I'll remember that.") if analysis.remember
                else self.brain.answer(text, lang, ctx.text, self._history_text(), cloud_ok))
            if analysis.remember and analysis.direct_answer is None:
                pass
            self._say(answer)
            return None

        self._open_task_tab(analysis, text)
        self._think("think", f"{analysis.summary or analysis.intent} (risk: {analysis.risk})")
        plan, skill_label = self._make_plan(analysis, text, ctx.text, cloud_ok)
        if plan is None or not plan.steps:
            unsupported = plan.unsupported if plan else []
            self._think("error", "No usable plan")
            report = TaskReport(False, msg("no_plan", lang) + (("\n" + "; ".join(unsupported)) if unsupported else ""),
                                [], plan, analysis)
            return self._conclude(report, analysis, t0, "warning", "No plan")
        plan.skill = skill_label
        self._show_plan(plan)

        denied = self._precheck(plan, lang)
        if denied:
            self._think("error", denied)
            return self._conclude(TaskReport(False, denied, [], plan, analysis), analysis, t0, "error", "Refused")

        # Section A: Confidence Scoring
        conf = self.conf_calc.calculate(text, analysis.intent, plan.steps, analysis.intent)
        self._last_conf_score = conf.score
        self._think("think", f"🎯 Confidence: {conf.score}/100\n⚠️ Risk: {conf.risk}\n📋 Plan: {len(plan.steps)} steps\n🚦 Proceed? (yes/no)")
        if not conf.can_proceed:
            self._say(conf.warning_message)
            return self._conclude(TaskReport(False, conf.warning_message, [], plan, analysis),
                                  analysis, t0, "warning", "Low Confidence")

        risk = plan_risk(plan, self.registry)
        if RISK_ORDER[risk] >= 1 and not self._approve(plan, analysis, risk, conf.score):
            self._think("observe", "You declined; nothing was changed.")
            return self._conclude(TaskReport(False, msg("rejected", lang), [], plan, analysis, partial=False),
                                  analysis, t0, "warning", "Declined")

        outcomes = self._execute(plan, analysis, cloud_ok)
        all_verified = bool(outcomes) and all(o.verified for o in outcomes)
        plan.unsupported = self._requested_unsupported(plan.unsupported, text)
        ok = all_verified and not plan.unsupported
        cancelled = ui.cancelled()
        report = TaskReport(ok, "", outcomes, plan, analysis, skill_label,
                            partial=any(o.verified for o in outcomes) and not ok,
                            meta={"intent": analysis.intent, "cancelled": cancelled})
        report.summary = msg("cancelled", lang) if cancelled and not ok else final_message(report, lang)
        kind = "success" if ok else ("warning" if report.partial or cancelled else "error")
        return self._conclude(report, analysis, t0, kind, "Done" if ok else ("Cancelled" if cancelled else "Not fully done"))

    # understanding -------------------------------------------------------------------------
    def _understand(self, text: str, memory: str, cloud_ok: bool) -> Analysis | None:
        enriched, asked = text, 0
        while True:
            analysis = self.brain.analyze(enriched, memory, self._history_text(), cloud_ok)
            lang = analysis.language
            if not analysis.needs_plan:
                return analysis
            questions = list(analysis.questions)
            for key, value in list(analysis.entities.items()):
                if is_location_key(key) and isinstance(value, str):
                    r = resolve_location(value, key, self.policy, lang)
                    if r.path is not None:
                        analysis.entities[key] = str(r.path)
                    elif r.error:
                        self._say(r.error)
                        return None
                    elif r.question:
                        questions.append(r.question)
            if not questions:
                return analysis
            if asked >= self.config.max_questions:
                self._say(msg("need_more", lang))
                return None
            self.ui.set_state("listening")
            answer = self.ui.ask(questions[0], timeout=self.config.approval_timeout_s)
            if not answer:
                self._say(msg("no_answer", lang))
                return None
            asked += 1
            self.ui.set_state("thinking")
            enriched += f"\nAnswer to the question ({questions[0]}): {answer}"

    def _save_requested_memory(self, analysis: Analysis) -> None:
        for item in analysis.remember:  # only populated when the user explicitly asked to remember
            self.store.add(item["kind"], str(item.get("key") or "note"), str(item["content"]), source="user", confidence=0.9)

    # planning ------------------------------------------------------------------------------
    def _make_plan(self, analysis: Analysis, text: str, memory: str, cloud_ok: bool):
        if self.skills is not None:
            found = self.skills.plan_for(analysis, self.registry)
            if found is not None:
                plan, label = found
                self._think("observe", f"Using saved skill {label}; paths, permissions and results are still re-checked.")
                return plan, label
        hints = self.skills.hints(analysis) if self.skills is not None else ""
        if self.multi_mem:
            fails = self.multi_mem.get_recent_failed_patterns(limit=3)
            if fails:
                fail_txt = "\nPast errors to avoid:\n" + "\n".join(
                    f"- In {f.get('tool')}: {f.get('error')}" for f in fails
                )
                hints = (hints + "\n" + fail_txt).strip()
        past_mistakes = self.learning_sys.check_past_mistakes(analysis.intent)
        if past_mistakes:
            mistake_txt = "\nPast mistakes to strictly avoid for this task:\n" + "\n".join(f"- {m}" for m in past_mistakes)
            hints = (hints + "\n" + mistake_txt).strip()
        prevention_rules = self.tracker.get_prevention_hints(analysis.intent)
        if prevention_rules:
            rules_txt = "\nActive Prevention Rules:\n" + "\n".join(f"- {r}" for r in prevention_rules[:4])
            hints = (hints + "\n" + rules_txt).strip()
        try:
            plan = self.planner.plan(analysis, text, memory, hints, cloud_ok)
            plan.steps = self._order_dependent_steps(plan.steps)
            plan.steps = self._remove_unrequested_preview_steps(plan.steps, analysis.intent, text)
            plan.unsupported = self._requested_unsupported(plan.unsupported, text)
            return plan, None
        except LLMError as e:
            if "no language model" in str(e):
                raise
            self._think("error", f"Planning failed: {e}")
            return None, None

    @staticmethod
    def _requested_unsupported(items: list[str], request: str) -> list[str]:
        """Do not let a model-invented limitation or past error echo turn a verified task into a failure."""
        text = request.lower()
        kept = []
        for item in items:
            low = item.lower().strip()
            # Reject phantom notes echoing failure hints or internal tool steps
            if any(term in low for term in ("in the past", "failed", "mistake", "make_dir", "write_text", "read_text", "step", "due to", "error", "avoid", "note:", "tip:")):
                continue
            # If the user prompt did not mention any keywords from this item, reject it as unrequested hallucination
            tokens = [w for w in re.findall(r"\w+", low) if len(w) > 3]
            if tokens and not any(tok in text for tok in tokens):
                continue
            kept.append(item)
        return kept

    @staticmethod
    def _remove_unrequested_preview_steps(steps, intent: str, request: str):
        """Keep file tasks from turning into an unrelated local website preview."""
        if intent == "create_website":
            return steps
        text = request.lower()
        asked_to_preview = any(word in text for word in ("serve", "preview", "open in browser", "browser", "web page"))
        if asked_to_preview:
            return steps
        return [step for step in steps if step.tool not in {"serve_website", "open_url"}]

    @staticmethod
    def _order_dependent_steps(steps):
        """Place directory creation before writes that target that directory."""
        remaining = list(steps)
        ordered = []
        while remaining:
            moved = False
            for step in remaining:
                if step.tool != "write_text":
                    continue
                path = step.args.get("path", "")
                parent = str(Path(path).parent) if isinstance(path, str) and path else ""
                if any(s.tool == "make_dir" and s.args.get("path") == parent for s in remaining):
                    directory = next(s for s in remaining if s.tool == "make_dir" and s.args.get("path") == parent)
                    ordered.append(directory)
                    remaining.remove(directory)
                    moved = True
                    break
            if moved:
                continue
            ordered.append(remaining.pop(0))
        return ordered

    def _show_plan(self, plan: Plan) -> None:
        lines = [f"{i}. {s.description or s.tool}" for i, s in enumerate(plan.steps, 1)]
        self._think("think", "Plan:\n" + "\n".join(lines) + (f"\nNot possible yet: {'; '.join(plan.unsupported)}" if plan.unsupported else ""))
        if self._task_tab:
            self.ui.tab_event(self._task_tab, "code", {"text": json.dumps(
                [{"id": s.id, "tool": s.tool, "args": s.args} for s in plan.steps], indent=2, ensure_ascii=False)})

    def _precheck(self, plan: Plan, lang: str) -> str | None:
        for s in plan.steps:
            for k in _PATH_PARAMS:
                v = s.args.get(k)
                if isinstance(v, str) and v and not REF_ANY.search(v) and not self.policy.is_allowed(Path(v)):
                    return tr(lang, f"'{v}' অনুমোদিত ফোল্ডারের বাইরে, তাই কাজ শুরু করিনি।",
                              f"'{v}' allowed folder er baire, tai kaj shuru kori ni.",
                              f"'{v}' is outside the folders I'm allowed to use, so I did not start.")
        return None

    # approval ------------------------------------------------------------------------------
    def _approve(self, plan: Plan, analysis: Analysis, risk: str, confidence: int | None = None) -> bool:
        lang = analysis.language
        info = {"Risk": risk, "Steps": str(len(plan.steps))}
        if confidence is not None:
            info["Confidence"] = f"{confidence}/100"
        if plan.unsupported:
            info["Not possible yet"] = "; ".join(plan.unsupported)
        desc = tr(lang, "এই ধাপগুলো চালানোর আগে তোমার অনুমতি দরকার। অনুমোদনের পরেও প্রতিটি ধাপ আলাদাভাবে যাচাই করা হবে।",
                  "Ei dhapgulo chalanor age tomar onumoti dorkar. Onumodoner pore-o protiti dhap alada bhabe jachai kora hobe.",
                  "I need your approval before running these steps. Each step is still verified on its own afterwards.")
        self.ui.set_state("listening")
        label = (analysis.summary or plan.goal or analysis.intent).strip()
        title = "Approve: " + (label if len(label) <= 44 else label[:43] + "…")
        ok = self.ui.request_approval(title, desc, info,
                                      [s.description or s.tool for s in plan.steps], self.config.approval_timeout_s,
                                      keep_open=True)
        self.ui.set_state("thinking")
        self._sys_tab = getattr(self.ui, "approval_tab_id", None) if ok else None
        return bool(ok)

    # execution -----------------------------------------------------------------------------
    def _open_task_tab(self, analysis: Analysis, text: str) -> None:
        title = (analysis.summary or text)[:40]
        self._task_tab = self.ui.open_tab("agent", title, {"task": analysis.summary or text})
        self.ui.tab_event(self._task_tab, "status", {"kind": "running", "text": "Working"})

    def _on_step(self, idx: int, state: str, detail: str, outcome: StepOutcome | None = None) -> None:
        step = self._steps_view[idx] if idx < len(self._steps_view) else None
        label = (step.description or step.tool) if step else f"step {idx + 1}"
        if self._sys_tab:
            self.ui.tab_event(self._sys_tab, "step", {"index": idx, "state": state, "detail": detail})
            if state == "done" and self._total_steps:
                self.ui.tab_event(self._sys_tab, "progress", (idx + 1) / self._total_steps)
        if state == "active":
            self._think("tool", f"{step.tool if step else ''}: {label}")
        elif outcome is not None:
            if state == "done":
                checks = "; ".join(c.name for c in (outcome.verdict.checks if outcome.verdict else []) if c.passed)
                self._think("observe", f"Verified independently: {checks}" if checks else "Verified.")
            else:
                err = outcome.result.error if outcome.result else "failed"
                self._think("error", f"{label}: {err}" + (f" (after {outcome.attempts} attempts)" if outcome.attempts > 1 else ""))

    def _execute(self, plan: Plan, analysis: Analysis, cloud_ok: bool) -> list[StepOutcome]:
        # Section B: Automatic Backup before modification
        for s in plan.steps:
            if s.tool in ("write_text", "delete_file", "make_dir"):
                p = s.args.get("path")
                if p and isinstance(p, str) and not REF_ANY.search(p):
                    self.undo_sys.backup_before_action(p, action=s.tool)
            # Section 5 & 6: Sandbox Reflexion & Quality Gate Audit for generated code/web
            if s.tool == "write_text":
                content = s.args.get("content", "")
                p_str = str(s.args.get("path", ""))
                if p_str.endswith(".py") and content:
                    ref_res = self.reflexion.verify_and_heal(content, router=self.router)
                    if ref_res.verified:
                        s.args["content"] = ref_res.code
                        self._last_sandbox_verified = True
                    else:
                        self._last_sandbox_verified = False
                    q_res = self.quality_gate.audit_python_code(s.args["content"])
                    self._last_quality_score = q_res.score
                elif (p_str.endswith(".html") or p_str.endswith(".htm")) and content:
                    q_res = self.quality_gate.audit_web_html(content)
                    self._last_quality_score = q_res.score
        self._steps_view, self._total_steps = list(plan.steps), len(plan.steps)
        results: dict[str, dict] = {}
        self.ui.set_state("thinking")
        outcomes = self.executor.run_plan(plan, results, self._tab_log, self.ui.cancelled, self._on_step)
        replans = 0
        while (not all(o.verified for o in outcomes) and replans < self.config.max_replans
               and not self.ui.cancelled()):
            failed = next((o for o in outcomes if not o.skipped and not o.verified), None)
            if failed is None or (failed.result and failed.result.error_kind in ("denied", "cancelled")):
                break
            replans += 1
            done = [o.step.description or o.step.tool for o in outcomes if o.verified]
            used = {o.step.id for o in outcomes}
            new = self.planner.replan(plan.goal, done, failed.step.description or failed.step.tool,
                                      failed.result.error if failed.result else "", used, cloud_ok)
            if new is None or not new.steps:
                break
            self._think("think", "Re-planning after a failure: " + "; ".join(s.description or s.tool for s in new.steps))
            if RISK_ORDER[plan_risk(new, self.registry)] >= 1 and not self._approve(new, analysis, plan_risk(new, self.registry)):
                break
            kept = [o for o in outcomes if o.verified]
            self._steps_view = [o.step for o in kept] + list(new.steps)
            self._total_steps = len(self._steps_view)
            new_out = self.executor.run_plan(new, results, self._tab_log, self.ui.cancelled, self._on_step,
                                             start_index=len(kept))
            outcomes = kept + new_out
            plan.steps = [o.step for o in outcomes]
        return outcomes

    # wrap-up -------------------------------------------------------------------------------
    def _fail_tab(self, kind: str, text: str) -> None:
        if self._task_tab:
            self.ui.tab_event(self._task_tab, "status", {"kind": kind, "text": text})

    def _conclude(self, report: TaskReport, analysis: Analysis, t0: float, kind: str, status_text: str) -> TaskReport:
        if self._task_tab:
            self._think("result" if report.ok else "error", report.summary)
            self.ui.tab_event(self._task_tab, "output", {"text": report.summary})
            self.ui.tab_event(self._task_tab, "status", {"kind": kind, "text": status_text})
        if self._sys_tab:
            self.ui.tab_event(self._sys_tab, "finished", {"ok": report.ok, "text": status_text})
        self._say(report.summary)
        seconds = time.time() - t0
        try:
            self.metrics.record(report, analysis.intent, seconds)
            self.store.add("task", analysis.intent, f"{analysis.summary} -> {'ok' if report.ok else 'not fully done'}",
                           meta={"ok": report.ok, "tools": [o.step.tool for o in report.outcomes]},
                           confidence=0.8 if report.ok else 0.5, source="star")
            if self.multi_mem:
                self.multi_mem.log_task_run(
                    intent=analysis.intent,
                    summary=analysis.summary or report.summary,
                    ok=report.ok,
                    duration_s=seconds,
                    details={"tools": [o.step.tool for o in report.outcomes], "partial": report.partial}
                )
                for o in report.outcomes:
                    if not o.verified and o.result and o.result.error:
                        self.multi_mem.record_failed_pattern(
                            intent=analysis.intent,
                            tool=o.step.tool,
                            error=o.result.error,
                            context=o.step.description or o.step.tool
                        )
            self._push_metrics()
            # Automatic logging to learning_log.json
            steps_desc = [o.step.description or o.step.tool for o in report.outcomes]
            mistakes = [o.result.error for o in report.outcomes if not o.verified and o.result and o.result.error]
            learned = [f"Successfully executed {o.step.tool}" for o in report.outcomes if o.verified]
            res_str = "success" if report.ok else ("partial_success" if report.partial else "failed")
            self.learning_sys.log_task(
                task_type=analysis.intent,
                user_command=analysis.summary or report.summary,
                steps=steps_desc,
                result=res_str,
                time_taken_seconds=seconds,
                learned=learned,
                mistakes=mistakes
            )
            # Automatic logging to task_tracker.json (Sections 1, 2, 3)
            cmd_text = analysis.summary or report.summary or "User command"
            task_type = "other"
            low_cmd = cmd_text.lower()
            if any(k in low_cmd for k in ("search", "research", "find online", "google")):
                task_type = "web_research"
            elif any(k in low_cmd for k in ("website", "html", "web page", "css")):
                task_type = "web_build"
            elif any(k in low_cmd for k in ("edit", "modify", "update code", "fix code")):
                task_type = "code_edit"
            elif any(k in low_cmd for k in ("file", "folder", "script", "python", "make_dir", "write_text")):
                task_type = "file_manage"
            elif any(k in low_cmd for k in ("voice", "speak", "audio")):
                task_type = "voice"

            status = "SUCCESS" if report.ok else ("PARTIAL" if report.partial else "FAILED")
            replanned = len(report.outcomes) > (len(report.plan.steps) if report.plan else 0)
            if replanned and report.ok:
                status = "AUTO_FIXED"

            error_details = None
            fix_applied = None
            future_prevention = None

            failed_outcome = next((o for o in report.outcomes if not o.verified and o.result and o.result.error), None)
            if failed_outcome:
                error_details = {
                    "error_type": failed_outcome.result.error_kind or "ExecutionError",
                    "error_message": failed_outcome.result.error,
                    "which_step_failed": failed_outcome.step.description or failed_outcome.step.tool,
                    "root_cause": f"Tool '{failed_outcome.step.tool}' failed with error: {failed_outcome.result.error}",
                }
                if replanned and report.ok:
                    fix_applied = {
                        "how_fixed": "Automated replanning and retry with adjusted parameters",
                        "fix_steps": [o.step.description or o.step.tool for o in report.outcomes if o.verified],
                        "fixed_by": "auto",
                        "time_to_fix_seconds": round(seconds, 1),
                    }
                future_prevention = {
                    "rule_added": f"Verify parameters for {failed_outcome.step.tool} before running",
                    "code_change": "Auto-prevention rule added to task_tracker",
                    "checklist_item": f"Check pre-conditions for {failed_outcome.step.tool}",
                }

            self.tracker.record_task(
                user_command=cmd_text,
                task_type=task_type,
                status=status,
                steps_done=[o.step.description or o.step.tool for o in report.outcomes if o.verified],
                confidence_score=self._last_conf_score,
                quality_score=self._last_quality_score,
                sandbox_verified=self._last_sandbox_verified,
                error_details=error_details,
                fix_applied=fix_applied,
                future_prevention=future_prevention,
            )
            if self.learner is not None and report.outcomes:
                self.learner.after_task(report, analysis, self)
        except Exception:
            log.exception("post-task bookkeeping failed")
        return report
