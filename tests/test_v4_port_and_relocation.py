"""Tests for the V4-ported behaviours (scope gate, Decimal precision, security headers)
and the new personal-tax, relocation and diagnostic modules. Expected values were
worked out by hand before the code was run."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.engine import diagnostic, gcc_compare, personal_tax, relocation, uae_ct, vat
from app.main import app

client = TestClient(app)


# ------------------------------------------------------------ scope gate -----
def test_scope_gate_marks_review_required_by_default():
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=1_000_000, revenue=10_000_000))
    assert r.outcome == "REVIEW_REQUIRED"
    assert r.outputs["corporate_tax_payable"] == 56_250.0  # figure still computed, shown greyed
    assert any(f.code == "review_required" for f in r.flags)
    assert len(r.review_reasons) >= 2


def test_scope_gate_clears_when_confirmed():
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=1_000_000, revenue=10_000_000, scope_confirmed=True, special_regime="no"))
    assert r.outcome == "ILLUSTRATIVE_ESTIMATE"
    assert r.review_reasons == []


def test_scope_gate_special_regime_yes_requires_review():
    r = vat.calculate(vat.VATInput(jurisdiction="AE", amount=1000, scope_confirmed=True, special_regime="yes"))
    assert r.outcome == "REVIEW_REQUIRED"


def test_unknown_fields_rejected():
    r = client.post("/api/v1/uae/corporate-tax", json={"accounting_profit": 1, "rate_override": 0.01})
    assert r.status_code == 422


# -------------------------------------------------------- decimal precision --
def test_three_decimal_currencies_in_gcc_compare():
    c = gcc_compare.compare(gcc_compare.GCCScenario(taxable_profit=Decimal("1000.333"), jurisdictions=["BH", "OM", "KW"], currency="AED"))
    om = next(r for r in c["rows"] if r["code"] == "OM")
    # 1000.333 x 15% = 150.04995 -> 150.05 at the scenario currency's 2 dp (AED)
    assert om["corporate_tax"] == 150.05
    from app.engine.core import money
    assert money("150.04995", "OMR") == 150.05 and money("150.0495", "OMR") == 150.05 and money("0.0005", "KWD") == 0.001


def test_half_up_rounding_not_bankers():
    from app.engine.core import money
    assert money("0.125", "AED") == 0.13
    assert money("0.0005", "BHD") == 0.001


def test_api_outputs_carry_outcome_and_persisted_false():
    d = client.post("/api/v1/vat", json={"amount": 100}).json()
    assert d["outcome"] == "REVIEW_REQUIRED" and d["persisted"] is False and d["currency_decimals"] == 2


# ------------------------------------------------------ security posture -----
def test_security_headers_and_no_store():
    r = client.get("/api/v1/health")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY" and r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cache-control"] == "no-store"
    assert "set-cookie" not in r.headers


def test_cross_origin_post_rejected_and_json_only():
    assert client.post("/api/v1/vat", json={"amount": 1}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/v1/vat", data="a=1", headers={"Content-Type": "application/x-www-form-urlencoded"}).status_code == 415
    assert client.post("/api/v1/vat", json={"amount": 1}, headers={"Content-Length": "999999"}).status_code == 413


def test_validation_errors_do_not_echo_input():
    r = client.post("/api/v1/uae/corporate-tax", json={"accounting_profit": "SECRET-VALUE-123"})
    assert r.status_code == 422
    assert "SECRET-VALUE-123" not in r.text
    assert r.json()["detail"][0]["field"] == "accounting_profit"


def test_no_third_party_assets_in_pages():
    for path in ["/", "/move", "/uae/corporate-tax"]:
        html = client.get(path).text
        assert "fonts.googleapis" not in html and "fontshare" not in html and "googletagmanager" not in html
        assert 'href="/static/css/fonts.css"' in html


def test_noindex_by_default():
    assert 'name="robots" content="noindex' in client.get("/").text
    assert "Disallow: /" in client.get("/robots.txt").text


def test_accessibility_landmarks():
    html = client.get("/uae/corporate-tax").text
    assert 'class="skip"' in html and '<main id="main"' in html and "<noscript>" in html and 'aria-live="polite"' in html


# ----------------------------------------------------------- personal tax ----
@pytest.mark.parametrize("country,gross,income_tax,total", [
    ("GB", 75_000, 17_432.00, 20_942.60),      # PA 12,570; 20% x 37,700 + 40% x 24,730; NI 8% x 37,700 + 2% x 24,730
    ("HK", 600_000, 55_500.00, 73_500.00),     # MPF 18,000; NCI 450,000 -> 58,500 progressive < 87,300 standard; less 3,000 reduction
    ("SG", 120_000, 7_835.00, 7_835.00),       # chargeable 119,000: 200 + 350 + 2,800 + 11.5% x 39,000
    ("IN", 2_000_000, 192_400.00, 192_400.00), # total income 19,25,000: 20k+40k+60k+65k = 185,000; cess 4%
    ("US", 150_000, 24_734.00, 36_209.00),     # taxable 133,900; FICA 9,300 + 2,175
    ("AU", 100_000, 20_520.00, 22_520.00),     # 15% x 26,800 + 30% x 55,000; no LITO; levy 2,000
    ("DE", 60_000, 9_832.00, 22_882.00),       # zvE 47,940 -> tariff 9,832; SV 13,050
    ("ZA", 500_000, 98_417.00, 100_542.44),    # 44,118 + 35,880 + 36,239 - 17,820; UIF 2,125.44
])
def test_personal_tax_hand_checked(country, gross, income_tax, total):
    r = personal_tax.calculate(personal_tax.PersonalTaxInput(country=country, gross_income=Decimal(gross)))
    assert r.outputs["income_tax"] == pytest.approx(income_tax, abs=0.01)
    assert r.outputs["total_deductions"] == pytest.approx(total, abs=0.01)
    assert r.outputs["net_income"] == pytest.approx(gross - total, abs=0.01)
    assert r.rule_metadata(), "personal rules must resolve to metadata"


def test_uk_personal_allowance_taper():
    r = personal_tax.calculate(personal_tax.PersonalTaxInput(country="GB", gross_income=Decimal(125_140)))
    # PA fully tapered: taxable 125,140 -> 7,540 + 40% x 87,440 = 34,976 + 7,540 = 42,516
    assert r.outputs["income_tax"] == 42_516.00


def test_india_rebate_and_marginal_relief():
    r = personal_tax.calculate(personal_tax.PersonalTaxInput(country="IN", gross_income=Decimal(1_275_000)))
    assert r.outputs["income_tax"] == 0.0  # 12,75,000 - 75,000 = 12,00,000 -> fully rebated
    r = personal_tax.calculate(personal_tax.PersonalTaxInput(country="IN", gross_income=Decimal(1_285_000)))
    # total income 12,10,000: slab tax 60,000 + 1,500 = 61,500 > 10,000 excess -> tax 10,000 + 4% cess = 10,400
    assert r.outputs["income_tax"] == 10_400.00


def test_us_person_residual_after_feie():
    r = personal_tax.calculate(personal_tax.PersonalTaxInput(country="US", gross_income=Decimal(200_000), foreign_resident_after_move=True))
    # tax(183,900) - tax(116,800) = 36,734 - 20,630 = 16,104
    assert r.outputs["income_tax"] == 16_104.00
    assert r.outputs["total_contributions"] == 0.0


def test_singapore_cpf_member():
    r = personal_tax.calculate(personal_tax.PersonalTaxInput(country="SG", gross_income=Decimal(120_000), cpf_member=True))
    # CPF 20% x 96,000 (ceiling 8,000 x 12) = 19,200; chargeable 99,800: 200+350+2,800+11.5% x 19,800 = 5,627
    assert r.outputs["income_tax"] == 5_627.00
    assert r.outputs["total_contributions"] == 19_200.00


def test_disabled_country_rejected():
    with pytest.raises(ValueError):
        personal_tax.calculate(personal_tax.PersonalTaxInput(country="PK", gross_income=Decimal(1)))
    assert client.post("/api/v1/personal-tax", json={"country": "PK", "gross_income": 1}).status_code == 422


# -------------------------------------------------------------- relocation ---
def test_relocation_uk_arithmetic():
    c = relocation.compare(relocation.RelocationInput(origin="GB", gross_income=Decimal(75_000), one_off_costs_aed=Decimal(40_000), additional_annual_costs_aed=Decimal(30_000)))
    comp = c["comparison"]
    assert comp["fx_aed_per_unit"] == 4.9
    assert comp["annual_tax_saved_aed"] == pytest.approx(20_942.60 * 4.9, abs=0.01)      # 102,618.74
    assert comp["annual_net_gain_aed"] == pytest.approx(102_618.74 - 30_000, abs=0.01)   # 72,618.74
    assert comp["first_year_gain_aed"] == pytest.approx(72_618.74 - 40_000, abs=0.01)
    assert comp["horizon_gain_aed"] == pytest.approx(72_618.74 * 5 - 40_000, abs=0.01)
    assert comp["payback_months"] == 6.6
    assert any(f["severity"] == "high" for f in c["flags"])  # residence not reviewed


def test_relocation_fx_override_and_explicit_package():
    c = relocation.compare(relocation.RelocationInput(origin="GB", gross_income=Decimal(75_000), fx_aed_per_unit=Decimal(5), uae_salary_aed=Decimal(300_000), residency_reviewed="yes", retained_connections="no"))
    assert c["comparison"]["fx_overridden"] is True
    assert c["uae"]["net_aed"] == 300_000.0
    assert c["comparison"]["annual_net_gain_aed"] == pytest.approx(300_000 - 54_057.40 * 5, abs=0.01)
    assert not any(f["severity"] == "high" for f in c["flags"])


def test_relocation_us_person_keeps_residual_tax():
    c = relocation.compare(relocation.RelocationInput(origin="US", gross_income=Decimal(200_000)))
    assert c["uae"]["tax_aed"] == pytest.approx(16_104 * 3.6725, abs=0.01)
    assert c["uae"]["residual_us"] is not None


def test_relocation_endpoint_and_pages():
    assert client.post("/api/v1/move-to-uae", json={"origin": "HK", "gross_income": 600000}).status_code == 200
    for path in ["/move", "/move/gb-to-uae", "/move/hong-kong-to-uae", "/move/usa-to-uae", "/personal-tax", "/personal-tax/DE", "/diagnose", "/privacy"]:
        assert client.get(path).status_code == 200, path
    assert client.get("/move/mars-to-uae").status_code == 404
    assert client.get("/personal-tax/PK").status_code == 404


# -------------------------------------------------------------- diagnostic ---
def test_diagnostic_deadline_precedence_and_ordering():
    answers = {k: "no" for k in diagnostic.questions("business")}
    answers.update({"deadline": "yes", "free_zone": "unknown", "related_party": "yes"})
    d = diagnostic.run(diagnostic.DiagnosticInput(profile="business", answers=answers))
    assert d["priority"] == "CHECK DEADLINE NOW"
    assert [a["key"] for a in d["actions"]] == ["deadline", "related_party", "free_zone"]


def test_diagnostic_unknown_deadline_and_clean_sheet():
    answers = {k: "no" for k in diagnostic.questions("personal")}
    assert diagnostic.run(diagnostic.DiagnosticInput(profile="personal", answers=answers))["priority"] == "KEEP RECORDS CURRENT"
    answers["deadline"] = "unknown"
    assert diagnostic.run(diagnostic.DiagnosticInput(profile="personal", answers=answers))["priority"] == "CONFIRM DEADLINES"


def test_diagnostic_requires_all_questions():
    with pytest.raises(ValueError):
        diagnostic.run(diagnostic.DiagnosticInput(profile="business", answers={"deadline": "yes"}))
    assert client.post("/api/v1/diagnostic", json={"profile": "business", "answers": {"deadline": "yes"}}).status_code == 422
    assert client.post("/api/v1/enquiries", json={}).status_code == 503
