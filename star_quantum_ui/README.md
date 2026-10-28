# 🌌 STAR Quantum Assistant ( Enterprise Architecture)

[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)](docs/benchmarks/BENCHMARK_AND_TEST_RESULTS.md)
[![Architecture](https://img.shields.io/badge/Architecture-Hybrid%20Intelligence-blue)](docs/architecture/HYBRID_INTELLIGENCE_BLUEPRINT.md)
[![Benchmarks](https://img.shields.io/badge/Benchmarks-55%2F55%20Passing-success)](docs/benchmarks/BENCHMARK_AND_TEST_RESULTS.md)
[![License](https://img.shields.io/badge/License-Proprietary-orange)](#)

> **STAR (Synthetic Telemetric Autonomous Reasoning)** is a next-generation local AI workstation assistant and autonomous execution runtime. It combines an ultra-fluid 60 FPS Qt6 cybernetic particle reactor interface with an enterprise hybrid intelligence engine: local LLM inference (`qwen2.5:3b` on Ollama), multi-tier episodic memory, automatic sandbox reflexion self-repair, and strict zero-tolerance workspace security.

---

## 📑 Central Documentation Hub

All technical specifications, architectural blueprints, developer guides, and test reports have been cleanly partitioned into the [docs/](file:///c:/Users/nilan/Downloads/star_quantum_ui%20%283%29/star_quantum_ui/docs) directory:

| Document | Category | Description |
| :--- | :--- | :--- |
| 📖 [Documentation Index](file:///c:/Users/nilan/Downloads/star_quantum_ui%20%283%29/star_quantum_ui/docs/INDEX.md) | **Master Portal** | Central entry point for all architectural layers, navigation maps, and user roles. |
| 📐 [Hybrid Intelligence Blueprint](file:///c:/Users/nilan/Downloads/star_quantum_ui%20%283%29/star_quantum_ui/docs/architecture/HYBRID_INTELLIGENCE_BLUEPRINT.md) | **Architecture** | Complete specification of streaming, multi-tier memory, reflexion loops, and LoRA fine-tuning. |
| 🗺️ [Project Overview & Roadmap](file:///c:/Users/nilan/Downloads/star_quantum_ui%20%283%29/star_quantum_ui/docs/architecture/STAR_PROJECT_OVERVIEW_AND_INTELLIGENCE_ROADMAP.md) | **Architecture** | System encyclopedia, sequence diagrams, component breakdowns, and intelligence roadmaps. |
| 🤖 [Agent System Prompt](file:///c:/Users/nilan/Downloads/star_quantum_ui%20%283%29/star_quantum_ui/docs/specifications/AGENT_SYSTEM_PROMPT.md) | **Specification** | Official 16-section behavioral constitution, confidence rubric, and error taxonomy. |
| 🧪 [Benchmark & Test Results](file:///c:/Users/nilan/Downloads/star_quantum_ui%20%283%29/star_quantum_ui/docs/benchmarks/BENCHMARK_AND_TEST_RESULTS.md) | **Verification** | 45-scenario test suite logs, 100% pass rate evidence, latency records, and security audits. |
| 💻 [Developer Guide](file:///c:/Users/nilan/Downloads/star_quantum_ui%20%283%29/star_quantum_ui/docs/guides/DEVELOPER_GUIDE.md) | **Operations** | Installation, environment setup, CLI flags, tool development, and debugging workflows. |
| 📊 [Phase Progress Report](file:///c:/Users/nilan/Downloads/star_quantum_ui%20%283%29/star_quantum_ui/docs/reports/PHASE_REPORT.md) | **Reports** | Historical milestone evolution, accuracy benchmarks, and architectural changelog. |

---

## ⚡ Quick Start

### 1. Requirements & Prerequisites
- **Python**: 3.10+
- **GPU**: NVIDIA RTX 3050 (or equivalent with CUDA/Vulkan support)
- **Local LLM Engine**: [Ollama](https://ollama.com/) running with model `qwen2.5:3b`:
  ```bash
  ollama serve
  ollama pull qwen2.5:3b
  ```

### 2. Installation
Clone the repository and install the core dependencies:
```bash
pip install -r requirements.txt
```

### 3. Launching STAR
```bash
# Verify system readiness and security paths
python run_star.py --check

# Launch Full Autonomous UI (Reactor + Ghost Terminal + Real Backend)
python run_star.py

# Launch Headless CLI Mode (No GPU display required)
python run_star.py --cli

# Run Complete 45-Scenario Verification Benchmark
python scratch/benchmark_45_tests.py
```

---

## 🏗️ Enterprise Directory Structure

```
star_quantum_ui/
├── docs/                                  # Clean Enterprise Documentation Hub
│   ├── INDEX.md                           # Master Documentation Portal
│   ├── architecture/                      # Blueprints, Roadmaps & Flowcharts
│   │   ├── HYBRID_INTELLIGENCE_BLUEPRINT.md
│   │   └── STAR_PROJECT_OVERVIEW_AND_INTELLIGENCE_ROADMAP.md
│   ├── specifications/                    # Behavioral & Protocol Specs
│   │   └── AGENT_SYSTEM_PROMPT.md
│   ├── benchmarks/                        # Test Suites & Quality Verification
│   │   └── BENCHMARK_AND_TEST_RESULTS.md
│   ├── guides/                            # Developer & Operational Guides
│   │   └── DEVELOPER_GUIDE.md
│   └── reports/                           # Milestone & Phase Reports
│       └── PHASE_REPORT.md
│
├── star_core/                             # Autonomous Backend Engine
│   ├── brain/                             # Intelligence, Routing & Self-Healing
│   │   ├── brain.py                       # Master Reasoning Coordinator
│   │   ├── router.py                      # Multi-provider LLM Router (Ollama/Qwen)
│   │   ├── confidence.py                  # Real-time Mathematical Calibrator (0-100)
│   │   ├── reflexion.py                   # AST-Guided Sandbox Self-Repair Engine
│   │   ├── clarifier.py                   # Socratic Ambiguity Classifier
│   │   ├── quality_gate.py                # 5-Dimensional Output Grader
│   │   ├── evolution.py                   # Dynamic Skill Synthesizer
│   │   ├── prompt.py                      # Dynamic Multi-Context Prompt Assembler
│   │   └── resolver.py                    # Natural Language Ambiguity Normalizer
│   ├── memory/                            # 5-Tier Memory Architecture
│   │   ├── multitier.py                   # Working, Episodic, Semantic, Procedural, Training
│   │   ├── task_tracker.py                # Persistent Task Tracker & JSON Ledger
│   │   ├── undo_system.py                 # Reversible Delta Rollback Engine
│   │   └── audit_logger.py                # Append-only Security Audit Log
│   ├── tools/                             # Secure OS & Web Execution Sandbox
│   │   ├── sandbox.py                     # Safe Subprocess Execution (<10s, no shell=True)
│   │   ├── registry.py                    # Zero-Trust Tool Registry
│   │   ├── file_ops.py                    # Atomic File System Handlers
│   │   ├── web_search.py                  # Dual-Engine DuckDuckGo HTML/Instant Web Fetch
│   │   └── bash_ops.py                    # Allow-listed CLI Command Runner
│   ├── voice/                             # Multimodal Speech Engine
│   │   ├── continuous.py                  # Low-latency Audio Stream Loop
│   │   ├── speech.py                      # Energy-adaptive VAD & Speech Recognition
│   │   └── elevenlabs.py                  # High-Fidelity Neural TTS Driver
│   ├── config.py                          # Unified Paths, Security Whitelists, & Limits
│   ├── orchestrator.py                    # Thread-safe Event Coordinator & Dispatcher
│   └── qt_bridge.py                       # High-Performance UI Signal Translator
│
├── star_ui/                               # Cybernetic Qt6 Frontend (60 FPS)
│   ├── main_window.py                     # Frameless Glassmorphic Master Window
│   ├── reactor.py                         # Quantum Energy Particle Canvas
│   ├── telemetry.py                       # System Stats, CPU/GPU & Confidence HUD
│   ├── ghost_panel.py                     # Interactive Ghost Terminal & Tab Host
│   ├── stage.py                           # Spring-Physics Layout Engine
│   └── tabs/                              # Multi-Context Workspace Tabs (Web, Agent, System)
│
├── run_star.py                            # Unified Production Entrypoint
├── main.py                                # Visual Design Sandbox Entrypoint
├── requirements.txt                       # Python Dependencies Manifest
└── task_tracker.json                      # Live Operational State & Metrics Ledger
```

---

## 🛡️ Security Architecture & Guardrails

STAR strictly implements a zero-trust computing model:
- **Sandbox Root Containment**: File and OS mutations are strictly locked to approved directories: `Desktop`, `Downloads`, `Documents`, and project workspaces. Root operating system paths (`C:\Windows`, `C:\Program Files`, etc.) are unconditionally rejected.
- **Forbidden Patterns**: Destructive CLI commands (`rmdir /s /q`, `format`, `del /f /s /q C:\`) trigger immediate refusal and user confirmation alerts.
- **Subprocess Isolation**: Scripts run in segregated subprocesses with strict timeouts (10s max for untrusted code), standard I/O capture, and no raw `shell=True` execution.
- **Rollback Guarantee**: Every file modification creates an automatic rollback snapshot in `star_core/memory/undo_system.py`, allowing instant single-command undo.

---

## 📈 Quality & Verification

Every code change must adhere to the 45-point regression benchmark suite in [`scratch/benchmark_45_tests.py`](file:///c:/Users/nilan/Downloads/star_quantum_ui%20%283%29/star_quantum_ui/scratch/benchmark_45_tests.py):
```
================================================================================
45/45 (100.0%) TESTS PASSED -- ALL SYSTEMS NOMINAL
================================================================================
```
Full test scenarios and execution outputs are documented in [BENCHMARK_AND_TEST_RESULTS.md](file:///c:/Users/nilan/Downloads/star_quantum_ui%20%283%29/star_quantum_ui/docs/benchmarks/BENCHMARK_AND_TEST_RESULTS.md).
