"""System task tab: glassy card with task info, step checklist, progress and a log."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ..fx import ScrambleLabel, stagger
from ..states import StateModel
from ..theme import SCROLLBAR_QSS, THEME
from ..widgets import GhostButton, GlassFrame, GlowProgress, IconBadge, StatusChip, StepList
from ..widgets.flow_grid import FlowGrid
from .base import BaseTab
from .code_view import ConsoleView
from .models import KIND_COLOR, TabKind, TabSpec


def _label(text: str, css: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(css + "background:transparent;")
    return lbl


class SystemTab(BaseTab):
    def __init__(self, model: StateModel, spec: TabSpec, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = model
        pkg = spec.payload.get("package", "package")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}" + SCROLLBAR_QSS)
        scroll.viewport().setStyleSheet("background:transparent;")
        outer.addWidget(scroll)

        self.card = GlassFrame(model, radius=14, body_alpha=70)
        scroll.setWidget(self.card)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(12)

        # header
        self._badge = IconBadge(model, "system", KIND_COLOR[TabKind.SYSTEM])
        self._title = _label(spec.payload.get("heading", f"Install {pkg}"),
                             f"color:{THEME.text}; font:600 14pt '{THEME.font}';")
        self._sub = _label(spec.payload.get("description", "STAR will run the steps below on this machine."),
                           f"color:{THEME.dim}; font:10pt '{THEME.font}';")
        self._title.setWordWrap(True)
        self._sub.setWordWrap(True)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(self._title)
        titles.addWidget(self._sub)
        self.chip = StatusChip(model)
        self.chip.set_status("warning", "Preparing")
        head = QHBoxLayout()
        head.setSpacing(14)
        head.addWidget(self._badge, 0, Qt.AlignTop)
        head.addLayout(titles, 1)
        head.addWidget(self.chip, 0, Qt.AlignTop)
        lay.addLayout(head)

        # info grid: items glide between 1 and 2 columns as the width changes
        self.info_grid = FlowGrid(model)
        lay.addWidget(self.info_grid)
        self._set_info(spec.payload.get("info", {"Package": pkg}))

        # steps + progress
        self._steps_label = _label("Steps", f"color:{THEME.dim}; font:600 9pt '{THEME.font}';")
        lay.addWidget(self._steps_label)
        self.steps = StepList(model)
        self.steps.set_steps(spec.payload.get("steps", []))
        lay.addWidget(self.steps)
        self.progress = GlowProgress(model, height=8)
        self.pct = _label("0%", f"color:{THEME.text}; font:10pt '{THEME.mono}';")
        prow = QHBoxLayout()
        prow.addWidget(self.progress, 1)
        prow.addWidget(self.pct)
        lay.addLayout(prow)

        # log
        self.log = ConsoleView()
        self.log.setMinimumHeight(90)
        lay.addWidget(self.log, 1)

        # actions
        self.btn_approve = GhostButton(model, "Approve and run", "check", "primary")
        self.btn_cancel = GhostButton(model, "Cancel", "close", "danger")
        self.btn_close = GhostButton(model, "Close", "close")
        for b in (self.btn_approve, self.btn_cancel, self.btn_close):
            b.hide()
        actions = QHBoxLayout()
        actions.addStretch(1)
        for b in (self.btn_cancel, self.btn_approve, self.btn_close):
            actions.addWidget(b)
        lay.addLayout(actions)

        self.btn_approve.clicked.connect(self._approve)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_close.clicked.connect(self.request_close.emit)

        # creation: sections rise in one after another (the info grid animates its own items)
        stagger([self._badge, self._title, self._sub, self.chip, self._steps_label,
                 self.progress, self.pct, self.log], start=0.05, step=0.08)

    # info -----------------------------------------------------------------------------
    def _set_info(self, info: dict) -> None:
        widgets = []
        for i, (k, v) in enumerate(info.items()):
            box = QWidget()
            box.setStyleSheet("background:transparent;")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(1)
            bl.addWidget(_label(str(k), f"color:{THEME.dim}; font:9pt '{THEME.font}';"))
            value = ScrambleLabel()
            value.setStyleSheet(f"color:{THEME.text}; font:10.5pt '{THEME.mono}'; background:transparent;")
            value.reveal(str(v), duration=0.65, delay=0.3 + 0.09 * i)  # decodes from random glyphs
            bl.addWidget(value)
            widgets.append(box)
        self.info_grid.set_items(widgets)

    # actions --------------------------------------------------------------------------
    def _approve(self) -> None:
        self.btn_approve.hide()
        self.chip.set_status("running", "Running")
        self.busy_changed.emit(True)
        self.user_action.emit("approve", None)

    def _cancel(self) -> None:
        self.user_action.emit("cancel", None)
        self.request_close.emit()

    # core -> UI -----------------------------------------------------------------------
    def handle_event(self, event: str, data) -> None:
        if event == "info":
            self._set_info(data or {})
        elif event == "steps":
            self.steps.set_steps(list(data or []))
        elif event == "step":
            self.steps.set_state(int(data["index"]), data.get("state", "active"), data.get("detail", ""))
        elif event == "progress":
            v = float(data)
            self.progress.set_value(v)
            self.pct.setText(f"{round(v * 100)}%")
        elif event == "log":
            self.log.append_output(str(data))
        elif event == "awaiting_approval":
            self.chip.set_status("warning", "Needs approval")
            self.btn_approve.show()
            self.btn_cancel.show()
            self.busy_changed.emit(False)
        elif event == "status":
            self.chip.set_status(data.get("kind", "running"), data.get("text", ""))
            if data.get("kind") == "running":
                self.btn_cancel.show()
                self.busy_changed.emit(True)
        elif event == "finished":
            ok = bool((data or {}).get("ok", True))
            self.chip.set_status("success" if ok else "error", (data or {}).get("text", "Done" if ok else "Failed"))
            if ok:
                self.progress.set_value(1.0)
                self.pct.setText("100%")
            self.btn_approve.hide()
            self.btn_cancel.hide()
            self.btn_close.show()
            self.busy_changed.emit(False)
