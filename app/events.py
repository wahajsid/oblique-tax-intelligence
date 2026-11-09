"""Cookieless, first-party usage counter.

What is recorded per event: the event name, the page path, the calculator (if any), the arrival source
(utm_source), the language and the time. Nothing else: no IP address, no user agent, no cookie, no visitor
or session identifier, and never any calculator input. Visitors who send Do Not Track or Global Privacy
Control are not counted (enforced in the browser and again here).

Storage: Supabase table `events` when SUPABASE_URL and SUPABASE_SERVICE_KEY are set (DDL in
docs/SETUP_CHECKLIST.md). Counts since the last restart are also kept in memory and can be read at
/api/v1/stats?token=... when STATS_TOKEN is set.
"""
from __future__ import annotations

import os
import threading
import time
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

EventName = Literal["page_view", "calc_run", "preset_used", "refine_opened", "pdf_requested", "enquiry_opened", "enquiry_sent",
                    "call_clicked", "whatsapp_clicked", "service_clicked", "link_copied", "subscribed", "game_clicked"]


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: EventName
    path: str = Field("", max_length=200)
    calculator: str = Field("", max_length=40)
    source: str = Field("", max_length=80)
    lang: Literal["en", "ar"] = "en"
    detail: str = Field("", max_length=60, description="Preset or service slug. Never free text from the visitor.")


_lock = threading.Lock()
_counts: Counter = Counter()
_started = datetime.now(timezone.utc).isoformat(timespec="seconds")
_hits: dict[str, deque[float]] = defaultdict(deque)
LIMIT_PER_MINUTE = 60


def throttled(key: str) -> bool:
    """Per-connection flood guard. The key is a salted hash held in memory for one minute only."""
    now = time.time()
    q = _hits[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= LIMIT_PER_MINUTE:
        return True
    q.append(now)
    return False


def supabase_enabled() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


def _clean_path(path: str) -> str:
    # Keep the route only: no query string, no fragment (fragments can carry shared calculator inputs).
    return path.split("#", 1)[0].split("?", 1)[0][:200]


def record(ev: EventInput) -> dict:
    row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "name": ev.name, "path": _clean_path(ev.path),
           "calculator": ev.calculator, "source": ev.source, "lang": ev.lang, "detail": ev.detail}
    with _lock:
        _counts[(ev.name, row["calculator"] or row["path"])] += 1
    return row


def store(row: dict) -> None:
    """Runs after the response is sent. A storage failure never reaches the visitor."""
    if not supabase_enabled():
        return
    try:
        base = os.environ["SUPABASE_URL"].rstrip("/")
        key = os.environ["SUPABASE_SERVICE_KEY"]
        httpx.post(f"{base}/rest/v1/{os.environ.get('SUPABASE_EVENTS_TABLE', 'events')}", json=row, timeout=8,
                   headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=minimal"})
    except Exception:  # noqa: BLE001
        pass


def summary() -> dict:
    with _lock:
        items = sorted(_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    by_name: Counter = Counter()
    for (name, _), n in items:
        by_name[name] += n
    return {"since": _started, "persisted_to": "supabase" if supabase_enabled() else "memory only (resets on deploy)",
            "totals": dict(by_name), "by_event_and_page": [{"event": k[0], "where": k[1], "count": n} for k, n in items]}


def reset() -> None:
    with _lock:
        _counts.clear()
    _hits.clear()
