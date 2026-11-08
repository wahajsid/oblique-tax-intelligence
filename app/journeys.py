"""Cross-border journeys: a guide, a worked example computed by the engine, a document
checklist and one focused review offer. Content is drafted for review by a named
Oblique technical reviewer; every journey shows its review status."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.engine import ksa_wht, personal_tax, uae_ct, vat

REVIEW = {"status": "draft_for_review", "reviewer": "Pending named technical reviewer", "date": "2026-11-08"}

JOURNEYS: dict[str, dict[str, Any]] = {
    "uae-saudi-transactions": {
        "title": "Selling from the UAE into Saudi Arabia",
        "eyebrow": "Cross-border · UAE → KSA",
        "lead": "Four taxes can touch one invoice: Saudi withholding, VAT on both sides, permanent establishment, and UAE Corporate Tax. Here is how they fit, with a worked example.",
        "who": "UAE companies invoicing Saudi customers for services, software, royalties or management fees. Also Saudi finance teams paying UAE suppliers.",
        "service": "uae_ksa_transaction",
        "tools": [("KSA Withholding Tax", "/ksa/withholding-tax"), ("KSA VAT", "/vat?j=SA"), ("UAE Corporate Tax", "/uae/corporate-tax"), ("GCC comparison", "/gcc/compare")],
        "sections": [
            ("Withholding tax is the customer's problem that becomes yours",
             "A Saudi payer must withhold on payments to non-residents: 5% on technical and consulting services, 15% on royalties, 20% on management fees, 5% on dividends and interest. Unless the contract says otherwise, you receive the net. The UAE–KSA treaty can reduce or remove the withholding for business profits and services where you have no permanent establishment in Saudi Arabia, but ZATCA generally expects the payer to withhold at the statutory rate and the supplier to reclaim, unless a residency certificate and the treaty forms are in place before payment. Price the contract knowing which route you are on."),
            ("VAT: zero-rated out, reverse-charged in",
             "A service supplied by a UAE business to a Saudi business customer is normally outside the scope of UAE VAT or zero-rated as an export, depending on the service; the Saudi customer self-accounts for 15% KSA VAT under the reverse charge. Get the customer's VAT number on the invoice and keep evidence that the customer is established in Saudi Arabia. Services performed physically in Saudi Arabia, and anything connected to Saudi real estate, follow different place-of-supply rules."),
            ("People on the ground create a permanent establishment",
             "Employees or contractors delivering the project in Saudi Arabia can create a service permanent establishment once presence crosses the treaty threshold (counted across a twelve-month period), and a dependent agent who habitually concludes contracts creates one immediately. A PE means a Saudi tax registration, 20% income tax on the profit attributable to it, and a filing obligation. Track days per person per project from the first visit."),
            ("UAE Corporate Tax and the credit for Saudi tax",
             "The income is taxable in the UAE at 9% above the AED 375,000 band like any other revenue. Saudi withholding actually suffered can be credited against the UAE Corporate Tax on that income, capped at the UAE tax on it. Withholding that could have been avoided under the treaty is still creditable only to the extent it was legally due."),
        ],
        "mistakes": ["Quoting a price without saying who bears withholding, then absorbing 5% to 20%.", "Invoicing a Saudi customer with 5% UAE VAT.", "Letting consultants stay past the PE threshold with no tracking.", "Forgetting the foreign tax credit in the UAE return."],
        "checklist": ["Signed contract with a tax clause: who bears withholding, gross-up if any", "Customer's KSA VAT registration number and address", "UAE tax residency certificate for the supplier entity, renewed annually", "ZATCA treaty relief forms or a refund plan", "Day-count log per person per project in Saudi Arabia", "Evidence the work was performed from the UAE where it was", "Schedule of Saudi withholding suffered, for the UAE foreign tax credit"],
    },
    "uk-founder-moving-to-dubai": {
        "title": "A UK founder moving to Dubai, keeping the UK company",
        "eyebrow": "Relocation · UK → UAE",
        "lead": "Moving yourself is one decision. Where your company is taxed afterwards is a separate one, and running it from Dubai can move it with you.",
        "who": "UK founders and directors relocating to the UAE who will keep operating a UK limited company.",
        "service": "uk_company_review",
        "tools": [("UK → UAE comparison", "/move/gb-to-uae"), ("UAE Corporate Tax", "/uae/corporate-tax"), ("Diagnostic (individual)", "/diagnose")],
        "sections": [
            ("Your own residence: the Statutory Residence Test",
             "You stop being UK resident when you meet an automatic overseas test or fail the ties test. Most founders plan around full-time work abroad (fewer than 91 UK days and fewer than 31 UK workdays) or the day-count tests. Split-year treatment can apply in the year you leave, so timing the move against 6 April matters. Keep a day log from day one."),
            ("Your company's residence: where it is managed from",
             "A UK-incorporated company is UK resident by incorporation, but if its central management and control moves to Dubai it can also become UAE resident, or have a UAE permanent establishment, and face 9% UAE Corporate Tax on the profits attributable to the UAE. The UK–UAE treaty tie-breaks dual residence to the place of effective management. Board meetings, who decides what and where, and contracts signed from Dubai all count. The honest answer for a one-person company run from a Dubai apartment is often that the business has moved."),
            ("Salary and dividends after the move",
             "Salary for duties performed outside the UK is not UK-taxable once you are non-resident; the company can apply for a no-tax PAYE code. UK dividends paid to a non-resident are 'disregarded income': no further UK tax beyond any credit at source, and the UAE charges nothing. UK National Insurance can continue for a period under the detached-worker rules unless you stop it correctly."),
            ("Selling or restructuring",
             "Selling UK shares while non-resident is generally outside UK capital gains tax, but return within five years and the gain is taxed in the year you come back. A UAE holding company, a redomicile, or simply timing the exit are the usual options; each changes the UAE Corporate Tax and participation exemption picture."),
            ("What stays UK-taxable",
             "UK rental income (with the non-resident landlord scheme), UK pensions, and any UK workdays. Inheritance tax follows long-term residence rules that take years to shake off."),
        ],
        "mistakes": ["Assuming a UK company is UK-taxed only because it is UK-incorporated.", "Keeping director decisions in Dubai with no board minutes anywhere.", "Paying salary through PAYE at full UK rates for a year after leaving.", "Selling the company in year four of a planned three-year stint."],
        "checklist": ["Day-count log (UK and worldwide) from the departure date", "Form P85 and the no-tax PAYE code application", "Board minutes showing where decisions are taken", "UAE visa, Emirates ID and tenancy for the residency certificate", "UK property: non-resident landlord registration", "Pension and ISA review before departure", "Share valuation at the move date if an exit is planned"],
    },
    "free-zone-selling-to-mainland": {
        "title": "A Free Zone company selling into the mainland",
        "eyebrow": "UAE · Free Zone → Mainland",
        "lead": "The 0% rate was never for everything. Mainland sales are usually non-qualifying revenue, and the de minimis limit is lower than most people think.",
        "who": "Free Zone companies with UAE mainland customers, or planning to win them.",
        "service": "free_zone_review",
        "tools": [("UAE Corporate Tax (Free Zone section)", "/uae/corporate-tax#free-zone"), ("UAE VAT", "/vat?j=AE"), ("Diagnostic (business)", "/diagnose")],
        "sections": [
            ("What qualifies, and what does not",
             "A Qualifying Free Zone Person pays 0% only on Qualifying Income: income from transactions with other Free Zone persons (where they are the beneficial recipient) and from a closed list of qualifying activities, such as manufacturing, fund management, headquarters services, logistics and distribution from a designated zone. Selling goods or services to a mainland UAE customer is generally non-qualifying revenue, taxed at 9%, with no AED 375,000 band."),
            ("The de minimis limit",
             "Non-qualifying revenue must stay within the lower of 5% of total revenue and AED 5,000,000 in the period. Go over by a dirham and you are not a Qualifying Free Zone Person for that period and the following four: all income taxed at 9%. The test is on revenue, not profit, so a thin-margin mainland line can cost the status."),
            ("Three ways to serve the mainland",
             "Keep mainland sales under the de minimis cap and monitor it monthly. Or accept 9% on the mainland line while keeping 0% on qualifying income, which works only while the cap holds. Or set up a mainland branch or subsidiary to carry the mainland business at 9% with the AED 375,000 band, leaving the Free Zone entity clean. The right answer depends on margins, licence conditions and VAT."),
            ("VAT and licences",
             "Goods moving from a designated zone into the mainland are an import with 5% VAT; services follow the normal rules. The commercial licence may not permit mainland trading without a dual licence or a local distributor; the tax answer and the licence answer must match."),
            ("Substance, audit, transfer pricing",
             "Qualifying status also needs adequate substance in the Free Zone, audited financial statements, arm's-length pricing with related parties and no election out. Lose any one and the 0% goes with it."),
        ],
        "mistakes": ["Treating 5% as 5% of profit.", "Discovering a breach at year end instead of month three.", "Opening a mainland branch and leaving the Free Zone entity to invoice anyway.", "No audited accounts because the Free Zone never asked for them."],
        "checklist": ["Revenue by customer and by location (Free Zone, mainland, foreign)", "Qualifying activity mapping per revenue stream", "Monthly de minimis monitor", "Audited financial statements", "Transfer pricing file for related-party transactions", "Licence terms on mainland activity", "VAT treatment of designated-zone movements"],
    },
}


def worked_example(slug: str) -> dict[str, Any]:
    """Live numbers from the engine so the example can never drift from the calculators."""
    if slug == "uae-saudi-transactions":
        w = ksa_wht.calculate(ksa_wht.KSAWHTInput(payments=[{"category": "technical_consulting", "amount": 1_000_000}], scope_confirmed=True, special_regime="no"))
        w_treaty = ksa_wht.calculate(ksa_wht.KSAWHTInput(payments=[{"category": "technical_consulting", "amount": 1_000_000, "treaty_rate": 0}], scope_confirmed=True, special_regime="no"))
        v = vat.calculate(vat.VATInput(jurisdiction="SA", mode="add_vat", amount=1_000_000, scope_confirmed=True, special_regime="no"))
        ct_gross = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=400_000 * Decimal("0.97933"), revenue=1_000_000 * Decimal("0.97933"), scope_confirmed=True, special_regime="no"))
        ct = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=400_000 * Decimal("0.97933"), revenue=1_000_000 * Decimal("0.97933"), foreign_tax_credit=50_000 * Decimal("0.97933"), scope_confirmed=True, special_regime="no"))
        return {"intro": "A UAE consultancy bills a Saudi company SAR 1,000,000 for advisory work performed from Dubai, with a 40% margin.",
                "rows": [("Saudi withholding at the statutory 5% if no treaty relief is in place", f"SAR {w.outputs['total_wht']:,.0f} deducted by the customer"),
                         ("With treaty relief applied at source (residency certificate and forms in place)", f"SAR {w_treaty.outputs['total_wht']:,.0f}"),
                         ("KSA VAT, self-accounted by the customer under the reverse charge", f"SAR {v.outputs['vat']:,.0f} (not your cash)"),
                         ("UAE Corporate Tax on the AED-equivalent profit of about AED 391,700 (first year, so most sits in the AED 375,000 band)", f"AED {ct_gross.outputs['corporate_tax_payable']:,.0f} before credit; AED {ct.outputs['corporate_tax_payable']:,.0f} after the foreign tax credit for Saudi withholding suffered, which is capped at the UAE tax on that income"),
                         ("Effect on margin if withholding is absorbed and not recovered", "5 points of the 40% margin")],
                "links": [("Open this withholding example", "/ksa/withholding-tax#payments=%5B%7B%22category%22%3A%22technical_consulting%22%2C%22amount%22%3A1000000%2C%22treaty_rate%22%3Anull%2C%22grossed_up%22%3Afalse%7D%5D")]}
    if slug == "uk-founder-moving-to-dubai":
        before = personal_tax.calculate(personal_tax.PersonalTaxInput(country="GB", gross_income=Decimal(150_000)))
        co = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=600_000, revenue=2_000_000, scope_confirmed=True, special_regime="no"))
        return {"intro": "A founder pays herself GBP 150,000 from a UK company that makes AED 600,000 (about GBP 122,000) profit after her salary, and moves to Dubai in April.",
                "rows": [("UK income tax and National Insurance on the salary today", f"GBP {before.outputs['total_deductions']:,.0f} a year ({before.outputs['effective_rate']*100:.1f}%)"),
                         ("UK tax on the same salary once non-resident with duties performed in Dubai", "GBP 0, with a no-tax PAYE code"),
                         ("UAE personal income tax", "AED 0"),
                         ("If the company is now managed and controlled from Dubai: UAE Corporate Tax on its AED 600,000 profit", f"AED {co.outputs['corporate_tax_payable']:,.0f} a year (9% above the AED 375,000 band), with UK corporation tax relief to be claimed under the treaty"),
                         ("If the company stays UK-managed (board and decisions genuinely in the UK)", "UK corporation tax at 19% to 25% continues; no UAE Corporate Tax, but a UAE permanent establishment must still be ruled out")],
                "links": [("Open the UK → UAE comparison at GBP 150,000", "/move/gb-to-uae#gross_income=150000")]}
    if slug == "free-zone-selling-to-mainland":
        ok = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=3_000_000, revenue=20_000_000, is_free_zone_person=True, elect_qfzp=True, qualifying_income=2_850_000, non_qualifying_revenue=900_000, scope_confirmed=True, special_regime="no"))
        breach = uae_ct.calculate(uae_ct.UAECorporateTaxInput(accounting_profit=3_000_000, revenue=20_000_000, is_free_zone_person=True, elect_qfzp=True, qualifying_income=2_850_000, non_qualifying_revenue=1_200_000, scope_confirmed=True, special_regime="no"))
        return {"intro": "A Free Zone distributor has AED 20m revenue and AED 3m profit. Its de minimis cap is the lower of 5% of revenue (AED 1m) and AED 5m, so AED 1,000,000.",
                "rows": [("Mainland sales of AED 900,000 (within the cap): tax on the non-qualifying share of profit", f"AED {ok.outputs['corporate_tax_payable']:,.0f}, status kept"),
                         ("Mainland sales of AED 1,200,000 (cap breached): status lost for five periods, everything at 9%", f"AED {breach.outputs['corporate_tax_payable']:,.0f} this year, and similar for the next four"),
                         ("Cost of the extra AED 300,000 of mainland sales", f"AED {breach.outputs['corporate_tax_payable'] - ok.outputs['corporate_tax_payable']:,.0f} of additional tax in year one alone"),
                         ("Alternative: a mainland subsidiary carrying the AED 1.2m of mainland sales at, say, 15% margin", "AED 0 (profit AED 180,000 sits under the AED 375,000 band); Free Zone entity keeps 0%")],
                "links": [("Open the breach case in the calculator", "/uae/corporate-tax#accounting_profit=3000000&revenue=20000000&is_free_zone_person=1&elect_qfzp=1&qualifying_income=2850000&non_qualifying_revenue=1200000")]}
    raise KeyError(slug)


def get(slug: str) -> dict[str, Any]:
    j = dict(JOURNEYS[slug])
    j["slug"] = slug
    j["example"] = worked_example(slug)
    j["review"] = REVIEW
    return j
