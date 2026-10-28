import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from star_core.memory.task_tracker import TaskTracker
from star_core.config import Config
from star_core.app import build_orchestrator
from star_core.ui_port import UIPort

class MockUI(UIPort):
    def __init__(self):
        super().__init__()
        self.said = []

    def request_approval(self, *args, **kwargs):
        return True

    def open_tab(self, *args, **kwargs):
        return "tab-1"

    def tab_event(self, *args, **kwargs):
        pass

    def say(self, text):
        self.said.append(text)

    def set_state(self, state):
        pass

    def metric(self, *args):
        pass

    def ask(self, *args, **kwargs):
        return "Desktop"


def test_tracker_system():
    print("="*60)
    print("1. TESTING TaskTracker UNIT FUNCTIONALITY")
    print("="*60)

    tracker_file = Path("task_tracker.json")
    if tracker_file.exists():
        tracker_file.unlink()

    tracker = TaskTracker(tracker_path=tracker_file)
    assert tracker_file.exists(), "task_tracker.json must exist in project root"

    # Verify initial schema
    raw = json.loads(tracker_file.read_text(encoding="utf-8"))
    assert "agent_stats" in raw
    assert "task_history" in raw
    assert "error_patterns" in raw
    assert "prevention_rules" in raw
    print("✓ Initial schema verified successfully.")

    # Record successful task
    tid1 = tracker.record_task(
        user_command="Desktop e python script lekho",
        task_type="file_manage",
        status="SUCCESS",
        steps_done=["make_dir Desktop/STAR_tasks", "write_text fib.py"]
    )
    assert tid1 == 1
    assert tracker.data["agent_stats"]["successful_tasks"] == 1
    assert tracker.data["agent_stats"]["total_tasks"] == 1
    assert tracker.data["agent_stats"]["success_rate_percent"] == 100.0
    print("✓ SUCCESS task recorded.")

    # Record failed task with error log
    tid2 = tracker.record_task(
        user_command="Download fake url",
        task_type="web_research",
        status="FAILED",
        steps_done=[],
        error_details={
            "error_type": "NetworkTimeout",
            "error_message": "Connection refused by host",
            "which_step_failed": "fetch_web_content",
            "root_cause": "Invalid URL supplied"
        },
        future_prevention={
            "rule_added": "Verify URL protocol and validity before network request"
        }
    )
    assert tid2 == 2
    assert tracker.data["agent_stats"]["failed_tasks"] == 1
    assert tracker.data["agent_stats"]["total_tasks"] == 2
    assert tracker.data["agent_stats"]["success_rate_percent"] == 50.0
    assert "Verify URL protocol and validity before network request" in tracker.data["prevention_rules"]

    err_file = Path("error_logs/error_002.txt")
    assert err_file.exists(), f"Error log {err_file} should have been created"
    print(f"✓ FAILED task recorded and error log verified: {err_file}")

    # Record auto-fixed task
    tid3 = tracker.record_task(
        user_command="Fix CSS break",
        task_type="web_build",
        status="AUTO_FIXED",
        steps_done=["build_page", "fix_viewport"],
        fix_applied={
            "how_fixed": "Added responsive viewport meta tag",
            "fix_steps": ["apply_meta_tag"],
            "fixed_by": "auto",
            "time_to_fix_seconds": 1.5
        }
    )
    assert tid3 == 3
    assert tracker.data["agent_stats"]["auto_fixed_tasks"] == 1
    assert tracker.data["agent_stats"]["successful_tasks"] == 2
    print("✓ AUTO_FIXED task recorded.")

    # Test Section 6 Stats Report ASCII Table
    stats_rep = tracker.generate_stats_report()
    print("\n" + stats_rep + "\n")
    assert "AGENT PERFORMANCE REPORT" in stats_rep
    assert "Total Tasks:" in stats_rep
    assert "Successful:" in stats_rep

    # Test Backup functionality
    dummy_file = Path("test_sample.py")
    dummy_file.write_text("print('hello')", encoding="utf-8")
    bak = tracker.backup_file(dummy_file)
    assert bak is not None and bak.exists(), "Backup file should be created in backup/"
    print(f"✓ Backup created successfully at: {bak}")
    dummy_file.unlink()

    # Test Section 7 Quick Command Handlers
    print("\n" + "="*60)
    print("2. TESTING QUICK COMMAND HANDLERS VIA ORCHESTRATOR")
    print("="*60)
    cfg = Config.load()
    ui = MockUI()
    orch = build_orchestrator(cfg, ui)

    commands_to_test = [
        ("stats dekhao", "AGENT PERFORMANCE REPORT"),
        ("error log dekhao", "error_logs"),
        ("ki ki fix korecho", "Auto-Fixed Tasks"),
        ("prevention rules", "Active Prevention Rules"),
        ("self audit koro", "Self-Audit Report"),
        ("improve koro", "Improvement Plan"),
        ("nijer code dekho", "Self Code Inspection"),
    ]

    for cmd, expected in commands_to_test:
        ui.said.clear()
        orch.handle(cmd)
        resp = " ".join(ui.said)
        assert expected.lower() in resp.lower(), f"Expected '{expected}' in response to '{cmd}', got: '{resp}'"
        print(f"✓ Command '{cmd}' -> Responded with expected content.")

    print("\n" + "="*60)
    print("ALL 7 SECTIONS VERIFIED & FULLY FUNCTIONAL!")
    print("="*60)

if __name__ == "__main__":
    test_tracker_system()
