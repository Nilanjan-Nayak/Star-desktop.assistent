# STAR backend (`star_core`)

Plugs into the existing frontend (`star_ui`) through one seam: `star_ui/bridge.py` <-> `star_core/qt_bridge.py`.
Standard library only (plus PySide6 for the window). Local-first: Ollama, with OpenRouter as an optional fallback.

## Run
    pip install -r requirements.txt
    python run_star.py --check          # is Ollama reachable? are the allowed folders there?
    python run_star.py                  # starts Ollama if needed, then opens window + backend
    python run_star.py --mock-llm       # window + backend with the offline test model (pipeline only)
    python run_star.py --demo           # window only, scripted fake assistant
    python run_star.py --no-ollama-autostart  # use an already-running Ollama only
    python -m unittest discover -s tests -t .   # 59 tests
    python -m star_core.selftest        # tests + accuracy scenarios -> PHASE_REPORT.md

## First-time setup (Windows 11)
1. Install Ollama and pull a model, e.g. `ollama pull qwen2.5:7b-instruct`. `python run_star.py` starts
   the Ollama service automatically; it does not download a missing model.
2. Run `python run_star.py --check` once: it creates `%USERPROFILE%\.star\star_config.json`.
3. Edit `allowed_roots` there to the folders STAR may touch (default: Documents, Desktop, Downloads, STAR_workspace).
   Anything outside is refused, never offered for approval.
4. Optional cloud fallback: set `"cloud_fallback": true` and the `OPENROUTER_API_KEY` environment variable.
   Memory snippets are not sent to the cloud unless `"allow_cloud_context": true`.
5. Optional voice replies: set the `ELEVENLABS_API_KEY` environment variable. STAR uses voice ID
   `o6qTxWUeRyzRYZyUNDVJ` and Eleven Multilingual v2; without the key, text replies continue normally.

## How a request flows (maps to the architecture doc)
    user text (chat; voice later)
      -> Memory: retrieve relevant notes (marked "may be wrong, verify")          memory/
      -> Brain: intent, entities, missing info, risk, language (bn/banglish/en)   brain/brain.py
      -> ask the user when something is missing or ambiguous (never guess)        orchestrator._understand
      -> resolve folder names to real paths inside the allowed roots              brain/resolver.py
      -> Planner: saved skill first, else LLM plan, then strictly validated       brain/planner.py, skills/
      -> approval (System tab) for medium/high risk                               qt_bridge.request_approval
      -> Executor: run each step, verify it independently on disk, retry only
         transient errors, optional re-plan                                       executor.py, tools/
      -> Reporter: final message built only from verified facts                   reporter.py
      -> Learn: save task memory/lessons; offer a tested skill                    skills/learner.py, metrics.py

## Guarantees the tests enforce
- A task is a success only if **every** step was independently verified (files re-hashed, `pip show`, etc.).
- A tool that claims success while the disk disagrees is caught and counted (`false_success_prevented`).
- 8 of 10 files copied is reported as partial, with the failed files and reasons.
- Unsupported requests (e.g. "send to phone") are admitted, not faked.
- Paths outside the allowed roots are refused; symlink and `..` escapes included.
- Personal memory is saved only when the user explicitly asks; task episodes and lessons are saved automatically.
- Skills: created only after approval, tested in a throw-away folder (including a "same name in two folders" case),
  activated only after a second approval, and a new version that regresses is blocked.
- High-risk workflows (installs, commands) are never turned into skills.

## Adding a tool
Subclass `star_core.tools.Tool`: set `name`, `description`, `risk`, `params`, `outputs`; implement `run()` and, crucially,
`verify()` which re-checks the real state without trusting `run()`. Register it in `tools/__init__.py:default_registry`.

## Frontend contract
Backend -> UI: `bridge.state / message / level / metric / tab_open / tab_event / tab_close`.
UI -> backend: `bridge.user_text` (answers and new requests; "stop"/"থামো" cancels) and `bridge.tab_action`
("approve", "cancel", "stop", "message").

## Honest limits
Not yet tested against a real model here, no voice/research/browser/phone control (phases 5-6), pause/resume not wired.
See `PHASE_REPORT.md`.
