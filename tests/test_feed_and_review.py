"""ECB FX feed, Turnstile, mandatory zakat warning, WHT rate display, booking fallback, diagnostic audience filter."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import fx, leads
from app.engine import diagnostic, ksa_wht, ksa_zakat, relocation
from app.main import app

ECB_XML = """<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
<Cube><Cube time="2026-11-06">
<Cube currency="USD" rate="1.1600"/><Cube currency="GBP" rate="0.8700"/><Cube currency="INR" rate="104.40"/>
<Cube currency="SGD" rate="1.4900"/><Cube currency="HKD" rate="9.0300"/><Cube currency="AUD" rate="1.7400"/><Cube currency="ZAR" rate="20.100"/>
</Cube></Cube></gesmes:Envelope>"""


class _Resp:
    def __init__(self, text): self.text = text
    def raise_for_status(self): pass


def test_ecb_feed_converts_through_the_peg(monkeypatch):
    monkeypatch.setenv("FX_FEED", "on"); fx.reset_cache()
    monkeypatch.setattr(fx.httpx, "get", lambda url, **kw: _Resp(ECB_XML))
    t = fx.table()
    assert t["live"] and t["as_of"] == "2026-11-06" and "ECB" in t["source"]
    r = t["aed_per_unit"]
    assert r["USD"] == 3.6725 and r["AED"] == 1 and r["SAR"] == pytest.approx(0.979333, abs=1e-6)
    assert r["EUR"] == pytest.approx(3.6725 * 1.16, abs=1e-6)            # 4.2601
    assert r["GBP"] == pytest.approx(3.6725 * 1.16 / 0.87, abs=1e-6)     # 4.896667
    assert r["INR"] == pytest.approx(3.6725 * 1.16 / 104.40, abs=1e-6)   # 0.040806
    assert r["PKR"] == fx.static_table()["aed_per_unit"]["PKR"]          # not published by the ECB: static value kept
    # cached: a second call does not fetch again
    monkeypatch.setattr(fx.httpx, "get", lambda url, **kw: (_ for _ in ()).throw(RuntimeError("no second fetch")))
    assert fx.table()["live"]
    fx.reset_cache()


def test_ecb_feed_falls_back_to_dated_table(monkeypatch):
    monkeypatch.setenv("FX_FEED", "on"); fx.reset_cache()
    monkeypatch.setattr(fx.httpx, "get", lambda url, **kw: (_ for _ in ()).throw(RuntimeError("offline")))
    t = fx.table()
    assert not t["live"] and t["as_of"] == fx.static_table()["as_of"] and "unavailable" in t["note"]
    fx.reset_cache()
    monkeypatch.setenv("FX_FEED", "off")
    out = relocation.compare(relocation.RelocationInput(origin="GB", gross_income=Decimal(100000)))
    assert out["comparison"]["fx_live"] is False and "indicative" in out["comparison"]["fx_source"]


def test_zakat_article_28_warning_is_mandatory():
    inp = ksa_zakat.KSAZakatInput(book_net_profit=Decimal(1_000_000), share_capital=Decimal(5_000_000), scope_confirmed=True, special_regime="no")
    r = ksa_zakat.calculate(inp).as_dict()
    assert r["outcome"] == "REVIEW_REQUIRED"
    assert any(f["code"] == "zakat_base_signoff" for f in r["flags"])
    assert any("Articles 25, 27 and 28" in x for x in r["review_reasons"])
    assert r["confidence"]["fit"]["confirmed"] is False


def test_wht_rate_display_keeps_decimals():
    inp = ksa_wht.KSAWHTInput(payments=[{"category": "royalties", "amount": 100000, "treaty_rate": 0.075}], scope_confirmed=True, special_regime="no")
    r = ksa_wht.calculate(inp).as_dict()
    labels = " ".join(s["label"] + " " + (s.get("formula") or "") for s in r["trace"])
    assert "7.5%" in labels and "8%" not in labels.replace("7.5%", "")
    assert r["outputs"]["lines"][0]["wht"] == 7500.0
    assert ksa_wht._rate(Decimal("0.15")) == "15%" and ksa_wht._rate(Decimal("0.0775")) == "7.75%"


def test_personal_diagnostic_never_recommends_business_services():
    answers = {k: "yes" for k in diagnostic.questions("personal")}
    r = diagnostic.run(diagnostic.DiagnosticInput(profile="personal", answers=answers))
    assert r["next_steps"] and all(s["audience"] == "personal" for s in r["next_steps"])
    assert not any(s["slug"] == "uae_ksa_transaction" for s in r["next_steps"])
    answers_b = {k: "yes" for k in diagnostic.questions("business")}
    rb = diagnostic.run(diagnostic.DiagnosticInput(profile="business", answers=answers_b))
    assert all(s["audience"] == "business" for s in rb["next_steps"])


def test_result_cta_links_to_booking_not_contact_form():
    c = TestClient(app)
    for path in ["/uae/corporate-tax", "/move/gb-to-uae", "/diagnose", "/gcc/compare"]:
        html = c.get(path).text
        assert "calendly.com/alina-obliqueconsult/30min?utm_source=tax-tools" in html
        assert 'data-booking="https://calendly.com' in html


def test_turnstile_gate(monkeypatch, tmp_path):
    for var in ("RESEND_API_KEY", "LEAD_WEBHOOK_URL", "HUBSPOT_PORTAL_ID", "HUBSPOT_FORM_GUID", "MS_TENANT_ID", "SUPABASE_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LEADS_SQLITE_PATH", str(tmp_path / "l.sqlite")); leads._hits.clear()
    monkeypatch.setenv("TURNSTILE_SITE_KEY", "site"); monkeypatch.setenv("TURNSTILE_SECRET", "secret")
    c = TestClient(app)
    assert c.get("/api/v1/leads/config").json()["turnstile_site_key"] == "site"
    body = {"email": "a@b.co", "topics": ["AE"], "consent_updates": True}
    assert c.post("/api/v1/subscribe", json=body).status_code == 400                     # no token
    calls = []
    class R:
        def raise_for_status(self): pass
        def json(self): return {"success": True}
    monkeypatch.setattr(leads.httpx, "post", lambda url, data=None, timeout=None, **kw: (calls.append((url, data)), R())[1])
    assert c.post("/api/v1/subscribe", json=dict(body, turnstile_token="tok")).status_code == 200
    assert calls and calls[0][0].endswith("/siteverify") and calls[0][1]["response"] == "tok"
    monkeypatch.delenv("TURNSTILE_SITE_KEY"); monkeypatch.delenv("TURNSTILE_SECRET")
    assert c.post("/api/v1/subscribe", json=body).status_code == 200                     # gate off: no token needed
