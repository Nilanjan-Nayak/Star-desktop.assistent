# 🛠️ STAR Developer & Contributor Guide

**Document Classification:** Developer Manual  
**Version:** v3.0  
**Target Audience:** Engineers, contributors, and local operators  

---

## 🚀 1. Quickstart

### Prerequisites
- Python 3.10, 3.11, or 3.12 (Windows recommended for full GUI & SAPI audio support).
- [Ollama](https://ollama.com/) installed and added to `PATH`.
- Local Model: `qwen2.5:3b` pulled via:
  ```bash
  ollama pull qwen2.5:3b
  ```

### Installation
Clone or navigate to the workspace directory and install dependencies:
```bash
pip install -r requirements.txt
```

Verify your setup:
```bash
python run_star.py --check
```
*Expected output:*
```text
STAR home : C:\Users\<User>\.star
Config    : C:\Users\<User>\.star\star_config.json (exists)
Allowed   : C:\Users\<User>\Documents (ok)
Allowed   : C:\Users\<User>\Desktop (ok)
Allowed   : C:\Users\<User>\Downloads (ok)
Allowed   : C:\Users\<User>\STAR_workspace (ok)
Ollama    : ready (http://127.0.0.1:11434, model qwen2.5:3b)
OpenRouter: no key; cloud_fallback=False
```

Launch the full application:
```bash
python run_star.py
```

---

## ⚙️ 2. Execution Modes & CLI Flags

| Command | Mode | Description |
|---|---|---|
| `python run_star.py` | **Production GUI** | Full Quantum Cyberpunk UI connected to local Ollama backend. |
| `python run_star.py --check` | **Diagnostic Check** | Prints connection health, path permissions, and model availability, then exits. |
| `python run_star.py --mock-llm` | **Offline Testing** | Runs with a deterministic mock model; useful for CI/CD and offline verification. |
| `python run_star.py --demo` | **UI Demo** | Frontend-only simulation mode with simulated assistant responses. |
| `python run_star.py --home <PATH>` | **Custom Home** | Sets a custom storage directory for config, memory, and logs. |

---

## 📁 3. Workspace Directory Layout

```text
star_quantum_ui/
├── run_star.py                # Main executable entry point
├── requirements.txt           # Package dependencies
├── agent_skills.md            # Canonical 16-section system prompt
├── task_tracker.json          # Live task history, success rate & error patterns
├── undo_stack.json            # Reversible action history
├── security_log.json          # Security interception log
├── learning_log.json          # Persistent learning patterns & user preferences
│
├── docs/                      # Master Enterprise Documentation
│   ├── INDEX.md               # Documentation navigation portal
│   ├── architecture/          # Blueprint & system architecture
│   ├── specifications/        # Canonical agent system prompts
│   ├── guides/                # Developer guide (this document)
│   ├── benchmarks/            # Regression test reports
│   └── reports/               # Milestone evolution history
│
├── star_core/                 # Backend Engine
│   ├── brain/                 # Planning, Socratic clarifier, confidence & reflexion
│   ├── evolution/             # Self-evolution engine (patcher.py)
│   ├── llm/                   # Ollama & OpenRouter clients + JSON-repair router
│   ├── memory/                # SQLite store, multi-tier memory & task tracker
│   ├── security/              # Permission policy, security guards & quality gate
│   ├── skills/                # Skill learner, sandbox & registry
│   ├── tools/                 # Filesystem, web, search & system execution tools
│   └── voice/                 # Speech recognition & ElevenLabs/SAPI TTS
│
├── star_memory/               # 5-Tier Memory Persistence
│   ├── working/               # Active task contexts & context_index.json
│   ├── episodic/              # tasks_timeline.jsonl, failed_patterns.jsonl, etc.
│   ├── semantic/              # user_profile.json, system_knowledge.json
│   ├── procedural/            # drafts/, tested/, active/, quarantine/
│   ├── training/              # candidates.jsonl, approved.jsonl, rejected.jsonl
│   └── manifests/             # memory_schema.json
│
├── star_ui/                   # Quantum Cyberpunk Frontend (PySide6)
│   ├── main_window.py         # Window shell, tab host, keyboard shortcuts
│   ├── theme.py               # HSL tailored cyberpunk neon palette
│   └── tabs/                  # Agent reasoning, output, code view & stats tabs
│
├── scratch/                   # Isolated test scripts & regression benchmarks
│   └── benchmark_45_tests.py  # Comprehensive 45-scenario test suite
│
├── backup/                    # Timestamped safety snapshots for instant rollbacks
└── error_logs/                # Detailed error logs (error_XXX.txt)
```

---

## 🛠️ 4. Adding a New Tool

To add a new native tool:
1. Create a function or class inheriting from `Tool` in `star_core/tools/`.
2. Define its argument types, description, and risk level (`low`, `medium`, or `high`).
3. Register the tool in `star_core/tools/registry.py`:

```python
# Example: star_core/tools/my_tool.py
from .base import Tool, ToolResult

class MyCustomTool(Tool):
    name = "custom_lookup"
    description = "Looks up internal system registry values."
    risk = "low"
    
    def run(self, key: str, ctx) -> ToolResult:
        # ctx provides policy enforcement, cancellation checks, and UI logging
        if ctx.cancelled():
            return ToolResult(False, error="Cancelled by user", error_kind="cancelled")
        return ToolResult(True, output=f"Found value for {key}")
```

---

## 🧪 5. Testing & Verification

Run the full 45-scenario regression benchmark:
```bash
python scratch/benchmark_45_tests.py
```

Run pytest on core unit tests:
```bash
pytest tests/
```

Run the built-in phase accuracy test:
```bash
python -m star_core.selftest
```

---

## 🔒 6. Security & Permission Best Practices
- **Allowed Roots:** Never bypass `PermissionPolicy`. All write/delete operations must strictly reside within the user's approved folders (`Desktop`, `Downloads`, `Documents`, `STAR_workspace`).
- **Atomic Operations:** Always invoke `UndoSystem.backup_before_action(path, action)` before writing to or deleting any file on disk.
- **Code Execution:** Never deploy synthesized Python code directly. Route code through `SandboxReflexionEngine.verify_and_heal()` to ensure execution exits with code `0`.
