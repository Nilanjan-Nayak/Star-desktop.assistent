"""Sandbox for CODE skills: static guard + isolated subprocess with timeout, memory cap and no builtins escape.

Honest scope: this blocks the common ways untrusted generated code reaches the file system, network or
processes, but it is a guard rail, not a security boundary against a determined attacker. Code skills are
therefore pure data transforms (dict in, dict out) and are never given tools.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass

ALLOWED_IMPORTS = {"re", "math", "json", "itertools", "functools", "collections", "datetime", "string", "textwrap",
                   "unicodedata", "statistics", "decimal", "fractions", "hashlib", "base64", "typing"}
FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "globals", "locals", "vars",
                   "breakpoint", "getattr", "setattr", "delattr", "memoryview", "exit", "quit"}
MARKER = "@@STAR_RESULT@@"

_RUNNER = r'''
import sys, json, builtins
data = json.load(sys.stdin)
ALLOWED = set(data["allowed"])
_real_import = builtins.__import__
def guarded_import(name, *a, **k):
    if name.split(".")[0] not in ALLOWED:
        raise ImportError("import not allowed: " + name)
    return _real_import(name, *a, **k)
names = ("abs all any bool dict enumerate float int len list map max min range reversed round set sorted str sum "
         "tuple zip isinstance ord chr filter repr divmod pow slice frozenset bytes bytearray format hash "
         "ValueError TypeError KeyError IndexError Exception ZeroDivisionError StopIteration").split()
safe = {n: getattr(builtins, n) for n in names}
safe["__import__"] = guarded_import
safe["__build_class__"] = builtins.__build_class__
g = {"__builtins__": safe, "__name__": "skill"}
try:
    exec(compile(data["code"], "<skill>", "exec"), g)
    result = g["run"](data["inputs"])
    out = json.dumps({"ok": True, "result": result}, ensure_ascii=False, default=str)
except BaseException as e:
    out = json.dumps({"ok": False, "error": type(e).__name__ + ": " + str(e)})
sys.stdout.write("\n" + "@@STAR_RESULT@@" + out)
'''


class GuardError(Exception):
    pass


def check_code(code: str) -> None:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise GuardError(f"syntax error: {e}") from e
    has_run = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    raise GuardError(f"import not allowed: {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                raise GuardError(f"import not allowed: {node.module}")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise GuardError(f"name not allowed: {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise GuardError(f"attribute not allowed: {node.attr}")
        elif isinstance(node, ast.FunctionDef) and node.name == "run":
            has_run = True
    if not has_run:
        raise GuardError("the skill must define run(inputs)")


@dataclass
class SandboxResult:
    ok: bool
    result: object = None
    error: str = ""


def _limits():  # POSIX only; on Windows the timeout is the guard
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    except Exception:
        pass


def run_code(code: str, inputs: dict, timeout: float = 5.0) -> SandboxResult:
    try:
        check_code(code)
    except GuardError as e:
        return SandboxResult(False, error=f"blocked by guard: {e}")
    payload = json.dumps({"code": code, "inputs": inputs, "allowed": sorted(ALLOWED_IMPORTS)})
    kwargs = {} if sys.platform == "win32" else {"preexec_fn": _limits}
    with tempfile.TemporaryDirectory() as cwd:
        try:
            proc = subprocess.run([sys.executable, "-I", "-c", _RUNNER], input=payload, capture_output=True, text=True,
                                  timeout=timeout, cwd=cwd, env={}, **kwargs)
        except subprocess.TimeoutExpired:
            return SandboxResult(False, error=f"timed out after {timeout:g}s")
    if MARKER not in proc.stdout:
        return SandboxResult(False, error=(proc.stderr or "no result")[-300:])
    data = json.loads(proc.stdout.split(MARKER, 1)[1][:200_000])
    return SandboxResult(bool(data.get("ok")), data.get("result"), data.get("error", ""))
