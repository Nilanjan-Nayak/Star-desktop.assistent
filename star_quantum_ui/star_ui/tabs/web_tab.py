"""Web tab: toolbar + embedded browser (QtWebEngine) with a graceful fallback card."""
from __future__ import annotations

import os

from PySide6.QtCore import QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter
from PySide6.QtWidgets import QLineEdit, QHBoxLayout, QVBoxLayout, QWidget

from ..fx import stagger, type_into
from ..states import StateModel
from ..theme import THEME, rgba
from ..widgets import GhostButton, GlowProgress, IconButton, draw_icon
from .base import BaseTab
from .models import TabSpec

try:
    if os.environ.get("STAR_NO_WEBVIEW") == "1":
        raise ImportError("webview disabled by environment")
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEB = True
except Exception:  # missing PySide6-Addons, or disabled
    QWebEngineView = None
    HAS_WEB = False


def normalize_url(text: str) -> str:
    text = text.strip()
    if "://" in text:
        return text
    if " " in text or "." not in text:
        return "https://www.google.com/search?q=" + text.replace(" ", "+")
    return "https://" + text


class _Fallback(QWidget):
    """Shown when QtWebEngine is unavailable."""

    def __init__(self, model: StateModel, url: str):
        super().__init__()
        self.model, self.url = model, url
        self.btn = GhostButton(model, "Open in browser", "web", "primary", self)
        self.btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.url)))

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        col = self.model.style.color
        p.setPen(Qt.NoPen)
        p.setBrush(rgba("#02060c", 110))
        p.drawRoundedRect(QRectF(0, 0, w, h), 12, 12)
        draw_icon(p, "web", QRectF(w / 2 - 22, h / 2 - 84, 44, 44), rgba(col, 255), 1.6)
        p.setPen(rgba(THEME.text, 255))
        p.setFont(QFont(THEME.font, 12, QFont.DemiBold))
        p.drawText(QRectF(0, h / 2 - 28, w, 24), Qt.AlignHCenter, "Embedded web view unavailable")
        p.setPen(rgba(THEME.dim, 255))
        p.setFont(QFont(THEME.font, 10))
        p.drawText(QRectF(24, h / 2 - 2, w - 48, 40), Qt.AlignHCenter | Qt.TextWordWrap,
                   "Install PySide6-Addons to browse inside this tab.")
        self.btn.move(int((w - self.btn.sizeHint().width()) / 2), int(h / 2 + 46))
        self.btn.resize(self.btn.sizeHint())


class WebTab(BaseTab):
    def __init__(self, model: StateModel, spec: TabSpec, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        url = normalize_url(spec.payload.get("url", "https://www.youtube.com"))

        self.back = IconButton(model, "back", "Back")
        self.fwd = IconButton(model, "forward", "Forward")
        self.reload = IconButton(model, "reload", "Reload")
        self.url_edit = QLineEdit(url)
        self.url_edit.setFixedHeight(32)
        self.url_edit.setStyleSheet(
            f"QLineEdit{{background:rgba(255,255,255,0.06); border:1px solid rgba(79,240,255,0.16);"
            f"border-radius:16px; padding:0 14px; color:{THEME.text}; font:10pt '{THEME.font}';"
            f"selection-background-color:rgba(79,240,255,0.35);}}"
            f"QLineEdit:focus{{border-color:rgba(79,240,255,0.7); background:rgba(255,255,255,0.09);}}")
        self.progress = GlowProgress(model, height=3)

        bar = QHBoxLayout()
        bar.setSpacing(4)
        for b in (self.back, self.fwd, self.reload):
            bar.addWidget(b)
        bar.addWidget(self.url_edit, 1)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(2)
        lay.addLayout(bar)
        lay.addWidget(self.progress)

        if HAS_WEB:
            self.view = QWebEngineView()
            self.view.page().setBackgroundColor(QColor(THEME.void))
            self.back.clicked.connect(self.view.back)
            self.fwd.clicked.connect(self.view.forward)
            self.reload.clicked.connect(self.view.reload)
            self.view.loadStarted.connect(lambda: (self.busy_changed.emit(True), self.progress.set_indeterminate(True)))
            self.view.loadProgress.connect(lambda v: (self.progress.set_value(v / 100.0)))
            self.view.loadFinished.connect(self._finished)
            self.view.urlChanged.connect(lambda u: self.url_edit.setText(u.toString()))
            self.view.titleChanged.connect(lambda t: self.title_changed.emit(t[:40]) if t else None)
            self.url_edit.returnPressed.connect(lambda: self.view.setUrl(QUrl(normalize_url(self.url_edit.text()))))
            self.view.setUrl(QUrl(url))
        else:
            self.view = _Fallback(model, url)
            for b in (self.back, self.fwd, self.reload):
                b.setEnabled(False)
            self.url_edit.setReadOnly(True)
            self.busy_changed.emit(True)
            self.progress.set_indeterminate(True)
            QTimer.singleShot(1400, self._finished)
        lay.addWidget(self.view, 1)
        stagger([self.back, self.fwd, self.reload, self.url_edit, self.progress], start=0.05, step=0.06)
        type_into(self.url_edit, url, 0.7, 0.25)

    def _finished(self, *_a) -> None:
        self.progress.set_value(1.0)
        self.busy_changed.emit(False)
        QTimer.singleShot(500, lambda: self.progress.set_value(0.0))

    def handle_event(self, event: str, data) -> None:
        if event == "navigate" and data and "url" in data:
            u = normalize_url(data["url"])
            self.url_edit.setText(u)
            if HAS_WEB:
                self.view.setUrl(QUrl(u))
