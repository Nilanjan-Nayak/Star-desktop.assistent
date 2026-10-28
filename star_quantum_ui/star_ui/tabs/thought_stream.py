"""Agent 'thought process' timeline: a rail of dots with fading-in entries."""
from __future__ import annotations

import html
import math

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (QGraphicsOpacityEffect, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from ..fx import fade_in
from ..motion import ease_out_back, ease_out_cubic
from ..states import StateModel
from ..theme import SCROLLBAR_QSS, THEME, rgba

KINDS = {
    "think":   ("Thinking",    THEME.violet),
    "tool":    ("Tool call",   THEME.cyan),
    "observe": ("Observation", THEME.amber),
    "result":  ("Result",      THEME.mint),
    "error":   ("Error",       THEME.red),
}


class ThoughtItem(QWidget):
    RAIL = 30
    CPS = 130  # typewriter speed, characters per second

    def __init__(self, model: StateModel, kind: str, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        label, self.color = KINDS.get(kind, KINDS["think"])
        self.active = False
        self._born = model.time
        self._full = text
        self._shown = -1
        self._done = False
        self._margin = self.RAIL + 6 + 20
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(self._margin, 4, 8, 16)
        self._lay.setSpacing(3)
        head = QLabel(label)
        head.setStyleSheet(f"color:{self.color}; font:600 9pt '{THEME.font}'; background:transparent;")
        self.body = QLabel()
        self.body.setTextFormat(Qt.RichText)
        self.body.setWordWrap(True)
        self.body.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # wrap to the column
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        family = THEME.mono if kind == "tool" else THEME.font
        self.body.setStyleSheet(f"color:{THEME.text}; font:10pt '{family}'; background:transparent;")
        self._lay.addWidget(head)
        self._lay.addWidget(self.body)
        self._render(0)
        model.ticked.connect(self._on_tick)

    def _render(self, n: int) -> None:
        # Unrevealed characters are laid out but transparent, so the item never changes height mid-type.
        vis = html.escape(self._full[:n]).replace("\n", "<br>")
        rest = html.escape(self._full[n:]).replace("\n", "<br>")
        self.body.setText(f'{vis}<span style="color:transparent">{rest}</span>')
        self._shown = n

    def _on_tick(self, _dt: float) -> None:
        age = self.model.time - self._born
        if not self._done:
            m = self.RAIL + 6 + int((1 - ease_out_cubic(age / 0.45)) * 20)
            if m != self._margin:
                self._margin = m
                self._lay.setContentsMargins(m, 4, 8, 16)
            n = min(len(self._full), int(max(0.0, age - 0.12) * self.CPS))
            if n != self._shown:
                self._render(n)
            if age > 0.6 and n >= len(self._full):
                self._done = True
                self.body.setText(html.escape(self._full).replace("\n", "<br>"))
        if not self._done or self.active:
            self.update()

    def set_active(self, on: bool) -> None:
        self.active = on
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        age = self.model.time - self._born
        c = QPointF(14, 14)
        rp = ease_out_cubic(age / 0.6)
        rail = QLinearGradient(0, 24, 0, self.height())
        rail.setColorAt(0.0, rgba(self.color, 110))
        rail.setColorAt(1.0, rgba(THEME.dim, 30))
        p.setPen(QPen(rail, 1.2))
        p.drawLine(QPointF(14, 24), QPointF(14, 24 + (self.height() - 24) * rp))
        p.setPen(Qt.NoPen)
        dot = max(0.0, ease_out_back(age / 0.4))
        if age < 0.6:  # arrival flash
            f = age / 0.6
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(rgba(self.color, 160 * (1 - f)), 1.4))
            p.drawEllipse(c, 4 + 14 * f, 4 + 14 * f)
            p.setPen(Qt.NoPen)
        if self.active:
            pulse = 0.5 + 0.5 * math.sin(self.model.time * 5)
            p.setBrush(rgba(self.color, 40 + 40 * pulse))
            p.drawEllipse(c, 9 + pulse * 2, 9 + pulse * 2)
        p.setBrush(rgba(self.color, 255))
        p.drawEllipse(c, 4 * dot, 4 * dot)


class ThoughtStream(QScrollArea):
    def __init__(self, model: StateModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea{background:transparent;border:none;}" + SCROLLBAR_QSS)
        self.viewport().setStyleSheet("background:transparent;")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self._lay = QVBoxLayout(inner)
        self._lay.setContentsMargins(0, 6, 0, 6)
        self._lay.setSpacing(0)
        self._lay.addStretch(1)
        self.setWidget(inner)
        self._inner = inner
        self._items: list[ThoughtItem] = []
        self._scroll_anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._scroll_anim.setDuration(260)
        self._scroll_anim.setEasingCurve(QEasingCurve.OutCubic)

    def add(self, kind: str, text: str) -> None:
        if self._items:
            self._items[-1].set_active(False)
        item = ThoughtItem(self.model, kind, text)
        item.set_active(kind == "think")
        self._lay.insertWidget(self._lay.count() - 1, item)
        self._items.append(item)
        fade_in(item, 0.0, 0.3)
        QTimer.singleShot(40, self._scroll_end)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._inner.setMaximumWidth(max(60, self.viewport().width()))

    def settle(self) -> None:
        """Stop the live pulse (call when the task finishes)."""
        if self._items:
            self._items[-1].set_active(False)

    def _scroll_end(self) -> None:
        bar = self.verticalScrollBar()
        self._scroll_anim.stop()
        self._scroll_anim.setStartValue(bar.value())
        self._scroll_anim.setEndValue(bar.maximum())
        self._scroll_anim.start()
