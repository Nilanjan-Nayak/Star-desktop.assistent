"""GhostPanel: near-invisible glass panel with grid, scan line and typewriter text."""
from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QPointF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget

from .states import StateModel
from .theme import THEME, rgba


class GhostPanel(QFrame):
    HEADER = 44

    def __init__(self, model: StateModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self.setFixedWidth(340)
        self.setMinimumHeight(260)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._body = QLabel("")
        self._body.setWordWrap(True)
        self._body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._body.setStyleSheet(
            f"color:{THEME.text}; background:transparent; font:10.5pt '{THEME.font}';")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, self.HEADER + 12, 24, 20)
        lay.addWidget(self._body)

        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)
        self._user, self._stage = 0.0, 1.0  # own fade x Stage fade
        self._fade_anim = QVariantAnimation(self)
        self._fade_anim.setDuration(420)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.valueChanged.connect(self._set_user)

        self._full, self._n = "", 0
        self._typer = QTimer(self)
        self._typer.setInterval(16)
        self._typer.timeout.connect(self._type_step)
        model.ticked.connect(self._on_tick)

    # public API -------------------------------------------------------------
    def show_text(self, text: str) -> None:
        self._full, self._n = text, 0
        self._typer.start()
        self._fade(1.0)

    def hide_panel(self) -> None:
        self._fade(0.0)

    def is_shown(self) -> bool:
        return self._fade_anim.endValue() == 1.0 if self._fade_anim.state() == QVariantAnimation.Running \
            else self._user > 0.5

    def set_stage_opacity(self, v: float) -> None:
        self._stage = v
        self._apply_opacity()

    def _set_user(self, v) -> None:
        self._user = float(v)
        self._apply_opacity()

    def _apply_opacity(self) -> None:
        self._fx.setOpacity(self._user * self._stage)

    # internals --------------------------------------------------------------
    def _fade(self, to: float) -> None:
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._user)
        self._fade_anim.setEndValue(to)
        self._fade_anim.start()

    def _type_step(self) -> None:
        self._n = min(self._n + 2, len(self._full))
        done = self._n >= len(self._full)
        self._body.setText(self._full[: self._n] + ("" if done else "\u258d"))
        if done:
            self._typer.stop()

    def _on_tick(self, _dt: float) -> None:
        if self._fx.opacity() > 0.01:
            self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        col, t = self.model.style.color, self.model.time

        wash = QLinearGradient(0, 0, w, 0)
        wash.setColorAt(0.0, rgba(col, 26))
        wash.setColorAt(1.0, rgba(col, 0))
        p.fillRect(self.rect(), wash)

        grid = rgba(THEME.grid, 110)
        p.setPen(QPen(grid, 1))
        for x in range(0, w, 24):
            p.drawLine(x, 0, x, h)
        for y in range(0, h, 24):
            p.drawLine(0, y, w, y)

        # scan line
        sy = (t * 55) % (h + 40) - 20
        band = QLinearGradient(0, sy - 18, 0, sy + 18)
        band.setColorAt(0.0, rgba(col, 0))
        band.setColorAt(0.5, rgba(col, 40))
        band.setColorAt(1.0, rgba(col, 0))
        p.fillRect(0, int(sy - 18), w, 36, band)

        # header: pulsing dot, live state label, hairline
        r = 3.5 + 1.2 * math.sin(t * 4)
        p.setPen(Qt.NoPen)
        p.setBrush(rgba(col, 55))
        p.drawEllipse(QPointF(28, 24), r * 2.4, r * 2.4)
        p.setBrush(col)
        p.drawEllipse(QPointF(28, 24), r, r)
        p.setPen(col)
        p.setFont(QFont(THEME.font, 10, QFont.DemiBold))
        p.drawText(QPointF(46, 28), self.model.style.label)
        line = QLinearGradient(0, 0, w, 0)
        line.setColorAt(0.0, rgba(col, 130))
        line.setColorAt(1.0, rgba(col, 0))
        p.setPen(QPen(line, 1))
        p.drawLine(QPointF(0, self.HEADER), QPointF(w, self.HEADER))

        # corner brackets
        p.setPen(QPen(col, 1.4))
        L = 16
        p.drawLine(0, 0, L, 0)
        p.drawLine(0, 0, 0, L)
        p.drawLine(w - 1, h - 1, w - 1 - L, h - 1)
        p.drawLine(w - 1, h - 1, w - 1, h - 1 - L)
