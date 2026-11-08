"""VAT calculator shared by the UAE (5%) and KSA (15%) with per-jurisdiction rules. Decimal arithmetic."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .core import Answer, CalculationResult, Flag, TraceStep, ZERO, load_rules, param, ratio, rule

Jurisdiction = Literal["AE", "SA"]
SCOPE_EXCLUDED = ("place-of-supply and time-of-supply determination, designated zones, margin schemes, "
                  "capital asset scheme adjustments, bad-debt relief and tax-group registrations.")


class VATInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jurisdiction: Jurisdiction = "AE"
    mode: Literal["add_vat", "extract_vat", "return"] = "add_vat"
    amount: Decimal = Field(ZERO, ge=0)
    rate_type: Literal["standard", "zero", "exempt"] = "standard"
    standard_rated_sales: Decimal = Field(ZERO, ge=0)
    zero_rated_sales: Decimal = Field(ZERO, ge=0)
    exempt_sales: Decimal = Field(ZERO, ge=0)
    standard_rated_purchases: Decimal = Field(ZERO, ge=0)
    reverse_charge_imports: Decimal = Field(ZERO, ge=0)
    blocked_input_vat: Decimal = Field(ZERO, ge=0)
    annual_taxable_supplies: Decimal | None = None
    scope_confirmed: bool = False
    special_regime: Answer = "unknown"

    @field_validator("annual_taxable_supplies", mode="before")
    @classmethod
    def _blank(cls, v: Any) -> Any:
        return None if v in ("", None) else v


def calculate(inp: VATInput) -> CalculationResult:
    jur = inp.jurisdiction.lower()
    data = load_rules(jur)
    r_rate = rule(jur, "vat", "standard_rate")
    r_reg = rule(jur, "vat", "registration_thresholds")
    std = param(r_rate, "standard_rate")
    cur = data["currency"]

    res = CalculationResult(calculator="vat", jurisdiction=inp.jurisdiction, currency=cur,
                            ruleset_version=data["ruleset_version"], inputs=inp.model_dump(mode="json"), outputs={})
    m = res.m
    res.assumptions.append("Place of supply is domestic unless reverse charge imports are entered.")

    if inp.mode in ("add_vat", "extract_vat"):
        rate = std if inp.rate_type == "standard" else ZERO
        if inp.mode == "add_vat":
            net = inp.amount
            vat = net * rate
            gross = net + vat
            res.add(TraceStep("Net amount", m(net), kind="input"))
            res.add(TraceStep(f"VAT at {rate:.0%} ({inp.rate_type})", m(vat), formula=f"{net:,.2f} x {rate:.0%}", rule_id=r_rate["rule_id"], kind="tax"))
            res.add(TraceStep("Gross amount", m(gross), kind="subtotal"))
        else:
            gross = inp.amount
            net = gross / (1 + rate)
            vat = gross - net
            res.add(TraceStep("Gross amount", m(gross), kind="input"))
            res.add(TraceStep(f"VAT extracted at {rate:.0%}", m(vat), formula=f"{gross:,.2f} - {gross:,.2f} / (1 + {rate})", rule_id=r_rate["rule_id"], kind="tax"))
            res.add(TraceStep("Net amount", m(net), kind="subtotal"))
        res.outputs = {"net": m(net), "vat": m(vat), "gross": m(gross), "rate": float(rate)}
        if inp.rate_type == "exempt":
            res.flag(Flag("exempt_supply", "info", "Exempt supply",
                          "No VAT is charged and input VAT attributable to exempt supplies is not recoverable (partial exemption applies to mixed businesses).",
                          "Oblique prepares input tax apportionment methods."))
    else:
        output_vat = inp.standard_rated_sales * std
        rc_vat = inp.reverse_charge_imports * std
        input_vat_gross = inp.standard_rated_purchases * std + rc_vat
        total_sales = inp.standard_rated_sales + inp.zero_rated_sales + inp.exempt_sales
        taxable_sales = inp.standard_rated_sales + inp.zero_rated_sales
        recovery = (taxable_sales / total_sales) if total_sales else Decimal(1)
        recoverable = max(input_vat_gross - inp.blocked_input_vat, ZERO) * recovery
        net_payable = output_vat + rc_vat - recoverable

        res.add(TraceStep("Output VAT on standard-rated sales", m(output_vat), formula=f"{inp.standard_rated_sales:,.0f} x {std:.0%}", rule_id=r_rate["rule_id"], kind="tax"))
        res.add(TraceStep("Zero-rated sales (0%, input VAT recoverable)", m(inp.zero_rated_sales), rule_id=r_rate["rule_id"], kind="info"))
        res.add(TraceStep("Exempt sales (no VAT, input VAT restricted)", m(inp.exempt_sales), rule_id=r_rate["rule_id"], kind="info"))
        if rc_vat:
            res.add(TraceStep("Reverse-charge VAT on imports (output and input)", m(rc_vat), rule_id=r_rate["rule_id"], kind="tax"))
        res.add(TraceStep("Input VAT on purchases and imports", m(input_vat_gross)))
        if inp.blocked_input_vat:
            res.add(TraceStep("Less: blocked input VAT", m(-inp.blocked_input_vat)))
        if recovery < 1:
            res.add(TraceStep("Input tax recovery ratio (taxable / total supplies, simplified)", ratio(taxable_sales, total_sales), kind="info"))
            res.flag(Flag("partial_exemption", "attention", "Partial exemption applies",
                          "Mixed taxable and exempt supplies require an input tax apportionment and an annual wash-up adjustment.",
                          "Oblique agrees apportionment methods with the authority."))
        res.add(TraceStep("Recoverable input VAT", m(recoverable), kind="subtotal"))
        res.add(TraceStep("Net VAT payable / (refundable)", m(net_payable), kind="tax"))
        res.outputs = {"output_vat": m(output_vat), "reverse_charge_vat": m(rc_vat), "recoverable_input_vat": m(recoverable),
                       "net_vat_payable": m(net_payable), "recovery_ratio": ratio(taxable_sales, total_sales) if total_sales else 1.0,
                       "position": "payable" if net_payable >= 0 else "refundable"}

    if inp.annual_taxable_supplies is not None:
        mand, vol = param(r_reg, "mandatory"), param(r_reg, "voluntary")
        status = "mandatory" if inp.annual_taxable_supplies > mand else "voluntary" if inp.annual_taxable_supplies > vol else "below_thresholds"
        res.outputs["registration_status"] = status
        res.add(TraceStep(f"Registration check: {status.replace('_', ' ')} (mandatory > {cur} {mand:,.0f}, voluntary > {cur} {vol:,.0f})",
                          m(inp.annual_taxable_supplies), rule_id=r_reg["rule_id"], kind="info"))
        if status == "mandatory":
            res.flag(Flag("vat_registration_required", "high", "VAT registration is mandatory",
                          f"Taxable supplies exceed {cur} {mand:,.0f}. Registration must be applied for within the statutory window; late registration penalties apply.",
                          "Oblique manages VAT registration and first-return filing."))

    res.apply_scope_gate(inp.scope_confirmed, inp.special_regime, SCOPE_EXCLUDED)
    return res
