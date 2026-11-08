"""Service catalogue: the specific next step a result should lead to.

The calculation is free. The service is the expert's judgement. Each entry says who it
is for, what the review covers, what the person receives, what is excluded and how it
starts. Calculators and flags map to services through recommend().
"""
from __future__ import annotations

from typing import Any

START = "A complimentary 30-minute call to scope it, then a fixed-fee proposal before any work starts."

SERVICES: dict[str, dict[str, Any]] = {
    "free_zone_review": {
        "title": "Review my Free Zone eligibility", "audience": "business",
        "for": "Free Zone companies relying on the 0% rate, or deciding whether to.",
        "includes": ["Qualifying Free Zone Person conditions: substance, audited accounts, transfer pricing, elections", "Classification of each revenue stream as qualifying, excluded or non-qualifying", "De minimis headroom and the five-period consequence of a breach", "Mainland branch or subsidiary alternative, with the numbers"],
        "receive": "A written position per revenue stream, the de minimis calculation, and a recommended structure.",
        "excludes": ["Filing the return (separate engagement)", "Licensing work with the Free Zone authority"],
        "start": START},
    "uae_ct_review": {
        "title": "Review my Corporate Tax computation", "audience": "business",
        "for": "Companies preparing or checking a UAE Corporate Tax return.",
        "includes": ["Accounting-to-tax reconciliation line by line", "Reliefs and elections: Small Business Relief, participation exemption, realisation basis, losses", "Interest cap and related-party adjustments", "Filing readiness and payment timing"],
        "receive": "A reviewed computation, the elections to make, and a list of open points with our recommendation on each.",
        "excludes": ["Statutory audit", "Prior-period amendments unless scoped"],
        "start": START},
    "sbr_check": {
        "title": "Confirm Small Business Relief", "audience": "business",
        "for": "Resident businesses near or under AED 3m revenue.",
        "includes": ["Revenue test for the current and every previous period", "Eligibility exclusions (Free Zone, MNE group)", "What the election costs you: losses, interest carry-forward", "Period-end dates against the 31 December 2029 cut-off"],
        "receive": "A yes/no with the evidence, and the election wording for the return.",
        "excludes": ["Bookkeeping to establish revenue"], "start": START},
    "uae_ksa_transaction": {
        "title": "Check a UAE–Saudi transaction", "audience": "business",
        "for": "UAE businesses invoicing Saudi customers, or Saudi businesses paying UAE suppliers.",
        "includes": ["Saudi withholding tax by payment type and whether treaty relief applies at source", "VAT on both sides: export of services, reverse charge, place of supply", "Permanent establishment risk from people on the ground", "UAE Corporate Tax treatment and foreign tax credit"],
        "receive": "A transaction memo: the taxes that apply, the rates, who pays, the documents each party needs, and the pricing impact.",
        "excludes": ["Contract drafting", "ZATCA refund filings unless scoped"], "start": START},
    "vat_registration": {
        "title": "Register for VAT and file the first return", "audience": "business",
        "for": "Businesses crossing the AED or SAR 375,000 threshold.",
        "includes": ["Threshold test and the registration deadline", "Registration with the FTA or ZATCA", "First-return setup: tax codes, invoices, reverse charge", "Penalty exposure if late"],
        "receive": "An active registration, a filed first return, and a compliance calendar.",
        "excludes": ["Ongoing monthly bookkeeping unless scoped"], "start": START},
    "partial_exemption": {
        "title": "Agree an input tax apportionment", "audience": "business",
        "for": "Businesses with both taxable and exempt supplies.",
        "includes": ["Standard method calculation and whether a special method is better", "Annual wash-up adjustment", "Capital asset scheme items"],
        "receive": "An apportionment method, the workings, and the authority correspondence if a special method is sought.",
        "excludes": ["Historic corrections beyond the current period unless scoped"], "start": START},
    "zakat_computation": {
        "title": "Prepare my zakat and income tax computation", "audience": "business",
        "for": "Saudi companies, including mixed Saudi and foreign ownership.",
        "includes": ["Zakat base under the 2024 Regulations including the alternative bases", "Split between zakat and income tax by shareholding", "Loss utilisation and adjustments", "ZATCA filing"],
        "receive": "A filed computation with a reconciliation to the accounts and a note of positions taken.",
        "excludes": ["Audit of the financial statements"], "start": START},
    "wht_treaty": {
        "title": "Apply treaty relief on withholding tax", "audience": "business",
        "for": "Saudi payers and their foreign suppliers.",
        "includes": ["Treaty rate for each payment type", "Documents to hold: residency certificate, beneficial ownership", "Relief at source versus pay-and-refund", "Gross-up clauses in contracts"],
        "receive": "The applicable rate per payment, the document pack, and the ZATCA forms.",
        "excludes": ["Negotiating the commercial contract"], "start": START},
    "tp_documentation": {
        "title": "Transfer pricing documentation", "audience": "business",
        "for": "Groups with related-party transactions in the UAE or KSA.",
        "includes": ["Threshold check for disclosure form, master file and local file", "Benchmarking of the main transactions", "Intercompany agreements review"],
        "receive": "The disclosure form, documentation that meets the thresholds, and a benchmarking report.",
        "excludes": ["Advance pricing agreements"], "start": START},
    "dmtt_assessment": {
        "title": "Pillar Two impact assessment", "audience": "business",
        "for": "UAE or GCC entities of groups with EUR 750m or more revenue.",
        "includes": ["Scope test and safe harbours", "GloBE income and covered taxes per jurisdiction", "Top-up estimate and filing obligations"],
        "receive": "A jurisdiction-by-jurisdiction top-up estimate and a compliance plan.",
        "excludes": ["Group-wide GloBE return preparation unless scoped"], "start": START},
    "einvoicing_readiness": {
        "title": "E-invoicing readiness", "audience": "business",
        "for": "UAE businesses ahead of their 2027 phase date.",
        "includes": ["Phase and deadline by revenue", "Invoice flow mapping and data gaps", "Accredited service provider selection", "Test plan"],
        "receive": "A readiness report with a dated action plan.",
        "excludes": ["System implementation"], "start": START},
    "residency_review": {
        "title": "Review my tax residency", "audience": "personal",
        "for": "Individuals moving to the UAE, or already here, unsure where they are taxable.",
        "includes": ["Home-country residence test applied to your travel and ties", "Split-year or departure treatment", "UAE tax residency certificate eligibility", "Income that stays taxable at home"],
        "receive": "A written residency position, the dates that matter, and a record-keeping plan.",
        "excludes": ["Home-country tax return preparation unless scoped"], "start": START},
    "relocation_plan": {
        "title": "Plan my move to the UAE", "audience": "personal",
        "for": "Founders, executives and families relocating.",
        "includes": ["Timing of the move against both tax years", "Assets to deal with before you leave: shares, property, pensions", "What your UAE package should look like", "The first 90 days: visa, Emirates ID, residency certificate"],
        "receive": "A dated plan with the tax consequences of each step.",
        "excludes": ["Immigration filings (we can refer)"], "start": START},
    "uk_company_review": {
        "title": "Keep my UK company while in Dubai", "audience": "personal",
        "for": "UK founders who will run a UK company from the UAE.",
        "includes": ["Company residence: central management and control from Dubai", "UAE Corporate Tax and permanent establishment exposure", "Salary, dividends and the UK–UAE treaty", "Exit alternatives: UAE holding, redomicile, sale timing"],
        "receive": "A structure recommendation with the UK and UAE tax on each option.",
        "excludes": ["UK company secretarial work"], "start": START},
}

CALCULATOR_SERVICES: dict[str, list[str]] = {
    "uae_corporate_tax": ["uae_ct_review"],
    "vat": ["vat_registration"],
    "ksa_zakat_income_tax": ["zakat_computation"],
    "ksa_withholding_tax": ["wht_treaty", "uae_ksa_transaction"],
    "gcc_compare": ["uae_ksa_transaction", "tp_documentation"],
    "personal_income_tax": ["residency_review"],
    "move_to_uae": ["residency_review", "relocation_plan"],
    "tax_exposure_diagnostic": [],
}

FLAG_SERVICES: dict[str, str] = {
    "qfzp_de_minimis_breached": "free_zone_review", "fz_not_qfzp": "free_zone_review",
    "sbr_not_available": "sbr_check", "sbr_prior_periods_unconfirmed": "sbr_check", "sbr_extension_unverified": "sbr_check",
    "dmtt_in_scope": "dmtt_assessment", "tp_documentation": "tp_documentation", "interest_limitation_untested": "uae_ct_review",
    "participation_exemption_conditions": "uae_ct_review",
    "vat_registration_required": "vat_registration", "partial_exemption": "partial_exemption", "exempt_supply": "partial_exemption",
    "zakat_minimum_base": "zakat_computation", "ksa_wht_and_tp": "wht_treaty",
    "us_state_tax": "residency_review", "gb_60pct_trap": "residency_review",
}

DIAGNOSTIC_SERVICES: dict[str, str] = {
    "free_zone": "free_zone_review", "ct_registration": "uae_ct_review", "vat_threshold": "vat_registration",
    "related_party": "tp_documentation", "einvoicing": "einvoicing_readiness", "residency": "residency_review",
    "cross_border": "uae_ksa_transaction", "pe_risk": "uae_ksa_transaction", "wht_payments": "wht_treaty", "vat_cross_border": "uae_ksa_transaction",
}


def get(slug: str) -> dict[str, Any]:
    return dict(slug=slug, **SERVICES[slug])


def recommend(calculator: str, flag_codes: list[str], extra: list[str] | None = None, limit: int = 3) -> list[dict[str, Any]]:
    """Ordered, de-duplicated recommendations: flag-driven first (most specific), then the calculator default."""
    slugs: list[str] = []
    for code in flag_codes:
        s = FLAG_SERVICES.get(code)
        if s and s not in slugs:
            slugs.append(s)
    for s in (extra or []) + CALCULATOR_SERVICES.get(calculator, []):
        if s not in slugs:
            slugs.append(s)
    return [get(s) for s in slugs[:limit]]
