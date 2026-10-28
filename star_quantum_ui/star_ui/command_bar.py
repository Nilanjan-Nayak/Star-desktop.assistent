"""Glass command input with a focus glow."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Signal
from PySide6.QtGui import QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QLineEdit, QWidget

from .states import StateModel
from .theme import THEME, rgba


class CommandBar(QLineEdit):
    submitted = Signal(str)

    def __init__(self, model: StateModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self.setFixedHeight(48)
        self.setPlaceholderText("Ask STAR anything, or type a command")
        self.setStyleSheet(
            f"QLineEdit{{background:transparent; border:none; padding:0 18px;"
            f"color:{THEME.text}; font:12pt '{THEME.font}';"
            f"selection-background-color:rgba(79,240,255,90);}}")
        self.returnPressed.connect(self._submit)
        model.ticked.connect(self._on_tick)

    def _on_tick(self, _dt: float) -> None:
        self.update()

    def _submit(self) -> None:
        text = self.text().strip()
        if text:
            self.submitted.emit(text)
            self.clear()

    def paintEvent(self, e) -> None:
        col = self.model.style.color
        w, h = self.width(), self.height()
        ip = self.model.intro.p(1.0, 0.9)
        p = QPainter(self)
        p.fillRect(self.rect(), rgba(col, (14 if self.hasFocus() else 7) * ip))
        p.end()

        super().paintEvent(e)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.hasFocus():
            glow = QLinearGradient(0, h - 22, 0, h)
            glow.setColorAt(0.0, rgba(col, 0))
            glow.setColorAt(1.0, rgba(col, 38))
            p.fillRect(0, h - 22, w, 22, glow)
        edge = rgba(col, 230 if self.hasFocus() else 90)
        p.setPen(QPen(edge, 1.5))
        half = w / 2 * ip
        p.drawLine(QPointF(w / 2 - half, h - 1), QPointF(w / 2 + half, h - 1))
        if ip > 0.95:
            p.drawLine(QPointF(0, h - 14), QPointF(0, h - 1))
            p.drawLine(QPointF(w - 1, h - 14), QPointF(w - 1, h - 1))
