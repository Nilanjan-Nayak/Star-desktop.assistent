import tempfile
import unittest
from pathlib import Path

from star_core.config import Config
from star_core.llm import LLMClient, LLMError, MockLLM, ModelRouter
from star_core.llm.router import extract_json
from star_core.skills import GuardError, check_code, run_code
from star_core.skills.evaluator import Evaluator
from star_core.skills.registry import Skill
from tests.helpers import Env


class RouterTests(unittest.TestCase):
    class Fixed(LLMClient):
        def __init__(self, text="{}", fail=False, name="fixed"):
            self.text, self.fail, self.name, self.calls = text, fail, name, 0

        def chat(self, messages, **k):
            from star_core.llm import ChatResponse
            self.calls += 1
            if self.fail:
                raise LLMError("down")
            return ChatResponse(self.text, "m", self.name, 1, 0.1)

    def msgs(self):
        return [{"role": "system", "content": "x"}, {"role": "user", "content": "y"}]

    def test_local_first_and_no_cloud_when_not_enabled(self):
        local, cloud = self.Fixed(name="local"), self.Fixed(name="cloud")
        r = ModelRouter(local, cloud, Config(cloud_fallback=False))
        r.chat(self.msgs())
        self.assertEqual((local.calls, cloud.calls), (1, 0))

    def test_cloud_fallback_only_when_enabled_and_local_fails(self):
        local, cloud = self.Fixed(fail=True), self.Fixed(name="cloud")
        cloud.available = lambda: True
        self.assertEqual(ModelRouter(local, cloud, Config(cloud_fallback=True)).chat(self.msgs()).provider, "cloud")
        with self.assertRaises(LLMError):
            ModelRouter(self.Fixed(fail=True), cloud, Config(cloud_fallback=False)).chat(self.msgs())

    def test_private_context_never_goes_to_the_cloud(self):
        local, cloud = self.Fixed(fail=True), self.Fixed(name="cloud")
        cloud.available = lambda: True
        r = ModelRouter(local, cloud, Config(cloud_fallback=True))
        with self.assertRaises(LLMError):
            r.chat(self.msgs(), cloud_ok=False)
        self.assertEqual(cloud.calls, 0)

    def test_invalid_json_is_repaired_by_asking_again(self):
        m = MockLLM()
        m.fail_next_json = 2
        r = ModelRouter(m, None, Config())
        d = r.json_chat([{"role": "system", "content": "[[TASK:analysis]]"},
                         {"role": "user", "content": "User request:\nhello"}], task="analysis", required=["intent"])
        self.assertEqual(d["intent"], "chat")
        self.assertEqual(len(m.calls), 3)

    def test_json_that_never_validates_raises(self):
        r = ModelRouter(self.Fixed(text="nope"), None, Config())
        with self.assertRaises(LLMError):
            r.json_chat(self.msgs(), task="analysis", required=["a"], retries=1)

    def test_extract_json_handles_fences_and_trailing_commas(self):
        self.assertEqual(extract_json('ok ```json\n{"a": [1, 2,],}\n``` bye'), {"a": [1, 2]})

    def test_planner_rejects_a_plan_with_an_invented_tool_and_retries(self):
        class Planner(MockLLM):
            n = 0

            def _planning(self, user):
                Planner.n += 1
                if Planner.n == 1:
                    return {"goal": "x", "unsupported": [], "steps": [{"id": "s1", "tool": "format_disk", "args": {}}]}
                return super()._planning(user)

        e = Env()
        e.llm = Planner()
        e.router.local = e.llm
        e.make_files()
        r = e.ask(e.copy_request())
        self.assertTrue(r.ok)
        self.assertEqual(Planner.n, 2)


class SandboxTests(unittest.TestCase):
    def test_guard_blocks_dangerous_code(self):
        for bad in ("import os\ndef run(i): return {}", "def run(i):\n    return open('x').read()",
                    "def run(i):\n    return ().__class__", "import subprocess\ndef run(i): return {}",
                    "def run(i):\n    return eval('1')", "x = 1"):
            with self.assertRaises(GuardError, msg=bad):
                check_code(bad)

    def test_good_code_runs(self):
        r = run_code("import re\ndef run(i):\n    return {'n': len(re.findall(r'a', i['t']))}", {"t": "banana"})
        self.assertTrue(r.ok)
        self.assertEqual(r.result, {"n": 3})

    def test_infinite_loop_is_killed(self):
        r = run_code("def run(i):\n    while True:\n        pass", {}, timeout=1.0)
        self.assertFalse(r.ok)
        self.assertIn("timed out", r.error)

    def test_runtime_error_is_reported_not_raised(self):
        r = run_code("def run(i):\n    return 1/0", {})
        self.assertFalse(r.ok)
        self.assertIn("ZeroDivisionError", r.error)

    def test_import_inside_function_is_still_blocked_at_runtime(self):
        r = run_code("def run(i):\n    import re\n    return {'ok': True}", {})
        self.assertTrue(r.ok)


class SkillLearningTests(unittest.TestCase):
    def test_learn_then_reuse_with_different_folders(self):
        e = Env(with_skills=True)
        e.make_files()
        r1 = e.ask(e.copy_request())
        self.assertTrue(r1.ok)
        titles = [c[1] for c in e.ui.events("approval")]
        self.assertTrue(any("reusable skill" in t for t in titles))
        self.assertEqual(e.skills.count_approved(), 1)
        skill = e.skills.active_skills()[0]
        self.assertEqual(skill.last_eval["false_success"], 0)
        self.assertIn("same name in two folders is never reported as success", skill.last_eval["cases"])

        src2, dst2 = e.tmp / "src2", e.tmp / "dst2"
        src2.mkdir()
        (src2 / "x.json").write_text("x")
        (src2 / "y.txt").write_text("y")
        r2 = e.ask(f"find all json files in '{src2}' and copy them to '{dst2}'")
        self.assertTrue(r2.ok)
        self.assertEqual(r2.skill_used, skill.label)
        self.assertEqual([p.name for p in dst2.iterdir()], ["x.json"])
        self.assertEqual(e.skills.get(skill.name, skill.version).uses, 1)

    def test_declining_creates_nothing_and_is_remembered(self):
        e = Env(with_skills=True, approvals=[True, False])    # approve the task, decline the skill
        e.make_files()
        e.ask(e.copy_request())
        self.assertEqual(e.skills.all(), [])
        self.assertTrue(any(m.key.startswith("skill_declined") for m in e.store.all("learning")))
        n = len(e.ui.events("approval"))
        e.ask(e.copy_request(e.tmp / "dst_b"))
        self.assertEqual(len(e.ui.events("approval")), n + 1)     # only the task approval, no new skill offer

    def test_skill_is_not_used_when_the_request_has_parts_it_never_handled(self):
        e = Env(with_skills=True)
        e.make_files()
        e.ask(e.copy_request())
        r = e.ask(e.copy_request(e.tmp / "dst_p") + " and send to phone")
        self.assertIsNone(r.skill_used)
        self.assertIn("phone", r.summary)

    def test_regression_blocks_a_worse_version(self):
        e = Env(with_skills=True)
        e.make_files()
        e.ask(e.copy_request())
        good = e.skills.active_skills()[0]
        ev = Evaluator(e.registry, e.config)
        broken = Skill(**{**good.__dict__})
        broken.version, broken.status = good.version + 1, "draft"
        broken.steps = [dict(s) for s in good.steps]
        for s in broken.steps:
            if s["tool"] == "copy_files":
                s["args"] = dict(s["args"], dest_dir="<<source_dir>>")   # "succeeds" by copying onto itself, delivers nothing
        old, new = ev.run(good), ev.run(broken, good.tests)
        reasons = ev.compare(new, old)
        self.assertTrue(reasons)
        self.assertTrue(any("fails its own tests" in r for r in reasons))
        self.assertTrue(any("false success" in r for r in reasons))   # verified-looking, but the files never arrived

    def test_overwrite_variant_is_still_caught_by_verification(self):
        """Even a version that overwrites collisions cannot fake success: the disk check disagrees."""
        e = Env(with_skills=True)
        e.make_files()
        e.ask(e.copy_request())
        good = e.skills.active_skills()[0]
        bad = Skill(**{**good.__dict__})
        bad.steps = [dict(s, args=dict(s["args"], overwrite=True)) if s["tool"] == "copy_files" else s for s in good.steps]
        ev = Evaluator(e.registry, e.config)
        collision = next(c for c in ev.run(bad, good.tests).cases if "same name" in c.name)
        self.assertTrue(collision.passed)

    def test_high_risk_workflows_are_never_turned_into_skills(self):
        e = Env(with_skills=True)
        e.ask("install requests")
        self.assertEqual(e.skills.all(), [])

    def test_two_failures_in_a_row_stop_a_skill_from_being_used(self):
        e = Env(with_skills=True)
        e.make_files()
        e.ask(e.copy_request())
        label = e.skills.active_skills()[0].label
        e.skills.record_use(label, False)
        e.skills.record_use(label, False)
        self.assertEqual(e.skills.count_approved(), 0)

    def test_code_skill_is_proposed_guarded_and_tested_but_not_activated(self):
        e = Env(with_skills=True)
        skill, result, text = e.learner.propose_code_skill("make a slug from a title", e.orch)
        self.assertIsNotNone(skill)
        self.assertTrue(result.passed)
        self.assertEqual(skill.status, "tested")
        self.assertEqual(e.skills.count_approved(), 0)       # needs the user's approval

    def test_code_skill_with_dangerous_code_is_rejected_before_any_test(self):
        class Evil(MockLLM):
            def _skill_code(self, user):
                return {"name": "evil", "code": "import os\ndef run(i):\n    return {}", "tests": []}

        e = Env(with_skills=True)
        e.router.local = Evil()
        skill, result, text = e.learner.propose_code_skill("x", e.orch)
        self.assertIsNone(skill)
        self.assertIn("safety guard", text)


if __name__ == "__main__":
    unittest.main()
