"""GCC comparison engine: same operation modelled across six jurisdictions. Decimal arithmetic,
rounded to each jurisdiction's currency precision (3 decimals for BHD, OMR, KWD).

This is a screening tool. It separates headline statutory exposure from the
scope questions (ownership, MNE status, VAT implementation) that decide whether
a tax applies at all, and it never collapses everything into one score.
"""
from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .core import RULES_DIR, D, Flag, TraceStep, ZERO, money, ratio


@lru_cache(maxsize=None)
def profiles() -> dict:
    with (RULES_DIR / "gcc.json").open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def fx_table() -> dict:
    """AED per 1 unit of currency, shared with the relocation module (app/rules/personal.json)."""
    with (RULES_DIR / "personal.json").open(encoding="utf-8") as fh:
        return json.load(fh)["fx"]


SUPPORTED_CURRENCIES = ("USD", "AED", "SAR", "EUR", "GBP")


def aed_band_in(currency: str, aed_amount) -> tuple[Decimal, Decimal]:
    """Convert an AED threshold into the scenario currency. Returns (amount, aed_per_unit)."""
    rate = D(fx_table()["aed_per_unit"][currency])
    return D(aed_amount) / rate, rate


class GCCScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    taxable_profit: Decimal = Field(Decimal(1_000_000), ge=0)
    revenue: Decimal = Field(Decimal(5_000_000), ge=0)
    foreign_ownership_pct: Decimal = Field(Decimal(100), ge=0, le=100)
    is_mne_constituent: bool = False
    mne_group_revenue_eur: Decimal = Field(ZERO, ge=0)
    annual_royalties_paid_abroad: Decimal = Field(ZERO, ge=0)
    annual_management_fees_paid_abroad: Decimal = Field(ZERO, ge=0)
    dividends_distributed_abroad: Decimal = Field(ZERO, ge=0)
    jurisdictions: list[str] = Field(default_factory=lambda: ["AE", "SA", "BH", "OM", "QA", "KW"])
    currency: str = Field("USD", description="Currency the scenario figures are expressed in; AED thresholds are converted at the indicative FX table")

    @field_validator("currency")
    @classmethod
    def _cur(cls, v: str) -> str:
        v = v.upper()
        if v not in SUPPORTED_CURRENCIES:
            raise ValueError(f"currency must be one of {', '.join(SUPPORTED_CURRENCIES)}")
        return v


def compare(s: GCCScenario) -> dict:
    data = profiles()
    rows = []
    foreign = s.foreign_ownership_pct / 100
    cur = s.currency.upper()
    m = lambda v: money(v, cur)  # noqa: E731
    for code in s.jurisdictions:
        if code not in data["jurisdictions"]:
            raise ValueError(f"Unknown jurisdiction '{code}'")
        p = data["jurisdictions"][code]
        trace: list[TraceStep] = []
        flags: list[Flag] = []
        ct = p["corporate_tax"]
        rate = D(ct["headline_rate"])

        if code == "AE":
            band, fx_rate = aed_band_in(cur, ct["zero_band"])
            above = max(s.taxable_profit - band, ZERO)
            cit = above * rate
            trace.append(TraceStep(f"CT: 9% above the AED 375,000 band = {cur} {band:,.2f} at {fx_rate} AED per {cur}", m(cit),
                                   formula=f"({s.taxable_profit:,.0f} - {band:,.2f}) x 9%"))
            if cur != "AED":
                flags.append(Flag("ae_zero_band_fx", "info", "AED band converted at an indicative rate",
                                  f"The AED 375,000 zero-rate band was converted to {cur} {band:,.2f} using {fx_rate} AED per {cur} (table dated {fx_table()['as_of']}; USD and SAR are pegged).", None))
        elif code in ("SA", "QA", "KW"):
            cit = s.taxable_profit * foreign * rate
            trace.append(TraceStep(f"CIT: {rate:.0%} on non-GCC share ({foreign:.0%})", m(cit)))
        elif code == "BH":
            cit = ZERO
            trace.append(TraceStep("No general CIT in force (draft 10% law for FY2027 not enacted)", 0.0))
        else:
            cit = s.taxable_profit * rate
            trace.append(TraceStep(f"CIT: {rate:.0%} on all profits", m(cit)))

        zakat = ZERO
        if p["zakat"]["applies"]:
            if code == "SA":
                zakat = s.taxable_profit * (1 - foreign) * D("0.02577683")
                trace.append(TraceStep("Zakat: 2.577683% x GCC share, screening proxy using profit as base (actual base is net assets, min. adjusted profit)", m(zakat)))
                flags.append(Flag("sa_zakat_proxy", "attention", "Zakat base proxy", "Profit used as the base for screening; the real base is sources of funds less non-zakatable assets and can be materially higher.", "Use the KSA Zakat calculator for a proper base."))
            elif code == "KW":
                zakat = s.taxable_profit * (1 - foreign) * D(p["zakat"]["rate"])
                trace.append(TraceStep("Zakat: 1% of net profit for Kuwaiti shareholding (listed cos. also pay 2.5% NLST)", m(zakat)))

        wht = ZERO
        if code == "SA":
            wht = s.annual_royalties_paid_abroad * D("0.15") + s.annual_management_fees_paid_abroad * D("0.20") + s.dividends_distributed_abroad * D("0.05")
            trace.append(TraceStep("WHT: royalties 15%, management fees 20%, dividends 5%", m(wht)))
        elif code == "OM":
            wht = (s.annual_royalties_paid_abroad + s.annual_management_fees_paid_abroad) * D("0.10")
            trace.append(TraceStep("WHT: 10% on royalties and management fees; dividends suspended", m(wht)))
        elif code == "QA":
            wht = (s.annual_royalties_paid_abroad + s.annual_management_fees_paid_abroad) * D("0.05")
            trace.append(TraceStep("WHT: 5% on royalties and services; none on dividends", m(wht)))
        elif code == "KW":
            trace.append(TraceStep("No WHT; 5% retention mechanism on contractor payments", 0.0))
        else:
            trace.append(TraceStep("WHT: 0%", 0.0))

        dmtt_applies = p["dmtt"]["applies"] and s.is_mne_constituent and s.mne_group_revenue_eur >= 750_000_000
        top_up = ZERO
        if dmtt_applies:
            etr = (cit / s.taxable_profit) if s.taxable_profit else ZERO
            top_up = max(D("0.15") * s.taxable_profit - cit, ZERO) if etr < D("0.15") else ZERO
            trace.append(TraceStep("DMTT top-up to 15% (simplified screen)", m(top_up)))

        total = cit + zakat + wht + top_up
        rows.append({
            "code": code, "name": p["name"], "flag": p["flag"], "currency": p["currency"],
            "corporate_tax": m(cit), "zakat": m(zakat), "withholding_tax": m(wht), "dmtt_top_up": m(top_up), "total_direct_tax": m(total),
            "effective_rate_on_profit": ratio(total, s.taxable_profit) if s.taxable_profit else 0.0,
            "vat_rate": p["vat"]["rate"], "vat_implemented": p["vat"]["implemented"],
            "headline_cit_rate": float(rate), "cit_scope": ct["applies_to"], "cit_review_status": ct["review_status"],
            "dmtt_in_scope": dmtt_applies, "dmtt_review_status": p["dmtt"]["review_status"],
            "personal_income_tax": p["personal_income_tax"], "transfer_pricing": p["transfer_pricing"]["regime"],
            "cit_filing_deadline": p["cit_filing_deadline"],
            "trace": [t.as_dict() for t in trace], "flags": [f.as_dict() for f in flags],
        })
    rows.sort(key=lambda r: r["total_direct_tax"])
    return {
        "scenario": s.model_dump(mode="json"), "currency": cur, "ruleset_version": data["ruleset_version"], "rows": rows,
        "matrix": {code: data["jurisdictions"][code] for code in s.jurisdictions},
        "caveat": ("Desktop screening comparison only. Statutory liability, cash tax, compliance cost and effective rate are "
                   "shown separately on purpose; scope, exemptions, substance, treaty access and foreign tax credits "
                   "must be assessed before any structuring decision. For precise figures, get in touch with Oblique Consult."),
        "persisted": False,
    }
