"""Brain: understands the request (intent, entities, missing info, risk) and answers plain questions."""
from __future__ import annotations

import os
from ..config import Config
from ..llm import ModelRouter
from ..models import Analysis
from ..text import detect_language
from .prompts import ANALYSIS_SYSTEM, CHAT_SYSTEM, user_message

_RISKS = ("low", "medium", "high")


def _clean_list(v) -> list:
    return [x for x in v if x] if isinstance(v, list) else []


class Brain:
    def __init__(self, router: ModelRouter, config: Config):
        self.router, self.config = router, config

    def analyze(self, text: str, memory: str = "", history: str = "", cloud_ok: bool = True) -> Analysis:
        detected = detect_language(text)
        if detected == "banglish":
            lang_inst = "\nUSER IS WRITING IN BANGLISH: Set language='banglish'. Any direct_answer or questions MUST be written in natural Banglish (Bengali words spelled in English/Latin letters, e.g. 'Ami apnake sahajjo korte pari'). NEVER reply in English or Bengali script."
        elif detected == "bn":
            lang_inst = "\nUSER IS WRITING IN BENGALI: Set language='bn'. Any direct_answer or questions MUST be in Bengali script."
        else:
            lang_inst = "\nUSER IS WRITING IN ENGLISH: Set language='en'."

        runtime = (
            f"\nRuntime platform: {os.name} (Windows paths use drive letters and backslashes). "
            f"Allowed roots: {', '.join(str(r) for r in self.config.roots)}. "
            "Never invent Linux paths such as /var/www or /home, and never use shell variables."
            f"{lang_inst}"
        )
        msgs = [{"role": "system", "content": ANALYSIS_SYSTEM + runtime},
                {"role": "user", "content": user_message(text, history, memory)}]
        d = self.router.json_chat(msgs, task="analysis", required=["intent", "needs_plan"],
                                  retries=self.config.llm_json_retries, cloud_ok=cloud_ok)
        if detected in ("bn", "banglish"):
            lang = detected
        else:
            lang = d.get("language") if d.get("language") in ("bn", "banglish", "en") else "en"
        risk = d.get("risk") if d.get("risk") in _RISKS else "low"
        ent = d.get("entities") if isinstance(d.get("entities"), dict) else {}
        answer = d.get("direct_answer")
        needs_plan = bool(d.get("needs_plan"))
        low_text = text.lower()
        if any(w in low_text for w in ("research koro", "web research", "save koro", "file poro", "read koro", "khuje ber koro", "folder banao", "list dekhao")):
            needs_plan = True
        return Analysis(
            intent=str(d.get("intent", "chat")), summary=str(d.get("summary", "")), language=lang, entities=dict(ent),
            missing_info=_clean_list(d.get("missing_info")), questions=[str(q) for q in _clean_list(d.get("questions"))],
            risk=risk, needs_plan=needs_plan, direct_answer=str(answer) if answer else None,
            remember=[r for r in _clean_list(d.get("remember")) if isinstance(r, dict)
                      and r.get("kind") in ("preference", "project") and r.get("content")])

    def answer(self, text: str, language: str, memory: str = "", history: str = "", cloud_ok: bool = True) -> str:
        if language == "banglish":
            lang_spec = "Reply strictly in natural conversational Banglish (Bengali words spelled in English/Latin letters, for example: 'Ami bhalo achi! Apnar ki sahajjo lagbe bolun?'). Never reply in pure English or Bengali alphabet."
        elif language == "bn":
            lang_spec = "সম্পূর্ণ বাংলায় উত্তর দিন।"
        else:
            lang_spec = "Reply in clear, natural English."
        msgs = [{"role": "system", "content": CHAT_SYSTEM.format(lang_spec=lang_spec)},
                {"role": "user", "content": user_message(text, history, memory)}]
        return self.router.chat(msgs, task="chat", cloud_ok=cloud_ok, temperature=0.4).text.strip()
