"""Facts about how well the engine is tested, read from the test suite itself so they cannot go stale."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent / "tests"
KEYWORDS = {
    "uae_corporate_tax": ["uae_ct", "sbr", "qfzp"], "vat": ["vat"], "ksa_zakat_income_tax": ["ksa_zakat", "zakat"],
    "ksa_withholding_tax": ["ksa_wht", "wht"], "gcc_compare": ["gcc_compare", "gcc"], "personal_income_tax": ["personal_tax", "personal"],
    "move_to_uae": ["relocation"], "tax_exposure_diagnostic": ["diagnostic"],
}


SNAPSHOT = Path(__file__).resolve().parent / "test_names.json"


def scan_tests() -> list[str]:
    out: list[str] = []
    if TESTS.exists():
        for f in sorted(TESTS.glob("test_*.py")):
            out += re.findall(r"^def (test_\w+)", f.read_text(encoding="utf-8"), flags=re.M)
    return out


@lru_cache(maxsize=None)
def _tests() -> list[str]:
    """Prefer the live test files; fall back to the committed snapshot (kept current by a test)."""
    live = scan_tests()
    if live:
        return live
    if SNAPSHOT.exists():
        import json
        return json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return []


def test_count(calculator: str | None) -> int:
    names = _tests()
    if calculator is None:
        return len(names)
    kws = KEYWORDS.get(calculator, [calculator])
    return sum(1 for n in names if any(k in n for k in kws))


def write_snapshot() -> int:
    import json
    names = scan_tests()
    SNAPSHOT.write_text(json.dumps(names, indent=0) + "\n", encoding="utf-8")
    return len(names)
