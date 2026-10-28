"""Sandbox Reflexion Loop (Section 5, Step 4).

Executes generated Python code in an isolated scratch/ sandbox before deployment.
If syntax or runtime errors occur:
- Captures traceback & stderr
- Prompts LLM for targeted fix (up to 3 attempts)
- Only deploys to user destination when exit code is 0.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("star.reflexion")


@dataclass
class ReflexionResult:
    verified: bool
    code: str
    attempts: int
    error: str | None = None
    output: str | None = None


class SandboxReflexionEngine:
    def __init__(self, scratch_dir: Path | str = "scratch", max_attempts: int = 3):
        self.scratch_dir = Path(scratch_dir)
        self.scratch_dir.mkdir(parents=True, exist_ok=True)
        self.max_attempts = max_attempts

    def verify_and_heal(self, initial_code: str, router=None, goal: str = "Execute Python script") -> ReflexionResult:
        current_code = initial_code
        attempts = 0
        temp_file = self.scratch_dir / "temp_sandbox_exec.py"

        while attempts < self.max_attempts:
            attempts += 1
            try:
                temp_file.write_text(current_code, encoding="utf-8")
            except Exception as e:
                return ReflexionResult(verified=False, code=current_code, attempts=attempts, error=str(e))

            # Run python compile and dry run
            try:
                res = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(temp_file)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if res.returncode == 0:
                    # Compile passed, perform short safe execution test
                    run_res = subprocess.run(
                        [sys.executable, str(temp_file)],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if run_res.returncode == 0:
                        log.info("Sandbox verification passed on attempt %d", attempts)
                        return ReflexionResult(
                            verified=True,
                            code=current_code,
                            attempts=attempts,
                            output=run_res.stdout.strip()[:300],
                        )
                    else:
                        err_msg = run_res.stderr.strip() or "Runtime error"
                else:
                    err_msg = res.stderr.strip() or "Syntax compile error"
            except subprocess.TimeoutExpired:
                err_msg = "Execution timed out (process exceeded 10s sandbox limit)"
            except Exception as ex:
                err_msg = f"Execution failed: {ex}"

            log.warning("Sandbox run failed (attempt %d/%d): %s", attempts, self.max_attempts, err_msg)

            # If no router or final attempt reached, exit loop
            if router is None or attempts >= self.max_attempts:
                return ReflexionResult(
                    verified=False,
                    code=current_code,
                    attempts=attempts,
                    error=err_msg,
                )

            # Reflexion Prompt: Ask LLM to fix the specific error
            prompt = (
                f"You are a Senior Python Engineer fixing a runtime failure.\n"
                f"Goal: {goal}\n\n"
                f"Failed Code:\n```python\n{current_code}\n```\n\n"
                f"Error Traceback:\n{err_msg}\n\n"
                f"Instructions:\n"
                f"- Fix the exact error shown in the traceback.\n"
                f"- Return ONLY the corrected, complete Python code.\n"
                f"- Do NOT wrap in explanation or markdown if possible; output pure code."
            )
            try:
                reply = router.chat([{"role": "user", "content": prompt}], task="planning", temperature=0.1)
                text = reply.text.strip()
                if "```python" in text:
                    text = text.split("```python")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()
                if text:
                    current_code = text
            except Exception as e:
                log.error("Reflexion LLM call failed: %s", e)
                break

        return ReflexionResult(verified=False, code=current_code, attempts=attempts, error=err_msg)
