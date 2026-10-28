"""CodeView (line-number gutter + Python highlighting) and ConsoleView (output log)."""
from __future__ import annotations

from PySide6.QtCore import QRect, QRegularExpression, Qt, QSize
from PySide6.QtGui import QColor, QFont, QPainter, QSyntaxHighlighter, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from ..theme import SCROLLBAR_QSS, THEME, rgba


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.DemiBold)
    f.setFontItalic(italic)
    return f


class PythonHighlighter(QSyntaxHighlighter):
    KEYWORDS = (r"\b(def|class|return|if|elif|else|for|while|import|from|as|with|try|except|finally|"
                r"raise|in|is|not|and|or|lambda|yield|pass|break|continue|None|True|False|self|"
                r"async|await|assert)\b")

    def __init__(self, doc):
        super().__init__(doc)
        spec = [
            (self.KEYWORDS, _fmt(THEME.violet, bold=True)),
            (r"\b[0-9]+(\.[0-9]+)?\b", _fmt(THEME.amber)),
            (r"(?<=def )\w+|(?<=class )\w+", _fmt(THEME.cyan)),
            (r"@\w+", _fmt(THEME.amber)),
            (r"\"[^\"\n]*\"|'[^'\n]*'", _fmt(THEME.mint)),
            (r"#[^\n]*", _fmt(THEME.dim, italic=True)),
        ]
        self._rules = [(QRegularExpression(rx), f) for rx, f in spec]

    def highlightBlock(self, text: str) -> None:
        for rx, f in self._rules:
            it = rx.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), f)


class _Gutter(QWidget):
    def __init__(self, editor: "CodeView"):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.gutter_width(), 0)

    def paintEvent(self, e) -> None:
        self._editor.paint_gutter(e)


_EDITOR_QSS = (
    "QPlainTextEdit{background:rgba(2,6,12,0.45); border:1px solid rgba(79,240,255,0.14);"
    f"border-radius:10px; color:{THEME.text}; padding:6px 4px;"
    "selection-background-color:rgba(79,240,255,0.30);}" + SCROLLBAR_QSS
)


def _mono(size: float) -> QFont:
    f = QFont(THEME.mono, int(size))
    f.setStyleHint(QFont.Monospace)
    return f


class CodeView(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(_mono(10))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setStyleSheet(_EDITOR_QSS)
        self._gutter = _Gutter(self)
        self._highlighter = PythonHighlighter(self.document())
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._on_update_request)
        self._update_margin()

    def gutter_width(self) -> int:
        digits = max(2, len(str(self.blockCount())))
        return 18 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margin(self, *_a) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _on_update_request(self, rect: QRect, dy: int) -> None:
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        cr = self.contentsRect()
        self._gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event) -> None:
        p = QPainter(self._gutter)
        p.setFont(self.font())
        p.setPen(rgba(THEME.dim, 140))
        block = self.firstVisibleBlock()
        n = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        fh = self.fontMetrics().height()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                p.drawText(0, top, self._gutter.width() - 10, fh, Qt.AlignRight, str(n + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            n += 1

    def set_code(self, text: str) -> None:
        self.setPlainText(text)
        self.moveCursor(QTextCursor.End)

    def append_code(self, chunk: str) -> None:
        self.moveCursor(QTextCursor.End)
        self.insertPlainText(chunk)
        self.moveCursor(QTextCursor.End)
        self.ensureCursorVisible()


class ConsoleView(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(_mono(9))
        self.setMaximumBlockCount(500)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.setStyleSheet(_EDITOR_QSS)

    def append_output(self, text: str) -> None:
        self.appendPlainText(text)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
