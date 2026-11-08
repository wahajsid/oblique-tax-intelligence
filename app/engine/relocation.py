"""Move-to-UAE comparison: origin-country personal tax versus the UAE's 0% personal income tax.

A lead-magnet tool that gives perspective, not a residence determination. It
computes the origin liability with the personal tax engine, converts at an
indicative (overridable) FX rate, applies the US residual rule for US persons,
and lays out annual, first-year and five-year differences with one-off and
recurring costs. Every output carries the desktop-estimate disclaimer.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .core import Answer, D, DISCLAIMER, ZERO, money, ratio
from . import personal_tax


class RelocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: personal_tax.CountryCode
    gross_income: Decimal = Field(..., ge=0, le=Decimal("1000000000"), description="Current annual gross income in the origin currency")
    uae_salary_aed: Decimal | None = Field(None, ge=0, description="Expected UAE package in AED (blank = same as current income converted)")
    fx_aed_per_unit: Decimal | None = Field(None, gt=0, description="Override: AED per 1 unit of origin currency")
    one_off_costs_aed: Decimal = Field(ZERO, ge=0, description="Relocation, visa, deposits, school fees etc.")
    additional_annual_costs_aed: Decimal = Field(ZERO, ge=0, description="Extra annual cost of living in the UAE vs home (housing, schooling, health cover)")
    years: int = Field(5, ge=1, le=10)
    # pass-through options
    cpf_member: bool = False
    us_person: bool = True
    state_tax_rate_pct: Decimal = Field(ZERO, ge=0, le=15)
    childless: bool = True
    # review answers
    residency_reviewed: Answer = "unknown"
    retained_connections: Answer = "unknown"

    @field_validator("uae_salary_aed", "fx_aed_per_unit", mode="before")
    @classmethod
    def _blank(cls, v: Any) -> Any:
        return None if v in ("", None) else v


def compare(inp: RelocationInput) -> dict[str, Any]:
    data = personal_tax.rules()
    c = data["countries"][inp.origin]
    cur = c["currency"]
    fx = inp.fx_aed_per_unit if inp.fx_aed_per_unit is not None else D(data["fx"]["aed_per_unit"][cur])

    origin = personal_tax.calculate(personal_tax.PersonalTaxInput(
        country=inp.origin, gross_income=inp.gross_income, cpf_member=inp.cpf_member, us_person=inp.us_person,
        state_tax_rate_pct=inp.state_tax_rate_pct, childless=inp.childless))
    o = origin.outputs
    origin_net_local = D(o["net_income"])
    origin_tax_local = D(o["total_deductions"])

    uae_gross_aed = inp.uae_salary_aed if inp.uae_salary_aed is not None else inp.gross_income * fx
    uae_tax_aed = ZERO
    uae_notes = ["UAE: 0% personal income tax and no social security for expatriate employees."]
    residual = None
    if inp.origin == "US" and inp.us_person:
        residual = personal_tax.calculate(personal_tax.PersonalTaxInput(country="US", gross_income=uae_gross_aed / fx, us_person=True, foreign_resident_after_move=True))
        uae_tax_aed = D(residual.outputs["total_deductions"]) * fx
        uae_notes.append("US person: residual US federal tax after the Foreign Earned Income Exclusion is included in the UAE column.")
    uae_net_aed = uae_gross_aed - uae_tax_aed - inp.additional_annual_costs_aed

    origin_net_aed = origin_net_local * fx
    origin_tax_aed = origin_tax_local * fx
    annual_gain_aed = uae_net_aed - origin_net_aed
    first_year_aed = annual_gain_aed - inp.one_off_costs_aed
    horizon_aed = annual_gain_aed * inp.years - inp.one_off_costs_aed
    payback_months = (inp.one_off_costs_aed / annual_gain_aed * 12) if annual_gain_aed > 0 and inp.one_off_costs_aed > 0 else None

    flags: list[dict[str, Any]] = [{"severity": "attention", "title": f"{c['name']}: breaking tax residence", "detail": f} for f in c.get("relocation_flags", [])]
    if inp.residency_reviewed != "yes":
        flags.append({"severity": "high", "title": "Residence not yet reviewed", "detail": "Whether and when you stop being taxable at home is the single biggest assumption in this comparison. Get a residence review before relying on the saving."})
    if inp.retained_connections != "no":
        flags.append({"severity": "attention", "title": "Retained home-country connections", "detail": "Property, business, family or significant days at home can keep you resident or keep home-source income taxable. Do not assume home tax falls to zero."})
    if inp.uae_salary_aed is None:
        flags.append({"severity": "info", "title": "UAE package assumed equal to current income", "detail": f"Converted at {fx} AED per {cur} (indicative rate as of {data['fx']['as_of']}). Enter your actual UAE offer for a real comparison."})
    flags.append({"severity": "info", "title": "Cost of living and benefits", "detail": "The UAE has 5% VAT, no state pension accrual for expatriates, and employer-funded health cover and end-of-service gratuity instead of social insurance. Use the 'additional annual costs' field to reflect housing and schooling."})

    m = lambda v, cur_=cur: money(v, cur_)  # noqa: E731
    return {
        "calculator": "move_to_uae",
        "origin": {"code": inp.origin, "name": c["name"], "flag": c["flag"], "currency": cur, "tax_year": c["tax_year"], "review_status": origin.review_status(),
                   "gross_local": m(inp.gross_income), "tax_local": m(origin_tax_local), "net_local": m(origin_net_local), "monthly_net_local": m(origin_net_local / 12),
                   "effective_rate": o["effective_rate"], "marginal_income_tax_rate": o["marginal_income_tax_rate"],
                   "gross_aed": money(inp.gross_income * fx, "AED"), "tax_aed": money(origin_tax_aed, "AED"), "net_aed": money(origin_net_aed, "AED"),
                   "result": origin.as_dict()},
        "uae": {"gross_aed": money(uae_gross_aed, "AED"), "tax_aed": money(uae_tax_aed, "AED"), "additional_costs_aed": money(inp.additional_annual_costs_aed, "AED"),
                "net_aed": money(uae_net_aed, "AED"), "monthly_net_aed": money(uae_net_aed / 12, "AED"), "notes": uae_notes,
                "residual_us": residual.as_dict() if residual else None},
        "comparison": {"fx_aed_per_unit": float(fx), "fx_as_of": data["fx"]["as_of"], "fx_overridden": inp.fx_aed_per_unit is not None,
                       "annual_net_gain_aed": money(annual_gain_aed, "AED"), "annual_net_gain_local": m(annual_gain_aed / fx),
                       "annual_tax_saved_aed": money(origin_tax_aed - uae_tax_aed, "AED"),
                       "first_year_gain_aed": money(first_year_aed, "AED"), "years": inp.years, "horizon_gain_aed": money(horizon_aed, "AED"),
                       "payback_months": float(payback_months.quantize(Decimal("0.1"))) if payback_months is not None else None,
                       "net_gain_pct_of_origin_net": ratio(annual_gain_aed, origin_net_aed) if origin_net_aed else None},
        "flags": flags,
        "assumptions": ["Recurring figures are held constant for the horizon; no inflation, salary growth, FX movement, investment return or discounting.",
                        "Origin tax is a full-year, single, employment-income estimate; split-year treatment, exit taxes and retained home-source income are not computed.",
                        "No tax-residence determination is made."] + origin.assumptions,
        "rules": origin.rule_metadata(),
        "review_status": origin.review_status(),
        "disclaimer": DISCLAIMER,
        "persisted": False,
    }
