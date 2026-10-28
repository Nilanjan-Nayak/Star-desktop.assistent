"""System tools: package install and allow-listed commands. Always high risk, always need approval."""
from __future__ import annotations

import re
import sys

from ..models import Check, ToolResult, Verdict
from .base import Param, Tool

_PKG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*(\[[A-Za-z0-9_,\-]+\])?([=<>!~]=?[A-Za-z0-9_.*\-]+)?$")


def _base_name(spec: str) -> str:
    return re.split(r"[\[=<>!~]", spec, maxsplit=1)[0]


class InstallPackage(Tool):
    outputs = ("exit_code",)
    name = "install_package"
    description = "Install a Python package with pip (shown to the user for approval first)."
    risk = "high"
    params = {"package": Param("str", desc="pip package name, optional version pin"),
              "manager": Param("str", False, "only 'pip' is supported", "pip")}

    def validate(self, args):
        errs = super().validate(args)
        if not errs and args.get("manager", "pip") != "pip":
            errs.append("only the 'pip' manager is supported")
        if not errs and not _PKG.match(args["package"]):
            errs.append(f"invalid package spec: {args['package']!r}")
        return errs

    def run(self, args, ctx):
        argv = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", args["package"]]
        ctx.log("$ " + " ".join(argv))
        code, out = ctx.runner.run(argv, timeout=900, on_line=ctx.log)
        if code != 0:
            kind = "timeout" if code == 124 else "install_failed"
            return ToolResult(False, {"exit_code": code, "tail": out[-500:]}, f"pip exited with {code}", kind)
        return ToolResult(True, {"exit_code": code})

    def verify(self, args, result, ctx):
        name = _base_name(args["package"])
        code, out = ctx.runner.run([sys.executable, "-m", "pip", "show", name], timeout=60)
        return Verdict.of([Check("pip exit code was 0", result.output.get("exit_code") == 0),
                           Check(f"'{name}' is now installed (pip show)", code == 0, out[-120:] if code else "")])


class RunCommand(Tool):
    name = "run_command"
    description = "Run an allow-listed program with arguments (no shell). Needs approval."
    risk = "high"
    params = {"argv": Param("list", desc="program followed by arguments")}

    def validate(self, args):
        errs = super().validate(args)
        if not errs and (not args["argv"] or not all(isinstance(a, str) for a in args["argv"])):
            errs.append("argv must be a non-empty list of strings")
        return errs

    def run(self, args, ctx):
        prog = args["argv"][0].lower().removesuffix(".exe")
        if prog not in ctx.config.command_allowlist:
            return ToolResult(False, {}, f"'{prog}' is not in the command allow-list", "denied")
        code, out = ctx.runner.run(args["argv"], timeout=300, on_line=ctx.log)
        return ToolResult(code == 0, {"exit_code": code, "tail": out[-800:]},
                          None if code == 0 else f"exit code {code}", None if code == 0 else "command_failed")

    def verify(self, args, result, ctx):
        return Verdict.of([Check("exit code is 0", result.output.get("exit_code") == 0)])
