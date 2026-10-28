"""MockLLM: a deterministic TEST DOUBLE that stands in for a real model.

It recognises a few fixed request shapes with regexes so the whole pipeline (analysis, planning,
approval, execution, verification, skills) can be tested offline. It is not intelligence; real
quality depends on the model you run through Ollama / OpenRouter.
"""
from __future__ import annotations

import json
import re

from ..text import detect_language
from .base import ChatResponse, LLMClient

_Q = re.compile(r"""["'\u2018\u2019\u201c\u201d]([^"'\u2018\u2019\u201c\u201d]+)["'\u2018\u2019\u201c\u201d]""")


class MockLLM(LLMClient):
    name = "mock"

    def __init__(self):
        self.calls: list[tuple[str, str]] = []   # (task, last user message)
        self.fail_next_json = 0                  # make the next N JSON replies invalid (router repair tests)

    # --------------------------------------------------------------------------------------
    def chat(self, messages, *, json_mode=False, temperature=0.1, timeout=180) -> ChatResponse:
        system = messages[0]["content"]
        task = (re.search(r"\[\[TASK:(\w+)\]\]", system) or [None, "chat"])[1]
        # the first user message holds the request; later ones are repair feedback from the router
        user = next(m["content"] for m in messages if m["role"] == "user")
        self.calls.append((task, user))
        if self.fail_next_json > 0 and json_mode:
            self.fail_next_json -= 1
            return ChatResponse("not json at all", "mock", "mock", 5, 0.01)
        handler = getattr(self, f"_{task}", self._chat)
        out = handler(user)
        text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
        return ChatResponse(text, "mock", "mock", max(1, len(text) // 4), 0.01)

    # --------------------------------------------------------------------------------------
    @staticmethod
    def _request(user: str) -> str:
        m = re.search(r"User request:\n(.*?)(?:\n\nMemory:|\n\nConversation:|\Z)", user, re.S)
        return (m.group(1) if m else user).strip()

    def _analysis(self, user: str) -> dict:
        text = self._request(user)
        low = text.lower()
        lang = detect_language(text)
        a = {"intent": "chat", "summary": text[:80], "language": lang, "entities": {}, "missing_info": [],
             "questions": [], "risk": "low", "needs_plan": False, "direct_answer": None, "remember": []}
        quoted = _Q.findall(text)
        if re.search(r"remember|মনে রাখ|mone rakho", low):
            a.update(intent="remember", direct_answer=None,
                     remember=[{"kind": "preference", "key": "user_note", "content": text}])
            return a
        if "youtube" in low:
            a.update(intent="open_url", needs_plan=True, entities={"url": "https://www.youtube.com", "title": "YouTube"})
            return a
        m = re.search(r"install\s+(\S+)|ইনস্টল\s+(\S+)", low)
        if m:
            a.update(intent="install_package", needs_plan=True, risk="high",
                     entities={"package": (m.group(1) or m.group(2)).strip(".,")})
            return a
        if ("json" in low or "জসন" in low) and re.search(r"copy|কপি", low):
            ent = {"pattern": "*.json"}
            if len(quoted) >= 2:
                ent["source_dir"], ent["dest_dir"] = quoted[0], quoted[1]
            elif len(quoted) == 1:
                ent["source_dir"] = quoted[0]
            if re.search(r"phone|ফোন|phone-e|fone", low):
                ent["send_to_phone"] = True
            a.update(intent="copy_files_by_pattern", needs_plan=True, risk="medium", entities=ent)
            if "dest_dir" not in ent:
                a["missing_info"] = ["dest_dir"]
                a["questions"] = ["কোন ফোল্ডারে কপি করব?" if lang == "bn" else "Which folder should I copy them to?"]
            return a
        a["direct_answer"] = f"(mock) {text}"
        return a

    def _planning(self, user: str) -> dict:
        m = re.search(r"Analysis JSON:\n(\{.*?\})\n\n", user, re.S)
        an = json.loads(m.group(1)) if m else {}
        ent, intent = an.get("entities", {}), an.get("intent")
        if intent == "copy_files_by_pattern":
            steps = [
                {"id": "s1", "tool": "find_files", "args": {"root": ent["source_dir"], "pattern": ent["pattern"]},
                 "description": f"Find {ent['pattern']} files in the source folder"},
                {"id": "s2", "tool": "make_dir", "args": {"path": ent["dest_dir"]},
                 "description": "Create the destination folder if needed"},
                {"id": "s3", "tool": "copy_files", "args": {"files": "${s1.files}", "dest_dir": ent["dest_dir"]},
                 "description": "Copy the files and verify them by hash"}]
            return {"goal": an.get("summary", ""), "steps": steps,
                    "unsupported": ["send the files to the phone"] if ent.get("send_to_phone") else []}
        if intent == "open_url":
            return {"goal": "open page", "unsupported": [], "steps": [
                {"id": "s1", "tool": "open_url", "args": {"url": ent["url"], "title": ent.get("title", "")},
                 "description": "Open the page in a STAR tab"}]}
        if intent == "install_package":
            return {"goal": f"install {ent['package']}", "unsupported": [], "steps": [
                {"id": "s1", "tool": "install_package", "args": {"package": ent["package"]},
                 "description": f"Install {ent['package']} with pip"}]}
        return {"goal": an.get("summary", ""), "steps": [], "unsupported": ["no matching tools"]}

    def _replan(self, user: str) -> dict:
        return {"steps": [], "give_up": True}

    def _chat(self, user: str) -> str:
        return f"(mock) {self._request(user)}"

    def _skill_code(self, user: str) -> dict:
        return {"name": "slugify", "description": "Turn a title into a URL slug",
                "code": ("import re\n\ndef run(inputs):\n    text = str(inputs['text']).strip().lower()\n"
                         "    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')\n    return {'slug': text}\n"),
                "tests": [{"input": {"text": "Hello, World!"}, "expect": {"slug": "hello-world"}},
                          {"input": {"text": "  Ghost   Terminal "}, "expect": {"slug": "ghost-terminal"}},
                          {"input": {"text": ""}, "expect": {"slug": ""}}]}
