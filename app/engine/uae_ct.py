"""UAE Corporate Tax calculator.

Reconciles accounting profit to taxable income, applies Small Business Relief,
Qualifying Free Zone Person treatment, loss relief, the standard 0%/9% bands
and a DMTT screen. Decimal arithmetic throughout; each step is traced.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .core import Answer, CalculationResult, D, Flag, TraceStep, ZERO, load_rules, param, ratio, rule

SCOPE_EXCLUDED = ("Tax Groups, transitional relief elections, treaty positions, natural persons, "
                  "exempt persons, partnerships and full Pillar Two GloBE computations.")


class UAECorporateTaxInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accounting_profit: Decimal = Field(..., description="Accounting net profit (or loss) before tax, AED")
    revenue: Decimal = Field(ZERO, ge=0, description="Total revenue for the tax period, AED")
    period_end: date | None = Field(None, description="End date of the tax period")

    # Reconciling items
    non_deductible_expenses: Decimal = Field(ZERO, ge=0)
    exempt_income: Decimal = Field(ZERO, ge=0)
    entertainment_expenses: Decimal = Field(ZERO, ge=0)
    unrealised_gains_capital: Decimal = Field(ZERO, ge=0)
    other_adjustments: Decimal = Field(ZERO)

    # Interest limitation
    net_interest_expense: Decimal = Field(ZERO, ge=0)
    tax_ebitda: Decimal | None = Field(None)

    # Losses and credits
    brought_forward_losses: Decimal = Field(ZERO, ge=0)
    foreign_tax_credit: Decimal = Field(ZERO, ge=0)

    # Status
    is_free_zone_person: bool = False
    elect_qfzp: bool = False
    qualifying_income: Decimal = Field(ZERO, ge=0)
    non_qualifying_revenue: Decimal = Field(ZERO, ge=0)
    elect_small_business_relief: bool = False
    is_mne_constituent: bool = False
    mne_group_revenue_eur: Decimal = Field(ZERO, ge=0)

    # Scope gate (V4 pattern)
    scope_confirmed: bool = Field(False, description="Visitor confirms the facts fit the stated scope")
    special_regime: Answer = Field("unknown", description="Does an unmodelled special regime, exemption or relief apply?")

    @field_validator("period_end", mode="before")
    @classmethod
    def _blank_date(cls, v: Any) -> Any:
        return None if v in ("", None) else v

    @field_validator("tax_ebitda", mode="before")
    @classmethod
    def _blank_num(cls, v: Any) -> Any:
        return None if v in ("", None) else v


def calculate(inp: UAECorporateTaxInput) -> CalculationResult:
    rules = load_rules("ae")
    r_std = rule("ae", "corporate_tax", "standard_rate")
    r_sbr = rule("ae", "corporate_tax", "small_business_relief")
    r_qfzp = rule("ae", "corporate_tax", "qualifying_free_zone_person")
    r_loss = rule("ae", "corporate_tax", "tax_loss_relief")
    r_int = rule("ae", "corporate_tax", "interest_deduction_limitation")
    r_ent = rule("ae", "corporate_tax", "entertainment_expenses")
    r_dmtt = rule("ae", "corporate_tax", "domestic_minimum_top_up_tax")
    r_file = rule("ae", "corporate_tax", "filing")

    res = CalculationResult(
        calculator="uae_corporate_tax", jurisdiction="AE", currency="AED",
        ruleset_version=rules["ruleset_version"], inputs=inp.model_dump(mode="json"), outputs={},
    )
    m = res.m
    res.assumptions += [
        "Taxable Person is a UAE Resident juridical person with a single 12-month tax period.",
        "Accounting profit is prepared under IFRS on an accrual basis.",
        "No Tax Group, no transitional relief elections and no treaty positions are modelled.",
        "Figures in AED.",
    ]

    # ---- 1. Reconciliation --------------------------------------------------------
    res.add(TraceStep("Accounting profit before tax", m(inp.accounting_profit), kind="input"))
    taxable = inp.accounting_profit

    if inp.non_deductible_expenses:
        taxable += inp.non_deductible_expenses
        res.add(TraceStep("Add: non-deductible expenses", m(inp.non_deductible_expenses), rule_id=r_std["rule_id"],
                          note="Fines, penalties, non-qualifying donations, dividends etc."))

    ent_disallowed = inp.entertainment_expenses * (1 - param(r_ent, "deductible_pct"))
    if ent_disallowed:
        taxable += ent_disallowed
        res.add(TraceStep("Add: 50% of entertainment expenditure", m(ent_disallowed),
                          formula=f"{inp.entertainment_expenses:,.0f} x 50%", rule_id=r_ent["rule_id"]))

    interest_disallowed = ZERO
    if inp.net_interest_expense and inp.tax_ebitda is not None:
        cap = max(param(r_int, "ebitda_pct") * max(inp.tax_ebitda, ZERO), param(r_int, "safe_harbour"))
        interest_disallowed = max(inp.net_interest_expense - cap, ZERO)
        res.add(TraceStep("Interest deduction cap (greater of 30% tax-EBITDA and AED 12m)", m(cap),
                          formula=f"max(30% x {inp.tax_ebitda:,.0f}, 12,000,000)", rule_id=r_int["rule_id"], kind="info"))
        if interest_disallowed:
            taxable += interest_disallowed
            res.add(TraceStep("Add: net interest above cap (carried forward up to 10 periods)", m(interest_disallowed), rule_id=r_int["rule_id"]))
    elif inp.net_interest_expense and inp.net_interest_expense > param(r_int, "safe_harbour"):
        res.flag(Flag("interest_limitation_untested", "attention", "Interest limitation not tested",
                      f"Net interest of AED {inp.net_interest_expense:,.0f} exceeds the AED 12m safe harbour but no tax-EBITDA was provided, so the 30% test could not be run.",
                      "Oblique can compute tax-EBITDA and model the carry-forward of disallowed interest."))

    if inp.exempt_income:
        taxable -= inp.exempt_income
        res.add(TraceStep("Less: exempt income (participation exemption / exempt foreign PE)", m(-inp.exempt_income), rule_id=r_std["rule_id"]))
    if inp.unrealised_gains_capital:
        taxable -= inp.unrealised_gains_capital
        res.add(TraceStep("Less: unrealised gains on capital assets (realisation basis)", m(-inp.unrealised_gains_capital), rule_id=r_std["rule_id"]))
    if inp.other_adjustments:
        taxable += inp.other_adjustments
        res.add(TraceStep("Other adjustments", m(inp.other_adjustments)))

    taxable_before_losses = taxable
    res.add(TraceStep("Taxable income before loss relief", m(taxable_before_losses), kind="subtotal"))

    # ---- 2. Loss relief (max 75%) ---------------------------------------------------
    losses_used = ZERO
    if inp.brought_forward_losses and taxable_before_losses > 0:
        losses_used = min(inp.brought_forward_losses, taxable_before_losses * param(r_loss, "max_offset_pct"))
        taxable -= losses_used
        res.add(TraceStep("Less: brought-forward tax losses (capped at 75% of taxable income)", m(-losses_used),
                          formula=f"min({inp.brought_forward_losses:,.0f}, 75% x {taxable_before_losses:,.0f})", rule_id=r_loss["rule_id"]))
    losses_cf = inp.brought_forward_losses - losses_used + (abs(taxable_before_losses) if taxable_before_losses < 0 else ZERO)
    taxable_income = max(taxable, ZERO)
    res.add(TraceStep("Taxable income", m(taxable_income), kind="subtotal"))

    # ---- 3. Regime ------------------------------------------------------------------
    regime = "standard"
    tax = ZERO
    sbr_eligible = (inp.revenue <= param(r_sbr, "revenue_threshold")
                    and not (inp.is_free_zone_person and inp.elect_qfzp) and not inp.is_mne_constituent)
    period_ok = inp.period_end is None or r_sbr["effective_to"] is None or inp.period_end.isoformat() <= r_sbr["effective_to"]

    if inp.elect_small_business_relief:
        if sbr_eligible and period_ok:
            regime = "small_business_relief"
            res.add(TraceStep("Small Business Relief elected: treated as having no taxable income", 0.0, rule_id=r_sbr["rule_id"], kind="tax",
                              note=f"Revenue AED {inp.revenue:,.0f} is within the AED 3,000,000 threshold."))
            if r_sbr["review_status"] != "verified":
                res.flag(Flag("sbr_extension_unverified", "info", "Small Business Relief end date", r_sbr.get("verification_note", ""),
                              "Oblique will confirm the applicable cut-off for your period end."))
        else:
            reason = []
            if inp.revenue > param(r_sbr, "revenue_threshold"):
                reason.append(f"revenue AED {inp.revenue:,.0f} exceeds AED 3,000,000")
            if inp.is_free_zone_person and inp.elect_qfzp:
                reason.append("Qualifying Free Zone Persons cannot elect")
            if inp.is_mne_constituent:
                reason.append("MNE constituent entities cannot elect")
            if not period_ok:
                reason.append(f"period ends after {r_sbr['effective_to']}")
            res.flag(Flag("sbr_not_available", "attention", "Small Business Relief not available", "; ".join(reason).capitalize() + ".",
                          "Oblique can review whether a prior-period election was validly made and the consequences of exceeding the threshold."))

    if regime == "standard" and inp.is_free_zone_person and inp.elect_qfzp:
        de_minimis_cap = min(param(r_qfzp, "de_minimis_pct") * inp.revenue, param(r_qfzp, "de_minimis_abs")) if inp.revenue else ZERO
        res.add(TraceStep("QFZP de minimis cap on non-qualifying revenue (lower of 5% revenue and AED 5m)", m(de_minimis_cap), rule_id=r_qfzp["rule_id"], kind="info"))
        if inp.non_qualifying_revenue > de_minimis_cap:
            res.flag(Flag("qfzp_de_minimis_breached", "high", "QFZP status lost: de minimis breached",
                          f"Non-qualifying revenue AED {inp.non_qualifying_revenue:,.0f} exceeds the cap of AED {de_minimis_cap:,.0f}. "
                          "The entity is taxed as a standard Taxable Person for this period and the next four periods.",
                          "Oblique can restructure revenue streams and assess the five-period disqualification impact."))
        else:
            regime = "qfzp"
            q_inc = min(inp.qualifying_income, taxable_income)
            nq_inc = taxable_income - q_inc
            res.add(TraceStep("Qualifying Income taxed at 0%", m(q_inc), rule_id=r_qfzp["rule_id"], kind="tax"))
            tax = nq_inc * param(r_qfzp, "non_qualifying_rate")
            res.add(TraceStep("Non-qualifying taxable income at 9% (no AED 375k zero band for a QFZP)", m(tax), formula=f"{nq_inc:,.0f} x 9%", rule_id=r_qfzp["rule_id"], kind="tax"))

    if regime == "standard":
        band0 = min(taxable_income, param(r_std, "zero_rate_threshold"))
        above = max(taxable_income - param(r_std, "zero_rate_threshold"), ZERO)
        tax = above * param(r_std, "rate_above_threshold")
        res.add(TraceStep("Taxable income at 0% (first AED 375,000)", m(band0), rule_id=r_std["rule_id"], kind="tax"))
        res.add(TraceStep("Taxable income above AED 375,000 at 9%", m(tax), formula=f"{above:,.0f} x 9%", rule_id=r_std["rule_id"], kind="tax"))

    # ---- 4. Credits -----------------------------------------------------------------
    ftc_used = ZERO
    if inp.foreign_tax_credit and tax > 0:
        ftc_used = min(inp.foreign_tax_credit, tax)
        tax -= ftc_used
        res.add(TraceStep("Less: foreign tax credit (capped at UAE CT on that income)", m(-ftc_used), rule_id=r_std["rule_id"], kind="tax"))
    tax = max(tax, ZERO)
    res.add(TraceStep("Corporate Tax payable", m(tax), kind="tax"))

    # ---- 5. DMTT screen -------------------------------------------------------------
    dmtt_in_scope = inp.is_mne_constituent and inp.mne_group_revenue_eur >= param(r_dmtt, "revenue_threshold_eur")
    top_up = None
    if dmtt_in_scope:
        etr = (tax / taxable_income) if taxable_income else ZERO
        if etr < param(r_dmtt, "minimum_rate"):
            top_up = max(param(r_dmtt, "minimum_rate") * taxable_income - tax, ZERO)
            res.add(TraceStep("DMTT top-up estimate to reach 15% (simplified: GloBE income assumed equal to taxable income)", m(top_up),
                              formula=f"15% x {taxable_income:,.0f} - {tax:,.0f}", rule_id=r_dmtt["rule_id"], kind="tax"))
        res.flag(Flag("dmtt_in_scope", "high", "Within scope of the 15% Domestic Minimum Top-up Tax",
                      "Group revenue meets the EUR 750m threshold. GloBE income, covered taxes and the substance-based income exclusion must be computed under Pillar Two rules; the estimate above is a screen only.",
                      "Oblique prepares full GloBE computations and DMTT returns."))

    # ---- 6. Outputs -----------------------------------------------------------------
    res.outputs = {
        "regime": regime,
        "taxable_income_before_losses": m(taxable_before_losses),
        "losses_utilised": m(losses_used),
        "losses_carried_forward": m(max(losses_cf, ZERO)),
        "taxable_income": m(taxable_income),
        "corporate_tax_payable": m(tax),
        "foreign_tax_credit_used": m(ftc_used),
        "effective_tax_rate_on_accounting_profit": (ratio(tax, inp.accounting_profit) if inp.accounting_profit > 0 else 0.0),
        "post_tax_profit": m(inp.accounting_profit - tax),
        "dmtt_in_scope": dmtt_in_scope,
        "dmtt_top_up_estimate": m(top_up) if top_up is not None else None,
        "filing_deadline_note": f"Return and payment due within {r_file['parameters']['months_after_period_end']} months of period end.",
    }
    res.rules_used.append(r_file["rule_id"])

    # ---- 7. Diagnostics -------------------------------------------------------------
    if inp.is_free_zone_person and not inp.elect_qfzp:
        res.flag(Flag("fz_not_qfzp", "attention", "Free Zone Person taxed at standard rates",
                      "You indicated a Free Zone entity that does not (or cannot) qualify as a QFZP. If substance, audited financial statements and TP documentation conditions can be met, 0% may be available on Qualifying Income.",
                      "Oblique runs a Free Zone eligibility review."))
    if inp.revenue and inp.revenue > 50_000_000 and not inp.is_mne_constituent:
        res.flag(Flag("tp_documentation", "info", "Transfer pricing documentation thresholds",
                      "Master file and local file are required where revenue is AED 200m or more or the group is an MNE with revenue of AED 3.15bn or more; the TP disclosure form applies to related-party transactions above AED 40m.",
                      "Oblique prepares TP disclosure forms and benchmarking."))
    if inp.exempt_income:
        res.flag(Flag("participation_exemption_conditions", "info", "Participation exemption conditions",
                      "Exempt treatment requires a 5% ownership (or AED 4m cost) held 12 months, a 9% subject-to-tax test and asset tests. Confirm each condition is met.",
                      "Oblique documents participation exemption positions."))
    if inp.accounting_profit < 0:
        res.flag(Flag("loss_period", "info", "Loss-making period",
                      "Tax losses are created only if the entity files a return; losses can be carried forward indefinitely subject to a 50% continuity-of-ownership test.", None))

    res.apply_scope_gate(inp.scope_confirmed, inp.special_regime, SCOPE_EXCLUDED)
    return res
