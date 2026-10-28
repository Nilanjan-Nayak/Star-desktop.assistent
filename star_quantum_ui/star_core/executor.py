"""Executor: runs plan steps, verifies each one independently, retries only what is safe to retry."""
from __future__ import annotations

import re
import time
from typing import Callable

from .config import Config
from .models import Check, Plan, Step, StepOutcome, ToolResult, Verdict
from .tools import ToolContext, ToolRegistry

REF_FULL = re.compile(r"^\$\{+(\w+)\.(\w+)\}+$")
REF_ANY = re.compile(r"\$\{+(\w+)\.(\w+)\}+")
RETRYABLE = {"os_error", "timeout", "busy", "exception", "verification_failed"}


def resolve_args(value, results: dict[str, dict]):
    if isinstance(value, str):
        m = REF_FULL.match(value)
        if m and m.group(1) in results and m.group(2) in results[m.group(1)]:
            return results[m.group(1)][m.group(2)]
        val = REF_ANY.sub(lambda m: str(results[m.group(1)][m.group(2)]) if m.group(1) in results and m.group(2) in results[m.group(1)] else m.group(0), value)
        # Unwrap accidental ${{...}} around literal absolute paths
        unwrapped = re.sub(r"^\$\{+([A-Za-z]:[\\/][^}]+)\}+$", r"\1", val).strip()
        return unwrapped
    if isinstance(value, list):
        return [resolve_args(v, results) for v in value]
    if isinstance(value, dict):
        return {k: resolve_args(v, results) for k, v in value.items()}
    return value


class Executor:
    def __init__(self, registry: ToolRegistry, config: Config, ctx_factory: Callable[[Callable[[str], None]], ToolContext]):
        self.registry, self.config, self.ctx_factory = registry, config, ctx_factory

    def run_step(self, step: Step, results: dict[str, dict], log: Callable[[str], None],
                 cancelled: Callable[[], bool]) -> StepOutcome:
        out = StepOutcome(step)
        tool = self.registry.get(step.tool)
        if tool is None:
            out.result = ToolResult(False, {}, f"unknown tool {step.tool}", "validation")
            return out
        try:
            args = tool.with_defaults(resolve_args(step.args, results))
        except KeyError as e:
            out.result = ToolResult(False, {}, f"reference to missing output {e}", "validation")
            return out
        errs = tool.validate(args)
        if errs:
            out.result = ToolResult(False, {}, "; ".join(errs), "validation")
            return out
        ctx = self.ctx_factory(log)
        for attempt in range(1, self.config.max_retries + 2):
            out.attempts = attempt
            try:
                res = tool.run(args, ctx)
            except Exception as e:  # a crashing tool is a failed step, not a crashed assistant
                res = ToolResult(False, {}, f"{type(e).__name__}: {e}", "exception")
            try:
                verdict = tool.verify(args, res, ctx)
            except Exception as e:
                verdict = Verdict(False, [Check("verification crashed", False, str(e))], str(e))
            if res.ok and not verdict.passed:   # tool claimed success, the disk disagrees
                res = ToolResult(False, res.output, f"verification failed: {verdict.reason}", "verification_failed")
            out.result, out.verdict = res, verdict
            if res.ok and verdict.passed:
                return out
            if res.error_kind in RETRYABLE and attempt <= self.config.max_retries and not cancelled():
                log(f"attempt {attempt} failed ({res.error}); retrying")
                time.sleep(min(0.2 * attempt, 1.0))
                continue
            break
        return out

    def run_plan(self, plan: Plan, results: dict[str, dict], log: Callable[[str], None],
                 cancelled: Callable[[], bool], on_step: Callable[..., None] | None = None,
                 start_index: int = 0) -> list[StepOutcome]:
        outcomes: list[StepOutcome] = []
        stop = False
        for i, step in enumerate(plan.steps):
            idx = start_index + i
            if stop or cancelled():
                stop = True
                outcomes.append(StepOutcome(step, skipped=True))
                continue
            if on_step:
                on_step(idx, "active", "")
            t0 = time.time()
            out = self.run_step(step, results, log, cancelled)
            outcomes.append(out)
            if out.verified:
                results[step.id] = out.result.output
                if on_step:
                    on_step(idx, "done", f"{time.time() - t0:.1f}s", out)
            else:
                stop = True
                if on_step:
                    on_step(idx, "failed", (out.result.error_kind or "") if out.result else "", out)
        return outcomes
