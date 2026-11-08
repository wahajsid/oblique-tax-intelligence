"""KSA withholding tax on payments to non-residents. Decimal arithmetic."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .core import Answer, CalculationResult, D, Flag, TraceStep, ZERO, load_rules, rule

SCOPE_EXCLUDED = ("payments to a permanent establishment, mixed-nature contracts, treaty eligibility tests, "
                  "beneficial-ownership analysis and refund procedures.")


class WHTPayment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    amount: Decimal = Field(..., ge=0)
    treaty_rate: Decimal | None = Field(None, ge=0, le=1)
    grossed_up: bool = False


class KSAWHTInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payments: list[WHTPayment] = Field(..., max_length=50)
    scope_confirmed: bool = False
    special_regime: Answer = "unknown"


def categories() -> dict:
    return rule("sa", "withholding_tax", "rates")["parameters"]["categories"]


def calculate(inp: KSAWHTInput) -> CalculationResult:
    data = load_rules("sa")
    r = rule("sa", "withholding_tax", "rates")
    cats = r["parameters"]["categories"]
    res = CalculationResult(calculator="ksa_withholding_tax", jurisdiction="SA", currency="SAR",
                            ruleset_version=data["ruleset_version"], inputs=inp.model_dump(mode="json"), outputs={})
    m = res.m
    res.assumptions += ["Payee is a non-resident without a permanent establishment in KSA.",
                        "Treaty relief, where entered, assumes the payee is the beneficial owner and treaty formalities are met."]
    total_wht = ZERO
    total_cost = ZERO
    lines = []
    for p in inp.payments:
        if p.category not in cats:
            raise ValueError(f"Unknown WHT category '{p.category}'. Valid: {', '.join(cats)}")
        statutory = D(cats[p.category]["rate"])
        applied = p.treaty_rate if p.treaty_rate is not None and p.treaty_rate < statutory else statutory
        if p.grossed_up:
            gross = p.amount / (1 - applied) if applied < 1 else p.amount
            wht = gross - p.amount
        else:
            gross = p.amount
            wht = gross * applied
        total_wht += wht
        total_cost += gross
        label = cats[p.category]["label"]
        res.add(TraceStep(f"{label}: WHT at {applied:.0%}" + (" (treaty)" if applied != statutory else "") + (" grossed up" if p.grossed_up else ""),
                          m(wht), formula=f"{gross:,.2f} x {applied:.0%}", rule_id=r["rule_id"], kind="tax"))
        lines.append({"category": p.category, "label": label, "gross": m(gross), "statutory_rate": float(statutory),
                      "applied_rate": float(applied), "wht": m(wht), "net_to_payee": m(gross - wht)})
        if p.treaty_rate is not None and p.treaty_rate < statutory:
            res.flag(Flag(f"treaty_{p.category}", "attention", f"Treaty rate applied to {label.lower()}",
                          "ZATCA allows treaty rates to be applied at source only where the payer holds the payee's tax residency certificate and files the required forms; otherwise pay at statutory rate and claim a refund.",
                          "Oblique manages treaty relief applications and refund claims."))
    res.add(TraceStep("Total withholding tax", m(total_wht), kind="tax"))
    res.outputs = {"lines": lines, "total_wht": m(total_wht), "total_cost_to_payer": m(total_cost),
                   "filing_note": "WHT return and payment due within the first 10 days of the month following payment."}
    if r["review_status"] != "verified":
        res.flag(Flag("wht_table_review", "info", "Rate table review status", r.get("verification_note", ""), None))
    res.apply_scope_gate(inp.scope_confirmed, inp.special_regime, SCOPE_EXCLUDED)
    return res
