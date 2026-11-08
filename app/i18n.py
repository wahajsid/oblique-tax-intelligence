"""Arabic (and future) translations.

Keys are the English source strings, so templates read naturally and anything
untranslated falls back to English instead of a blank. Dynamic engine strings
("... (60%)") are matched against templates with {} placeholders.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

I18N_DIR = Path(__file__).resolve().parent / "i18n"
LANGS = {"en": {"dir": "ltr", "name": "English", "native": "English"}, "ar": {"dir": "rtl", "name": "Arabic", "native": "العربية"}}

# Pages available in Arabic (path without the /ar prefix). Anything else under /ar/ falls back to English.
AR_PATHS = {"/", "/uae/corporate-tax", "/vat", "/ksa/zakat-income-tax", "/ksa/withholding-tax", "/guides/AE", "/guides/SA", "/diagnose"}


@lru_cache(maxsize=None)
def catalog(lang: str) -> dict[str, str]:
    path = I18N_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    flat: dict[str, str] = {}
    for section in data.values():
        if isinstance(section, dict):
            flat.update(section)
    return flat


@lru_cache(maxsize=None)
def _patterns(lang: str) -> list[tuple[re.Pattern[str], str]]:
    out = []
    for k, v in catalog(lang).items():
        if "{}" in k:
            parts = [re.escape(p) for p in k.split("{}")]
            out.append((re.compile("^" + "(.+?)".join(parts) + "$"), v))
    return out


def t(text: str, lang: str = "en") -> str:
    """Translate an exact string; placeholder templates are tried for dynamic strings."""
    if lang == "en" or not text:
        return text
    cat = catalog(lang)
    if text in cat:
        return cat[text]
    for pat, template in _patterns(lang):
        m = pat.match(text)
        if m:
            out = template
            for g in m.groups():
                out = out.replace("{}", g, 1)
            return out
    return text


def client_catalog(lang: str) -> dict[str, Any]:
    """What the browser needs to translate engine output: exact strings plus templates."""
    if lang == "en":
        return {}
    return catalog(lang)
