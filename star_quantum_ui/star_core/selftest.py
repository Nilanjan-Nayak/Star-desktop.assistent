"""Phase self-test: runs the whole suite plus accuracy scenarios and writes PHASE_REPORT.md.

    python -m star_core.selftest

The report has what the architecture doc asks for after every phase: files, tests run, results,
remaining problems and how to roll back. It reports measured numbers only.
"""
from __future__ import annotations

import hashlib
import io
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


def _run_suite() -> tuple[unittest.TestResult, float, str]:
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    stream = io.StringIO()
    t0 = time.time()
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    return result, time.time() - t0, stream.getvalue()


def _scenarios() -> list[dict]:
    """Realistic situations run end to end with the offline test model. Measures verified outcomes, not claims."""
    from tests.helpers import Env
    import shutil
    out = []

    def run(name, expect_ok, fn):
        e = Env()
        t0 = time.time()
        r = fn(e)
        ok = bool(r and r.ok)
        out.append({"name": name, "expected_ok": expect_ok, "verified_ok": ok, "match": ok == expect_ok,
                    "seconds": round(time.time() - t0, 2), "false_success": bool(r and r.ok and not expect_ok)})

    def happy(e):
        e.make_files()
        return e.ask(e.copy_request())

    def partial(e):
        e.make_files([f"f{i}.json" for i in range(10)])
        real = shutil.copy2
        flaky = lambda s, d, *a, **k: (_ for _ in ()).throw(PermissionError("locked")) if str(s).endswith(("f3.json", "f7.json")) else real(s, d, *a, **k)
        with mock.patch("star_core.tools.files.shutil.copy2", flaky):
            return e.ask(e.copy_request())

    def collision(e):
        for d in ("x", "y"):
            (e.src / d).mkdir()
            (e.src / d / "a.json").write_text(d)
        return e.ask(e.copy_request())

    def phone(e):
        e.make_files()
        return e.ask(e.copy_request() + " and send them to my phone")

    def declined(e):
        e.ui.approvals = [False]
        e.make_files()
        return e.ask(e.copy_request())

    run("copy 3 JSON files", True, happy)
    run("10 files, 2 locked (the doc's 8-of-10 case)", False, partial)
    run("same file name in two sub-folders", False, collision)
    run("copy + send to phone (not supported yet)", False, phone)
    run("user declines the plan", False, declined)
    return out


def main() -> int:
    result, secs, log = _run_suite()
    scen = _scenarios()
    files = sorted(p for p in (ROOT / "star_core").rglob("*.py")) + sorted((ROOT / "tests").glob("*.py"))
    total_lines = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in files)
    lines = ["# STAR backend: phase report", "",
             f"Generated {time.strftime('%Y-%m-%d %H:%M:%S')} by `python -m star_core.selftest`.", "",
             "## Scope of this phase",
             "Phases 2-4 of the master plan: Brain + Memory integration, Planning + Tool execution with permissions, "
             "Skill learning + accuracy/error recovery, plus the bridge to the existing frontend. "
             "Not included: voice (phase 5), research/evidence, browser automation and phone remote control (phase 6).", "",
             "## Tests",
             f"- Ran: **{result.testsRun}**  Passed: **{result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)}**  "
             f"Failed: **{len(result.failures)}**  Errors: **{len(result.errors)}**  Skipped: **{len(result.skipped)}**  ({secs:.1f}s)",
             "- Language model used by the tests: an offline test double (`MockLLM`). It checks the pipeline, **not** how well a real model understands Bangla.", ""]
    for kind, items in (("FAIL", result.failures), ("ERROR", result.errors)):
        for t, tb in items:
            lines += [f"### {kind}: {t}", "```", tb.strip()[-600:], "```"]
    lines += ["## Accuracy scenarios (end to end, real files on disk)", "",
              "| Scenario | Correct outcome | Reported verified success | Matches | False success |", "|---|---|---|---|---|"]
    for s in scen:
        lines.append(f"| {s['name']} | {'success' if s['expected_ok'] else 'not a full success'} | {s['verified_ok']} | "
                     f"{'yes' if s['match'] else '**NO**'} | {'**YES**' if s['false_success'] else 'no'} |")
    fs = sum(s["false_success"] for s in scen)
    lines += ["", f"False successes in these scenarios: **{fs}**. Scenarios matching the expected outcome: "
                 f"**{sum(s['match'] for s in scen)}/{len(scen)}**.", "",
              "## Files", f"{len(files)} Python files, {total_lines} lines.", "", "| File | Lines | SHA-256 (first 12) |", "|---|---|---|"]
    for p in files:
        txt = p.read_bytes()
        lines.append(f"| `{p.relative_to(ROOT)}` | {len(txt.splitlines())} | {hashlib.sha256(txt).hexdigest()[:12]} |")
    lines += ["", "## Known gaps and risks",
              "- Never run against a real Ollama/OpenRouter model in this environment. Prompt quality, JSON reliability and Bangla "
              "understanding must be measured on your machine (`python run_star.py --check`, then try real requests).",
              "- Sandbox for code skills is a guard rail (AST allow-list, no builtins escape, timeout, memory cap on Linux/macOS), "
              "not a hard security boundary. On Windows the memory cap is not applied.",
              "- Path policy covers the file tools. `run_command`/`install_package` are allow-listed and always need approval, but "
              "they act on the whole machine once approved.",
              "- Pause/resume in the agent tab is not wired to the backend yet. Stop and Cancel are.",
              "- No voice, research, browser automation or phone access yet (phases 5-6).",
              "- Only pip installs are supported by `install_package`.", "",
              "## Rollback",
              "Everything is additive: `star_core/`, `tests/`, `run_star.py`, plus small edits in `star_ui/tabs/system_tab.py` "
              "(title wrapping). To roll back: delete those folders/files (the frontend runs on its own with "
              "`python main.py` or `python run_star.py --demo`). Runtime data lives in the STAR home folder "
              "(`~/.star` or `$STAR_HOME`): `star.db` (memory), `skills/`, `star_config.json`; delete it to reset the assistant.", ""]
    out = ROOT / "PHASE_REPORT.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{result.testsRun} tests, {len(result.failures)} failures, {len(result.errors)} errors; "
          f"{sum(s['match'] for s in scen)}/{len(scen)} scenarios as expected, {fs} false successes -> {out}")
    return 0 if result.wasSuccessful() and fs == 0 and all(s["match"] for s in scen) else 1


if __name__ == "__main__":
    sys.exit(main())
