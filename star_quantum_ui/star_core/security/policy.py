"""Hard boundaries. A path outside the allowed roots is refused outright, never offered for approval."""
from __future__ import annotations

from pathlib import Path


class PolicyError(Exception):
    """Raised when an action is outside what STAR is allowed to do."""


import re


class PermissionPolicy:
    def __init__(self, roots: list[Path]):
        self.roots = [Path(r).expanduser().resolve() for r in roots]

    def is_allowed(self, path: str | Path) -> bool:
        try:
            s = str(path).strip().strip("\"'")
            s = re.sub(r"^\$\{+([^}]+)\}+$", r"\1", s).strip()
            p = Path(s).expanduser().resolve()
        except (OSError, RuntimeError):
            return False
        return any(p == r or r in p.parents for r in self.roots)

    def resolve(self, path: str | Path) -> Path:
        s = str(path).strip().strip("\"'")
        # Strip accidental ${{...}} or ${...} wrappers around paths
        s = re.sub(r"^\$\{+([^}]+)\}+$", r"\1", s).strip()
        p = Path(s).expanduser()

        if not p.is_absolute():
            # Check if relative path starts with an allowed root name (e.g. "Desktop/...", "Downloads/...")
            for root in self.roots:
                if p.parts and p.parts[0].lower() == root.name.lower():
                    cand = root / Path(*p.parts[1:])
                    if self.is_allowed(cand):
                        return cand.resolve()
            # If still relative, try under first allowed root
            if self.roots:
                cand = self.roots[0] / p
                if self.is_allowed(cand):
                    return cand.resolve()
            raise PolicyError(f"path must be absolute: {path}")

        p = p.resolve()
        if not self.is_allowed(p):
            raise PolicyError(f"outside the folders STAR may use: {p}")
        return p
