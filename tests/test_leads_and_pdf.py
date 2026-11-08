"""Lead capture (consent, sinks, rate limit, honeypot) and PDF working papers."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import leads, pdf
from app.main import app

client = TestClient(app)

LEAD = {"name": "Test Person", "email": "test@example.com", "company": "Example LLC", "consent_contact": True, "consent_marketing": False,
        "consent_version": leads.CONSENT_VERSION, "context": {"calculator": "uae_corporate_tax", "inputs": {"accounting_profit": 1500000, "revenue": 12000000}, "page_url": "https://x.test/uae/corporate-tax"}}


@pytest.fixture
def sqlite_sink(tmp_path, monkeypatch):
    path = tmp_path / "leads.sqlite"
    for var in ("RESEND_API_KEY", "LEAD_EMAIL_TO", "LEAD_WEBHOOK_URL", "HUBSPOT_PORTAL_ID", "HUBSPOT_FORM_GUID"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LEADS_SQLITE_PATH", str(path))
    leads._hits.clear()
    return path


@pytest.fixture
def m365_sink(monkeypatch):
    for var in ("RESEND_API_KEY", "LEAD_WEBHOOK_URL", "HUBSPOT_PORTAL_ID", "HUBSPOT_FORM_GUID", "LEADS_SQLITE_PATH"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MS_TENANT_ID", "tenant-id"); monkeypatch.setenv("MS_CLIENT_ID", "client-id"); monkeypatch.setenv("MS_CLIENT_SECRET", "secret")
    monkeypatch.setenv("MS_SENDER", "tax@obliqueconsult.com"); monkeypatch.setenv("LEAD_EMAIL_TO", "info@obliqueconsult.com, wahaj@obliqueconsult.com")
    calls = []

    class FakeResp:
        def __init__(self, payload): self._p = payload
        def raise_for_status(self): return None
        def json(self): return self._p

    def fake_post(url, **kw):
        calls.append((url, kw))
        return FakeResp({"access_token": "tok"} if "oauth2" in url else {})
    monkeypatch.setattr(leads.httpx, "post", fake_post)
    leads._hits.clear()
    return calls


@pytest.fixture
def no_sink(monkeypatch):
    for var in ("RESEND_API_KEY", "LEAD_EMAIL_TO", "LEAD_WEBHOOK_URL", "HUBSPOT_PORTAL_ID", "HUBSPOT_FORM_GUID", "LEADS_SQLITE_PATH"):
        monkeypatch.delenv(var, raising=False)
    leads._hits.clear()


# ---------------------------------------------------------------- PDF --------
@pytest.mark.parametrize("calculator,inputs", [
    ("uae_corporate_tax", {"accounting_profit": 1500000, "revenue": 12000000}),
    ("vat", {"jurisdiction": "AE", "amount": 1000}),
    ("ksa_zakat_income_tax", {"share_capital": 4000000, "book_net_profit": 1000000}),
    ("ksa_withholding_tax", {"payments": [{"category": "royalties", "amount": 100000}]}),
    ("personal_income_tax", {"country": "GB", "gross_income": 75000}),
    ("move_to_uae", {"origin": "US", "gross_income": 200000}),
    ("gcc_compare", {"taxable_profit": 1000000}),
    ("tax_exposure_diagnostic", {"profile": "personal", "answers": {"deadline": "yes", "cross_border": "no", "residency": "unknown", "eligibility": "no", "records": "no"}}),
])
def test_pdf_renders_for_every_calculator(calculator, inputs):
    data, res = pdf.render_pdf(calculator, inputs, prepared_for="QA")
    assert data[:5] == b"%PDF-" and len(data) > 3000
    assert res  # recomputed, not echoed


def test_pdf_recomputes_and_ignores_client_figures():
    # Inputs decide the figures; nothing in the request can set an output value.
    data, res = pdf.render_pdf("uae_corporate_tax", {"accounting_profit": 1000000, "revenue": 10000000, "scope_confirmed": True, "special_regime": "no"})
    assert res["outputs"]["corporate_tax_payable"] == 56250.0
    with pytest.raises(Exception):
        pdf.render_pdf("uae_corporate_tax", {"accounting_profit": 1, "corporate_tax_payable": 0})  # extra='forbid'


def test_pdf_endpoint_free_when_no_sink(no_sink):
    r = client.post("/api/v1/pdf", json={"calculator": "vat", "inputs": {"amount": 100}})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:5] == b"%PDF-"
    assert "attachment" in r.headers["content-disposition"]
    assert client.post("/api/v1/pdf", json={"calculator": "nope", "inputs": {}}).status_code == 422
    assert client.post("/api/v1/pdf", json={"calculator": "vat", "inputs": {"amount": "x"}}).status_code == 422


# -------------------------------------------------------------- leads --------
def test_leads_disabled_without_sink(no_sink):
    assert client.get("/api/v1/leads/config").json()["enabled"] is False
    assert client.post("/api/v1/leads", json=LEAD).status_code == 503


def test_lead_flow_with_sqlite_sink(sqlite_sink):
    cfg = client.get("/api/v1/leads/config").json()
    assert cfg["enabled"] is True and cfg["consent_version"] == leads.CONSENT_VERSION and "contact" in cfg["consent_text"]
    # PDF now gated
    assert client.post("/api/v1/pdf", json={"calculator": "vat", "inputs": {"amount": 100}}).status_code == 403
    r = client.post("/api/v1/leads", json=LEAD)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "received" and j["delivery"] == {"sqlite": "ok"} and j["pdf_token"]
    # token unlocks the PDF
    r2 = client.post("/api/v1/pdf", json={"calculator": "uae_corporate_tax", "inputs": LEAD["context"]["inputs"], "token": j["pdf_token"]})
    assert r2.status_code == 200 and r2.content[:5] == b"%PDF-"
    assert client.post("/api/v1/pdf", json={"calculator": "vat", "inputs": {"amount": 1}, "token": "bad:1:2"}).status_code == 403
    # stored record carries consent text, version and timestamp, hashed IP only
    con = sqlite3.connect(sqlite_sink)
    rows = con.execute("SELECT record FROM leads").fetchall(); con.close()
    assert len(rows) == 1
    rec = json.loads(rows[0][0])
    assert rec["consents"]["contact"] == {"given": True, "version": leads.CONSENT_VERSION, "text": leads.CONSENT_TEXT["contact"], "at": rec["consents"]["contact"]["at"]}
    assert rec["consents"]["marketing"]["given"] is False and rec["consents"]["marketing"]["at"] is None
    assert "ip_hash" in rec and "ip" not in rec and rec["context"]["calculator"] == "uae_corporate_tax"


def test_lead_requires_contact_consent_and_valid_email(sqlite_sink):
    bad = dict(LEAD, consent_contact=False)
    assert client.post("/api/v1/leads", json=bad).status_code == 422
    bad = dict(LEAD, email="not-an-email")
    assert client.post("/api/v1/leads", json=bad).status_code == 422
    r = client.post("/api/v1/leads", json=dict(LEAD, extra_field=1))
    assert r.status_code == 422


def test_lead_honeypot_and_rate_limit(sqlite_sink, monkeypatch):
    hp = client.post("/api/v1/leads", json=dict(LEAD, website="http://spam"))
    assert hp.status_code == 200 and hp.json()["pdf_token"] is None  # silently dropped
    con = sqlite3.connect(sqlite_sink)
    assert con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='leads'").fetchone()[0] == 0  # nothing was ever stored
    con.close()
    monkeypatch.setenv("LEAD_RATE_LIMIT_PER_HOUR", "2")
    leads._hits.clear()
    assert client.post("/api/v1/leads", json=LEAD).status_code == 200
    assert client.post("/api/v1/leads", json=LEAD).status_code == 200
    assert client.post("/api/v1/leads", json=LEAD).status_code == 429


def test_lead_delivery_failure_reported(sqlite_sink, monkeypatch):
    monkeypatch.setenv("LEADS_SQLITE_PATH", "/nonexistent-dir/leads.sqlite")
    assert client.post("/api/v1/leads", json=LEAD).status_code == 502


def test_pdf_token_expiry():
    t = leads.pdf_token("abc", ttl_seconds=-1)
    assert leads.verify_pdf_token(t) is False
    assert leads.verify_pdf_token(leads.pdf_token("abc")) is True


def test_old_enquiries_endpoint_gone():
    assert client.post("/api/v1/enquiries", json={}).status_code == 410


def test_pages_include_dialog_and_pdf_button(no_sink):
    html = client.get("/uae/corporate-tax").text
    assert 'id="lead-modal"' in html and 'id="btn-pdf"' in html and 'name="consent_marketing"' in html


def test_lead_profile_recorded(sqlite_sink):
    r = client.post("/api/v1/leads", json=dict(LEAD, profile="personal", interest="relocation", company=""))
    assert r.status_code == 200
    con = sqlite3.connect(sqlite_sink)
    rec = json.loads(con.execute("SELECT record FROM leads ORDER BY received_at DESC").fetchone()[0]); con.close()
    assert rec["profile"] == "personal" and rec["interest"] == "relocation"


def test_m365_sink_sends_via_graph_with_pdf(m365_sink):
    assert client.get("/api/v1/leads/config").json()["processors"] == ["m365"]
    r = client.post("/api/v1/leads", json=LEAD)
    assert r.status_code == 200 and r.json()["delivery"] == {"m365": "ok"}
    token_call, send_call = m365_sink
    assert token_call[0] == "https://login.microsoftonline.com/tenant-id/oauth2/v2.0/token"
    assert token_call[1]["data"]["grant_type"] == "client_credentials"
    assert send_call[0] == "https://graph.microsoft.com/v1.0/users/tax@obliqueconsult.com/sendMail"
    assert send_call[1]["headers"]["Authorization"] == "Bearer tok"
    msg = send_call[1]["json"]["message"]
    assert [x["emailAddress"]["address"] for x in msg["toRecipients"]] == ["info@obliqueconsult.com", "wahaj@obliqueconsult.com"]
    assert msg["replyTo"][0]["emailAddress"]["address"] == "test@example.com"
    assert msg["attachments"][0]["name"] == "oblique-working-paper-uae-corporate-tax.pdf" and msg["attachments"][0]["contentType"] == "application/pdf"
    assert "SECRET" not in str(send_call[1]) and "secret" not in send_call[1]["headers"]["Authorization"]
