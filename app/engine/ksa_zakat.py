"""KSA Zakat and Corporate Income Tax calculator (mixed-ownership aware). Decimal arithmetic.

Zakat base follows the Implementing Regulations for Zakat Collection 1445H (Ministerial
Resolution 1007, as amended by MR 1248), read from ZATCA's English text:

- Articles 23, 26 and 29: sources of funds (equity and equivalents, non-current liabilities,
  the adjusted-less-book profit difference) less deducted assets.
- Article 28 (maximum): the base cannot exceed equity and equivalents per the year-end statement
  of financial position plus (adjusted net profit or loss minus book net profit or loss).
  Equity covers items reclassified to equity: profits declared but unpaid (Art. 36), partners'
  loans treated as equity (Art. 30) and provisions treated as equity (Art. 24).
- Article 27 (minimum): if the base falls below adjusted net profit, the base becomes the lower of
  (a) undeducted assets plus the adjusted-less-book difference and (b) adjusted net profit.
  A negative base with no adjusted net profit gives no base; a positive base with no adjusted
  net profit stands.
Article 25 (proportional placement of current liabilities) is not modelled.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .core import Answer, CalculationResult, Flag, TraceStep, ZERO, load_rules, param, ratio, rule

# Articles 27 and 28 are implemented from the regulation text. Flip to True only when the Oblique tax team has
# signed off the implementation against worked cases (see docs/LAUNCH_GATES.md gate 1). Until then the result
# stays review-required and says why.
ARTICLES_27_28_SIGNED_OFF = False

SCOPE_EXCLUDED = ("Article 25 proportional placement of current liabilities, partial-year proration, zakat on investment funds, "
                  "financing-activity rules, hydrocarbon rates, tax groups and treaty relief.")


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
    equity_year_end: Decimal | None = Field(None, description="Equity and equivalents per the year-end statement of financial position, including items reclassified to equity (Art. 24, 30, 36). Derived from the inputs above when blank.")
    total_assets: Decimal | None = Field(None, ge=0, description="Total assets per the year-end statement of financial position; needed for the Article 27 alternative base.")
    scope_confirmed: bool = False
    special_regime: Answer = "unknown"


def calculate(inp: KSAZakatInput) -> CalculationResult:
    data = load_rules("sa")
    r_rate = rule("sa", "zakat", "rate")
    r_base = rule("sa", "zakat", "base")
    r_min = rule("sa", "zakat", "min_base")
    r_max = rule("sa", "zakat", "max_base")
    r_mix = rule("sa", "zakat", "mixed_ownership")
    r_cit = rule("sa", "income_tax", "standard_rate")
    r_loss = rule("sa", "income_tax", "tax_loss_relief")

    res = CalculationResult(calculator="ksa_zakat_income_tax", jurisdiction="SA", currency="SAR",
                            ruleset_version=data["ruleset_version"], inputs=inp.model_dump(mode="json"), outputs={})
    m = res.m
    res.assumptions += [
        "Entity is a Saudi resident company subject to zakat on the Saudi/GCC share and income tax on the non-Saudi share.",
        "Year-end closing balances are used for base items; no partial-year proration of additions.",
        "Articles 27 (minimum) and 28 (maximum) of the Regulations are applied; Article 25 proportional placement of current liabilities is not.",
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
    res.add(TraceStep("Zakat base before the Article 27 and 28 limits", m(net_assets_base), kind="subtotal", rule_id=r_base["rule_id"]))

    # ---- Article 28: maximum base = equity and equivalents at year end + (adjusted - book) ----
    diff = adjusted_profit - inp.book_net_profit
    if inp.equity_year_end is not None:
        equity = inp.equity_year_end
        res.add(TraceStep("Equity and equivalents at year end (as entered)", m(equity), kind="input", rule_id=r_max["rule_id"]))
    else:
        equity = inp.share_capital + inp.retained_earnings_opening + inp.reserves_and_provisions + inp.book_net_profit
        res.add(TraceStep("Equity and equivalents at year end (derived: capital + opening retained earnings + reserves and provisions + book profit)", m(equity),
                          kind="input", rule_id=r_max["rule_id"], note="Enter the balance-sheet figure if dividends were paid or items were reclassified to equity."))
    max_base = equity + diff
    res.add(TraceStep("Article 28 maximum base: equity + (adjusted net profit − book net profit)", m(max_base), rule_id=r_max["rule_id"],
                      formula=f"{equity:,.0f} + ({adjusted_profit:,.0f} − {inp.book_net_profit:,.0f})"))
    maximum_applied = net_assets_base > max_base
    zakat_base = min(net_assets_base, max_base) if maximum_applied else net_assets_base
    if maximum_applied:
        res.add(TraceStep("Maximum applied: base capped under Article 28", m(zakat_base), kind="subtotal", rule_id=r_max["rule_id"]))

    # ---- Article 27: minimum base when the base falls below adjusted net profit ----
    minimum_applied = False
    alt_base = None
    if adjusted_profit > 0 and zakat_base < adjusted_profit:
        if inp.total_assets is not None:
            undeducted = max(inp.total_assets - deductions, ZERO)
            alt_base = undeducted + diff
            res.add(TraceStep("Article 27 alternative base: undeducted assets + (adjusted − book)", m(alt_base), rule_id=r_min["rule_id"],
                              formula=f"({inp.total_assets:,.0f} − {deductions:,.0f}) + {diff:,.0f}"))
            floor = min(alt_base, adjusted_profit)
            which = "alternative base" if alt_base < adjusted_profit else "adjusted net profit"
        else:
            floor = adjusted_profit
            which = "adjusted net profit (enter total assets to test the alternative base)"
        if floor > zakat_base:
            minimum_applied = True
            zakat_base = floor
            res.add(TraceStep(f"Minimum applied under Article 27: {which}", m(zakat_base), kind="subtotal", rule_id=r_min["rule_id"]))
    if zakat_base < 0:
        # Art. 27(3): negative base and no adjusted net profit means no base
        res.add(TraceStep("Negative base with no adjusted net profit: no zakat base (Article 27(3))", m(ZERO), kind="subtotal", rule_id=r_min["rule_id"]))
        zakat_base = ZERO

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
        "maximum_base": m(max_base), "maximum_base_applied": maximum_applied,
        "minimum_base_applied": minimum_applied, "article_27_alternative_base": m(alt_base) if alt_base is not None else None,
        "equity_year_end": m(equity), "equity_derived": inp.equity_year_end is None,
    }

    if maximum_applied:
        res.flag(Flag("zakat_maximum_base", "attention", "Article 28 maximum applied",
                      f"Sources of funds less deducted assets came to SAR {net_assets_base:,.0f}, above the Article 28 ceiling of equity plus the adjusted-less-book difference "
                      f"(SAR {max_base:,.0f}). The base is capped at the ceiling. "
                      + ("The ceiling uses equity derived from your inputs; enter the balance-sheet equity figure, including items reclassified to equity, to confirm it." if inp.equity_year_end is None else ""),
                      "Oblique confirms the equity figure and reclassified items against the audited statements."))
    if minimum_applied:
        res.flag(Flag("zakat_minimum_base", "attention", "Article 27 minimum applied",
                      ("The base fell below adjusted net profit, so Article 27 substitutes the lower of the alternative base (undeducted assets plus the adjusted-less-book difference) and adjusted net profit."
                       if inp.total_assets is not None else
                       "The base fell below adjusted net profit. Without total assets the calculator uses adjusted net profit, which is the higher of the two Article 27 outcomes; enter total assets to test the alternative base."),
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

    if not ARTICLES_27_28_SIGNED_OFF:
        # Mandatory until the tax team signs off the Article 27 and 28 implementation. Cannot be cleared by confirming scope.
        res.flag(Flag("zakat_art27_28_signoff", "attention", "Articles 27 and 28 applied, awaiting sign-off",
                      "The minimum and maximum base rules are implemented from the text of the Implementing Regulations for Zakat Collection 1445H (Articles 27 and 28). "
                      "The Oblique tax team has not yet signed off the implementation against worked cases, so the figure stays a screen.",
                      "Oblique prepares and signs the zakat base computation."))
        res.review_reasons.append("The Article 27 and 28 base limits are implemented but await technical sign-off by the Oblique tax team.")
    res.apply_scope_gate(inp.scope_confirmed, inp.special_regime, SCOPE_EXCLUDED)
    return res
