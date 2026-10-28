"""Tab data types."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..theme import THEME


class TabKind(str, Enum):
    WEB = "web"
    AGENT = "agent"
    SYSTEM = "system"


KIND_COLOR = {TabKind.WEB: THEME.cyan, TabKind.AGENT: THEME.violet, TabKind.SYSTEM: THEME.mint}


@dataclass
class TabSpec:
    id: str
    kind: TabKind
    title: str
    payload: dict = field(default_factory=dict)
