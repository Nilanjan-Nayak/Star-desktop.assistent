"""Final messages. Built ONLY from verified facts, so the assistant cannot talk itself into a false success."""
from __future__ import annotations

from .models import StepOutcome, TaskReport


def _t(lang: str, bn: str, bl: str, en: str) -> str:
    return {"bn": bn, "banglish": bl}.get(lang, en)


def _fact(o: StepOutcome, lang: str) -> str:
    r, tool = o.result, o.step.tool
    out = r.output if r else {}
    if tool == "find_files":
        return _t(lang, f"{out.get('count', 0)}টি ফাইল খুঁজে পেয়েছি", f"{out.get('count', 0)}ta file khuje peyechi",
                  f"found {out.get('count', 0)} files")
    if tool == "make_dir":
        return _t(lang, f"ফোল্ডার প্রস্তুত: {out.get('path')}", f"folder ready: {out.get('path')}", f"folder ready: {out.get('path')}")
    if tool == "copy_files":
        c, s = len(out.get("copied", [])), len(out.get("skipped", []))
        extra_bn = f", {s}টি আগে থেকেই ছিল" if s else ""
        extra_bl = f", {s}ta age thekei chilo" if s else ""
        extra_en = f", {s} were already there" if s else ""
        return _t(lang, f"{c}টি ফাইল কপি করেছি{extra_bn} (প্রতিটির hash মিলিয়ে দেখেছি)",
                  f"{c}ta file copy korechi{extra_bl} (protitar hash miliye dekhechi)",
                  f"copied {c} files{extra_en} (every file checked by hash)")
    if tool == "open_url":
        return _t(lang, "পেজটি নতুন ট্যাবে খুলেছি", "page ta notun tab e khulechi", "opened the page in a new tab")
    if tool == "serve_website":
        return _t(lang, f"লোকাল website চালু হয়েছে: {out.get('url')}",
                  f"local website chalu hoyeche: {out.get('url')}",
                  f"started the local website: {out.get('url')}")
    if tool == "write_text":
        content = str(out.get("content", ""))
        preview = content if len(content) <= 500 else content[:500] + "..."
        if out.get("unchanged"):
            return _t(lang, f"ফাইলটি আগে থেকেই একই ছিল: {out.get('path')}\n{preview}",
                      f"file ta age thekei eki chilo: {out.get('path')}\n{preview}",
                      f"file already had the same content: {out.get('path')}\n{preview}")
        return _t(lang, f"ফাইল সেভ হয়েছে: {out.get('path')}\n{preview}",
                  f"file save hoyeche: {out.get('path')}\n{preview}",
                  f"saved file: {out.get('path')}\n{preview}")
    if tool == "install_package":
        return _t(lang, f"'{o.step.args.get('package')}' ইনস্টল হয়েছে (pip show দিয়ে যাচাই করেছি)",
                  f"'{o.step.args.get('package')}' install hoyeche (pip show diye jachai korechi)",
                  f"installed '{o.step.args.get('package')}' (confirmed with pip show)")
    return _t(lang, f"{o.step.description or tool} — সম্পন্ন ও যাচাই করা", f"{o.step.description or tool} — sompurno o jachai kora",
              f"{o.step.description or tool} — done and verified")


def _failure(o: StepOutcome, lang: str) -> str:
    r = o.result
    reason = (r.error if r else "") or "unknown"
    lines = [_t(lang, f"ব্যর্থ ধাপ: {o.step.description or o.step.tool} — {reason}",
                f"Ber-tho dhap: {o.step.description or o.step.tool} — {reason}",
                f"Failed step: {o.step.description or o.step.tool} — {reason}")]
    for f in (r.output.get("failed", []) if r else [])[:5]:
        lines.append(f"   • {f.get('src', '').split('/')[-1].split(chr(92))[-1]}: {f.get('reason')}")
    return "\n".join(lines)


def final_message(report: TaskReport, lang: str) -> str:
    done = [o for o in report.outcomes if o.verified]
    failed = [o for o in report.outcomes if not o.skipped and not o.verified]
    skipped = [o for o in report.outcomes if o.skipped]
    plan = report.plan
    unsupported = plan.unsupported if plan else []
    lines: list[str] = []
    if report.ok:
        lines.append(_t(lang, "কাজ শেষ, সবকিছু যাচাই করেছি।", "Kaj shesh, sob kichu jachai korechi.", "Done, and everything is verified."))
    elif done and not failed and unsupported:
        lines.append(_t(lang, "কাজের একটা অংশ সম্পন্ন করেছি, বাকিটা এখনো করতে পারি না।",
                        "Kajer ekta ongsho shesh korechi, baki ta ekhono korte pari na.",
                        "I finished part of the job; the rest is not something I can do yet."))
    elif done:
        lines.append(_t(lang, "কাজ আংশিক হয়েছে, পুরোটা সফল বলা যাচ্ছে না।", "Kaj angshik hoyeche, puro ta sofol bola jachhe na.",
                        "Only part of the job worked; I can't call it a success."))
    else:
        lines.append(_t(lang, "কাজটা সম্পন্ন করতে পারিনি।", "Kaj ta shesh korte pari ni.", "I could not complete the job."))
    for o in done:
        lines.append("✓ " + _fact(o, lang))
    for o in failed:
        lines.append("✗ " + _failure(o, lang))
    if skipped:
        lines.append(_t(lang, f"{len(skipped)}টি ধাপ চালাইনি (আগের ধাপ ব্যর্থ বা বাতিল)।",
                        f"{len(skipped)}ta dhap chalai ni (ager dhap ber-tho ba batil).",
                        f"{len(skipped)} step(s) not run (an earlier step failed or was cancelled)."))
    if unsupported:
        lines.append(_t(lang, "যা পারিনি: " + "; ".join(unsupported) + " — এই ক্ষমতা এখনো যোগ হয়নি।",
                        "Ja pari ni: " + "; ".join(unsupported) + " — ei khomota ekhono jog hoy ni.",
                        "Not possible yet: " + "; ".join(unsupported) + "."))
    if report.skill_used:
        lines.append(_t(lang, f"(সেভ করা skill ব্যবহার করেছি: {report.skill_used})", f"(save kora skill byabohar korechi: {report.skill_used})",
                        f"(used saved skill: {report.skill_used})"))
    return "\n".join(lines)


MESSAGES = {
    "no_model": ("ভাষা মডেল পাচ্ছি না। Ollama চালু করো, অথবা OpenRouter key দিয়ে cloud fallback চালু করো।",
                 "Language model pachhi na. Ollama chalu koro, ba OpenRouter key diye cloud fallback chalu koro.",
                 "No language model is reachable. Start Ollama, or enable cloud fallback with an OpenRouter key."),
    "rejected": ("ঠিক আছে, কিছুই পরিবর্তন করিনি।", "Thik ache, kichui poriborton kori ni.", "Okay, nothing was changed."),
    "no_answer": ("উত্তর পাইনি, তাই কাজটা থামিয়ে দিলাম।", "Uttor pai ni, tai kaj ta thamiye dilam.", "No answer received, so I stopped."),
    "need_more": ("প্রয়োজনীয় তথ্য এখনো অসম্পূর্ণ, তাই অনুমান করে কিছু করছি না।",
                  "Proyojoniyo tothyo ekhono osompurno, tai onuman kore kichu korchi na.",
                  "Some details are still missing, so I'm not guessing."),
    "no_plan": ("এই কাজের জন্য আমার কাছে উপযুক্ত tool নেই।", "Ei kajer jonno amar kache upojukto tool nei.",
                "I don't have a suitable tool for this yet."),
    "cancelled": ("কাজ বাতিল করেছি।", "Kaj batil korechi.", "Cancelled."),
    "crash": ("একটা অপ্রত্যাশিত সমস্যা হয়েছে; কাজটা থামিয়েছি। বিস্তারিত log-এ আছে।",
              "Ekta oprotyashito somossa hoyeche; kaj ta thamiyechi. Bistarito log e ache.",
              "Something unexpected went wrong; I stopped. Details are in the log."),
}


def msg(key: str, lang: str) -> str:
    bn, bl, en = MESSAGES[key]
    return _t(lang, bn, bl, en)
