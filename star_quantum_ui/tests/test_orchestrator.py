import unittest
from unittest import mock

from star_core.llm import LLMError, LLMClient, ModelRouter
from star_core.tools.files import CopyFiles
from star_core.models import ToolResult
from star_core.ui_port import RecordingPort
from tests.helpers import Env


class CopyTaskTests(unittest.TestCase):
    def test_success_is_verified_and_reported(self):
        e = Env()
        e.make_files()
        r = e.ask(e.copy_request())
        self.assertTrue(r.ok)
        self.assertEqual(sorted(p.name for p in e.dst.iterdir()), ["a.json", "b.json", "c.json"])
        self.assertIn("verified", r.summary)
        self.assertEqual(e.orch.metrics.summary()["verified_rate"], 1.0)

    def test_plan_needs_approval_and_it_is_shown_to_the_user(self):
        e = Env()
        e.make_files()
        e.ask(e.copy_request())
        approval = e.ui.events("approval")[0]
        self.assertEqual(approval[3]["Risk"], "medium")
        self.assertEqual(len(approval[4]), 3)

    def test_rejected_approval_changes_nothing(self):
        e = Env(approvals=[False])
        e.make_files()
        r = e.ask(e.copy_request())
        self.assertFalse(r.ok)
        self.assertFalse(e.dst.exists())
        self.assertEqual(r.outcomes, [])

    def test_partial_copy_is_never_called_a_success(self):
        """The architecture doc's example: 10 files, only 8 arrive."""
        e = Env()
        e.make_files([f"f{i}.json" for i in range(10)])
        import shutil
        real = shutil.copy2

        def flaky(src, dst, *a, **k):
            if str(src).endswith(("f3.json", "f7.json")):
                raise PermissionError("locked by another program")
            return real(src, dst, *a, **k)

        with mock.patch("star_core.tools.files.shutil.copy2", flaky):
            r = e.ask(e.copy_request())
        self.assertFalse(r.ok)
        self.assertTrue(r.partial)
        self.assertEqual(len(list(e.dst.iterdir())), 8)
        self.assertIn("✗", r.summary)
        self.assertIn("f3.json", r.summary)
        self.assertIn("locked", r.summary)
        self.assertEqual(e.orch.metrics.summary()["verified_ok"], 0)

    def test_tool_that_lies_is_caught_by_independent_verification(self):
        e = Env()
        e.make_files()
        real = CopyFiles.run

        def liar(self, args, ctx):
            res = real(self, dict(args, files=args["files"][:-1]), ctx)   # silently skips one file, claims success
            return ToolResult(True, {"copied": res.output["copied"], "skipped": [], "failed": [], "total": len(args["files"])})

        with mock.patch.object(CopyFiles, "run", liar):
            r = e.ask(e.copy_request())
        self.assertFalse(r.ok)
        self.assertEqual(e.orch.metrics.summary()["false_success_prevented"], 1)
        self.assertIn("verification failed", r.summary)

    def test_transient_error_is_retried_then_succeeds(self):
        e = Env()
        e.make_files()
        import shutil
        real, calls = shutil.copy2, {"n": 0}

        def once_flaky(src, dst, *a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("device busy")
            return real(src, dst, *a, **k)

        with mock.patch("star_core.tools.files.shutil.copy2", once_flaky):
            r = e.ask(e.copy_request())
        self.assertTrue(r.ok)
        self.assertGreaterEqual(next(o for o in r.outcomes if o.step.tool == "copy_files").attempts, 2)

    def test_name_collision_is_reported_not_overwritten(self):
        e = Env()
        (e.src / "x").mkdir()
        (e.src / "y").mkdir()
        (e.src / "x" / "a.json").write_text("one")
        (e.src / "y" / "a.json").write_text("two")
        r = e.ask(e.copy_request())
        self.assertFalse(r.ok)
        self.assertIn("collision", r.summary)
        self.assertEqual((e.dst / "a.json").read_text(), "one")

    def test_unsupported_part_is_admitted_not_faked(self):
        e = Env()
        e.make_files()
        r = e.ask(e.copy_request() + " and send them to my phone")
        self.assertFalse(r.ok)
        self.assertTrue(r.partial)
        self.assertEqual(len(list(e.dst.iterdir())), 3)
        self.assertIn("phone", r.summary)

    def test_cancel_stops_before_any_step(self):
        e = Env()
        e.make_files()
        orig = e.ui.request_approval

        def approve_then_cancel(*a, **k):
            ok = orig(*a, **k)
            e.ui.cancel.set()
            return ok

        e.ui.request_approval = approve_then_cancel
        r = e.ask(e.copy_request())
        self.assertFalse(r.ok)
        self.assertFalse(e.dst.exists())
        self.assertIn("Cancelled", r.summary)


class UnderstandingTests(unittest.TestCase):
    def test_asks_instead_of_guessing_a_missing_destination(self):
        e = Env(answers=[None])
        e.make_files()
        r = e.ask(f"find all json files in '{e.src}' and copy them")
        self.assertIsNone(r)
        self.assertEqual(len(e.ui.events("ask")), 1)
        self.assertFalse(e.dst.exists())

    def test_answer_to_the_question_completes_the_task(self):
        e = Env()
        e.make_files()
        e.ui.answers = [f"'{e.dst}'"]
        r = e.ask(f"find all json files in '{e.src}' and copy them")
        self.assertTrue(r.ok)
        self.assertEqual(len(e.ui.events("ask")), 1)

    def test_folder_name_is_resolved_to_a_real_path(self):
        e = Env()
        e.make_files()
        r = e.ask(f"find all json files in 'src' and copy them to '{e.dst}'")
        self.assertTrue(r.ok)

    def test_ambiguous_folder_name_triggers_a_question(self):
        e = Env(answers=[None])
        (e.tmp / "a" / "src").mkdir(parents=True)
        e.ask(f"find all json files in 'src' and copy them to '{e.dst}'")
        self.assertIn("Several folders", e.ui.events("ask")[0][1])

    def test_outside_allowed_folders_is_refused_without_touching_anything(self):
        e = Env()
        r = e.ask(f"find all json files in '/etc' and copy them to '{e.dst}'")
        self.assertIsNone(r)
        self.assertTrue(any("outside" in m for m in e.ui.messages))
        self.assertEqual(e.ui.events("open_tab"), [])

    def test_plain_chat_needs_no_plan_and_no_tabs(self):
        e = Env()
        e.ask("hello there")
        self.assertEqual(e.ui.events("open_tab"), [])
        self.assertTrue(e.ui.messages)

    def test_bengali_request_gets_a_bengali_answer(self):
        e = Env()
        e.make_files()
        r = e.ask(f"'{e.src}' ফোল্ডার থেকে সব JSON ফাইল '{e.dst}' ফোল্ডারে কপি করো")
        self.assertTrue(r.ok)
        self.assertIn("কাজ শেষ", r.summary)

    def test_banglish_request_gets_a_banglish_answer(self):
        e = Env()
        e.make_files()
        r = e.ask(f"amar '{e.src}' folder theke sob json file '{e.dst}' e copy koro")
        self.assertTrue(r.ok)
        self.assertIn("Kaj shesh", r.summary)

    def test_personal_memory_is_saved_only_when_the_user_asks(self):
        e = Env()
        e.make_files()
        e.ask(e.copy_request())
        self.assertEqual(e.store.count("preference"), 0)
        self.assertEqual(e.store.count("project"), 0)
        e.ask("please remember I prefer short answers")
        self.assertEqual(e.store.count("preference"), 1)

    def test_finished_tasks_leave_a_task_memory_and_failed_ones_a_lesson(self):
        e = Env(with_skills=True, default_approval=True)
        e.make_files()
        e.ask(e.copy_request())
        self.assertGreaterEqual(e.store.count("task"), 1)


class DownLLM(LLMClient):
    name = "down"

    def chat(self, *a, **k):
        raise LLMError("connection refused")


class ResilienceTests(unittest.TestCase):
    def test_model_down_gives_a_clear_message_not_a_crash(self):
        e = Env()
        e.router.local = DownLLM()
        r = e.ask("hello")
        self.assertIsNone(r)
        self.assertTrue(any("language model" in m or "Ollama" in m for m in e.ui.messages))

    def test_a_crashing_tool_fails_the_step_not_the_assistant(self):
        e = Env()
        e.make_files()
        with mock.patch.object(CopyFiles, "run", side_effect=RuntimeError("boom")):
            r = e.ask(e.copy_request())
        self.assertFalse(r.ok)
        self.assertIn("boom", r.summary)


if __name__ == "__main__":
    unittest.main()
