"""Hand-checked expectations for every calculator. Each number below was worked
out independently of the code, so a passing test means the engine agrees with
the arithmetic, not just with itself."""
import pytest

from app.engine import gcc_compare, ksa_wht, ksa_zakat, uae_ct, vat


# ---------------------------------------------------------------- UAE CT -----
def test_uae_ct_standard_bands():
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=1_000_000, revenue=10_000_000))
    # (1,000,000 - 375,000) x 9% = 56,250
    assert r.outputs["corporate_tax_payable"] == 56_250.0
    assert r.outputs["regime"] == "standard"
    assert r.outputs["effective_tax_rate_on_accounting_profit"] == pytest.approx(0.0563, abs=1e-4)


def test_uae_ct_below_threshold_is_zero():
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=300_000, revenue=5_000_000))
    assert r.outputs["corporate_tax_payable"] == 0.0


def test_uae_ct_reconciling_items():
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(
        accounting_profit=1_000_000, revenue=8_000_000,
        non_deductible_expenses=50_000, entertainment_expenses=100_000, exempt_income=200_000))
    # 1,000,000 + 50,000 + 50,000 - 200,000 = 900,000 ; (900,000-375,000) x 9% = 47,250
    assert r.outputs["taxable_income"] == 900_000.0
    assert r.outputs["corporate_tax_payable"] == 47_250.0


def test_uae_ct_loss_relief_capped_at_75pct():
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=1_000_000, revenue=8_000_000, brought_forward_losses=2_000_000))
    # offset capped at 75% x 1,000,000 = 750,000 -> taxable 250,000 (< 375k) -> tax 0 ; losses c/f 1,250,000
    assert r.outputs["losses_utilised"] == 750_000.0
    assert r.outputs["taxable_income"] == 250_000.0
    assert r.outputs["corporate_tax_payable"] == 0.0
    assert r.outputs["losses_carried_forward"] == 1_250_000.0


def test_uae_ct_small_business_relief():
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=900_000, revenue=2_500_000, elect_small_business_relief=True))
    assert r.outputs["regime"] == "small_business_relief"
    assert r.outputs["corporate_tax_payable"] == 0.0


def test_uae_ct_small_business_relief_available_for_2027_to_2029_periods():
    from datetime import date
    for end in (date(2027, 12, 31), date(2028, 6, 30), date(2029, 12, 31)):
        r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=900_000, revenue=2_500_000, elect_small_business_relief=True, period_end=end))
        assert r.outputs["regime"] == "small_business_relief", end
        assert r.outputs["corporate_tax_payable"] == 0.0
        assert not any(f.code == "sbr_not_available" for f in r.flags)
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=900_000, revenue=2_500_000, elect_small_business_relief=True, period_end=date(2030, 12, 31)))
    assert r.outputs["regime"] == "standard" and any(f.code == "sbr_not_available" for f in r.flags)


def test_uae_ct_small_business_relief_refused_over_revenue():
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=900_000, revenue=3_000_001, elect_small_business_relief=True))
    assert r.outputs["regime"] == "standard"
    assert any(f.code == "sbr_not_available" for f in r.flags)
    assert r.outputs["corporate_tax_payable"] == (900_000 - 375_000) * 0.09


def test_uae_ct_qfzp_no_zero_band():
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(
        accounting_profit=2_000_000, revenue=20_000_000, is_free_zone_person=True, elect_qfzp=True,
        qualifying_income=1_500_000, non_qualifying_revenue=800_000))
    # de minimis cap = min(5% x 20m = 1m, 5m) = 1m ; 800k within cap -> QFZP
    # non-qualifying taxable income = 2,000,000 - 1,500,000 = 500,000 x 9% = 45,000 (no 375k band)
    assert r.outputs["regime"] == "qfzp"
    assert r.outputs["corporate_tax_payable"] == 45_000.0


def test_uae_ct_qfzp_de_minimis_breach_falls_back_to_standard():
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(
        accounting_profit=2_000_000, revenue=20_000_000, is_free_zone_person=True, elect_qfzp=True,
        qualifying_income=1_500_000, non_qualifying_revenue=1_200_000))
    assert r.outputs["regime"] == "standard"
    assert any(f.code == "qfzp_de_minimis_breached" and f.severity == "high" for f in r.flags)
    assert r.outputs["corporate_tax_payable"] == (2_000_000 - 375_000) * 0.09


def test_uae_ct_interest_limitation():
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(
        accounting_profit=10_000_000, revenue=100_000_000, net_interest_expense=20_000_000, tax_ebitda=50_000_000))
    # cap = max(30% x 50m = 15m, 12m) = 15m ; disallowed 5m ; taxable 15m ; (15m-375k) x 9% = 1,316,250
    assert r.outputs["taxable_income"] == 15_000_000.0
    assert r.outputs["corporate_tax_payable"] == 1_316_250.0


def test_uae_ct_dmtt_screen():
    r = uae_ct.calculate(uae_ct.UAECorporateTaxInput(
        accounting_profit=100_000_000, revenue=500_000_000, is_mne_constituent=True, mne_group_revenue_eur=900_000_000))
    ct = (100_000_000 - 375_000) * 0.09  # 8,966,250
    assert r.outputs["corporate_tax_payable"] == ct
    assert r.outputs["dmtt_in_scope"] is True
    assert r.outputs["dmtt_top_up_estimate"] == pytest.approx(15_000_000 - ct)


def test_uae_ct_result_has_trace_and_rules():
    d = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=500_000, revenue=1_000_000)).as_dict()
    assert d["trace"] and d["rules"] and d["disclaimer"]
    assert all({"rule_id", "review_status", "source_reference"} <= set(m) for m in d["rules"])


# ------------------------------------------------------------------- VAT -----
def test_vat_add_and_extract_uae():
    a = vat.calculate(vat.VATInput(jurisdiction="AE", mode="add_vat", amount=1000))
    assert (a.outputs["vat"], a.outputs["gross"]) == (50.0, 1050.0)
    e = vat.calculate(vat.VATInput(jurisdiction="AE", mode="extract_vat", amount=1050))
    assert (e.outputs["net"], e.outputs["vat"]) == (1000.0, 50.0)


def test_vat_ksa_return_with_partial_exemption():
    r = vat.calculate(vat.VATInput(jurisdiction="SA", mode="return", standard_rated_sales=1_000_000,
                                   exempt_sales=1_000_000, standard_rated_purchases=400_000, reverse_charge_imports=100_000))
    # output 150,000 ; RC 15,000 ; input gross 60,000+15,000 = 75,000 ; ratio 0.5 -> recoverable 37,500
    # net = 150,000 + 15,000 - 37,500 = 127,500
    assert r.outputs["output_vat"] == 150_000.0
    assert r.outputs["recoverable_input_vat"] == 37_500.0
    assert r.outputs["net_vat_payable"] == 127_500.0
    assert any(f.code == "partial_exemption" for f in r.flags)


def test_vat_registration_thresholds():
    r = vat.calculate(vat.VATInput(jurisdiction="AE", mode="add_vat", amount=0, annual_taxable_supplies=200_000))
    assert r.outputs["registration_status"] == "voluntary"
    r = vat.calculate(vat.VATInput(jurisdiction="AE", mode="add_vat", amount=0, annual_taxable_supplies=400_000))
    assert r.outputs["registration_status"] == "mandatory"


# ------------------------------------------------------------ KSA Zakat ------
def test_ksa_zakat_gregorian_rate_is_prorated():
    assert pytest.approx(0.025 * 365 / 354, rel=1e-6) == 0.02577683


def test_ksa_zakat_full_saudi_ownership():
    r = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(
        share_capital=10_000_000, retained_earnings_opening=2_000_000, reserves_and_provisions=500_000,
        long_term_liabilities=1_500_000, book_net_profit=3_000_000, net_fixed_assets=6_000_000, long_term_investments=1_000_000))
    # sources 10m+2m+0.5m+1.5m+3m = 17m ; deductions 7m ; base 10m ; zakat 10m x 2.577683% = 257,768.30
    assert r.outputs["zakat_base"] == 10_000_000.0
    assert r.outputs["zakat_due"] == 257_768.3
    assert r.outputs["income_tax_due"] == 0.0


def test_ksa_zakat_hijri_rate():
    r = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(year_basis="hijri", share_capital=4_000_000, book_net_profit=0))
    assert r.outputs["zakat_due"] == 100_000.0  # 4m x 2.5%


def test_ksa_mixed_ownership_splits_zakat_and_tax():
    r = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(
        saudi_gcc_ownership_pct=60, share_capital=5_000_000, retained_earnings_opening=1_000_000,
        book_net_profit=2_000_000, net_fixed_assets=3_000_000))
    # base 5m ; zakat 3m x 2.577683% = 77,330.49 ; tax 2m x 40% x 20% = 160,000
    assert r.outputs["zakat_due"] == 77_330.49
    assert r.outputs["income_tax_due"] == 160_000.0
    assert r.outputs["total_due"] == 237_330.49


def test_ksa_minimum_base_floor():
    r = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(share_capital=1_000_000, book_net_profit=2_000_000, net_fixed_assets=5_000_000))
    # sources 3m - 5m = -2m -> floor at adjusted profit 2m
    assert r.outputs["zakat_base"] == 2_000_000.0
    assert r.outputs["minimum_base_applied"] is True


def test_ksa_tax_loss_offset_capped_at_25pct():
    r = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(saudi_gcc_ownership_pct=0, book_net_profit=1_000_000, brought_forward_tax_losses=5_000_000))
    # offset 25% x 1m = 250k ; taxable 750k x 20% = 150,000
    assert r.outputs["losses_utilised"] == 250_000.0
    assert r.outputs["income_tax_due"] == 150_000.0


# --------------------------------------------------------------- KSA WHT -----
def test_ksa_wht_rates_and_gross_up():
    r = ksa_wht.calculate(ksa_wht.KSAWHTInput(payments=[
        {"category": "royalties", "amount": 100_000},
        {"category": "management_fees", "amount": 100_000},
        {"category": "dividends", "amount": 100_000, "treaty_rate": 0.0},
        {"category": "technical_consulting", "amount": 95_000, "grossed_up": True},
    ]))
    # 15,000 + 20,000 + 0 + (95,000/0.95 - 95,000 = 5,000) = 40,000
    assert r.outputs["total_wht"] == 40_000.0


def test_ksa_wht_unknown_category():
    with pytest.raises(ValueError):
        ksa_wht.calculate(ksa_wht.KSAWHTInput(payments=[{"category": "nonsense", "amount": 1}]))


# -------------------------------------------------------------- GCC ----------
def test_gcc_compare_ranks_and_scopes():
    c = gcc_compare.compare(gcc_compare.GCCScenario(taxable_profit=1_000_000, foreign_ownership_pct=100))
    totals = {r["code"]: r["total_direct_tax"] for r in c["rows"]}
    # AE: band AED 375,000 / 3.6725 = USD 102,110.28 ; (1,000,000 - 102,110.28) x 9% = 80,810.07
    assert totals == {"BH": 0.0, "AE": 80_810.07, "QA": 100_000.0, "OM": 150_000.0, "KW": 150_000.0, "SA": 200_000.0}
    assert c["rows"][0]["code"] == "BH"


def test_gcc_compare_band_in_aed_and_sar():
    c_aed = gcc_compare.compare(gcc_compare.GCCScenario(taxable_profit=1_000_000, currency="AED", jurisdictions=["AE"]))
    assert c_aed["rows"][0]["corporate_tax"] == 56_250.0            # (1,000,000 - 375,000) x 9% in AED itself
    c_sar = gcc_compare.compare(gcc_compare.GCCScenario(taxable_profit=1_000_000, currency="SAR", jurisdictions=["AE"]))
    # band in SAR = 375,000 / 0.979333 = 382,913.65 ; (1,000,000 - 382,913.65) x 9% = 55,537.77
    assert c_sar["rows"][0]["corporate_tax"] == pytest.approx(55_537.77, abs=0.01)
    with pytest.raises(Exception):
        gcc_compare.GCCScenario(currency="JPY")


def test_gcc_compare_gcc_owned_pays_zakat_not_cit():
    c = gcc_compare.compare(gcc_compare.GCCScenario(taxable_profit=1_000_000, foreign_ownership_pct=0))
    sa = next(r for r in c["rows"] if r["code"] == "SA")
    assert sa["corporate_tax"] == 0.0 and sa["zakat"] == 25_776.83
    qa = next(r for r in c["rows"] if r["code"] == "QA")
    assert qa["corporate_tax"] == 0.0


def test_gcc_compare_dmtt_top_up():
    c = gcc_compare.compare(gcc_compare.GCCScenario(taxable_profit=10_000_000, is_mne_constituent=True, mne_group_revenue_eur=800_000_000, jurisdictions=["BH", "AE"]))
    bh = next(r for r in c["rows"] if r["code"] == "BH")
    assert bh["dmtt_top_up"] == 1_500_000.0
    ae = next(r for r in c["rows"] if r["code"] == "AE")
    band = 375_000 / 3.6725
    assert ae["dmtt_top_up"] == pytest.approx(1_500_000 - (10_000_000 - band) * 0.09, abs=0.01)


# ------------------------------------------------ zakat: Articles 27 and 28 (MR 1007 text) ----
def test_zakat_article_28_maximum_caps_base_at_equity_plus_difference():
    # Dividends of 1,500,000 were paid in the year, so year-end equity is 2,000,000 although the components entered sum to 3,500,000.
    # sources 1,000,000 + 2,000,000 + 500,000 = 3,500,000; no deductions; ceiling = equity 2,000,000 + (500,000 - 500,000) = 2,000,000
    # base capped at 2,000,000; hijri 2.5% -> 50,000
    r = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(year_basis="hijri", share_capital=1_000_000, retained_earnings_opening=2_000_000,
                                                     book_net_profit=500_000, equity_year_end=2_000_000))
    assert r.outputs["maximum_base"] == 2_000_000.0 and r.outputs["maximum_base_applied"] is True
    assert r.outputs["zakat_base"] == 2_000_000.0 and r.outputs["zakat_due"] == 50_000.0 and r.outputs["equity_derived"] is False
    assert any(f.code == "zakat_maximum_base" for f in r.flags) and "sa.zakat.max_base" in r.rules_used
    # the adjusted-less-book difference lifts the ceiling: non-deductible 100,000 -> ceiling 2,100,000 -> 52,500
    r2 = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(year_basis="hijri", share_capital=1_000_000, retained_earnings_opening=2_000_000,
                                                      book_net_profit=500_000, non_deductible_expenses=100_000, equity_year_end=2_000_000))
    assert r2.outputs["maximum_base"] == 2_100_000.0 and r2.outputs["zakat_due"] == 52_500.0


def test_zakat_liabilities_limited_to_assets_deducted_article_23_2():
    # NCL 5,000,000 but only 1,000,000 of assets deducted -> liabilities added 1,000,000
    # sources 1,000,000 + 500,000 + 1,000,000 = 2,500,000; less 1,000,000 = 1,500,000; ceiling 1,500,000 (not exceeded); 2.5% -> 37,500
    r = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(year_basis="hijri", share_capital=1_000_000, long_term_liabilities=5_000_000,
                                                     book_net_profit=500_000, net_fixed_assets=1_000_000))
    assert r.outputs["liabilities_added"] == 1_000_000.0 and r.outputs["liabilities_capped_at_deductions"] is True
    assert r.outputs["zakat_base"] == 1_500_000.0 and r.outputs["zakat_due"] == 37_500.0 and r.outputs["maximum_base_applied"] is False
    assert "sa.zakat.liabilities" in r.rules_used


def test_zakat_article_25_2_excludes_liabilities_financing_undeducted_non_current_assets():
    # total NCA 8,000,000, deducted 6,000,000 -> undeducted 2,000,000; excluded = 2/8 x 4,000,000 = 1,000,000; added 3,000,000
    # sources 5,000,000 + 1,000,000 + 3,000,000 = 9,000,000; less 6,000,000 = 3,000,000; 2.5% -> 75,000
    base = dict(year_basis="hijri", share_capital=5_000_000, book_net_profit=1_000_000, long_term_liabilities=4_000_000, net_fixed_assets=6_000_000)
    r = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(**base, total_non_current_assets=8_000_000))
    assert r.outputs["non_current_liabilities_excluded"] == 1_000_000.0 and r.outputs["liabilities_added"] == 3_000_000.0
    assert r.outputs["zakat_base"] == 3_000_000.0 and r.outputs["zakat_due"] == 75_000.0
    # without total non-current assets the full 4,000,000 is added -> base 4,000,000 -> 100,000, with a flag
    r2 = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(**base))
    assert r2.outputs["zakat_base"] == 4_000_000.0 and r2.outputs["zakat_due"] == 100_000.0
    assert any(f.code == "zakat_art25_ncl_untested" for f in r2.flags)
    # the exclusion can never exceed the undeducted asset: total NCA 6,100,000 -> undeducted 100,000; ratio gives 65,573.77 (< 100,000)
    r3 = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(**base, total_non_current_assets=6_100_000))
    assert r3.outputs["non_current_liabilities_excluded"] == 65_573.77


def test_zakat_article_25_3_adds_current_liabilities_in_proportion():
    # deducted current assets 1,200,000 of 6,000,000 -> 20% x current liabilities 3,000,000 = 600,000 (< 1,200,000)
    # sources 2,000,000 + 500,000 + 600,000 = 3,100,000; deductions 1,000,000 + 1,200,000 = 2,200,000; base 900,000; 2.5% -> 22,500
    base = dict(year_basis="hijri", share_capital=2_000_000, book_net_profit=500_000, current_liabilities=3_000_000,
                deducted_current_assets=1_200_000, net_fixed_assets=1_000_000)
    r = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(**base, total_current_assets=6_000_000))
    assert r.outputs["current_liabilities_added"] == 600_000.0 and r.outputs["total_deductions"] == 2_200_000.0
    assert r.outputs["zakat_base"] == 900_000.0 and r.outputs["zakat_due"] == 22_500.0
    # without total current assets: upper bound = lower of 3,000,000 and 1,200,000 = 1,200,000 -> base 1,500,000 -> 37,500, flagged
    r2 = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(**base))
    assert r2.outputs["current_liabilities_added"] == 1_200_000.0 and r2.outputs["zakat_due"] == 37_500.0
    assert any(f.code == "zakat_art25_cl_upper_bound" for f in r2.flags)
    # no current asset deducted -> no current liabilities added at all
    r3 = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(year_basis="hijri", share_capital=2_000_000, book_net_profit=500_000,
                                                      current_liabilities=3_000_000, total_current_assets=6_000_000, net_fixed_assets=1_000_000))
    assert r3.outputs["current_liabilities_added"] == 0.0 and r3.outputs["zakat_base"] == 1_500_000.0


def test_zakat_article_29_2_b_adds_excess_of_current_liabilities_over_current_assets():
    # current liabilities 2,000,000 against current assets 1,500,000 -> 500,000 added (within deductions 3,000,000)
    # sources 4,000,000 + 500,000 = 4,500,000; less 3,000,000 = 1,500,000; ceiling 4,000,000; 2.5% -> 37,500
    r = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(year_basis="hijri", share_capital=4_000_000, current_liabilities=2_000_000,
                                                     total_current_assets=1_500_000, net_fixed_assets=3_000_000))
    assert r.outputs["current_liabilities_added"] == 500_000.0 and r.outputs["zakat_base"] == 1_500_000.0 and r.outputs["zakat_due"] == 37_500.0
    assert any(f.code == "zakat_cl_exceeds_ca" for f in r.flags)


def test_zakat_rejects_inconsistent_balance_sheet():
    import pytest
    with pytest.raises(ValueError):
        ksa_zakat.KSAZakatInput(net_fixed_assets=6_000_000, total_non_current_assets=5_000_000)
    with pytest.raises(ValueError):
        ksa_zakat.KSAZakatInput(deducted_current_assets=2_000_000, total_current_assets=1_000_000)


def test_zakat_article_27_minimum_uses_lower_of_alternative_base_and_adjusted_profit():
    # sources 2,000,000 - 1,500,000 + adjusted 500,000 = 1,000,000; deductions 900,000 -> 100,000 < adjusted 500,000
    # equity 2,000,000 - 1,500,000 + 300,000 = 800,000; diff 200,000 -> ceiling 1,000,000 (not binding)
    # total assets 1,100,000: undeducted 200,000 + diff 200,000 = 400,000 < 500,000 -> base 400,000 -> hijri 10,000
    base = dict(year_basis="hijri", share_capital=2_000_000, retained_earnings_opening=-1_500_000, book_net_profit=300_000,
                non_deductible_expenses=200_000, net_fixed_assets=900_000)
    r = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(**base, total_assets=1_100_000))
    assert r.outputs["article_27_alternative_base"] == 400_000.0 and r.outputs["zakat_base"] == 400_000.0 and r.outputs["zakat_due"] == 10_000.0
    assert r.outputs["minimum_base_applied"] is True and r.outputs["maximum_base_applied"] is False
    # with more undeducted assets the alternative exceeds adjusted profit, so adjusted profit is the floor: 500,000 -> 12,500
    r2 = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(**base, total_assets=1_500_000))
    assert r2.outputs["article_27_alternative_base"] == 800_000.0 and r2.outputs["zakat_base"] == 500_000.0 and r2.outputs["zakat_due"] == 12_500.0
    # without total assets the calculator takes adjusted profit (the higher outcome) and says so
    r3 = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(**base))
    assert r3.outputs["zakat_base"] == 500_000.0 and any("enter total assets" in f.detail for f in r3.flags if f.code == "zakat_minimum_base")


def test_zakat_article_27_negative_base_without_profit_gives_no_base():
    r = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(year_basis="hijri", share_capital=100_000, retained_earnings_opening=-400_000, book_net_profit=-50_000))
    assert r.outputs["zakat_base"] == 0.0 and r.outputs["zakat_due"] == 0.0 and r.outputs["minimum_base_applied"] is False


def test_zakat_result_stays_review_required_until_sign_off():
    r = ksa_zakat.calculate(ksa_zakat.KSAZakatInput(share_capital=4_000_000, book_net_profit=100_000, scope_confirmed=True, special_regime="no"))
    assert ksa_zakat.ZAKAT_BASE_SIGNED_OFF is False
    assert r.outcome == "REVIEW_REQUIRED" and any(f.code == "zakat_base_signoff" for f in r.flags)
