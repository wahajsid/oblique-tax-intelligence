"""Tax exposure diagnostic: a short questionnaire that returns a prioritised action list.

Deliberately not a numeric risk score (a score implies legal certainty and
under-weights deadlines). Deadline answers take precedence. Each action links
to the calculator or Oblique service that resolves it.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .core import Answer, DISCLAIMER

Profile = Literal["business", "gcc", "personal"]

QUESTIONS: dict[str, dict[str, Any]] = {
    "deadline": {"profiles": ["business", "gcc", "personal"], "label": "A filing or payment due within 30 days, or already missed?",
                 "action": "Check the exact filing and payment date with the authority or your adviser now. UAE Corporate Tax returns are due 9 months after period end; VAT returns monthly or quarterly by the 28th; KSA zakat/CIT within 120 days of year end.",
                 "action_personal": "Check the exact date now. Typical personal deadlines: UK self-assessment 31 January; US federal return 15 April (15 June abroad, with extensions to October); India 31 July; Australia 31 October; Singapore 18 April; South Africa per the SARS filing season. Penalties and interest run from the deadline.",
                 "hook": "Oblique files returns and negotiates penalty waivers.", "link": None},
    "ct_registration": {"profiles": ["business"], "label": "Unsure about your UAE Corporate Tax registration or first return?",
                        "action": "Confirm registration with the FTA (all juridical persons must register) and the first period's filing date. Late registration carries an AED 10,000 penalty.",
                        "hook": "Oblique handles registration and first-return readiness.", "link": "/uae/corporate-tax"},
    "vat_threshold": {"profiles": ["business"], "label": "Taxable sales near or above AED or SAR 375,000 in the last 12 months?", "help": "The mandatory VAT registration threshold in both the UAE and KSA.",
                      "action": "Run the registration check: mandatory registration is required within the statutory window once the threshold is exceeded; voluntary registration from AED/SAR 187,500.",
                      "hook": "Oblique manages VAT registration and first returns.", "link": "/vat"},
    "free_zone": {"profiles": ["business"], "label": "A Free Zone entity relying on the 0% rate?",
                  "action": "Test the Qualifying Free Zone Person conditions: adequate substance, audited financial statements, qualifying activities, transfer pricing compliance and the de minimis limit on non-qualifying revenue.",
                  "hook": "Oblique runs a Free Zone eligibility review.", "link": "/uae/corporate-tax#free-zone"},
    "cross_border": {"profiles": ["business", "gcc", "personal"], "label": "Income or business in more than one country?",
                     "action": "List each income source, contracting entity and work location for a residence, permanent-establishment, withholding-tax and treaty review.",
                     "action_personal": "List each income source and where the work was done (employment, rental, dividends, pensions, capital gains). Home-source income usually stays taxable at home even after you move; treaties and foreign tax credits decide who taxes what.",
                     "hook": "Oblique prepares cross-border exposure maps.", "link": "/move"},
    "related_party": {"profiles": ["business", "gcc"], "label": "Transactions with group companies or connected people?",
                      "action": "List related-party balances, fees and agreements. UAE requires arm's-length pricing, a TP disclosure form above AED 40m of related-party transactions and master/local files above revenue thresholds; KSA requires TP documentation for zakat payers too.",
                      "hook": "Oblique prepares TP documentation and benchmarking.", "link": None},
    "residency": {"profiles": ["personal", "business"], "label": "Tax residence or cross-border working not yet settled?",
                  "action": "Prepare a dated travel and work calendar; identify homes, family ties and where decisions are made. Apply the home-country residence test before assuming the UAE's 0% rate applies to you.",
                  "hook": "Oblique provides residence reviews and UAE tax residency certificates.", "link": "/move"},
    "eligibility": {"profiles": ["business", "gcc", "personal"], "label": "Unsure whether a relief, exemption or special regime applies?",
                    "label_personal": "Unsure whether a relief or treaty benefit applies to you?", "help_personal": "Split-year treatment, foreign earned income exclusion, non-resident rates, treaty tie-breakers.",
                    "action": "Confirm the exact eligibility conditions (Small Business Relief, participation exemption, free zone, treaty rate) and make any required election in the return before using a reduced rate or relief.",
                    "action_personal": "Confirm the conditions and claim the relief in the right return and year: split-year or departure rules at home, UAE tax residency certificate for treaty claims, foreign tax credits for income taxed twice.",
                    "hook": "Oblique documents elections and relief positions.", "link": None},
    "records": {"profiles": ["business", "gcc", "personal"], "label": "Records or reconciliations incomplete?",
                "label_personal": "Records for your residence and income incomplete?", "help_personal": "Travel days, tenancy, payslips, bank interest, disposals.",
                "action": "Reconcile the trial balance to returns; collect invoices, contracts and prior filings. UAE requires records for 7 years; audited financial statements are mandatory above AED 50m revenue and for all QFZPs.",
                "action_personal": "Keep a dated travel log with proof (boarding passes, entry stamps), tenancy or ownership documents, employment contracts and payslips, statements for interest and dividends, and records of asset disposals around the move date.",
                "hook": "Oblique's team assembles and reviews supporting records.", "link": None},
    "pe_risk": {"profiles": ["gcc"], "label": "People delivering work in another GCC country?", "help": "Employees, contractors or agents on the ground in Saudi Arabia, Qatar, Oman, Bahrain or Kuwait.",
                "action": "Log days per person per country from the first trip. A service permanent establishment arises once presence crosses the treaty threshold; a dependent agent who concludes contracts creates one at once. A PE means local registration and tax on the profit attributed to it.",
                "hook": "Oblique maps PE exposure and registers where needed.", "link": "/journeys/uae-saudi-transactions"},
    "wht_payments": {"profiles": ["gcc"], "label": "Paying or receiving cross-border fees, royalties, interest or dividends?", "help": "Saudi withholding runs 5% to 20%; Oman 10%; Qatar 5%; the UAE 0%.",
                     "action": "Identify the payment type and the statutory rate, then whether a treaty reduces it and whether relief at source is available or a refund must be claimed. Fix who bears it in the contract.",
                     "hook": "Oblique handles treaty relief and refunds.", "link": "/ksa/withholding-tax"},
    "vat_cross_border": {"profiles": ["gcc"], "label": "Selling goods or services to customers in another GCC country?", "help": "Each state applies its own VAT law; the GCC framework is not yet integrated.",
                         "action": "Determine the place of supply under both laws: exports of services are usually zero-rated or outside scope at home with the customer self-accounting abroad; goods follow customs. Keep the customer's VAT number and evidence of establishment.",
                         "hook": "Oblique prepares cross-border VAT positions.", "link": "/vat?j=SA"},
    "einvoicing": {"profiles": ["business"], "label": "Ready for UAE e-invoicing?", "help": "Pilot from 1 July 2026. Live 1 January 2027 if revenue is AED 50m or more, 1 July 2027 below that. Government entities 1 October 2027.",
                   "action": "Identify your phase by revenue: AED 50m or more means an accredited service provider appointed by 31 July 2026 and e-invoicing live from 1 January 2027; below AED 50m means appointment by 31 March 2027 and live from 1 July 2027 (Ministerial Decisions 243 and 244 of 2025). B2C is out of scope for now. Map invoice flows and test the Peppol-based format before your date.",
                   "hook": "Oblique runs e-invoicing readiness assessments.", "link": None},
}


class DiagnosticInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Profile = "business"
    answers: dict[str, Answer] = Field(..., description="Answers keyed by question id")


def questions(profile: Profile | None = None) -> dict[str, dict[str, Any]]:
    personal = profile == "personal"
    return {k: {"label": (v.get("label_personal") if personal and v.get("label_personal") else v["label"]),
                "help": (v.get("help_personal") if personal and v.get("help_personal") else v.get("help", ""))}
            for k, v in QUESTIONS.items() if profile is None or profile in v["profiles"]}


def question_list() -> list[dict[str, Any]]:
    """Ordered list for templates (Jinja's tojson sorts dict keys, which scrambled the order)."""
    return [dict(key=k, **v) for k, v in QUESTIONS.items()]


def run(inp: DiagnosticInput) -> dict[str, Any]:
    expected = set(questions(inp.profile))
    unknown = set(inp.answers) - set(QUESTIONS)
    if unknown:
        raise ValueError(f"Unknown question ids: {', '.join(sorted(unknown))}")
    missing = expected - set(inp.answers)
    if missing:
        raise ValueError(f"Answer every question for the {inp.profile} profile. Missing: {', '.join(sorted(missing))}")
    actions = []
    for key in questions(inp.profile):
        ans = inp.answers[key]
        if ans == "no":
            continue
        q = QUESTIONS[key]
        personal = inp.profile == "personal"
        actions.append({"key": key, "answer": ans, "label": q.get("label_personal") if personal and q.get("label_personal") else q["label"],
                        "action": q.get("action_personal") if personal and q.get("action_personal") else q["action"], "advisory_hook": q["hook"], "link": q["link"],
                        "urgency": "now" if key == "deadline" and ans == "yes" else "soon" if ans == "yes" else "clarify"})
    actions.sort(key=lambda a: {"now": 0, "soon": 1, "clarify": 2}[a["urgency"]])
    deadline = inp.answers.get("deadline", "unknown")
    priority = ("CHECK DEADLINE NOW" if deadline == "yes" else "CONFIRM DEADLINES" if deadline == "unknown"
                else "PLAN A REVIEW" if actions else "KEEP RECORDS CURRENT")
    from app import services as svc
    slugs = []
    for a in actions:
        sl = svc.DIAGNOSTIC_SERVICES.get(a["key"])
        if sl and sl not in slugs:
            slugs.append(sl)
    return {
        "calculator": "tax_exposure_diagnostic", "profile": inp.profile, "priority": priority, "answers": inp.answers, "actions": actions,
        "next_steps": [svc.get(sl) for sl in slugs[:3]],
        "open_items": len(actions), "methodology": "A checklist built from your answers. It is not a risk score and not a tax opinion.",
        "warnings": ["No flagged items does not establish compliance or confirm that no tax is due.",
                     "No contact details are needed to view, copy or print this checklist."],
        "disclaimer": DISCLAIMER, "persisted": False,
    }
