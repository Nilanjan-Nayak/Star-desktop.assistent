"""GhostTabBar: pill tabs on springs. Tabs grow in, neighbours glide aside, closed tabs shrink away."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QFontMetrics, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..motion import Spring, clamp01
from ..states import StateModel
from ..theme import THEME, rgba
from ..widgets.icons import draw_icon
from .manager import TabManager
from .models import KIND_COLOR, TabSpec


class _Item:
    __slots__ = ("spec", "x", "w", "a", "closing")

    def __init__(self, spec: TabSpec):
        self.spec = spec
        self.x = Spring(0.0, 260)
        self.w = Spring(0.0, 260)
        self.a = Spring.bouncy(0.0, 280)
        self.a.target = 1.0
        self.closing = False


class GhostTabBar(QWidget):
    H, GAP, PAD = 42, 6, 4
    MIN_W, MAX_W, COMPACT_BELOW = 44.0, 210.0, 110.0

    def __init__(self, model: StateModel, manager: TabManager, parent: QWidget | None = None):
        super().__init__(parent)
        self.model, self.manager = model, manager
        self.setFixedHeight(self.H)
        self.setMouseTracking(True)
        self._items: list[_Item] = []
        self._tw = self.MAX_W
        self._hover, self._hover_close = -1, False
        self._ind_x, self._ind_w = Spring(0.0, 320), Spring(0.0, 320)
        manager.opened.connect(self._on_opened)
        manager.closed.connect(self._on_closed)
        manager.activated.connect(self._on_changed)
        manager.retitled.connect(self._on_changed)
        model.ticked.connect(self._tick)

    # model events -------------------------------------------------------------------
    def _live(self) -> list[_Item]:
        return [i for i in self._items if not i.closing]

    def _on_opened(self, spec: TabSpec) -> None:
        it = _Item(spec)
        self._items.append(it)
        self._retarget()
        it.x.snap(it.x.target)  # appears in place, then grows

    def _on_closed(self, tab_id: str) -> None:
        for it in self._items:
            if it.spec.id == tab_id:
                it.closing = True
                it.w.target = 0.0
                it.a.target = 0.0
        self._retarget()

    def _on_changed(self, *_a) -> None:
        self.update()

    def _retarget(self) -> None:
        live = self._live()
        n = len(live)
        if n == 0:
            return
        avail = self.width() - 2 * self.PAD - self.GAP * (n - 1)
        self._tw = max(self.MIN_W, min(self.MAX_W, avail / n))
        for i, it in enumerate(live):
            it.x.target = self.PAD + i * (self._tw + self.GAP)
            it.w.target = self._tw

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._retarget()

    # per frame -----------------------------------------------------------------------
    def _tick(self, dt: float) -> None:
        if not self.isVisible():
            return
        for it in self._items:
            it.x.update(dt)
            it.w.update(dt)
            it.a.update(dt)
        self._items = [i for i in self._items if not (i.closing and i.a.x < 0.03 and i.w.x < 1.5)]
        active = next((i for i in self._live() if i.spec.id == self.manager.active_id), None)
        if active:
            self._ind_x.target, self._ind_w.target = active.x.target, active.w.target
            if self._ind_w.x < 1:
                self._ind_x.snap(), self._ind_w.snap()
            self._ind_x.update(dt)
            self._ind_w.update(dt)
        self.update()

    # painting ------------------------------------------------------------------------
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = self.model.time
        fm = QFontMetrics(QFont(THEME.font, 10))
        compact = self._tw < self.COMPACT_BELOW
        live = self._live()
        for it in self._items:
            if it.w.x < 1:
                continue
            r = QRectF(it.x.x, 4, it.w.x, self.H - 8)
            a = clamp01(it.a.x)
            scale = 0.88 + 0.12 * min(1.2, it.a.x)
            p.save()
            p.setOpacity(a)
            p.translate(r.center())
            p.scale(scale, scale)
            p.translate(-r.center())
            spec = it.spec
            idx = live.index(it) if it in live else -1
            active = spec.id == self.manager.active_id and not it.closing
            hover = idx == self._hover
            kc = KIND_COLOR[spec.kind]

            p.setPen(Qt.NoPen)
            p.setBrush(rgba("#ffffff", 22 if active else 10 if hover else 0))
            p.drawRoundedRect(r, 11, 11)
            if active:
                p.setBrush(rgba(kc, 24))
                p.drawRoundedRect(r, 11, 11)
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(rgba(kc, 80), 1))
                p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 11, 11)

            icon_r = QRectF(r.center().x() - 8 if compact else r.left() + 12, r.center().y() - 8, 16, 16)
            if self.manager.is_busy(spec.id):
                ring = 0.5 + 0.5 * math.sin(t * 5)
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(rgba(kc, 60 + 150 * ring), 1.4))
                p.drawEllipse(icon_r.center(), 11 + ring * 1.5, 11 + ring * 1.5)
            draw_icon(p, spec.kind.value, icon_r, rgba(kc, 255), 1.5)

            if not compact and r.width() > 70:
                show_close = (active or hover) and r.width() > 100
                right = r.right() - (32 if show_close else 12)
                text = fm.elidedText(spec.title, Qt.ElideRight, max(0, int(right - (r.left() + 36))))
                p.setFont(QFont(THEME.font, 10))
                p.setPen(rgba(THEME.text if active else THEME.dim, 255))
                p.drawText(QPointF(r.left() + 36, r.center().y() + 4), text)
                if show_close:
                    cr = self._close_rect(r)
                    if hover and self._hover_close:
                        p.setPen(Qt.NoPen)
                        p.setBrush(rgba("#ffffff", 30))
                        p.drawEllipse(cr)
                    draw_icon(p, "close", cr.adjusted(5, 5, -5, -5), rgba(THEME.dim, 255), 1.4)
            p.restore()

        active_spec = next((i.spec for i in live if i.spec.id == self.manager.active_id), None)
        if active_spec and self._ind_w.x > 2:
            kc = KIND_COLOR[active_spec.kind]
            x, w = self._ind_x.x, self._ind_w.x
            g = QLinearGradient(x, 0, x + w, 0)
            g.setColorAt(0.0, rgba(kc, 0))
            g.setColorAt(0.5, rgba(kc, 255))
            g.setColorAt(1.0, rgba(kc, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawRoundedRect(QRectF(x, self.H - 3, w, 2), 1, 1)

    @staticmethod
    def _close_rect(r: QRectF) -> QRectF:
        return QRectF(r.right() - 26, r.center().y() - 9, 18, 18)

    # mouse ---------------------------------------------------------------------------
    def _hit(self, pos: QPointF) -> tuple[int, bool]:
        for i, it in enumerate(self._live()):
            r = QRectF(it.x.x, 4, it.w.x, self.H - 8)
            if r.contains(pos):
                return i, self._tw >= self.COMPACT_BELOW and r.width() > 100 and self._close_rect(r).contains(pos)
        return -1, False

    def mouseMoveEvent(self, e) -> None:
        self._hover, self._hover_close = self._hit(e.position())
        live = self._live()
        self.setToolTip(live[self._hover].spec.title if 0 <= self._hover < len(live) else "")
        self.setCursor(Qt.PointingHandCursor if self._hover >= 0 else Qt.ArrowCursor)

    def leaveEvent(self, e) -> None:
        self._hover, self._hover_close = -1, False
        super().leaveEvent(e)

    def mousePressEvent(self, e) -> None:
        idx, on_close = self._hit(e.position())
        live = self._live()
        if idx < 0:
            return
        if e.button() == Qt.MiddleButton or (e.button() == Qt.LeftButton and on_close):
            self.manager.close_tab(live[idx].spec.id)
        elif e.button() == Qt.LeftButton:
            self.manager.activate(live[idx].spec.id)
