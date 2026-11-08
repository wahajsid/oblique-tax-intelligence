"""Consent-led lead capture.

Principles:
- Nothing is collected unless at least one delivery sink is configured by environment
  variable; the UI hides the form and the API returns 503 otherwise.
- Contact consent is required and separate from an unticked marketing consent. The
  exact consent text version and timestamp are stored with every lead.
- The calculation context (calculator + inputs) travels with the lead only because the
  visitor asked for the working paper; it is what makes the enquiry useful to Oblique.
- Spam controls: honeypot field, per-IP rate limit, payload size limits.

Sinks (any combination):
  MS_TENANT_ID + MS_CLIENT_ID + MS_CLIENT_SECRET + MS_SENDER + LEAD_EMAIL_TO
                                                        Microsoft 365 (Graph sendMail) from your own @obliqueconsult.com mailbox, PDF attached
  RESEND_API_KEY + LEAD_EMAIL_TO [+ LEAD_EMAIL_FROM]   email via Resend with the PDF attached (needs domain DNS records)
  LEAD_WEBHOOK_URL [+ LEAD_WEBHOOK_SECRET]              JSON POST (Zapier, Make, Slack, n8n...)
  HUBSPOT_PORTAL_ID + HUBSPOT_FORM_GUID                 HubSpot Forms submission (legal consent included)
  LEADS_SQLITE_PATH                                     append to a SQLite file (mount a volume)
Other:
  APP_SECRET                                            HMAC key for PDF tokens and IP hashing
  LEAD_RATE_LIMIT_PER_HOUR                              default 5 per IP
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

CONSENT_VERSION = "2026-11-08.1"
CONSENT_TEXT = {
    "updates": "Oblique Consult may email me when the tax rules behind these calculators change. One message per change, unsubscribe in every email.",
    "contact": ("I agree that Oblique Consult may contact me about this enquiry and may process the details and the calculation "
                "I submitted for that purpose. I can withdraw this at any time by emailing info@obliqueconsult.com."),
    "marketing": ("Optional: I would also like to receive occasional GCC tax updates from Oblique Consult. I can unsubscribe at any time."),
}
RETENTION = "Enquiry records are kept for 24 months from last contact, then deleted unless an engagement follows."

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,}$")
_APP_SECRET = os.environ.get("APP_SECRET") or secrets.token_hex(32)


class LeadContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calculator: str = Field(..., max_length=40)
    inputs: dict[str, Any] = Field(default_factory=dict)
    page_url: str = Field("", max_length=2000)
    source: str = Field("", max_length=80, description="utm_source captured on arrival, e.g. website, game, linkedin")
    shared_inputs: bool = Field(True, description="Whether the visitor chose to attach calculation inputs")


class LeadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=2, max_length=80)
    email: str = Field(..., max_length=160)
    phone: str = Field("", max_length=40)
    company: str = Field("", max_length=120)
    message: str = Field("", max_length=1000)
    interest: Literal["working_paper", "expert_review", "relocation", "diagnostic", "other"] = "working_paper"
    profile: Literal["business", "personal"] = "business"
    service: str = Field("", max_length=40, description="Service slug the visitor chose, if any")
    consent_contact: bool
    consent_marketing: bool = False
    consent_version: str = Field(CONSENT_VERSION, max_length=20)
    context: LeadContext
    website: str = Field("", max_length=200)  # honeypot: must stay empty
    turnstile_token: str = Field("", max_length=4000)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v.lower()

    @field_validator("consent_contact")
    @classmethod
    def _consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Contact consent is required to send your working paper")
        return v


class SubscribeInput(BaseModel):
    """Rule-change notifications. Email only; topics name the rulesets to follow."""
    model_config = ConfigDict(extra="forbid")
    email: str = Field(..., max_length=160)
    topics: list[Literal["AE", "SA", "GCC", "Personal"]] = Field(..., min_length=1, max_length=4)
    consent_updates: bool
    consent_version: str = Field(CONSENT_VERSION, max_length=20)
    page_url: str = Field("", max_length=2000)
    source: str = Field("", max_length=80)
    website: str = Field("", max_length=200)  # honeypot
    turnstile_token: str = Field("", max_length=4000)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v.lower()

    @field_validator("consent_updates")
    @classmethod
    def _consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Tick the box so we may email you when the rules change")
        return v


def make_subscription_record(sub: SubscribeInput, ip: str) -> dict[str, Any]:
    """Shaped like an enquiry record so every configured sink can carry it unchanged."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "id": str(uuid.uuid4()), "received_at": now, "source": "oblique-tax-intelligence",
        "name": "Rule-change subscriber", "email": sub.email, "phone": "", "company": "",
        "message": "Notify when these rulesets change: " + ", ".join(sub.topics), "interest": "other", "profile": "business", "service": "rule_updates",
        "consents": {
            "contact": {"given": True, "version": sub.consent_version, "text": CONSENT_TEXT["updates"], "at": now},
            "marketing": {"given": False, "version": sub.consent_version, "text": CONSENT_TEXT["marketing"], "at": None},
        },
        "context": {"calculator": "rule_updates", "inputs": {"topics": sub.topics}, "page_url": sub.page_url, "source": sub.source, "shared_inputs": False},
        "ip_hash": ip_hash(ip), "retention": RETENTION,
    }


# ------------------------------------------------------------------ config -----
def sinks_configured() -> dict[str, bool]:
    e = os.environ.get
    return {
        "m365": bool(e("MS_TENANT_ID") and e("MS_CLIENT_ID") and e("MS_CLIENT_SECRET") and e("MS_SENDER") and e("LEAD_EMAIL_TO")),
        "email": bool(e("RESEND_API_KEY") and e("LEAD_EMAIL_TO")),
        "webhook": bool(e("LEAD_WEBHOOK_URL")),
        "hubspot": bool(e("HUBSPOT_PORTAL_ID") and e("HUBSPOT_FORM_GUID")),
        "supabase": bool(e("SUPABASE_URL") and e("SUPABASE_SERVICE_KEY")),
        "sqlite": bool(e("LEADS_SQLITE_PATH")),
    }


def enabled() -> bool:
    return any(sinks_configured().values())


# --------------------------------------------------------------- Turnstile -----
def turnstile_enabled() -> bool:
    return bool(os.environ.get("TURNSTILE_SITE_KEY") and os.environ.get("TURNSTILE_SECRET"))


def verify_turnstile(token: str, ip: str) -> bool:
    """Cloudflare Turnstile server-side check. Only called when TURNSTILE_SECRET is set."""
    if not token:
        return False
    try:
        r = httpx.post("https://challenges.cloudflare.com/turnstile/v0/siteverify",
                       data={"secret": os.environ["TURNSTILE_SECRET"], "response": token, "remoteip": ip}, timeout=10)
        r.raise_for_status()
        return bool(r.json().get("success"))
    except Exception:  # noqa: BLE001 - a Cloudflare outage must not accept spam, nor crash
        return False


def public_config() -> dict[str, Any]:
    return {"enabled": enabled(), "turnstile_site_key": os.environ.get("TURNSTILE_SITE_KEY", "") if turnstile_enabled() else "", "consent_version": CONSENT_VERSION, "consent_text": CONSENT_TEXT, "retention": RETENTION,
            "controller": "Oblique Consult, Dubai and Sharjah, United Arab Emirates", "contact": "info@obliqueconsult.com",
            "processors": [k for k, v in sinks_configured().items() if v and k != "sqlite"]}


# -------------------------------------------------------------- rate limit -----
_hits: dict[str, deque[float]] = defaultdict(deque)


def rate_limited(ip: str) -> bool:
    limit = int(os.environ.get("LEAD_RATE_LIMIT_PER_HOUR", "5"))
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def ip_hash(ip: str) -> str:
    return hmac.new(_APP_SECRET.encode(), ip.encode(), hashlib.sha256).hexdigest()[:24]


# ------------------------------------------------------------------ tokens -----
def pdf_token(lead_id: str, ttl_seconds: int = 900) -> str:
    exp = int(time.time()) + ttl_seconds
    msg = f"{lead_id}:{exp}"
    sig = hmac.new(_APP_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{msg}:{sig}"


def verify_pdf_token(token: str) -> bool:
    try:
        lead_id, exp, sig = token.split(":")
        if int(exp) < time.time():
            return False
        expected = hmac.new(_APP_SECRET.encode(), f"{lead_id}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]
        return hmac.compare_digest(sig, expected)
    except (ValueError, AttributeError):
        return False


# ------------------------------------------------------------------ record -----
def make_record(lead: LeadInput, ip: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "id": str(uuid.uuid4()), "received_at": now, "source": "oblique-tax-intelligence",
        "name": lead.name.strip(), "email": lead.email, "phone": lead.phone.strip(), "company": lead.company.strip(),
        "message": lead.message.strip(), "interest": lead.interest, "profile": lead.profile, "service": lead.service,
        "consents": {
            "contact": {"given": True, "version": lead.consent_version, "text": CONSENT_TEXT["contact"], "at": now},
            "marketing": {"given": bool(lead.consent_marketing), "version": lead.consent_version, "text": CONSENT_TEXT["marketing"], "at": now if lead.consent_marketing else None},
        },
        "context": lead.context.model_dump(), "ip_hash": ip_hash(ip), "retention": RETENTION,
    }


# ------------------------------------------------------------------- sinks -----
def _email_html(rec: dict[str, Any], summary: str) -> str:
    c = rec["context"]
    rows = "".join(f"<tr><td style='padding:4px 10px 4px 0;color:#666'>{k}</td><td style='padding:4px 0'>{v}</td></tr>" for k, v in [
        ("Name", rec["name"]), ("Email", rec["email"]), ("Phone", rec["phone"] or "—"), ("Company", rec["company"] or "—"),
        ("Interest", rec["interest"]), ("Service", rec.get("service") or "—"), ("Enquiring as", rec.get("profile", "business")), ("Source", c.get("source") or "—"), ("Message", rec["message"] or "—"), ("Calculator", c["calculator"]), ("Page", c["page_url"] or "—"),
        ("Contact consent", f"yes · {rec['consents']['contact']['version']} · {rec['consents']['contact']['at']}"),
        ("Marketing consent", "yes" if rec["consents"]["marketing"]["given"] else "no"), ("Lead id", rec["id"])])
    return (f"<h2 style='font-family:sans-serif'>New enquiry from Oblique Tax Intelligence</h2><p style='font-family:sans-serif'>{summary}</p>"
            f"<table style='font-family:sans-serif;font-size:14px'>{rows}</table>"
            f"<pre style='font-size:11px;background:#f4f6f9;padding:10px'>{json.dumps(c['inputs'], indent=1)}</pre>")


def _send_email(rec: dict[str, Any], summary: str, pdf: bytes | None, filename: str) -> None:
    payload: dict[str, Any] = {
        "from": os.environ.get("LEAD_EMAIL_FROM", "Oblique Tax Intelligence <onboarding@resend.dev>"),
        "to": [a.strip() for a in os.environ["LEAD_EMAIL_TO"].split(",") if a.strip()],
        "reply_to": rec["email"],
        "subject": f"Tax Intelligence enquiry: {rec['name']} · {rec['context']['calculator']}",
        "html": _email_html(rec, summary),
    }
    if pdf:
        payload["attachments"] = [{"filename": filename, "content": base64.b64encode(pdf).decode()}]
    r = httpx.post("https://api.resend.com/emails", json=payload, headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"}, timeout=15)
    r.raise_for_status()


def _graph_token() -> str:
    tenant = os.environ["MS_TENANT_ID"]
    r = httpx.post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token", data={
        "client_id": os.environ["MS_CLIENT_ID"], "client_secret": os.environ["MS_CLIENT_SECRET"],
        "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"}, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]


def _send_m365(rec: dict[str, Any], summary: str, pdf: bytes | None, filename: str) -> None:
    """Send from an Exchange Online mailbox via Microsoft Graph (application permission Mail.Send,
    ideally restricted to MS_SENDER with an ApplicationAccessPolicy)."""
    token = _graph_token()
    sender = os.environ["MS_SENDER"]
    recipients = [{"emailAddress": {"address": a.strip()}} for a in os.environ["LEAD_EMAIL_TO"].split(",") if a.strip()]
    message: dict[str, Any] = {
        "subject": f"Tax Intelligence enquiry: {rec['name']} · {rec['context']['calculator']}",
        "body": {"contentType": "HTML", "content": _email_html(rec, summary)},
        "toRecipients": recipients,
        "replyTo": [{"emailAddress": {"address": rec["email"], "name": rec["name"]}}],
    }
    if pdf:
        message["attachments"] = [{"@odata.type": "#microsoft.graph.fileAttachment", "name": filename, "contentType": "application/pdf",
                                   "contentBytes": base64.b64encode(pdf).decode()}]
    r = httpx.post(f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail", json={"message": message, "saveToSentItems": True},
                   headers={"Authorization": f"Bearer {token}"}, timeout=20)
    r.raise_for_status()


def _send_webhook(rec: dict[str, Any], summary: str, pdf: bytes | None, filename: str) -> None:
    body = dict(rec, summary=summary)
    if pdf and os.environ.get("LEAD_WEBHOOK_INCLUDE_PDF", "false").lower() in ("1", "true", "yes"):
        body["pdf"] = {"filename": filename, "content_base64": base64.b64encode(pdf).decode()}
    headers = {"Content-Type": "application/json"}
    raw = json.dumps(body).encode()
    if os.environ.get("LEAD_WEBHOOK_SECRET"):
        headers["X-Signature-256"] = hmac.new(os.environ["LEAD_WEBHOOK_SECRET"].encode(), raw, hashlib.sha256).hexdigest()
    r = httpx.post(os.environ["LEAD_WEBHOOK_URL"], content=raw, headers=headers, timeout=15)
    r.raise_for_status()


def _send_hubspot(rec: dict[str, Any], summary: str, pdf: bytes | None, filename: str) -> None:
    first, _, last = rec["name"].partition(" ")
    fields = [{"name": "email", "value": rec["email"]}, {"name": "firstname", "value": first}, {"name": "lastname", "value": last},
              {"name": "phone", "value": rec["phone"]}, {"name": "company", "value": rec["company"]},
              {"name": "message", "value": f"{summary}\n\n{rec['message']}\n\nCalculator: {rec['context']['calculator']}\nInputs: {json.dumps(rec['context']['inputs'])}"}]
    legal: dict[str, Any] = {"consent": {"consentToProcess": True, "text": CONSENT_TEXT["contact"], "communications": []}}
    sub_id = os.environ.get("HUBSPOT_SUBSCRIPTION_TYPE_ID")
    if sub_id:
        legal["consent"]["communications"].append({"value": bool(rec["consents"]["marketing"]["given"]), "subscriptionTypeId": int(sub_id), "text": CONSENT_TEXT["marketing"]})
    body = {"fields": [f for f in fields if f["value"]], "context": {"pageUri": rec["context"]["page_url"] or None, "pageName": "Oblique Tax Intelligence"}, "legalConsentOptions": legal}
    url = f"https://api.hsforms.com/submissions/v3/integration/submit/{os.environ['HUBSPOT_PORTAL_ID']}/{os.environ['HUBSPOT_FORM_GUID']}"
    r = httpx.post(url, json=body, timeout=15)
    r.raise_for_status()


def _store_supabase(rec: dict[str, Any], summary: str, pdf: bytes | None, filename: str) -> None:
    """Insert one row into a Supabase (PostgREST) table. Table DDL is in docs/SETUP_CHECKLIST.md.
    Uses the service-role key server-side only; the PDF is never stored."""
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_KEY"]
    table = os.environ.get("SUPABASE_TABLE", "leads")
    row = {"id": rec["id"], "received_at": rec["received_at"], "kind": "subscription" if rec.get("service") == "rule_updates" else "enquiry",
           "name": rec["name"], "email": rec["email"], "phone": rec["phone"], "company": rec["company"], "message": rec["message"],
           "interest": rec["interest"], "profile": rec["profile"], "service": rec.get("service", ""), "calculator": rec["context"]["calculator"],
           "source": rec["context"].get("source", ""), "page_url": rec["context"].get("page_url", ""), "summary": summary,
           "consent_contact": rec["consents"]["contact"], "consent_marketing": rec["consents"]["marketing"],
           "inputs": rec["context"]["inputs"] if rec["context"].get("shared_inputs", True) else None,
           "ip_hash": rec["ip_hash"], "retention": rec["retention"]}
    r = httpx.post(f"{base}/rest/v1/{table}", json=row, timeout=15,
                   headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=minimal"})
    r.raise_for_status()


def _store_sqlite(rec: dict[str, Any], summary: str, pdf: bytes | None, filename: str) -> None:
    path = os.environ["LEADS_SQLITE_PATH"]
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE IF NOT EXISTS leads (id TEXT PRIMARY KEY, received_at TEXT, email TEXT, record TEXT)")
        con.execute("INSERT INTO leads VALUES (?,?,?,?)", (rec["id"], rec["received_at"], rec["email"], json.dumps(rec)))
        con.commit()
    finally:
        con.close()


SINKS = {"m365": _send_m365, "email": _send_email, "webhook": _send_webhook, "hubspot": _send_hubspot, "supabase": _store_supabase, "sqlite": _store_sqlite}


def deliver(rec: dict[str, Any], summary: str, pdf: bytes | None, filename: str) -> dict[str, str]:
    """Run every configured sink. Returns per-sink status; raises if ALL fail."""
    status: dict[str, str] = {}
    for name, on in sinks_configured().items():
        if not on:
            continue
        try:
            SINKS[name](rec, summary, pdf, filename)
            status[name] = "ok"
        except Exception as exc:  # noqa: BLE001 - we report, never crash the visitor's request
            status[name] = f"failed: {type(exc).__name__}"
    if status and all(v != "ok" for v in status.values()):
        raise RuntimeError("Lead delivery failed for every configured destination")
    return status
