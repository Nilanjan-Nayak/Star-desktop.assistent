"""Task Rollback & Undo System (Section B).

Maintains undo_stack.json, backup/ and backup/deleted/ directories.
Supports:
- "undo koro" -> Reverses last action
- "undo 3 steps" -> Reverses last 3 actions
- "rollback koro" -> Reverses all actions in current task
- "backup dekhao" -> Lists available backups
- "restore koro" -> Restores a specific backup
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger("star.undo")


class UndoSystem:
    def __init__(
        self,
        stack_file: Path | str = "undo_stack.json",
        backup_dir: Path | str = "backup",
    ):
        self.stack_file = Path(stack_file)
        self.backup_dir = Path(backup_dir)
        self.deleted_dir = self.backup_dir / "deleted"
        self._lock = threading.RLock()

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.deleted_dir.mkdir(parents=True, exist_ok=True)
        self.stack: list[dict[str, Any]] = self._load_stack()

    def _load_stack(self) -> list[dict[str, Any]]:
        with self._lock:
            if self.stack_file.exists():
                try:
                    return json.loads(self.stack_file.read_text(encoding="utf-8"))
                except Exception as e:
                    log.warning("Could not load undo stack (%s); creating fresh stack", e)
            initial: list[dict[str, Any]] = []
            try:
                self.stack_file.write_text("[]", encoding="utf-8")
            except Exception:
                pass
            return initial

    def _save_stack(self) -> None:
        with self._lock:
            try:
                self.stack_file.write_text(json.dumps(self.stack, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                log.error("Failed to save %s: %s", self.stack_file, e)

    def backup_before_action(self, target_path: Path | str, action: str) -> str | None:
        """Create a backup before modifying or deleting a file, and record in undo stack."""
        src = Path(target_path)
        with self._lock:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = None

            if src.exists() and src.is_file():
                if action == "delete_file":
                    backup_path = self.deleted_dir / f"{src.stem}_{ts}{src.suffix}"
                    try:
                        shutil.copy2(src, backup_path)
                    except Exception as e:
                        log.warning("Could not backup file before deletion: %s", e)
                else:  # edit / write_text
                    backup_path = self.backup_dir / f"{src.stem}_{ts}{src.suffix}"
                    try:
                        shutil.copy2(src, backup_path)
                    except Exception as e:
                        log.warning("Could not backup file before write: %s", e)

            entry = {
                "action": action,
                "target": str(src),
                "backup_path": str(backup_path) if backup_path else None,
                "timestamp": datetime.now().isoformat(),
                "reversible": True,
                "created_new": not src.exists(),
            }
            self.stack.append(entry)
            self._save_stack()
            return str(backup_path) if backup_path else None

    def undo(self) -> str:
        """Undo last single action."""
        with self._lock:
            if not self.stack:
                return "কোনো রিভার্সেবল অ্যাকশন পাওয়া যায়নি। (Undo stack is empty)"
            entry = self.stack.pop()
            self._save_stack()
            return self._revert_entry(entry)

    def undo_steps(self, n: int = 1) -> str:
        """Undo last n actions."""
        with self._lock:
            if not self.stack:
                return "কোনো রিভার্সেবল অ্যাকশন পাওয়া যায়নি। (Undo stack is empty)"
            reverted = []
            for _ in range(min(n, len(self.stack))):
                entry = self.stack.pop()
                reverted.append(self._revert_entry(entry))
            self._save_stack()
            return f"🔄 {len(reverted)} steps reversed:\n" + "\n".join(f"- {r}" for r in reverted)

    def rollback(self) -> str:
        """Rollback all actions in the current undo stack."""
        with self._lock:
            if not self.stack:
                return "রোলব্যাক করার মতো কোনো অ্যাকশন নেই। (Nothing to rollback)"
            count = len(self.stack)
            reverted = []
            while self.stack:
                entry = self.stack.pop()
                reverted.append(self._revert_entry(entry))
            self._save_stack()
            return f"⏪ Rollback complete ({count} actions restored to original state)."

    def _revert_entry(self, entry: dict[str, Any]) -> str:
        target = Path(entry["target"])
        action = entry.get("action", "")
        backup_path = entry.get("backup_path")
        created_new = entry.get("created_new", False)

        try:
            if created_new and target.exists():
                # If the action created a brand new file, undo means removing it
                if target.is_file():
                    target.unlink()
                    return f"Removed created file: {target.name}"
                elif target.is_dir() and not any(target.iterdir()):
                    target.rmdir()
                    return f"Removed empty created directory: {target.name}"
            elif backup_path and Path(backup_path).exists():
                # Restore original content from backup
                shutil.copy2(backup_path, target)
                return f"Restored {target.name} from {Path(backup_path).name}"
            elif action == "delete_file" and backup_path and Path(backup_path).exists():
                shutil.copy2(backup_path, target)
                return f"Undeleted {target.name} from deleted backup"
            return f"Action on {target.name} acknowledged (no file rollback needed)"
        except Exception as e:
            log.error("Failed reverting %s: %s", target, e)
            return f"Failed to revert {target.name}: {e}"

    def list_backups(self) -> str:
        with self._lock:
            files = list(self.backup_dir.glob("*.*"))
            if not files:
                return "বর্তমানে কোনো ব্যাকআপ ফাইল পাওয়া যায়নি। (`backup/` is empty)"
            lines = ["📦 **Available Backup Files:**\n"]
            for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:8]:
                mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                size_kb = round(f.stat().st_size / 1024, 1)
                lines.append(f"- `{f.name}` ({size_kb} KB) — {mtime}")
            return "\n".join(lines)

    def restore(self, identifier: str) -> str:
        with self._lock:
            files = list(self.backup_dir.glob(f"*{identifier}*"))
            if not files:
                return f"'{identifier}' সম্পর্কিত কোনো ব্যাকআপ পাওয়া যায়নি।"
            latest = sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[0]
            # Infer original file destination from stem (strip _YYYYMMDD_HHMMSS)
            clean_stem = latest.stem.rsplit("_", 2)[0]
            # Try to restore in Desktop or Documents
            dest = Path.home() / "Desktop" / f"{clean_stem}{latest.suffix}"
            try:
                shutil.copy2(latest, dest)
                return f"✅ '{latest.name}' সফলভাবে রিস্টোর করা হয়েছে এখানে: `{dest}`"
            except Exception as e:
                return f"রিস্টোর করতে সমস্যা হয়েছে: {e}"
