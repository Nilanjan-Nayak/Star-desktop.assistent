"""GhostButton (text + optional icon) and IconButton (icon only) with eased hover glow."""
from __future__ import annotations

from PySide6.QtCore import Qt, QEasingCurve, QPointF, QRectF, QSize, QVariantAnimation
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QWidget

from ..states import StateModel
from ..theme import THEME, rgba
from .icons import draw_icon


class _HoverButton(QAbstractButton):
    def __init__(self, model: StateModel, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        self._hover = 0.0
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._set_hover)

    def _set_hover(self, v) -> None:
        self._hover = float(v)
        self.update()

    def _go(self, to: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(to)
        self._anim.start()

    def enterEvent(self, e) -> None:
        self._go(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._go(0.0)
        super().leaveEvent(e)


class GhostButton(_HoverButton):
    def __init__(self, model: StateModel, text: str = "", icon: str = "", variant: str = "ghost",
                 parent: QWidget | None = None):
        super().__init__(model, parent)
        self.setText(text)
        self._icon, self._variant = icon, variant
        self.setFixedHeight(34)

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self.update()

    def set_icon(self, icon: str) -> None:
        self._icon = icon
        self.update()

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(QFont(THEME.font, 10))
        return QSize(fm.horizontalAdvance(self.text()) + 34 + (22 if self._icon else 0), 34)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        base = {"primary": self.model.style.color, "danger": THEME.red}.get(self._variant, THEME.dim)
        h = self._hover
        dim = 1.0 if self.isEnabled() else 0.4
        fill_a = ({"primary": 30, "danger": 20}.get(self._variant, 0) + 38 * h + (30 if self.isDown() else 0)) * dim
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setBrush(rgba(base, fill_a))
        p.setPen(QPen(rgba(base, (110 + 120 * h) * dim), 1))
        p.drawRoundedRect(r, 10, 10)
        fg = rgba(THEME.text if self._variant == "ghost" and h > 0.5 else base, 255 * dim)
        x = 16
        if self._icon:
            draw_icon(p, self._icon, QRectF(x, self.height() / 2 - 7, 14, 14), fg, 1.6)
            x += 22
        p.setFont(QFont(THEME.font, 10))
        p.setPen(fg)
        p.drawText(QPointF(x, self.height() / 2 + 4), self.text())


class IconButton(_HoverButton):
    def __init__(self, model: StateModel, icon: str, tip: str = "", size: int = 32,
                 parent: QWidget | None = None):
        super().__init__(model, parent)
        self._icon = icon
        self.setFixedSize(size, size)
        self.setToolTip(tip)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self._hover
        dim = 1.0 if self.isEnabled() else 0.35
        p.setPen(Qt.NoPen)
        p.setBrush(rgba("#ffffff", (10 + 26 * h + (20 if self.isDown() else 0)) * dim))
        p.drawEllipse(QRectF(2, 2, self.width() - 4, self.height() - 4))
        col = rgba(THEME.text if h > 0.4 else THEME.dim, 255 * dim)
        m = self.width() * 0.3
        draw_icon(p, self._icon, QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m), col, 1.6)
