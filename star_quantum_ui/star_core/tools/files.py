"""File tools. Every one works only inside the allowed roots and verifies itself against the disk."""
from __future__ import annotations

import fnmatch
import hashlib
import os
import shutil
from pathlib import Path

from ..models import Check, ToolResult, Verdict
from ..security import PolicyError
from .base import Param, Tool, ToolContext


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fail(kind: str, msg: str) -> ToolResult:
    return ToolResult(False, {}, msg, kind)


class FindFiles(Tool):
    outputs = ("files", "count")
    name = "find_files"
    description = "Find files by glob pattern (case-insensitive) under a folder. Returns absolute paths."
    risk = "low"
    params = {"root": Param("str", desc="absolute folder"), "pattern": Param("str", False, "e.g. *.json", "*"),
              "recursive": Param("bool", False, "search sub-folders", True), "limit": Param("int", False, "max files", 10000)}

    def run(self, args, ctx: ToolContext):
        try:
            root = ctx.policy.resolve(args["root"])
        except PolicyError as e:
            return _fail("denied", str(e))
        if not root.is_dir():
            return _fail("not_found", f"folder not found: {root}")
        pat, found = args["pattern"].lower(), []
        walker = os.walk(root) if args["recursive"] else [(str(root), [], [p.name for p in root.iterdir() if p.is_file()])]
        for base, _dirs, names in walker:
            for n in sorted(names):
                if fnmatch.fnmatch(n.lower(), pat):
                    found.append(str(Path(base) / n))
                    if len(found) >= args["limit"]:
                        break
        found.sort()
        return ToolResult(True, {"files": found, "count": len(found)})

    def verify(self, args, result, ctx):
        files = result.output.get("files", [])
        pat = args["pattern"].lower()
        missing = [f for f in files if not Path(f).is_file()]
        wrong = [f for f in files if not fnmatch.fnmatch(Path(f).name.lower(), pat)]
        return Verdict.of([Check("files exist", not missing, f"{len(missing)} missing"),
                           Check("pattern matches", not wrong, f"{len(wrong)} mismatching"),
                           Check("count consistent", result.output.get("count") == len(files))])


class ListDir(Tool):
    outputs = ("entries", "count")
    name = "list_dir"
    description = "List the entries of a folder (names only)."
    params = {"path": Param("str", desc="absolute folder")}

    def run(self, args, ctx):
        try:
            p = ctx.policy.resolve(args["path"])
        except PolicyError as e:
            return _fail("denied", str(e))
        if not p.is_dir():
            return _fail("not_found", f"folder not found: {p}")
        names = sorted(x.name + ("/" if x.is_dir() else "") for x in p.iterdir())
        return ToolResult(True, {"entries": names, "count": len(names)})

    def verify(self, args, result, ctx):
        return Verdict.of([Check("folder still exists", Path(args["path"]).is_dir())])


class MakeDir(Tool):
    outputs = ("path",)
    name = "make_dir"
    description = "Create a folder (and parents). Safe if it already exists."
    risk = "medium"
    params = {"path": Param("str", desc="absolute folder to create")}

    def run(self, args, ctx):
        try:
            p = ctx.policy.resolve(args["path"])
            p.mkdir(parents=True, exist_ok=True)
        except PolicyError as e:
            return _fail("denied", str(e))
        except OSError as e:
            return _fail("os_error", str(e))
        return ToolResult(True, {"path": str(p)})

    def verify(self, args, result, ctx):
        return Verdict.of([Check("folder exists", Path(result.output.get("path", args["path"])).is_dir())])


class CopyFiles(Tool):
    outputs = ("copied", "skipped", "failed", "total")
    name = "copy_files"
    description = ("Copy files into a destination folder. Never overwrites by default; identical files are "
                   "skipped; different files with the same name are reported as conflicts.")
    risk = "medium"
    params = {"files": Param("list", desc="absolute file paths"), "dest_dir": Param("str", desc="absolute folder"),
              "overwrite": Param("bool", False, "replace existing files (high risk)", False),
              "base_dir": Param("str", False, "if set, keep sub-folder structure relative to this folder", "")}

    def risk_for(self, args):
        return "high" if args.get("overwrite") else "medium"

    def _target(self, src: Path, dest: Path, base: str) -> Path:
        if base:
            try:
                return dest / src.relative_to(Path(base).resolve())
            except ValueError:
                pass
        return dest / src.name

    def run(self, args, ctx):
        try:
            dest = ctx.policy.resolve(args["dest_dir"])
        except PolicyError as e:
            return _fail("denied", str(e))
        if not dest.is_dir():
            return _fail("not_found", f"destination folder missing: {dest}")
        copied, skipped, failed = [], [], []
        for raw in args["files"]:
            if ctx.cancelled():
                failed.append({"src": raw, "reason": "cancelled", "kind": "cancelled"})
                continue
            try:
                src = ctx.policy.resolve(raw)
                if not src.is_file():
                    raise FileNotFoundError(f"source missing: {src}")
                dst = self._target(src, dest, args["base_dir"])
                if dst.exists() and not args["overwrite"]:
                    if sha256(src) == sha256(dst):
                        skipped.append({"src": str(src), "dst": str(dst), "reason": "identical file already there"})
                    else:
                        failed.append({"src": str(src), "reason": f"name collision, different file exists: {dst.name}",
                                       "kind": "conflict"})
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied.append({"src": str(src), "dst": str(dst)})
            except PolicyError as e:
                failed.append({"src": raw, "reason": str(e), "kind": "denied"})
            except FileNotFoundError as e:
                failed.append({"src": raw, "reason": str(e), "kind": "not_found"})
            except OSError as e:
                failed.append({"src": raw, "reason": f"{type(e).__name__}: {e}", "kind": "os_error"})
        out = {"copied": copied, "skipped": skipped, "failed": failed, "total": len(args["files"])}
        if failed:
            kinds = sorted({f["kind"] for f in failed})
            return ToolResult(False, out, f"{len(failed)} of {out['total']} files not copied", kinds[0])
        return ToolResult(True, out)

    def verify(self, args, result, ctx):
        """Independent check: re-hash every source against its destination on disk."""
        dest = Path(args["dest_dir"]).resolve()
        checks, bad = [], []
        for raw in args["files"]:
            src = Path(raw).resolve()
            dst = self._target(src, dest, args.get("base_dir", ""))
            try:
                ok = dst.is_file() and sha256(src) == sha256(dst)
            except OSError:
                ok = False
            if not ok:
                bad.append(src.name)
        checks.append(Check("every file present and identical at destination", not bad,
                            f"{len(bad)} missing or different: {', '.join(bad[:5])}" if bad else ""))
        out = result.output
        accounted = len(out.get("copied", [])) + len(out.get("skipped", []))
        checks.append(Check("tool's own count agrees with the disk", accounted == len(args["files"]) - len(bad),
                            f"tool reported {accounted}, disk shows {len(args['files']) - len(bad)}"))
        return Verdict.of(checks)


class ReadText(Tool):
    outputs = ("text",)
    name = "read_text"
    description = "Read a text file (first 64 KB)."
    params = {"path": Param("str", desc="absolute file")}

    def run(self, args, ctx):
        try:
            p = ctx.policy.resolve(args["path"])
            data = p.read_bytes()[:65536].decode("utf-8", errors="replace")
        except PolicyError as e:
            return _fail("denied", str(e))
        except FileNotFoundError:
            return _fail("not_found", f"file not found: {args['path']}")
        except OSError as e:
            return _fail("os_error", str(e))
        return ToolResult(True, {"text": data})

    def verify(self, args, result, ctx):
        return Verdict.of([Check("file readable", Path(args["path"]).is_file())])


class WriteText(Tool):
    outputs = ("path", "bytes", "content")
    name = "write_text"
    description = "Write a text file. Refuses to overwrite unless overwrite=true (high risk)."
    risk = "medium"
    params = {"path": Param("str", desc="absolute file"), "content": Param("str", desc="text"),
              "overwrite": Param("bool", False, "replace if exists", False)}

    def risk_for(self, args):
        return "high" if args.get("overwrite") else "medium"

    def run(self, args, ctx):
        try:
            p = ctx.policy.resolve(args["path"])
            if p.exists() and not args["overwrite"]:
                if p.is_file() and p.read_text(encoding="utf-8") == args["content"]:
                    content = args["content"]
                    return ToolResult(True, {"path": str(p), "bytes": len(content.encode("utf-8")),
                                             "content": content, "unchanged": True})
                return _fail("conflict", f"already exists with different content: {p}")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args["content"], encoding="utf-8")
        except PolicyError as e:
            return _fail("denied", str(e))
        except OSError as e:
            return _fail("os_error", str(e))
        return ToolResult(True, {"path": str(p), "bytes": len(args["content"].encode("utf-8")),
                                 "content": args["content"]})

    def verify(self, args, result, ctx):
        try:
            same = Path(args["path"]).read_text(encoding="utf-8") == args["content"]
        except OSError:
            same = False
        return Verdict.of([Check("file content matches what was requested", same)])
