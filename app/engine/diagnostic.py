"""Tax exposure diagnostic: a short questionnaire that returns a prioritised action list.

Deliberately not a numeric risk score (a score implies legal certainty and
under-weights deadlines). Deadline answers take precedence. Each action links
to the calculator or Oblique service that resolves it.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .core import Answer, DISCLAIMER

Profile = Literal["business", "personal"]

QUESTIONS: dict[str, dict[str, Any]] = {
    "deadline": {"profiles": ["business", "personal"], "label": "Do you have a tax filing or payment deadline within 30 days, or one already missed?",
                 "action": "Check the exact filing and payment date with the authority or your adviser now. UAE Corporate Tax returns are due 9 months after period end; VAT returns monthly or quarterly by the 28th; KSA zakat/CIT within 120 days of year end.",
                 "hook": "Oblique files returns and negotiates penalty waivers.", "link": None},
    "ct_registration": {"profiles": ["business"], "label": "Is your UAE Corporate Tax registration or first return status unclear?",
                        "action": "Confirm registration with the FTA (all juridical persons must register) and the first period's filing date. Late registration carries an AED 10,000 penalty.",
                        "hook": "Oblique handles registration and first-return readiness.", "link": "/uae/corporate-tax"},
    "vat_threshold": {"profiles": ["business"], "label": "Are your taxable supplies near or above AED 375,000 (UAE) or SAR 375,000 (KSA) in the last 12 months?",
                      "action": "Run the registration check: mandatory registration is required within the statutory window once the threshold is exceeded; voluntary registration from AED/SAR 187,500.",
                      "hook": "Oblique manages VAT registration and first returns.", "link": "/vat"},
    "free_zone": {"profiles": ["business"], "label": "Are you a Free Zone entity relying on the 0% rate?",
                  "action": "Test the Qualifying Free Zone Person conditions: adequate substance, audited financial statements, qualifying activities, transfer pricing compliance and the de minimis limit on non-qualifying revenue.",
                  "hook": "Oblique runs a Free Zone eligibility review.", "link": "/uae/corporate-tax#free-zone"},
    "cross_border": {"profiles": ["business", "personal"], "label": "Do you earn income or do business in more than one country?",
                     "action": "List each income source, contracting entity and work location for a residence, permanent-establishment, withholding-tax and treaty review.",
                     "hook": "Oblique prepares cross-border exposure maps.", "link": "/gcc/compare"},
    "related_party": {"profiles": ["business"], "label": "Are there transactions with connected persons or group companies?",
                      "action": "List related-party balances, fees and agreements. UAE requires arm's-length pricing, a TP disclosure form above AED 40m of related-party transactions and master/local files above revenue thresholds; KSA requires TP documentation for zakat payers too.",
                      "hook": "Oblique prepares TP documentation and benchmarking.", "link": None},
    "residency": {"profiles": ["personal", "business"], "label": "Are your personal tax residence or cross-border working arrangements unresolved?",
                  "action": "Prepare a dated travel and work calendar; identify homes, family ties and where decisions are made. Apply the home-country residence test before assuming the UAE's 0% rate applies to you.",
                  "hook": "Oblique provides residence reviews and UAE tax residency certificates.", "link": "/move"},
    "eligibility": {"profiles": ["business", "personal"], "label": "Are you unsure whether a relief, exemption or special regime applies (Small Business Relief, participation exemption, free zone, treaty rate)?",
                    "action": "Confirm the exact eligibility conditions and make any required election in the return before using a reduced rate or relief.",
                    "hook": "Oblique documents elections and relief positions.", "link": None},
    "records": {"profiles": ["business", "personal"], "label": "Are the records or reconciliations needed to support your tax position incomplete?",
                "action": "Reconcile the trial balance to returns; collect invoices, contracts and prior filings. UAE requires records for 7 years; audited financial statements are mandatory above AED 50m revenue and for all QFZPs.",
                "hook": "Oblique's accounting team rebuilds and reconciles records.", "link": None},
    "einvoicing": {"profiles": ["business"], "label": "Have you assessed UAE e-invoicing readiness (phased mandate starting July 2026)?",
                   "action": "Map invoice flows, select an accredited service provider and test the Peppol-based format ahead of your phase date.",
                   "hook": "Oblique runs e-invoicing readiness assessments.", "link": None},
}


class DiagnosticInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Profile = "business"
    answers: dict[str, Answer] = Field(..., description="Answers keyed by question id")


def questions(profile: Profile | None = None) -> dict[str, dict[str, Any]]:
    return {k: {"label": v["label"]} for k, v in QUESTIONS.items() if profile is None or profile in v["profiles"]}


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
        actions.append({"key": key, "answer": ans, "label": q["label"], "action": q["action"], "advisory_hook": q["hook"], "link": q["link"],
                        "urgency": "now" if key == "deadline" and ans == "yes" else "soon" if ans == "yes" else "clarify"})
    actions.sort(key=lambda a: {"now": 0, "soon": 1, "clarify": 2}[a["urgency"]])
    deadline = inp.answers.get("deadline", "unknown")
    priority = ("CHECK DEADLINE NOW" if deadline == "yes" else "CONFIRM DEADLINES" if deadline == "unknown"
                else "PLAN A REVIEW" if actions else "KEEP RECORDS CURRENT")
    return {
        "calculator": "tax_exposure_diagnostic", "profile": inp.profile, "priority": priority, "answers": inp.answers, "actions": actions,
        "open_items": len(actions), "methodology": "A checklist built from your answers. It is not a risk score and not a tax opinion.",
        "warnings": ["No flagged items does not establish compliance or confirm that no tax is due.",
                     "No contact details are needed to view, copy or print this checklist."],
        "disclaimer": DISCLAIMER, "persisted": False,
    }
