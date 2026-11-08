# QA report

Date: 8 November 2026. Environment: Python 3.13, FastAPI 0.162, Pydantic 2.13, headless Chromium via Playwright. Development verification, not certification of law, accessibility or production security.

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
