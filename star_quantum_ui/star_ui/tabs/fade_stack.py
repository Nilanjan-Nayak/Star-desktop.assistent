"""QStackedWidget that cross-fades and slides between pages using a snapshot overlay.

The effect is applied to a pixmap of the old page, never to the pages themselves, so
live content (code views, embedded web views) is not forced through a graphics effect.
"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, Qt
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QStackedWidget, QWidget


class FadeStack(QStackedWidget):
    SLIDE = 26

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._ghost = QLabel(self)
        self._ghost.hide()
        self._ghost.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._fx = QGraphicsOpacityEffect(self._ghost)
        self._ghost.setGraphicsEffect(self._fx)
        self._fade = QPropertyAnimation(self._fx, b"opacity", self)
        self._fade.setDuration(300)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._slide = QPropertyAnimation(self._ghost, b"pos", self)
        self._slide.setDuration(300)
        self._slide.setEasingCurve(QEasingCurve.OutCubic)
        self._group = QParallelAnimationGroup(self)
        self._group.addAnimation(self._fade)
        self._group.addAnimation(self._slide)
        self._group.finished.connect(self._ghost.hide)

    def fade_to(self, widget: QWidget) -> None:
        old = self.currentWidget()
        if old is not None and old is not widget and self.isVisible():
            direction = -1 if self.indexOf(widget) > self.indexOf(old) else 1
            self._group.stop()
            self._ghost.setPixmap(old.grab())
            self._ghost.setGeometry(self.rect())
            self._fx.setOpacity(1.0)
            self._ghost.show()
            self.setCurrentWidget(widget)
            self._ghost.raise_()
            self._slide.setStartValue(QPoint(0, 0))
            self._slide.setEndValue(QPoint(direction * self.SLIDE, 0))
            self._group.start()
        else:
            self.setCurrentWidget(widget)
