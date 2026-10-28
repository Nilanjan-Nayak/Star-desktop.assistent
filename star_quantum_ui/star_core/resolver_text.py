def tr(lang: str, bn: str, banglish: str, en: str) -> str:
    return {"bn": bn, "banglish": banglish}.get(lang, en)
