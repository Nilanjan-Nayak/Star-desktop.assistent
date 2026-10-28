import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from star_core.config import Config
from star_core.app import build_orchestrator
from star_core.ui_port import UIPort

class MockUI(UIPort):
    def request_approval(self, *args, **kwargs):
        print(f"Approval requested: {args}")
        return True
    def open_tab(self, *args, **kwargs):
        return 'tab-1'
    def tab_event(self, *args, **kwargs):
        pass
    def say(self, text):
        print('STAR said:', text)
    def set_state(self, state):
        pass
    def metric(self, *args):
        pass
    def ask(self, *args, **kwargs):
        return "Desktop"

def main():
    cfg = Config.load()
    ui = MockUI()
    orch = build_orchestrator(cfg, ui)

    test_queries = [
        "Desktop e ekta python script lekho jeta fibonacci number ber kore",
        "Downloads e ekta test.txt file banao",
    ]

    for q in test_queries:
        print("\n" + "="*50)
        print("RUNNING:", q)
        print("="*50)
        report = orch.handle(q)
        if report:
            print("OK status:", report.ok)
            print("Partial:", report.partial)
            print("Summary:", report.summary)
            print("Unsupported:", report.plan.unsupported if report.plan else None)
            assert report.ok is True, f"Failed for {q}"
        else:
            print("Direct answer or no report")

    print("\nALL VOICE/CHAT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
