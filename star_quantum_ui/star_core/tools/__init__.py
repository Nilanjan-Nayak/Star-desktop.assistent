from .base import CommandRunner, Param, Tool, ToolContext
from .files import CopyFiles, FindFiles, ListDir, MakeDir, ReadText, WriteText, sha256
from .registry import ToolRegistry
from .system import InstallPackage, RunCommand
from .web import OpenUrl, ServeWebsite, WebSearch


def default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    for t in (FindFiles(), ListDir(), MakeDir(), CopyFiles(), ReadText(), WriteText(),
              InstallPackage(), RunCommand(), OpenUrl(), ServeWebsite(), WebSearch()):
        reg.register(t)
    return reg


__all__ = ["CommandRunner", "Param", "Tool", "ToolContext", "ToolRegistry", "default_registry", "sha256", "WebSearch"]
