"""Security & Safety Guards (Sections C & D).

Implements:
- Path traversal block (../ block, logs to security_log.json)
- Dangerous command block (rm -rf, format C:, del /s /q)
- API key masking (sk-****) and exposure warnings
- Code injection escaping (< > & " ')
- Infinite loop detection (same tool + same args 3x)
"""
from __future__ import annotations

import html
import json
import logging
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("star.security_guard")

DANGEROUS_COMMANDS = (
    r"\brm\s+-rf\b",
    r"\bformat\s+[A-Za-z]:",
    r"\bdel\s+/[sS]\s+/[qQ]\b",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",  # fork bomb
)

API_KEY_PATTERN = re.compile(r"\b(sk-[A-Za-z0-9_-]{8,})\b")


class SecurityGuard:
    def __init__(self, log_path: Path | str = "security_log.json"):
        self.log_path = Path(log_path)
        self._lock = threading.RLock()
        self._recent_tool_calls: list[tuple[str, str]] = []

    def log_incident(self, rule: str, details: str, input_str: str) -> None:
        """Log violation to security_log.json."""
        with self._lock:
            entries = []
            if self.log_path.exists():
                try:
                    entries = json.loads(self.log_path.read_text(encoding="utf-8"))
                except Exception:
                    entries = []
            entries.append({
                "timestamp": datetime.now().isoformat(),
                "rule": rule,
                "details": details,
                "input": input_str[:200],
            })
            try:
                self.log_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                log.error("Could not write security log: %s", e)

    def check_path_traversal(self, path_str: str) -> bool:
        """Returns True if path traversal is detected."""
        if not path_str:
            return False
        clean = path_str.replace("\\", "/")
        if "/../" in clean or clean.startswith("../") or clean.endswith("/..") or clean == "..":
            self.log_incident("PATH_TRAVERSAL_BLOCK", "Attempted relative directory traversal", path_str)
            return True
        return False

    def check_dangerous_command(self, cmd_str: str) -> tuple[bool, str | None]:
        """Returns (is_dangerous, matched_pattern)."""
        if not cmd_str:
            return False, None
        for pattern in DANGEROUS_COMMANDS:
            if re.search(pattern, cmd_str, re.IGNORECASE):
                self.log_incident("DANGEROUS_COMMAND_BLOCK", f"Matched pattern: {pattern}", cmd_str)
                return True, pattern
        return False, None

    def mask_api_keys(self, text: str) -> tuple[str, bool]:
        """Masks any API keys found in text, returns (masked_text, had_key)."""
        if not text:
            return text, False
        had_key = False
        def _repl(match):
            nonlocal had_key
            had_key = True
            key = match.group(1)
            return f"sk-****{key[-4:]}"
        masked = API_KEY_PATTERN.sub(_repl, text)
        return masked, had_key

    def sanitize_html(self, text: str) -> str:
        """Escape HTML code injection."""
        return html.escape(text)

    def record_and_check_loop(self, tool_name: str, args: dict[str, Any]) -> bool:
        """Returns True if infinite loop detected (same tool + same args 3 consecutive times)."""
        with self._lock:
            args_str = json.dumps(args, sort_keys=True)
            self._recent_tool_calls.append((tool_name, args_str))
            if len(self._recent_tool_calls) > 10:
                self._recent_tool_calls = self._recent_tool_calls[-10:]

            if len(self._recent_tool_calls) >= 3:
                last_3 = self._recent_tool_calls[-3:]
                if all(item == last_3[0] for item in last_3):
                    self.log_incident("INFINITE_LOOP_DETECTED", f"Tool '{tool_name}' called 3 times with identical arguments", args_str)
                    return True
            return False
