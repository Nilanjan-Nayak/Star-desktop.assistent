"""Design tokens and small colour helpers shared by every widget."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor


@dataclass(frozen=True)
class Theme:
    void: str = "#03050a"
    deep: str = "#07111a"
    grid: str = "#143040"
    cyan: str = "#4ff0ff"
    violet: str = "#9b7bff"
    amber: str = "#ffb347"
    mint: str = "#5dffb0"
    red: str = "#ff6b81"
    text: str = "#cdeff5"
    dim: str = "#6f9aa6"
    font: str = "Segoe UI"
    mono: str = "Consolas"


THEME = Theme()


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def mix(c1: QColor, c2: QColor, t: float) -> QColor:
    return QColor(
        round(lerp(c1.red(), c2.red(), t)),
        round(lerp(c1.green(), c2.green(), t)),
        round(lerp(c1.blue(), c2.blue(), t)),
    )


def rgba(color, alpha: float) -> QColor:
    """Copy of `color` (QColor or hex string) with alpha 0..255."""
    c = QColor(color)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


SCROLLBAR_QSS = """
QScrollBar:vertical{background:transparent;width:8px;margin:2px;}
QScrollBar::handle:vertical{background:rgba(79,240,255,0.25);border-radius:3px;min-height:24px;}
QScrollBar::handle:vertical:hover{background:rgba(79,240,255,0.5);}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent;}
QScrollBar:horizontal{background:transparent;height:8px;margin:2px;}
QScrollBar::handle:horizontal{background:rgba(79,240,255,0.25);border-radius:3px;min-width:24px;}
QScrollBar::handle:horizontal:hover{background:rgba(79,240,255,0.5);}
QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0;}
QScrollBar::add-page:horizontal,QScrollBar::sub-page:horizontal{background:transparent;}
"""
