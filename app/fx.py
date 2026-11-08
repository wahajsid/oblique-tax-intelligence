"""Exchange rates: ECB euro reference rates, converted to AED per unit through the USD peg.

The ECB publishes about thirty currencies against the euro once a working day (around 16:00 CET).
AED and SAR are not among them, but both are pegged to the US dollar (AED 3.6725, SAR 3.75), so
AED per X = 3.6725 x (USD per EUR) / (X per EUR). Currencies the ECB does not cover (PKR) keep the
static table value. If the feed is unreachable, or FX_FEED=off, the dated static table in
app/rules/personal.json is used and the result says so. Rates are cached in memory for six hours;
a failed fetch is cached for ten minutes so a visitor never waits on the ECB twice.
"""
from __future__ import annotations

import json
import os
import threading
import time
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import httpx

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
AED_PER_USD = Decimal("3.6725")
SAR_PER_USD = Decimal("3.75")
TTL_OK = 6 * 3600
TTL_FAIL = 600
_RULES = Path(__file__).parent / "rules" / "personal.json"
_lock = threading.Lock()
_cache: dict[str, Any] = {"table": None, "expires": 0.0}


def static_table() -> dict[str, Any]:
    with _RULES.open(encoding="utf-8") as fh:
        t = dict(json.load(fh)["fx"])
    t["live"] = False
    t["source"] = f"indicative table dated {t['as_of']}"
    return t


def parse_ecb(xml_text: str) -> tuple[str, dict[str, Decimal]]:
    """Return (date, {currency: units per EUR}) from the ECB daily XML."""
    root = ET.fromstring(xml_text)
    ns = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
    day = root.find(".//e:Cube[@time]", ns)
    if day is None:
        raise ValueError("ECB feed: no dated Cube element")
    rates = {c.get("currency"): Decimal(c.get("rate")) for c in day.findall("e:Cube", ns) if c.get("currency") and c.get("rate")}
    if "USD" not in rates:
        raise ValueError("ECB feed: USD missing")
    return day.get("time"), rates


def aed_table_from_ecb(date: str, per_eur: dict[str, Decimal], base: dict[str, Any]) -> dict[str, Any]:
    usd_per_eur = per_eur["USD"]
    out: dict[str, float] = {}
    for cur, static_value in base["aed_per_unit"].items():
        if cur == "AED":
            val = Decimal(1)
        elif cur == "USD":
            val = AED_PER_USD
        elif cur == "SAR":
            val = AED_PER_USD / SAR_PER_USD
        elif cur == "EUR":
            val = AED_PER_USD * usd_per_eur
        elif cur in per_eur:
            val = AED_PER_USD * usd_per_eur / per_eur[cur]
        else:
            out[cur] = static_value  # not published by the ECB (e.g. PKR): keep the dated table value
            continue
        out[cur] = float(val.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
    t = dict(base)
    t["aed_per_unit"] = out
    t["as_of"] = date
    t["live"] = True
    t["source"] = f"ECB euro reference rates of {date}, converted through the AED 3.6725 per USD peg"
    t["note"] = ("Rates derived from the European Central Bank's daily euro reference rates and the AED and SAR pegs to the US dollar. "
                 "Mid-market reference rates, not dealing rates; for screening only. The visitor can override the rate in the move calculator. "
                 "Currencies the ECB does not publish keep the dated table value.")
    t["review_status"] = "verified"
    return t


def table() -> dict[str, Any]:
    base = static_table()
    if os.environ.get("FX_FEED", "on").lower() in ("off", "0", "false", "no"):
        return base
    now = time.time()
    with _lock:
        if _cache["table"] is not None and now < _cache["expires"]:
            return _cache["table"]
        try:
            r = httpx.get(ECB_URL, timeout=5, headers={"Accept": "application/xml"})
            r.raise_for_status()
            date, per_eur = parse_ecb(r.text)
            t = aed_table_from_ecb(date, per_eur, base)
            _cache.update(table=t, expires=now + TTL_OK)
        except Exception:  # noqa: BLE001 - any failure means "use the dated table", never an error page
            t = base
            t["note"] = base.get("note", "") + " Live ECB rates were unavailable at the time of this calculation."
            _cache.update(table=t, expires=now + TTL_FAIL)
        return t


def reset_cache() -> None:
    with _lock:
        _cache.update(table=None, expires=0.0)
