"""Tool contract. A tool does one thing, declares its risk, and knows how to *verify itself independently*."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable

from ..config import Config
from ..models import ToolResult, Verdict
from ..security import PermissionPolicy


@dataclass
class Param:
    type: str                      # str | int | bool | list | dict
    required: bool = True
    desc: str = ""
    default: Any = None


class CommandRunner:
    """Runs external commands (argv list, never a shell). Replaceable in tests."""

    def run(self, argv: list[str], timeout: float = 600, on_line: Callable[[str], None] | None = None,
            cwd: str | None = None) -> tuple[int, str]:
        lines: list[str] = []
        with subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              encoding="utf-8", errors="replace", cwd=cwd) as proc:
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    line = line.rstrip()
                    lines.append(line)
                    if on_line:
                        on_line(line)
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                return 124, "\n".join(lines) + "\n[timed out]"
        return proc.returncode, "\n".join(lines)


@dataclass
class ToolContext:
    policy: PermissionPolicy
    config: Config
    log: Callable[[str], None] = lambda _m: None
    cancelled: Callable[[], bool] = lambda: False
    runner: CommandRunner = field(default_factory=CommandRunner)
    ui: Any = None


_TYPES = {"str": str, "int": int, "bool": bool, "list": list, "dict": dict}


class Tool:
    name = ""
    description = ""
    risk = "low"                   # low | medium | high
    params: dict[str, Param] = {}
    outputs: tuple = ()            # field names later steps may reference as ${step.field}

    def risk_for(self, args: dict) -> str:
        return self.risk

    def validate(self, args: dict) -> list[str]:
        errs = []
        for k in args:
            if k not in self.params:
                errs.append(f"unknown argument '{k}'")
        for k, p in self.params.items():
            if k not in args:
                if p.required:
                    errs.append(f"missing argument '{k}'")
                continue
            # Auto-coerce common LLM string formats
            if p.type == "bool" and isinstance(args[k], str) and args[k].lower() in ("true", "false"):
                args[k] = (args[k].lower() == "true")
            elif p.type == "int" and isinstance(args[k], str) and args[k].isdigit():
                args[k] = int(args[k])
            if not isinstance(args[k], _TYPES[p.type]) or (p.type == "int" and isinstance(args[k], bool)):
                errs.append(f"argument '{k}' must be {p.type}")
        return errs

    def with_defaults(self, args: dict) -> dict:
        out = dict(args)
        for k, p in self.params.items():
            if k not in out and not p.required:
                out[k] = p.default
        return out

    def run(self, args: dict, ctx: ToolContext) -> ToolResult:  # pragma: no cover - interface
        raise NotImplementedError

    def verify(self, args: dict, result: ToolResult, ctx: ToolContext) -> Verdict:  # pragma: no cover
        raise NotImplementedError

    def catalog_entry(self) -> str:
        ps = ", ".join(f"{k}:{p.type}{'' if p.required else '?'}" for k, p in self.params.items())
        return f"- {self.name}({ps}) [risk={self.risk}] {self.description}"
