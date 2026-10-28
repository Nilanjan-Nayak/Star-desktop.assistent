import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from star_core.config import Config
from star_core.app import build_orchestrator
from star_core.ui_port import UIPort

class MockUI(UIPort):
    def request_approval(self, *args, **kwargs):
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

cfg = Config.load()
ui = MockUI()
orch = build_orchestrator(cfg, ui)
rep = orch.handle('Desktop e ekta python script lekho jeta fibonacci number ber kore')
print('=== FINAL RESULT ===')
if rep:
    print('OK status:', rep.ok)
    print('Partial:', rep.partial)
    print('Summary:', rep.summary)
    print('Outcomes count:', len(rep.outcomes))
    for o in rep.outcomes:
        print(f"  Step {o.step.id} ({o.step.tool}): verified={o.verified}")
else:
    print('No report returned')
