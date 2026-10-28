import json
import tempfile
from pathlib import Path

from star_core.config import Config
from star_core.llm import MockLLM, ModelRouter
from star_core.memory import MemoryStore
from star_core.orchestrator import Orchestrator
from star_core.tools import default_registry
from star_core.ui_port import RecordingPort


class Env:
    """A complete backend wired to a temp folder, a MockLLM and a recording UI."""

    def __init__(self, approvals=None, answers=None, with_skills=False, default_approval=True):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.src, self.dst = self.tmp / "src", self.tmp / "dst"
        self.src.mkdir()
        self.config = Config(home=self.tmp / "home", allowed_roots=[str(self.tmp)])
        self.llm = MockLLM()
        self.router = ModelRouter(self.llm, None, self.config)
        self.store = MemoryStore()
        self.ui = RecordingPort(approvals=approvals, answers=answers, default_approval=default_approval)
        self.registry = default_registry()
        self.skills = self.learner = None
        if with_skills:
            from star_core.skills import SkillLearner, SkillRegistry
            self.skills = SkillRegistry(self.config.skills_dir, self.store)
            self.learner = SkillLearner(self.skills, self.router, self.config)
        self.orch = Orchestrator(self.config, self.router, self.store, self.registry, self.ui,
                                 skills=self.skills, learner=self.learner)

    def make_files(self, names=("a.json", "b.json", "c.json", "note.txt")):
        for n in names:
            (self.src / n).write_text(f"content of {n}")

    def ask(self, text):
        return self.orch.handle(text)

    def copy_request(self, dst=None):
        dst = dst or self.dst
        return f"find all json files in '{self.src}' and copy them to '{dst}'"
