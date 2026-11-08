"""Personal income tax and mandatory employee contributions for origin countries.

Each country function returns the same shape so the relocation comparison and
the per-country calculator page can treat them uniformly. Decimal throughout.
"""
from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .core import RULES_DIR, CalculationResult, D, Flag, TraceStep, ZERO, money, ratio

CountryCode = Literal["GB", "HK", "SG", "IN", "US", "AU", "DE", "ZA", "PK"]


@lru_cache(maxsize=None)
def rules() -> dict[str, Any]:
    with (RULES_DIR / "personal.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def enabled_countries() -> dict[str, Any]:
    return {c: v for c, v in rules()["countries"].items() if v.get("enabled")}


class PersonalTaxInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    country: CountryCode
    gross_income: Decimal = Field(..., ge=0, le=Decimal("1000000000"), description="Annual gross employment income in the country's currency")
    cpf_member: bool = Field(False, description="Singapore: citizen or PR making CPF contributions")
    us_person: bool = Field(True, description="USA: citizen or green-card holder (stays taxable after moving)")
    state_tax_rate_pct: Decimal = Field(ZERO, ge=0, le=15, description="USA: optional flat state income tax rate to add")
    childless: bool = Field(True, description="Germany: apply childless care-insurance surcharge")
    foreign_resident_after_move: bool = Field(False, description="Internal: compute the post-move residual liability (US persons)")


# ------------------------------------------------------------------ helpers -----
def progressive(amount: Decimal, brackets: list[list[Any]], res: CalculationResult, rule_id: str, label: str, cur: str) -> Decimal:
    """Apply [upper, rate] brackets (upper=None for the top band) to `amount`, tracing each band."""
    tax = ZERO
    lower = ZERO
    for upper, rate in brackets:
        upper_d = D(upper) if upper is not None else None
        slice_amt = (min(amount, upper_d) - lower) if upper_d is not None else (amount - lower)
        if slice_amt <= 0:
            break
        rate_d = D(rate)
        band_tax = slice_amt * rate_d
        tax += band_tax
        rng = f"{lower:,.0f} to {upper_d:,.0f}" if upper_d is not None else f"above {lower:,.0f}"
        res.add(TraceStep(f"{label}: {rate_d:.1%} on {cur} {rng}", money(band_tax, cur), formula=f"{slice_amt:,.0f} x {rate_d:.1%}", rule_id=rule_id, kind="tax"))
        lower = upper_d if upper_d is not None else lower
        if upper_d is not None and amount <= upper_d:
            break
    return tax


def marginal_rate(amount: Decimal, brackets: list[list[Any]]) -> Decimal:
    for upper, rate in brackets:
        if upper is None or amount <= D(upper):
            return D(rate)
    return D(brackets[-1][1])


def _result(country: str, inp: PersonalTaxInput) -> tuple[CalculationResult, dict[str, Any], dict[str, Any]]:
    data = rules()
    c = data["countries"][country]
    res = CalculationResult(calculator="personal_income_tax", jurisdiction=country, currency=c["currency"],
                            ruleset_version=data["ruleset_version"], inputs=inp.model_dump(mode="json"), outputs={})
    res.assumptions += c.get("assumptions", [])
    res.add(TraceStep(f"Gross annual employment income ({c['tax_year']})", money(inp.gross_income, c["currency"]), kind="input"))
    return res, c, c["rules"]


def _finish(res: CalculationResult, gross: Decimal, income_tax: Decimal, contributions: list[tuple[str, Decimal]], marginal: Decimal, extra: dict[str, Any] | None = None) -> CalculationResult:
    cur = res.currency
    total_contrib = sum((a for _, a in contributions), ZERO)
    total = income_tax + total_contrib
    net = gross - total
    res.add(TraceStep("Income tax", money(income_tax, cur), kind="subtotal"))
    for label, amt in contributions:
        res.add(TraceStep(label, money(amt, cur), kind="tax"))
    res.add(TraceStep("Total tax and mandatory contributions", money(total, cur), kind="tax"))
    res.add(TraceStep("Net take-home pay", money(net, cur), kind="subtotal"))
    res.outputs = {
        "gross_income": money(gross, cur), "income_tax": money(income_tax, cur),
        "contributions": [{"label": l, "amount": money(a, cur)} for l, a in contributions],
        "total_contributions": money(total_contrib, cur), "total_deductions": money(total, cur),
        "net_income": money(net, cur), "monthly_net": money(net / 12, cur),
        "effective_rate": ratio(total, gross) if gross else 0.0, "marginal_income_tax_rate": float(marginal),
        **(extra or {}),
    }
    return res


# ------------------------------------------------------------------ countries ---
def calc_gb(inp: PersonalTaxInput) -> CalculationResult:
    res, c, r = _result("GB", inp)
    g = inp.gross_income
    pa_rule, bands, ni = r["personal_allowance"], r["bands"], r["national_insurance"]
    pa = D(pa_rule["parameters"]["allowance"])
    taper_start = D(pa_rule["parameters"]["taper_start"])
    if g > taper_start:
        pa = max(pa - (g - taper_start) / 2, ZERO)
    res.add(TraceStep("Less: Personal Allowance" + (" (tapered above GBP 100,000)" if g > taper_start else ""), money(-pa, "GBP"), rule_id=pa_rule["rule_id"]))
    taxable = max(g - pa, ZERO)
    res.add(TraceStep("Taxable income", money(taxable, "GBP"), kind="subtotal"))
    tax = progressive(taxable, bands["parameters"]["brackets"], res, bands["rule_id"], "Income tax", "GBP")
    p = ni["parameters"]
    main = max(min(g, D(p["upper_earnings_limit"])) - D(p["primary_threshold"]), ZERO) * D(p["main_rate"])
    upper = max(g - D(p["upper_earnings_limit"]), ZERO) * D(p["upper_rate"])
    res.rules_used.append(ni["rule_id"])
    marginal = marginal_rate(taxable, bands["parameters"]["brackets"])
    if taper_start < g < D("125140"):
        res.flag(Flag("gb_60pct_trap", "attention", "60% effective marginal rate zone", "Between GBP 100,000 and 125,140 the Personal Allowance taper creates an effective marginal income tax rate of 60%.", None))
    return _finish(res, g, tax, [("National Insurance (Class 1, 8%)", main), ("National Insurance (2% above UEL)", upper)], marginal)


def calc_hk(inp: PersonalTaxInput) -> CalculationResult:
    res, c, r = _result("HK", inp)
    g = inp.gross_income
    mpf = min(g * D(r["mpf"]["parameters"]["rate"]), D(r["mpf"]["parameters"]["annual_cap"]))
    res.add(TraceStep("Less: MPF mandatory contribution (5%, capped HKD 18,000), deductible", money(-mpf, "HKD"), rule_id=r["mpf"]["rule_id"]))
    net_income = max(g - mpf, ZERO)
    allowance = D(r["allowance"]["parameters"]["allowance"])
    res.add(TraceStep("Less: basic allowance", money(-allowance, "HKD"), rule_id=r["allowance"]["rule_id"]))
    nci = max(net_income - allowance, ZERO)
    res.add(TraceStep("Net chargeable income", money(nci, "HKD"), kind="subtotal"))
    prog = progressive(nci, r["progressive"]["parameters"]["brackets"], res, r["progressive"]["rule_id"], "Progressive", "HKD")
    std = progressive(net_income, r["standard_rate"]["parameters"]["brackets"], res, r["standard_rate"]["rule_id"], "Standard rate on net income", "HKD")
    tax = min(prog, std)
    res.add(TraceStep(f"Lower of progressive ({prog:,.0f}) and standard rate ({std:,.0f})", money(tax, "HKD"), kind="subtotal"))
    red_rule = r.get("one_off_reduction")
    red = min(tax, D(red_rule["parameters"]["cap"])) if red_rule else ZERO
    if red:
        tax -= red
        res.add(TraceStep(f"Less: one-off tax reduction (100%, capped HKD {D(red_rule['parameters']['cap']):,.0f})", money(-red, "HKD"), rule_id=red_rule["rule_id"]))
    marginal = marginal_rate(nci, r["progressive"]["parameters"]["brackets"]) if prog <= std else D("0.15")
    return _finish(res, g, tax, [("MPF employee contribution", mpf)], marginal, {"standard_rate_applies": std < prog})


def calc_sg(inp: PersonalTaxInput) -> CalculationResult:
    res, c, r = _result("SG", inp)
    g = inp.gross_income
    contributions: list[tuple[str, Decimal]] = []
    cpf = ZERO
    if inp.cpf_member:
        p = r["cpf"]["parameters"]
        cpf = min(g, D(p["monthly_ceiling"]) * 12) * D(p["rate"])
        contributions.append(("CPF employee contribution (20%)", cpf))
        res.add(TraceStep("Less: CPF relief (employee contributions)", money(-cpf, "SGD"), rule_id=r["cpf"]["rule_id"]))
    eir = D(r["earned_income_relief"]["parameters"]["relief"])
    res.add(TraceStep("Less: Earned Income Relief", money(-eir, "SGD"), rule_id=r["earned_income_relief"]["rule_id"]))
    chargeable = max(g - cpf - eir, ZERO)
    res.add(TraceStep("Chargeable income", money(chargeable, "SGD"), kind="subtotal"))
    tax = progressive(chargeable, r["bands"]["parameters"]["brackets"], res, r["bands"]["rule_id"], "Income tax", "SGD")
    if not inp.cpf_member:
        res.flag(Flag("sg_no_cpf", "info", "No CPF modelled", "CPF applies only to Singapore citizens and permanent residents. Tick 'CPF member' if that is you.", None))
    return _finish(res, g, tax, contributions, marginal_rate(chargeable, r["bands"]["parameters"]["brackets"]))


def calc_in(inp: PersonalTaxInput) -> CalculationResult:
    res, c, r = _result("IN", inp)
    g = inp.gross_income
    sd = D(r["standard_deduction"]["parameters"]["deduction"])
    res.add(TraceStep("Less: standard deduction", money(-sd, "INR"), rule_id=r["standard_deduction"]["rule_id"]))
    total_income = max(g - sd, ZERO)
    res.add(TraceStep("Total income (new regime)", money(total_income, "INR"), kind="subtotal"))
    tax = progressive(total_income, r["slabs"]["parameters"]["brackets"], res, r["slabs"]["rule_id"], "Slab tax", "INR")
    reb = r["rebate_87a"]["parameters"]
    if total_income <= D(reb["income_limit"]):
        rebate = min(tax, D(reb["max_rebate"]))
        tax -= rebate
        res.add(TraceStep("Less: Section 87A rebate", money(-rebate, "INR"), rule_id=r["rebate_87a"]["rule_id"]))
    else:
        excess = total_income - D(reb["income_limit"])
        if tax > excess:
            res.add(TraceStep("Marginal relief: tax limited to income above INR 12,00,000", money(excess, "INR"), rule_id=r["rebate_87a"]["rule_id"]))
            tax = excess
    surcharge = ZERO
    tiers = r["surcharge"]["parameters"]["tiers"]
    srate = ZERO
    for threshold, rate in tiers:
        if total_income > D(threshold):
            srate = D(rate)
    if srate:
        surcharge = tax * srate
        # simplified marginal relief: total tax+surcharge cannot exceed tax at the threshold plus the income above it
        thr = max(D(t) for t, rt in tiers if D(rt) <= srate and total_income > D(t))
        tax_at_thr = progressive(thr, r["slabs"]["parameters"]["brackets"], CalculationResult("x", "IN", "INR", "", {}, {}), "", "", "INR")
        lower_tier = max([D(rt) for t, rt in tiers if D(t) < thr] or [ZERO])
        cap = tax_at_thr * (1 + lower_tier) + (total_income - thr)
        if tax + surcharge > cap:
            surcharge = max(cap - tax, ZERO)
            res.add(TraceStep(f"Surcharge {srate:.0%} with marginal relief", money(surcharge, "INR"), rule_id=r["surcharge"]["rule_id"], kind="tax"))
        else:
            res.add(TraceStep(f"Surcharge {srate:.0%}", money(surcharge, "INR"), rule_id=r["surcharge"]["rule_id"], kind="tax"))
    cess = (tax + surcharge) * D(r["cess"]["parameters"]["rate"])
    res.add(TraceStep("Health and education cess 4%", money(cess, "INR"), rule_id=r["cess"]["rule_id"], kind="tax"))
    total_tax = tax + surcharge + cess
    res.flag(Flag("in_epf", "info", "Provident Fund not included", "Employee Provident Fund contributions (12% of basic salary) are not modelled and would reduce take-home further.", None))
    return _finish(res, g, total_tax, [], marginal_rate(total_income, r["slabs"]["parameters"]["brackets"]))


def _us_fit(taxable: Decimal, brackets: list[list[Any]]) -> Decimal:
    tax, lower = ZERO, ZERO
    for upper, rate in brackets:
        upper_d = D(upper) if upper is not None else None
        slice_amt = (min(taxable, upper_d) - lower) if upper_d is not None else (taxable - lower)
        if slice_amt <= 0:
            break
        tax += slice_amt * D(rate)
        if upper_d is None or taxable <= upper_d:
            break
        lower = upper_d
    return tax


def calc_us(inp: PersonalTaxInput) -> CalculationResult:
    res, c, r = _result("US", inp)
    g = inp.gross_income
    sd = D(r["standard_deduction"]["parameters"]["deduction"])
    brackets = r["brackets"]["parameters"]["brackets"]
    contributions: list[tuple[str, Decimal]] = []
    extra: dict[str, Any] = {}
    if inp.foreign_resident_after_move:
        # Post-move residual US liability for a US person living in the UAE: FEIE with stacking rule.
        feie = min(g, D(r["feie"]["parameters"]["exclusion"]))
        res.add(TraceStep("Foreign Earned Income Exclusion (2026)", money(-feie, "USD"), rule_id=r["feie"]["rule_id"]))
        taxable_all = max(g - sd, ZERO)
        taxable_excl = max(feie - sd, ZERO)
        tax = max(_us_fit(taxable_all, brackets) - _us_fit(taxable_excl, brackets), ZERO)
        res.add(TraceStep("US tax after FEIE (stacking rule: tax on all income less tax on excluded income)", money(tax, "USD"),
                          formula=f"tax({taxable_all:,.0f}) - tax({taxable_excl:,.0f})", rule_id=r["brackets"]["rule_id"], kind="tax"))
        res.rules_used.append(r["standard_deduction"]["rule_id"])
        extra["feie_applied"] = money(feie, "USD")
        res.flag(Flag("us_fica_abroad", "info", "FICA after moving", "Social Security and Medicare taxes stop only if you are paid by a non-US employer; a US employer keeps withholding FICA.", None))
        return _finish(res, g, tax, contributions, marginal_rate(max(g - sd, ZERO), brackets), extra)

    res.add(TraceStep("Less: standard deduction (single)", money(-sd, "USD"), rule_id=r["standard_deduction"]["rule_id"]))
    taxable = max(g - sd, ZERO)
    res.add(TraceStep("Taxable income", money(taxable, "USD"), kind="subtotal"))
    tax = progressive(taxable, brackets, res, r["brackets"]["rule_id"], "Federal income tax", "USD")
    p = r["fica"]["parameters"]
    ss = min(g, D(p["ss_wage_base"])) * D(p["ss_rate"])
    med = g * D(p["medicare_rate"]) + max(g - D(p["additional_medicare_threshold"]), ZERO) * D(p["additional_medicare_rate"])
    res.rules_used.append(r["fica"]["rule_id"])
    contributions += [("Social Security (6.2% to wage base)", ss), ("Medicare (1.45% + 0.9% above USD 200k)", med)]
    if inp.state_tax_rate_pct:
        st = g * inp.state_tax_rate_pct / 100
        contributions.append((f"State income tax (flat {inp.state_tax_rate_pct}% as entered)", st))
    else:
        res.flag(Flag("us_state_tax", "attention", "State and city tax not included", "Add a flat state rate above to approximate it; actual state tax depends on state brackets, deductions and local taxes.", None))
    return _finish(res, g, tax, contributions, marginal_rate(taxable, brackets), extra)


def calc_au(inp: PersonalTaxInput) -> CalculationResult:
    res, c, r = _result("AU", inp)
    g = inp.gross_income
    tax = progressive(g, r["brackets"]["parameters"]["brackets"], res, r["brackets"]["rule_id"], "Income tax", "AUD")
    p = r["lito"]["parameters"]
    lito = D(p["max"])
    if g > D(p["phase2_start"]):
        lito = max(D(p["max"]) - (D(p["phase2_start"]) - D(p["phase1_start"])) * D(p["phase1_rate"]) - (g - D(p["phase2_start"])) * D(p["phase2_rate"]), ZERO)
    elif g > D(p["phase1_start"]):
        lito = D(p["max"]) - (g - D(p["phase1_start"])) * D(p["phase1_rate"])
    lito = min(lito, tax)
    if lito:
        tax -= lito
        res.add(TraceStep("Less: Low Income Tax Offset", money(-lito, "AUD"), rule_id=r["lito"]["rule_id"]))
    levy = g * D(r["medicare_levy"]["parameters"]["rate"])
    res.rules_used.append(r["medicare_levy"]["rule_id"])
    return _finish(res, g, tax, [("Medicare levy (2%)", levy)], marginal_rate(g, r["brackets"]["parameters"]["brackets"]))


def calc_de(inp: PersonalTaxInput) -> CalculationResult:
    res, c, r = _result("DE", inp)
    g = inp.gross_income
    s = r["social"]["parameters"]
    pens_base = min(g, D(s["pension_ceiling"]))
    health_base = min(g, D(s["health_ceiling"]))
    pension = pens_base * D(s["pension_rate"])
    unemployment = pens_base * D(s["unemployment_rate"])
    health = health_base * (D(s["health_rate"]) + D(s["health_supplement_rate"]))
    care = health_base * (D(s["care_rate"]) + (D(s["care_childless_surcharge"]) if inp.childless else ZERO))
    res.rules_used.append(r["social"]["rule_id"])
    deductible = pension + health * D("0.96") + care
    res.add(TraceStep("Less: deductible social contributions (simplified: pension 100%, health 96%, care 100%)", money(-deductible, "EUR"), rule_id=r["social"]["rule_id"]))
    zve = max(g - deductible, ZERO)
    res.add(TraceStep("Taxable income (zu versteuerndes Einkommen)", money(zve, "EUR"), kind="subtotal"))
    t = r["tariff"]["parameters"]
    x = zve
    if x <= D(t["gfb"]):
        est = ZERO; zone = "zero zone"
    elif x <= D(t["z2_end"]):
        y = (x - D(t["gfb"])) / 10000
        est = (D(t["z2"][0]) * y + D(t["z2"][1])) * y; zone = "first progression zone"
    elif x <= D(t["z3_end"]):
        z = (x - D(t["z2_end"])) / 10000
        est = (D(t["z3"][0]) * z + D(t["z3"][1])) * z + D(t["z3"][2]); zone = "second progression zone"
    elif x <= D(t["z4_end"]):
        est = D(t["z4"][0]) * x - D(t["z4"][1]); zone = "42% zone"
    else:
        est = D(t["z5"][0]) * x - D(t["z5"][1]); zone = "45% zone"
    est = est.to_integral_value(rounding="ROUND_DOWN")  # section 32a: round down to full euro
    res.add(TraceStep(f"Income tax per section 32a EStG tariff ({zone})", money(est, "EUR"), rule_id=r["tariff"]["rule_id"], kind="tax"))
    so = r["soli"]["parameters"]
    soli = ZERO
    if est > D(so["exemption"]):
        soli = min(est * D(so["rate"]), (est - D(so["exemption"])) * D(so["sliding_rate"]))
        res.add(TraceStep("Solidarity surcharge (5.5%, sliding zone above EUR 20,350 tax)", money(soli, "EUR"), rule_id=r["soli"]["rule_id"], kind="tax"))
    marginal = D("0.45") if x > D(t["z4_end"]) else D("0.42") if x > D(t["z3_end"]) else D("0.24") if x > D(t["z2_end"]) else D("0.14") if x > D(t["gfb"]) else ZERO
    return _finish(res, g, est + soli, [("Pension insurance (9.3%)", pension), ("Unemployment insurance (1.3%)", unemployment),
                                        ("Health insurance (7.3% + 1.45%)", health), ("Long-term care insurance", care)], marginal)


def calc_za(inp: PersonalTaxInput) -> CalculationResult:
    res, c, r = _result("ZA", inp)
    g = inp.gross_income
    tax = progressive(g, r["brackets"]["parameters"]["brackets"], res, r["brackets"]["rule_id"], "Income tax", "ZAR")
    rebate = min(tax, D(r["rebate"]["parameters"]["rebate"]))
    tax -= rebate
    res.add(TraceStep("Less: primary rebate", money(-rebate, "ZAR"), rule_id=r["rebate"]["rule_id"]))
    p = r["uif"]["parameters"]
    uif = min(g, D(p["monthly_ceiling"]) * 12) * D(p["rate"])
    res.rules_used.append(r["uif"]["rule_id"])
    return _finish(res, g, tax, [("UIF employee contribution (1%, capped)", uif)], marginal_rate(g, r["brackets"]["parameters"]["brackets"]))


CALCULATORS = {"GB": calc_gb, "HK": calc_hk, "SG": calc_sg, "IN": calc_in, "US": calc_us, "AU": calc_au, "DE": calc_de, "ZA": calc_za}


def calculate(inp: PersonalTaxInput) -> CalculationResult:
    c = rules()["countries"].get(inp.country)
    if not c or not c.get("enabled") or inp.country not in CALCULATORS:
        raise ValueError(f"Personal tax rules for {inp.country} are not yet verified and enabled.")
    res = CALCULATORS[inp.country](inp)
    res.outputs["tax_year"] = c["tax_year"]
    res.outputs["country_name"] = c["name"]
    return res
