"""Runtime configuration. Stored as JSON in the STAR home folder; edit it by hand or in code."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def default_home() -> Path:
    return Path(os.environ.get("STAR_HOME", Path.home() / ".star"))


@dataclass
class Config:
    home: Path = field(default_factory=default_home)
    # Folders STAR may read/write. Anything outside is refused, never "asked about".
    allowed_roots: list[str] = field(default_factory=lambda: [
        str(Path.home() / "Documents"), str(Path.home() / "Desktop"),
        str(Path.home() / "Downloads"), str(Path.home() / "STAR_workspace")])
    # LLMs (local first)
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b"
    openrouter_model: str = "openrouter/auto"
    openrouter_key: str = ""            # or env OPENROUTER_API_KEY
    elevenlabs_key: str = "sk_99d598d594078f22219ccede1b43b040005e7a9148979cb9"
    elevenlabs_voice_id: str = "o6qTxWUeRyzRYZyUNDVJ"
    voice_enabled: bool = True
    voice_input_enabled: bool = True
    voice_input_language: str = "bn-IN"
    cloud_fallback: bool = False        # use OpenRouter when the local model fails
    allow_cloud_context: bool = False   # may memory snippets be sent to the cloud?
    cloud_tasks: list[str] = field(default_factory=list)  # task kinds always sent to cloud, e.g. ["planning"]
    # Behaviour
    approval_timeout_s: int = 300
    max_retries: int = 2
    llm_json_retries: int = 1
    max_replans: int = 1
    max_questions: int = 2
    skill_activation_requires_approval: bool = True
    command_allowlist: list[str] = field(default_factory=lambda: ["python", "pip", "git", "node", "npm"])

    @property
    def db_path(self) -> Path:
        return self.home / "star.db"

    @property
    def skills_dir(self) -> Path:
        return self.home / "skills"

    @property
    def roots(self) -> list[Path]:
        return [Path(r).expanduser() for r in self.allowed_roots]

    @property
    def openrouter_api_key(self) -> str:
        return self.openrouter_key or os.environ.get("OPENROUTER_API_KEY", "")

    @property
    def elevenlabs_api_key(self) -> str:
        return self.elevenlabs_key or os.environ.get("ELEVENLABS_API_KEY", "")

    # persistence ---------------------------------------------------------------------
    @classmethod
    def load(cls, home: Path | None = None) -> "Config":
        home = Path(home) if home else default_home()
        cfg = cls(home=home)
        path = home / "star_config.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            for k, v in data.items():
                if hasattr(cfg, k) and k != "home":
                    setattr(cfg, k, v)
        return cfg

    def save(self) -> Path:
        self.home.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        data.pop("home")
        path = self.home / "star_config.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
