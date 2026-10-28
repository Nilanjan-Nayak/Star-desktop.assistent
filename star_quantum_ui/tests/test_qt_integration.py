"""The real STAR window + the real backend, driven through the same signals a user would trigger."""
import os
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["STAR_NO_WEBVIEW"] = "1"
try:
    from PySide6.QtWidgets import QApplication
    from star_ui import MainWindow, StateModel, UIBridge
    from star_ui.tabs.system_tab import SystemTab
except ImportError as e:  # pragma: no cover
    raise unittest.SkipTest(f"PySide6 not available: {e}")

from star_core.app import BackendRunner, build_orchestrator
from star_core.config import Config
from star_core.qt_bridge import BridgePort


class QtStackTests(unittest.TestCase):
    def setUp(self):
        self.app = QApplication.instance() or QApplication([])
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.src, self.dst = self.tmp / "src", self.tmp / "dst"
        self.src.mkdir()
        for n in ("a.json", "b.json", "c.json", "n.txt"):
            (self.src / n).write_text("x" + n)
        self.model, self.bridge = StateModel(), UIBridge()
        self.win = MainWindow(self.model, self.bridge)
        self.win.show()
        cfg = Config(home=self.tmp / "home", allowed_roots=[str(self.tmp)])
        self.port = BridgePort(self.bridge)
        self.orch = build_orchestrator(cfg, self.port, mock_llm=True)
        self.runner = BackendRunner(self.port, self.orch)
        self.runner.start()
        self.messages = []
        self.bridge.message.connect(self.messages.append)
        self.clicked = set()

    def tearDown(self):
        self.runner.stop()
        self.win.close()
        self.pump(0.2)

    def pump(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            self.app.processEvents()
            time.sleep(0.02)

    def system_tabs(self):
        return [(i, t) for i, t in self.win.terminal._tabs.items() if isinstance(t, SystemTab)]

    def wait_until(self, cond, timeout=15.0, auto=None):
        """auto: 'approve' | 'cancel' | None, applied to any system tab that is waiting for a decision."""
        end = time.time() + timeout
        while time.time() < end:
            self.app.processEvents()
            if auto:
                for tid, tab in self.system_tabs():
                    btn = tab.btn_approve if auto == "approve" else tab.btn_cancel
                    if not tab.btn_approve.isHidden() and tid not in self.clicked:
                        self.clicked.add(tid)
                        btn.click()
            if cond():
                return True
            time.sleep(0.02)
        return False

    def request(self):
        return f"find all json files in '{self.src}' and copy them to '{self.dst}'"

    def test_task_runs_through_real_buttons_and_the_ui_shows_the_work(self):
        self.bridge.user_text.emit(self.request())
        ok = self.wait_until(lambda: any("Done" in m for m in self.messages), auto="approve")
        self.assertTrue(ok, self.messages)
        self.assertEqual(sorted(p.name for p in self.dst.iterdir()), ["a.json", "b.json", "c.json"])
        agent = next(t for t in self.win.terminal._tabs.values() if t.__class__.__name__ == "AgentTab")
        self.assertGreaterEqual(len(agent.thoughts._items), 4)          # understanding, plan, tool calls, result
        approval = self.system_tabs()[0][1]
        self.assertTrue(all(s[1] == "done" for s in approval.steps._steps))
        self.assertEqual(approval.pct.text(), "100%")

    def test_cancel_button_means_nothing_is_touched(self):
        self.bridge.user_text.emit(self.request())
        ok = self.wait_until(lambda: any("nothing was changed" in m for m in self.messages), auto="cancel")
        self.assertTrue(ok, self.messages)
        self.assertFalse(self.dst.exists())

    def test_question_and_answer_travel_through_the_command_bar_signal(self):
        self.bridge.user_text.emit(f"find all json files in '{self.src}' and copy them")
        self.assertTrue(self.wait_until(lambda: any("Which folder" in m for m in self.messages)))
        self.assertEqual(self.model.name, "listening")
        self.bridge.user_text.emit(f"'{self.dst}'")                      # the answer
        self.assertTrue(self.wait_until(lambda: any("Done" in m for m in self.messages), auto="approve"), self.messages)
        self.assertEqual(len(list(self.dst.iterdir())), 3)

    def test_metrics_reach_the_telemetry_panel(self):
        self.bridge.user_text.emit(self.request())
        self.wait_until(lambda: any("Done" in m for m in self.messages), auto="approve")
        self.pump(0.3)
        self.assertGreater(self.win.telemetry._data["Memory nodes"][-1], 0)

    def test_state_returns_to_idle_after_speaking(self):
        self.bridge.user_text.emit("hello there")
        self.assertTrue(self.wait_until(lambda: self.model.name == "speaking", timeout=5))
        self.assertTrue(self.wait_until(lambda: self.model.name == "idle", timeout=8))


if __name__ == "__main__":
    unittest.main()
