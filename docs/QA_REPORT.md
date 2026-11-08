# QA report

Updated 8 November 2026 (lead capture, PDF, two live-site corrections). First pass 8 November 2026. Environment: Python 3.13, FastAPI 0.162, Pydantic 2.13, headless Chromium via Playwright. Development verification, not certification of law, accessibility or production security.

## Automated

`python -m pytest -q tests` → **64 passed**.

- `tests/test_engine.py` (25): UAE CT bands, reconciling items, 75% loss cap, SBR eligibility and refusal, QFZP with and without de minimis breach, interest cap, DMTT screen; VAT add/extract/return with partial exemption and registration thresholds; KSA zakat Gregorian/Hijri, mixed ownership, minimum base, 25% loss cap; KSA WHT rates, treaty, gross-up; GCC ranking, GCC-owned zakat, DMTT top-up.
- `tests/test_api.py` (6): health, rules, contract shape, 422s, every page renders, sitemap.
- `tests/test_v4_port_and_relocation.py` (33): scope gate default/confirmed/special-regime; unknown fields rejected; three-decimal currencies; half-up rounding; security headers and no-store; cross-origin 403, form body 415, oversize 413; validation errors do not echo input; no third-party assets in pages; noindex default; landmarks; eight personal-tax countries against hand-worked figures; UK taper; India rebate and marginal relief; US FEIE residual; Singapore CPF; disabled Pakistan; relocation arithmetic, FX override, explicit package, US residual; diagnostic precedence, ordering, clean sheet, validation; enquiries 503.

Hand-checked expectations (worked before running the code):

| Case | Expected | Engine |
|---|---|---|
| UK £75,000 | income tax 17,432.00; NI 3,016 + 494.60 | match |
| Hong Kong HK$600,000 | 58,500 progressive vs 87,300 standard, less 3,000 reduction = 55,500; MPF 18,000 | match |
| Singapore S$120,000 (no CPF) | 7,835 | match |
| India ₹20,00,000 | slab 185,000 + cess 7,400 = 192,400 | match |
| USA $150,000 single | federal 24,734; SS 9,300; Medicare 2,175 | match |
| Australia A$100,000 | 20,520 + levy 2,000 | match |
| Germany €60,000 | zvE 47,940 → 9,832; contributions 13,050 | match |
| South Africa R500,000 | 116,237 − 17,820 = 98,417; UIF 2,125.44 | match |
| UK → UAE, £75,000, AED 30k extra costs, AED 40k one-off | tax saved 102,618.74; net gain 72,618.74; first year 32,618.74; 5-year 323,093.70; payback 6.6 months | match |
| US person $200,000 in UAE | residual federal 36,734 − 20,630 = 16,104 | match |

## Browser (headless Chromium, 1440×900 and 390×844)

Screenshots in `docs/screenshots/prototype-v2/`.

1. Every page loads with **zero third-party requests** and no console or page errors (home, calculators, move pages for GB/US/IN, personal tax DE, diagnostic, GCC comparison, privacy, methodology).
2. Horizontal scroll width equals the viewport on desktop and mobile (no overflow).
3. UAE CT default state shows outcome "Review required", the banner with reasons, and greyed tiles; after selecting "No, my facts fit the ordinary scope" and ticking the confirmation the outcome changes to "Illustrative estimate" and the tile reads AED 101,250 for the AED 1.5m / AED 12m default.
4. Move GB→UAE renders the gain card (AED 102,618.74 at the default inputs, which carry no extra costs), the side-by-side, tiles, flags (residence not reviewed = high), working paper and rules.
5. Move US→UAE shows the residual US tax line in the UAE column; Move IN→UAE shows AED 11,934 for ₹24 lakh.
6. Diagnostic with deadline = yes shows "CHECK DEADLINE NOW" and 10 open items for the business profile.
7. First Tab press focuses the "Skip to content" link.
8. Fonts load from `/static/fonts/` (Satoshi 400/500/700, Inter 400/500/600).

## Not verified / limits

- No qualified tax adviser has signed off any rule; statuses are as recorded in the rules files.
- Screen-reader, Safari and Firefox runs not performed; keyboard navigation checked only for the first focus stop.
- FX table is indicative as of 2026-11-06 and not sourced from a central bank feed.
- No load, penetration, hosting or proxy tests. `'unsafe-inline'` remains in the CSP for per-page scripts and Swagger.
- Download and copy-link buttons were code-reviewed and exercised in the first build; the downloaded JSON bytes were not inspected in this pass.


## Update: live-site corrections and lead capture / PDF (8 November 2026, later)

Corrections reported by the owner from the live site, both fixed and pushed:

| Issue | Before | After | Commit |
|---|---|---|---|
| GCC comparison treated the AED 375,000 band as USD 375,000 | USD 1m profit → USD 56,250 | band = 375,000 / 3.6725 = USD 102,110.28 → USD 80,810.07; currency selector (USD, AED, SAR, EUR, GBP); rate shown in the trace | `eff299c` |
| Small Business Relief refused for periods ending after 31 Dec 2026 | 2027 period → standard 9% | cut-off 31 Dec 2029 per Ministerial Decision No. 131 of 2026 (MoF); tests for 2027/2028/2029 allowed, 2030 refused | `5ebd3a3` |

New automated coverage: `tests/test_leads_and_pdf.py` (PDF renders for all eight calculators; server recomputes and rejects client-supplied outputs; PDF free when no sink is configured and 403 without a token when one is; lead 503 without sink; SQLite sink end-to-end with consent text/version/timestamp and hashed IP; contact consent required; invalid email and unknown fields rejected; honeypot silently dropped; rate limit 429; delivery failure 502; token expiry; old endpoint 410). Suite total: **84 passed**.

Browser run (headless Chromium, SQLite sink enabled): PDF button opens the dialog with consent texts loaded and focus on the name field; submitting without the required consent keeps the dialog open; with consent, the lead is stored and a PDF download starts (`oblique-working-paper-uae-corporate-tax.pdf`, `%PDF-` header); success message shown; Escape closes and returns focus; a direct PDF request without a token returns 403; the Move page button opens the same dialog. Two defects found and fixed during the run: the hidden dialog overlay intercepted clicks (CSS `display` overriding `hidden`), and the success message was inside the hidden form.

PDF content checked by eye for the UAE Corporate Tax working paper: logo header, generated-at and ruleset line, headline tiles, working-paper table with formulas and rule ids, inputs, rules with status and source, assumptions, desktop-calculator disclaimer and Oblique contact details, page footer. Not yet checked by eye: the other seven layouts beyond byte-level rendering.


## Update: owner's live-site review (8 November 2026, evening)

All "fix first" items and all "improve next" items from the owner's review are implemented. Suite: **88 passed**. Browser run (headless Chromium, SQLite sink enabled):

| Review item | Verification |
|---|---|
| Currency band in USD comparison | fixed earlier (`eff299c`); home table shows USD 80,810.07 |
| SBR 2029 cut-off and prior-period revenue condition | 2027 period accepted when prior periods confirmed; "No" refuses with the permanent-loss reason; "not sure" applies the relief but marks the outcome review-required |
| Shared links change the facts | KSA WHT link reopened with the same four payments and SAR 71,173.80 total; US relocation link reopened with citizenship unchecked and the same AED 132,977.55 gain; links now live in the URL fragment (never sent to servers); legacy `?query` links still prefill |
| Privacy wording on share links | corrected on /privacy (fragment behaviour, browser history, older query links) |
| E-invoicing dates | question and action state pilot 1 July 2026, Phase 1 (AED 50m+) live 1 January 2027, Phase 2 live 1 July 2027, government 1 October 2027 (MD 243/244 of 2025); Phase 1 ASP date 31 July 2026 flagged for confirmation |
| Old results after invalid input | result panel greys with "Showing the previous result" and the validation message; clears on the next valid calculation |
| Labels for assistive technology | zero unlabelled controls on the UAE CT form; hints exposed through aria-describedby |
| Personal diagnostics | personal profile uses personal labels and actions (no corporate tax, trial balance or QFZP wording); e-invoicing excluded |
| Enquiry journey | "Get precise figures" opens the in-site dialog when a destination is configured; business / individual paths; individuals skip the company field; scenario attached only via the consent form |
| Verified vs review required; internal labels; versions | badge reads "Rules: Verified" with a tooltip, outcome label reads "Outcome: review required"; P0/P1 pills removed; footer shows "App v0.1.0 · Tax rules: AE 2026.2, SA 2026.1, GCC 2026.2, Personal 2026.1" |

Not covered: mobile rendering on real devices (desktop and 390 px headless only), screen-reader run, tax-law certification.


## Update: decision-led journey (8 November 2026, night)

Added: three entry paths on the home page with tailored path pages; a service catalogue (14 services) with includes / you receive / not included, recommended per result from flags and calculator; a cross-border diagnostic profile with permanent establishment, withholding and cross-border VAT questions; three journeys (UAE→Saudi transactions, UK founder keeping a UK company, Free Zone selling to the mainland) with live worked examples, checklists and one review offer each; a confidence panel on every result; enquiry dialog with question-first fields, optional attachment of inputs, and the free 30-minute booking link; utm_source attribution. Suite: see latest run in CI. Journeys and services are marked draft for technical and partner review.

## External audit of the live site, 8 November 2026

An outside review (text-only crawl, no JavaScript) was received after the day's fixes were pushed. Status of each finding:

| Finding | Status |
|---|---|
| GCC comparison applied AED 375,000 as USD | Fixed earlier the same day (USD 80,810.07; GCC 2026.1 changelog) |
| Small Business Relief cut-off 2026 | Fixed earlier the same day (AE 2026.2, MD 131/2026, prior-period condition) |
| No integrated enquiry form | Built: enquiry dialog, consent, PDF working paper, service buttons. Collects nothing until a destination is configured on the host |
| Share links carry figures in the URL | Fixed earlier: inputs travel in the fragment, never sent to a server; copy warns |
| KSA VAT "since 2018", Bahrain "since 2019" | Fixed now: `since` is the current-rate date, `introduced` added (GCC 2026.2) |
| Oman PIT 2028 "uncertain" | Note restated against RD 56/2025; stays pending verification until the executive regulations are checked |
| HK 2025/26 and India FY 2025-26 tax years | Open. Current-year rates need verification from primary sources before the engines are updated (launch gate 2) |
| "Reviewed by Oblique tax team" vs actual approvals | Journeys approved by the team on 8 Nov; rule files carry `reviewed_by`; the Arabic catalogue is marked pending |
| API keys and rate limits | Open by design while the API is unpromoted; API removed from the main nav. Rate limiting exists on enquiries and subscriptions only |
| Sitemap response type | Confirmed `application/xml`; OpenAPI no longer describes it as JSON |
| Analytics | Not added (privacy page promise). First-party counter is a later option |
| Founder relocation journey, deeper GCC calculators | Roadmap, not started |

