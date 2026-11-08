# Oblique Tax Website V4 vs. the Oblique Tax Intelligence prototype in this repo

Date: 8 November 2026. V4 = the `Oblique-Tax-Website-V4.zip` package (FastAPI + single `index.html`, 8 rules,
38 tests, decision log, QA report). "This repo" = the prototype built on 7 November from the CountryTaxCalc evaluation
and the GCC-first strategy brief. Both were run locally, probed with curl and exercised in headless Chromium.

## One-paragraph verdict

The two builds are complementary, not duplicates. V4 is a **governance and trust layer**: narrow, scope-gated
arithmetic, a review-required path when applicability is unknown, a six-question diagnostic, a relocation cash-flow
tool, strict privacy and security headers, and a disciplined decision log with launch gates. This repo is a **tax
engine and distribution layer**: real reconciliations (UAE CT with SBR, QFZP, losses, interest cap, DMTT; KSA zakat
base with mixed ownership; KSA WHT; VAT returns), a six-country comparison engine, guide and comparison pages, a
published API, and the real obliqueconsult.com brand. Where V4 is lacking is depth, distribution and brand; where this
repo is lacking is V4's caution, privacy posture and accessibility hygiene. The right next step is to merge: keep this
repo's engine, pages and brand, and port V4's gating, diagnostic, relocation module, security headers and governance
documents.

## Where V4 is lacking (relative to this repo and the strategy brief)

| Gap | Evidence in V4 | What this repo has |
| --- | --- | --- |
| **P0 modules missing.** The brief's launch set is UAE CT, UAE VAT, KSA Zakat and income tax, KSA VAT and WHT, GCC comparison. | Saudi Arabia offers only standard-rated VAT (`SA.tools = ["vat"]`). No zakat, no 20% income tax, no withholding tax anywhere. The calculator page states these are "deliberately not calculated". | KSA zakat base under the 2024 Regulations with minimum-base rule and Saudi/non-Saudi split; WHT by category with treaty rate and gross-up; 25% loss cap. |
| **UAE CT is a one-line formula.** | `AE-CT-ORDINARY`: `max(0, base - 375000) x 9%`. Input "must already be taxable income". Excluded: free zone, reliefs, losses, credits, DMTT. | Accounting-profit-to-taxable-income reconciliation, Small Business Relief election with eligibility checks, QFZP with de minimis test and status loss, 75% loss offset, interest cap (30% EBITDA / AED 12m), 50% entertainment, foreign tax credit, DMTT screen. |
| **VAT is add-only.** | `base x rate - input_vat`. No extraction from gross, no period return, no reverse charge, no partial exemption, no registration thresholds. | Add, extract, period return with reverse charge and recovery ratio, mandatory/voluntary registration check for AE and SA. |
| **No cross-jurisdiction comparison.** | One country at a time. | Six-country comparison engine, capability matrix, 15 pairwise pages, home-page quick table. |
| **Zero search distribution.** | `<meta name="robots" content="noindex,nofollow">`, one HTML file with `{{title}}` substitution, four generic guides, no sitemap, no schema.org, no per-jurisdiction pages. CountryTaxCalc's entire advantage is 2,633 indexable templated URLs. | Per-jurisdiction guides, pairwise compare pages, sitemap.xml, robots.txt, WebApplication and Article JSON-LD, year-stamped titles. |
| **Brand does not match obliqueconsult.com.** | Decision log says "Preserve Oblique's navy/coral design" (#0d1420 / #e14f49 coral / #e6b665 gold, text glyph "◩" as logo). The live site is #0b0d12 with cyan #adebf2 and teal-to-lime gradients, Satoshi type, pill buttons, and the ob/co and oblique/consult wordmarks. | Tokens extracted from the live site by computed style (docs/BRAND.md); real SVG logos and favicon. |
| **Default path yields no number.** | `special_regime` defaults to "unknown" and `scope_confirmed` defaults to false, so a first click returns REVIEW REQUIRED with `amount: null`. Good caution, but CountryTaxCalc shows that the instant number is what earns the visit. | Instant result as you type, with the caveats carried as flags and a worst-status badge instead of suppressing the figure. |
| **Rule metadata is thin.** | 8 rules, one status (`SOURCE_RESEARCHED`), no effective-from/to dates, no verification notes, no distinction between primary and secondary confirmation. Period dates are "context only, not validated". | 25 rules across three files with effective dates, four review statuses, verification notes, source URLs; SBR cut-off is checked against the period end. |
| **API is hidden.** | `docs_url=None, redoc_url=None`; cross-origin POSTs rejected; no versioned path. The brief names API licensing as a revenue line. | `/api/v1/*`, Swagger and ReDoc, OpenAPI JSON, rules endpoints. |
| **Three-decimal currencies handled, but only for 8 rules.** | Correct BHD/OMR/KWD precision. | Comparison engine rounds to 2 decimals for every currency (see gaps below). |
| **Kuwait source gap.** | KDIPA PDF could not be retrieved; flagged as a launch gate. | Same figure (15% on foreign corporate bodies) marked `verified`; also needs primary-source confirmation. |
| **Tests check plumbing more than tax.** | 38 tests, mostly validation, headers, pages and the single-formula amounts. | 31 tests, each a hand-worked tax computation (loss caps, de minimis breach, interest cap, mixed ownership, gross-up, partial exemption) plus API and page tests. |

## Where this repo is lacking (relative to V4)

| Gap | Evidence in this repo | What V4 does |
| --- | --- | --- |
| **No "review required" gate.** A visitor who ticks "Free Zone" and "QFZP" without meeting conditions still gets a 0% figure with a flag. | Flags are advisory; the number always renders. | Suppresses the amount until scope is confirmed and no special regime applies; returns an explanation and next steps instead. |
| **No diagnostic module.** The brief's "tax exposure diagnostic" is only partly present as per-calculation flags. | Flags attached to results. | Standalone six-question diagnostic with deadline precedence and an action list, deliberately not a numeric score. |
| **No relocation tool.** | Not built. | UK/Singapore to UAE, personal/business, user-supplied estimates with first-year, five-year and payback arithmetic and residence warnings. |
| **Privacy posture is weaker.** | Loads Satoshi from api.fontshare.com and Inter from Google Fonts, so a third party sees visits; no privacy page; no CSP. | No external scripts or fonts, no cookies, no storage, CSP, no-store, no-referrer, frame denial, cross-origin POST rejection, errors never echo input, a privacy page, `noindex` while unapproved. |
| **Float arithmetic.** | Python floats with half-up rounding at the end; fine for estimates, not for statutory rounding claims. | `Decimal` end to end with per-currency precision. |
| **Two-decimal rounding for BHD, OMR, KWD.** | `money()` defaults to 2 places in the GCC comparison. | Currency `decimals` field drives rounding (3 for BHD/OMR/KWD). |
| **Accessibility basics.** | No skip link, no `noscript` message, results region not `aria-live`, form not disabled while a request is in flight, no reduced-motion rule. | Skip link, `noscript`, `aria-live` results, `aria-busy` forms, focus management to the result, reduced-motion and print rules. |
| **Governance documents.** | README, ROADMAP, EVALUATION. | Decision log with rationale and rejected options, QA report with observed browser results, technical spec with explicit launch gates and a rule lifecycle (`PLACEHOLDER` / `SOURCE_RESEARCHED` / `EXPERT_APPROVED`). |
| **Enquiry journey.** | A button to obliqueconsult.com. | Results-first optional enquiry preview with separate, unticked contact and marketing consents (demo only, nothing transmitted). |
| **Validation strictness.** | Pydantic defaults; unknown fields ignored. | `extra='forbid'`, bounded decimals, body-size and content-type checks. |

## Things both are missing

- Expert sign-off on any rule (both say so; V4 says it more loudly).
- Lead capture that actually delivers (CRM, email), consent records, retention policy.
- PDF or Excel working paper export (both offer JSON only).
- Arabic version, analytics events, rate limiting and API keys, hosting.
- Free Zone eligibility questionnaire, transfer pricing risk analyzer, full GloBE/DMTT computation.

## Recommended merge (one codebase)

1. **Base:** this repo (engine, pages, API, brand, SEO scaffolding).
2. **Port from V4 as-is:** security headers middleware and CSP; the six-question diagnostic (as `/diagnose` plus its API); the relocation module (as `/move`); the privacy page; `noindex` until expert approval; `extra='forbid'` on input models; `aria-live`, skip link, `noscript`, busy-state handling in `calc.js`.
3. **Adopt V4's gate, but keep the number:** add a "scope confirmed / special regime" control to each calculator. When unconfirmed, show the figure greyed with a REVIEW REQUIRED banner rather than suppressing it entirely. This preserves CountryTaxCalc's instant-value lesson while honouring V4's caution.
4. **Fix in this repo regardless:** Decimal arithmetic, per-currency decimals, self-host the Satoshi and Inter font files so no third-party request is made.
5. **Carry V4's governance files forward:** DECISIONS.md, TECHNICAL_SPEC.md launch gates and the rule lifecycle, with `EXPERT_APPROVED` mapped onto this repo's `verified` status only when a named reviewer signs.
6. **Drop from V4:** the navy/coral palette and glyph logo (replace with the extracted brand), the single-file page router, `docs_url=None`.

Estimated effort for the merge: two to three working days for one developer, excluding tax review.


---

## Addendum, 8 November 2026: gaps closed

All five items in "Where this repo is lacking" were ported the same day (see docs/DECISIONS.md):
scope gate (figure greyed, not hidden), standalone diagnostic and Move-to-UAE module (with real origin-country
engines rather than user-typed estimates), privacy posture (self-hosted fonts, CSP, headers, same-origin JSON-only
POSTs, no input echo, `noindex` by default, privacy page), Decimal arithmetic with per-currency precision, and
accessibility plus governance documents (skip link, live regions, busy states, decision log, launch gates, QA report).
Remaining from the V4 list: none. Remaining for both: expert sign-off, lead capture, PDF export, Arabic, API keys, hosting.
