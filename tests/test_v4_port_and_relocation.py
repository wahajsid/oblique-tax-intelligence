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
    ("HK", 600_000, 56_290.00, 74_290.00),     # 2026/27: MPF 18,000; NCI 437,000 -> 16,000 + 17% x 237,000 = 56,290 < 87,300 standard; no reduction
    ("SG", 120_000, 7_835.00, 7_835.00),       # chargeable 119,000: 200 + 350 + 2,800 + 11.5% x 39,000
    ("IN", 2_000_000, 192_400.00, 192_400.00), # TY 2026-27 (unchanged): total income 19,25,000: 20k+40k+60k+65k = 185,000; cess 4%
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
    assert client.post("/api/v1/enquiries", json={}).status_code == 410


# ------------------------------------------------ owner review, 8 Nov 2026 ----
def test_sbr_prior_period_revenue_condition():
    from datetime import date
    base = dict(accounting_profit=900_000, revenue=2_500_000, elect_small_business_relief=True, period_end=date(2027, 12, 31), scope_confirmed=True, special_regime="no")
    # a previous period above AED 3m loses the relief permanently
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(**base, prior_periods_within_threshold="no"))
    assert r.outputs["regime"] == "standard" and any(f.code == "sbr_not_available" and "previous tax period" in f.detail for f in r.flags)
    # unknown: relief applied provisionally but the result needs review
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(**base, prior_periods_within_threshold="unknown"))
    assert r.outputs["regime"] == "small_business_relief" and r.outcome == "REVIEW_REQUIRED"
    assert any("every previous tax period" in x for x in r.review_reasons)
    # confirmed: clean estimate
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(**base, prior_periods_within_threshold="yes"))
    assert r.outputs["regime"] == "small_business_relief" and r.outcome == "ILLUSTRATIVE_ESTIMATE"


def test_diagnostic_personal_profile_uses_personal_wording():
    qs = diagnostic.questions("personal")
    rec = (qs["records"]["label"] + " " + qs["records"]["help"]).lower()
    assert "corporate" not in rec and "travel" in rec
    answers = {k: "yes" for k in qs}
    d = diagnostic.run(diagnostic.DiagnosticInput(profile="personal", answers=answers))
    text = " ".join(a["action"] for a in d["actions"]).lower()
    assert "corporate tax" not in text and "trial balance" not in text and "qfzp" not in text
    assert "einvoicing" not in [a["key"] for a in d["actions"]]
    biz = diagnostic.run(diagnostic.DiagnosticInput(profile="business", answers={k: "yes" for k in diagnostic.questions("business")}))
    ein = next(a for a in biz["actions"] if a["key"] == "einvoicing")
    assert "1 January 2027" in ein["action"] and "1 July 2027" in ein["action"] and "AED 50m" in ein["action"]


def test_footer_shows_app_and_rule_versions_separately():
    html = client.get("/").text
    assert "App v" in html and "Tax rules: AE 2026.2" in html
    assert "P0</span>" not in html


# --------------------------------------------- journeys, services, confidence ----
def test_services_recommended_from_flags_and_calculator():
    from app import services
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=2_000_000, revenue=20_000_000, is_free_zone_person=True, elect_qfzp=True,
                                                     qualifying_income=1_500_000, non_qualifying_revenue=1_200_000, scope_confirmed=True, special_regime="no")).as_dict()
    assert [s["slug"] for s in r["next_steps"]][:2] == ["free_zone_review", "uae_ct_review"]
    for s in services.SERVICES.values():
        assert s["includes"] and s["receive"] and s["excludes"] and s["audience"] in ("business", "personal")
    assert services.recommend("move_to_uae", [], extra=["uk_company_review"])[0]["slug"] == "uk_company_review"


def test_confidence_block_separates_rules_calculation_and_fit():
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=1_000_000, revenue=10_000_000)).as_dict()
    c = r["confidence"]
    assert c["rules"]["status"] == "verified" and c["rules"]["reviewed_by"] == "Oblique Consult tax team"
    assert c["calculation"]["checks"] > 5 and c["calculation"]["suite_total"] > c["calculation"]["checks"]
    assert c["fit"]["confirmed"] is False and c["fit"]["reasons"]


def test_diagnostic_gcc_profile_and_next_steps():
    qs = diagnostic.questions("gcc")
    assert {"pe_risk", "wht_payments", "vat_cross_border", "deadline"} <= set(qs) and "einvoicing" not in qs
    d = diagnostic.run(diagnostic.DiagnosticInput(profile="gcc", answers={k: ("yes" if k == "pe_risk" else "no") for k in qs}))
    assert d["next_steps"][0]["slug"] == "uae_ksa_transaction"


def test_journeys_and_paths_render_with_live_examples():
    from app import journeys
    for slug in journeys.JOURNEYS:
        j = journeys.get(slug)
        assert j["example"]["rows"] and j["checklist"] and j["service"]
        assert client.get(f"/journeys/{slug}").status_code == 200
    fz = journeys.get("free-zone-selling-to-mainland")["example"]["rows"]
    assert "AED 13,500" in fz[0][1] and "AED 236,250" in fz[1][1]  # (3m-375k) x 9% once status is lost
    for path in ["/start/business", "/start/gcc", "/start/move", "/journeys", "/services", "/diagnose?profile=gcc"]:
        assert client.get(path).status_code == 200, path
    assert client.get("/start/nope").status_code == 404
    html = client.get("/").text
    assert "Check my business tax" in html and "Expand or trade across the GCC" in html and "Plan my move to the UAE" in html
    assert "/journeys/uae-saudi-transactions" in client.get("/sitemap.xml").text



def test_test_name_snapshot_is_current():
    """The confidence panel falls back to app/test_names.json when the tests folder is absent in production.
    Regenerate it whenever tests change: python -c "from app import quality; quality.write_snapshot()" """
    import json
    from app import quality
    assert json.loads(quality.SNAPSHOT.read_text()) == quality.scan_tests(), "run quality.write_snapshot()"
    assert quality.test_count("uae_corporate_tax") > 5


# ------------------------------------------------------------------ Arabic ----
def test_arabic_routes_and_fallbacks():
    from app import i18n
    r = client.get("/ar/uae/corporate-tax")
    assert r.status_code == 200 and '<html lang="ar" dir="rtl">' in r.text and "حاسبة ضريبة الشركات" in r.text
    assert 'hreflang="ar"' in r.text and 'class="lang-switch"' in r.text
    assert client.get("/ar").status_code == 200 and client.get("/ar/diagnose").status_code == 200 and client.get("/ar/guides/SA").status_code == 200
    # pages without an Arabic version redirect to English rather than showing a half-translated page
    r = client.get("/ar/move", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/move"
    # English pages are untouched
    en = client.get("/uae/corporate-tax").text
    assert '<html lang="en" dir="ltr">' in en and "حاسبة" not in en
    # translator: exact, template, fallback
    assert i18n.t("Taxable income", "ar") == "الدخل الخاضع للضريبة"
    assert i18n.t("Zakat at 2.577683% (gregorian year)", "ar").startswith("الزكاة بنسبة 2.577683%")
    assert i18n.t("Something untranslated", "ar") == "Something untranslated"
    assert "/ar/uae/corporate-tax" in client.get("/sitemap.xml").text
