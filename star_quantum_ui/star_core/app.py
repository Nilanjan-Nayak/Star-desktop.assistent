"""Assembles the backend. One place to see what is wired to what."""
from __future__ import annotations

import logging
import threading

from .config import Config
from .llm import MockLLM, ModelRouter, OllamaClient, OpenRouterClient
from .memory import AgentLearningSystem, MemoryStore, MultiTierMemory, TaskTracker
from .orchestrator import Orchestrator
from .skills import SkillLearner, SkillRegistry, register_skill_tool
from .tools import CommandRunner, default_registry

log = logging.getLogger("star")


def build_orchestrator(config: Config, ui, *, mock_llm: bool = False, runner: CommandRunner | None = None,
                       store: MemoryStore | None = None) -> Orchestrator:
    config.home.mkdir(parents=True, exist_ok=True)
    store = store or MemoryStore(config.db_path)
    multi_mem = MultiTierMemory(config.home / "star_memory")
    learning_sys = AgentLearningSystem("learning_log.json")
    tracker = TaskTracker("task_tracker.json")
    local = MockLLM() if mock_llm else OllamaClient(config.ollama_url, config.ollama_model)
    key = config.openrouter_api_key
    cloud = OpenRouterClient(key, config.openrouter_model) if key else None
    router = ModelRouter(local, cloud, config)
    tools = default_registry()
    skills = SkillRegistry(config.skills_dir, store)
    register_skill_tool(tools, skills)
    learner = SkillLearner(skills, router, config)
    return Orchestrator(config, router, store, tools, ui, runner=runner, skills=skills, learner=learner,
                        multi_mem=multi_mem, learning_sys=learning_sys, tracker=tracker)


class BackendRunner:
    """Worker thread: takes user text from the port's inbox and runs it through the orchestrator, one at a time."""

    def __init__(self, port, orchestrator: Orchestrator):
        self.port, self.orch = port, orchestrator
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="star-backend", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if hasattr(self.port, "shutdown"):
            self.port.shutdown()

    def _loop(self) -> None:
        import queue
        self.orch._push_metrics()
        while not self._stop.is_set():
            try:
                text = self.port.inbox.get(timeout=0.4)
            except queue.Empty:
                continue
            self.port.reset_cancel()
            try:
                self.orch.handle(text)
            except Exception:
                log.exception("unhandled error in backend loop")
