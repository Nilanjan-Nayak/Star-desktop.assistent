import os
import tempfile
import time
import unittest
from pathlib import Path

from star_core.memory import MemoryStore, Retriever
from star_core.security import PermissionPolicy, PolicyError
from star_core.text import detect_language, tokens


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.s = MemoryStore()

    def test_bengali_tokens_keep_vowel_signs(self):
        self.assertIn("ফোল্ডারে", tokens("Nilanjan ফোল্ডারে JSON ফাইল"))

    def test_bengali_search_finds_the_right_memory(self):
        self.s.add("project", "json_folder", "Nilanjan ফোল্ডারে আমার সব JSON ফাইল থাকে")
        self.s.add("project", "ui", "STAR এর UI PySide6 দিয়ে তৈরি")
        hits = self.s.search("JSON ফাইল কোথায় থাকে")
        self.assertTrue(hits)
        self.assertEqual(hits[0].memory.key, "json_folder")

    def test_preference_is_upserted_not_duplicated(self):
        a = self.s.add("preference", "reply_language", "Bangla")
        b = self.s.add("preference", "reply_language", "English")
        self.assertEqual(a, b)
        self.assertEqual(self.s.count("preference"), 1)
        self.assertEqual(self.s.get(a).content, "English")

    def test_stale_memory_ranks_lower_and_is_flagged(self):
        a = self.s.add("project", "x1", "the build folder is C:\\old")
        self.s.add("project", "x2", "the build folder is C:\\new")
        self.s.mark_stale(a)
        hits = self.s.search("build folder")
        self.assertEqual(hits[0].memory.key, "x2")
        self.assertIn("STALE", Retriever(self.s).context_for("build folder").text)

    def test_context_warns_that_memory_may_be_wrong(self):
        self.s.add("learning", "k", "copying json files can hit name collisions")
        self.assertIn("may be outdated or wrong", Retriever(self.s).context_for("copy json files").text)

    def test_forget_and_prune(self):
        i = self.s.add("task", "t", "did something")
        self.assertTrue(self.s.forget(i))
        self.assertIsNone(self.s.get(i))
        for n in range(80):
            self.s.add("conversation", "user", f"m{n}")
        self.s.prune_conversation(keep=10)
        self.assertEqual(self.s.count("conversation"), 10)

    def test_persists_on_disk(self):
        p = Path(tempfile.mkdtemp()) / "m.db"
        MemoryStore(p).add("project", "a", "persisted")
        self.assertEqual(MemoryStore(p).count(), 1)

    def test_language_detection(self):
        self.assertEqual(detect_language("সব JSON ফাইল কপি করো"), "bn")
        self.assertEqual(detect_language("ami amar folder theke file khuje ber korte chai"), "banglish")
        self.assertEqual(detect_language("copy all json files"), "en")


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.p = PermissionPolicy([self.root])

    def test_inside_ok_outside_refused(self):
        self.assertEqual(self.p.resolve(self.root / "a"), self.root / "a")
        with self.assertRaises(PolicyError):
            self.p.resolve("/etc")

    def test_relative_paths_refused(self):
        with self.assertRaises(PolicyError):
            self.p.resolve("a/b")

    def test_dotdot_escape_refused(self):
        with self.assertRaises(PolicyError):
            self.p.resolve(self.root / ".." / "x")

    def test_symlink_escape_refused(self):
        outside = Path(tempfile.mkdtemp()).resolve()
        link = self.root / "link"
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not available")
        with self.assertRaises(PolicyError):
            self.p.resolve(link / "file")


if __name__ == "__main__":
    unittest.main()
