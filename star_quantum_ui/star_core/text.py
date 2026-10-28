"""Tokenising and language helpers that work for Bangla, Banglish and English."""
from __future__ import annotations

import re

# Python's \w does not match Bengali vowel signs, so split on punctuation/space instead.
_SPLIT = re.compile(r"[\s\.,;:!?()\[\]{}\"'`/\\|<>=+*&^%$#@~\-_\u0964]+")
_BN = re.compile(r"[\u0980-\u09FF]")
_BANGLISH_STRONG = {
    "ami", "amar", "amake", "amra", "amader", "amio",
    "tumi", "tomar", "tomake", "tumio", "toder", "toke", "tora",
    "apni", "apnar", "apnake",
    "se", "tar", "take", "tara", "tader", "ora", "oder", "oke",
    "kemon", "acho", "achen", "achi", "achis",
    "koro", "korbo", "korcho", "korchen", "korchi", "korte", "kore", "kora", "kori", "koris", "korlam", "korle",
    "hobe", "hocche", "hoche", "hoyeche", "holo", "hoy", "hobar",
    "ache", "nei", "keno", "kothay", "kothaye", "kokhon", "kivabe", "kibhabe", "koto", "kotota", "konta", "kon",
    "bolo", "bolun", "bolte", "bolcho", "bolchen", "bolchi", "bolbo",
    "dekho", "dekhun", "dakho", "dekhi", "dekhchi", "dekhbo",
    "shuno", "shunun", "shunbo", "shunchi", "shuncho",
    "bhalo", "valo", "khobor", "thik", "bhul", "dhonnobad",
    "ekta", "akta", "duto", "tinta", "gulo", "gula", "sob", "shob",
    "ekhon", "akhon", "tokhon", "jokhon", "pore", "aage", "age",
    "oita", "seta", "eta", "ata", "jeta", "sheta", "eita",
    "jate", "jeno", "karor", "karon", "naki", "naaki", "bujhte", "bujhechi", "bujhlam",
    "parbo", "parbe", "paro", "paren", "pari", "parchi", "parchen",
    "dao", "dite", "dibo", "debo", "diyecho", "diyechen",
    "khuje", "toiri", "pathao", "pathaw", "chole", "asho", "ashun", "ashchi", "aschhi",
    "shomoy", "somoy", "tarikh", "shagotom", "ektu", "beshi", "kom", "khub", "onek", "onak"
}

_BANGLISH_SUFFIX = re.compile(r"(?:c?h[ie]|c?hen|c?ho|bo|ben|lam|len|te|tesi|taso|si|ba)$")


def tokens(text: str) -> list[str]:
    return [t for t in _SPLIT.split(text.lower()) if t]


def trigrams(text: str) -> set[str]:
    s = " " + " ".join(tokens(text)) + " "
    return {s[i:i + 3] for i in range(len(s) - 2)}


def detect_language(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "en"
    if len(_BN.findall(text)) / len(letters) > 0.3:
        return "bn"
    words = [t for t in tokens(text) if t]
    if not words:
        return "en"
    word_set = set(words)
    if word_set & _BANGLISH_STRONG:
        return "banglish"
    # Suffix check for words of length >= 4 with particles
    if any(_BANGLISH_SUFFIX.search(w) for w in words if len(w) >= 4 and w not in {"the", "into", "onto", "with", "from", "some", "come", "home", "site", "make", "create"}):
        if any(w in {"ki", "na", "ar", "aar", "ba", "to", "o", "se", "ta"} for w in words):
            return "banglish"
    return "en"
