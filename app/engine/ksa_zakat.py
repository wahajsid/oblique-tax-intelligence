"""KSA Zakat and Corporate Income Tax calculator (mixed-ownership aware). Decimal arithmetic.

Zakat base follows the structure of the 2024 Executive Regulations for Zakat
Collection (MR 1007): sources of funds less non-zakatable assets, with a floor
of adjusted net profit. The Article 28 upper limit is NOT applied because its
exact formula was not confirmed from the regulation text during review.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .core import Answer, CalculationResult, Flag, TraceStep, ZERO, load_rules, param, ratio, rule

# Flip to True only when the Article 28 formula is implemented AND signed off by the technical reviewer (see docs/LAUNCH_GATES.md).
ARTICLE_28_IMPLEMENTED = False

SCOPE_EXCLUDED = ("the Article 28 upper-limit base, partial-year proration, zakat on investment funds, "
                  "hydrocarbon rates, tax groups and treaty relief.")


class KSAZakatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year_basis: Literal["gregorian", "hijri"] = "gregorian"
    saudi_gcc_ownership_pct: Decimal = Field(Decimal(100), ge=0, le=100)
    share_capital: Decimal = Field(ZERO, ge=0)
    retained_earnings_opening: Decimal = Field(ZERO)
    reserves_and_provisions: Decimal = Field(ZERO, ge=0)
    long_term_liabilities: Decimal = Field(ZERO, ge=0)
    book_net_profit: Decimal = Field(ZERO)
    non_deductible_expenses: Decimal = Field(ZERO, ge=0)
    exempt_or_deductible_income: Decimal = Field(ZERO, ge=0)
    net_fixed_assets: Decimal = Field(ZERO, ge=0)
    long_term_investments: Decimal = Field(ZERO, ge=0)
    capital_work_in_progress: Decimal = Field(ZERO, ge=0)
    intangible_assets: Decimal = Field(ZERO, ge=0)
    other_deductible_assets: Decimal = Field(ZERO, ge=0)
    brought_forward_tax_losses: Decimal = Field(ZERO, ge=0)
    scope_confirmed: bool = False
    special_regime: Answer = "unknown"


def calculate(inp: KSAZakatInput) -> CalculationResult:
    data = load_rules("sa")
    r_rate = rule("sa", "zakat", "rate")
    r_base = rule("sa", "zakat", "base")
    r_mix = rule("sa", "zakat", "mixed_ownership")
    r_cit = rule("sa", "income_tax", "standard_rate")
    r_loss = rule("sa", "income_tax", "tax_loss_relief")

    res = CalculationResult(calculator="ksa_zakat_income_tax", jurisdiction="SA", currency="SAR",
                            ruleset_version=data["ruleset_version"], inputs=inp.model_dump(mode="json"), outputs={})
    m = res.m
    res.assumptions += [
        "Entity is a Saudi resident company subject to zakat on the Saudi/GCC share and income tax on the non-Saudi share.",
        "Year-end closing balances are used for base items; no partial-year proration of additions.",
        "The Article 28 upper limit on the zakat base is not applied (formula pending verification).",
        "Figures in SAR.",
    ]
    saudi = inp.saudi_gcc_ownership_pct / 100
    foreign = 1 - saudi

    res.add(TraceStep("Book net profit", m(inp.book_net_profit), kind="input"))
    adjusted_profit = inp.book_net_profit + inp.non_deductible_expenses - inp.exempt_or_deductible_income
    if inp.non_deductible_expenses:
        res.add(TraceStep("Add: non-deductible expenses", m(inp.non_deductible_expenses), rule_id=r_base["rule_id"]))
    if inp.exempt_or_deductible_income:
        res.add(TraceStep("Less: exempt / deductible income", m(-inp.exempt_or_deductible_income), rule_id=r_base["rule_id"]))
    res.add(TraceStep("Adjusted net profit", m(adjusted_profit), kind="subtotal", rule_id=r_base["rule_id"]))

    sources = inp.share_capital + inp.retained_earnings_opening + inp.reserves_and_provisions + inp.long_term_liabilities + adjusted_profit
    res.add(TraceStep("Share capital", m(inp.share_capital), kind="input"))
    res.add(TraceStep("Retained earnings / (accumulated losses) at start of year", m(inp.retained_earnings_opening), kind="input"))
    res.add(TraceStep("Reserves and provisions", m(inp.reserves_and_provisions), kind="input"))
    res.add(TraceStep("Long-term liabilities", m(inp.long_term_liabilities), kind="input"))
    res.add(TraceStep("Total sources of funds (incl. adjusted net profit)", m(sources), kind="subtotal", rule_id=r_base["rule_id"]))

    deductions = inp.net_fixed_assets + inp.long_term_investments + inp.capital_work_in_progress + inp.intangible_assets + inp.other_deductible_assets
    for label, amt in [("Net fixed assets", inp.net_fixed_assets), ("Long-term investments", inp.long_term_investments),
                       ("Capital work in progress", inp.capital_work_in_progress), ("Intangible assets", inp.intangible_assets),
                       ("Other deductible assets", inp.other_deductible_assets)]:
        if amt:
            res.add(TraceStep(f"Less: {label.lower()}", m(-amt), rule_id=r_base["rule_id"]))
    net_assets_base = sources - deductions
    res.add(TraceStep("Zakat base before minimum test", m(net_assets_base), kind="subtotal", rule_id=r_base["rule_id"]))

    floor = max(adjusted_profit, ZERO)
    zakat_base = max(net_assets_base, floor)
    if zakat_base != net_assets_base:
        res.add(TraceStep("Minimum base applied: base cannot be below adjusted net profit", m(zakat_base), rule_id=r_base["rule_id"], kind="subtotal",
                          note="Deductions limited so the base is at least the adjusted net profit."))
    zakat_base = max(zakat_base, ZERO)

    zrate = param(r_rate, "hijri_rate" if inp.year_basis == "hijri" else "gregorian_rate")
    saudi_base = zakat_base * saudi
    zakat_due = saudi_base * zrate
    res.add(TraceStep(f"Zakat base attributable to Saudi/GCC shareholders ({saudi:.0%})", m(saudi_base), rule_id=r_mix["rule_id"]))
    res.add(TraceStep(f"Zakat at {zrate:.6%} ({inp.year_basis} year)", m(zakat_due), formula=f"{saudi_base:,.0f} x {zrate:.6%}", rule_id=r_rate["rule_id"], kind="tax"))

    income_tax = ZERO
    losses_used = ZERO
    taxable_profit_foreign = max(adjusted_profit, ZERO) * foreign
    if foreign > 0:
        res.add(TraceStep(f"Adjusted taxable profit attributable to non-Saudi shareholders ({foreign:.0%})", m(taxable_profit_foreign), rule_id=r_mix["rule_id"]))
        if inp.brought_forward_tax_losses and taxable_profit_foreign > 0:
            losses_used = min(inp.brought_forward_tax_losses, taxable_profit_foreign * param(r_loss, "max_offset_pct"))
            taxable_profit_foreign -= losses_used
            res.add(TraceStep("Less: brought-forward losses (max 25% of taxable profit)", m(-losses_used), rule_id=r_loss["rule_id"]))
        income_tax = taxable_profit_foreign * param(r_cit, "rate")
        res.add(TraceStep("Income tax at 20%", m(income_tax), formula=f"{taxable_profit_foreign:,.0f} x 20%", rule_id=r_cit["rule_id"], kind="tax"))

    total = zakat_due + income_tax
    res.add(TraceStep("Total zakat and income tax", m(total), kind="tax"))

    res.outputs = {
        "adjusted_net_profit": m(adjusted_profit), "zakat_base": m(zakat_base), "zakat_rate": float(zrate),
        "zakat_due": m(zakat_due), "income_tax_due": m(income_tax), "losses_utilised": m(losses_used), "total_due": m(total),
        "effective_rate_on_book_profit": ratio(total, inp.book_net_profit) if inp.book_net_profit > 0 else None,
        "minimum_base_applied": zakat_base > net_assets_base,
    }

    if zakat_base > net_assets_base:
        res.flag(Flag("zakat_minimum_base", "attention", "Minimum zakat base applied",
                      "Deductible assets exceed sources of funds, so the base was floored at adjusted net profit. The alternative-base rules in Articles 27 and 28 of the Regulations should be applied to confirm.",
                      "Oblique prepares full zakat base computations under the 2024 Regulations."))
    if inp.long_term_investments:
        res.flag(Flag("zakat_investment_deduction", "info", "Investment deduction conditions",
                      "Investments are deductible only if held for more than a year in entities that themselves pay zakat in KSA; confirm the counterparties' status.", None))
    if foreign > 0:
        res.flag(Flag("ksa_wht_and_tp", "info", "Mixed ownership: withholding tax and transfer pricing",
                      "Dividends to non-resident shareholders attract 5% WHT and related-party transactions must meet transfer pricing documentation thresholds.",
                      "Oblique handles WHT filings and TP documentation."))
    if r_base["review_status"] != "verified":
        res.flag(Flag("zakat_regs_review", "info", "Base rules under 2024 Regulations", r_base.get("verification_note", ""), None))

    if not ARTICLE_28_IMPLEMENTED:
        # Mandatory until the Article 28 upper-limit formula is implemented and technically reviewed.
        # It cannot be cleared by the visitor confirming scope.
        res.flag(Flag("zakat_art28_unmodelled", "attention", "Article 28 upper limit not applied",
                      "The 2024 Regulations cap the zakat base under Article 28. This calculator does not apply that cap, so the base, and the zakat on it, "
                      "may be overstated for some companies. The figure is a screen until the base is confirmed.",
                      "Oblique applies Articles 23 to 28 in full in the computation it prepares."))
        res.review_reasons.append("The Article 28 upper limit on the zakat base is not applied by this calculator. A technical review of the base is required before the figure is relied on.")
    res.apply_scope_gate(inp.scope_confirmed, inp.special_regime, SCOPE_EXCLUDED)
    return res
