# Oblique Tax Intelligence

A GCC business-tax decision engine for [Oblique Consult](https://www.obliqueconsult.com/), inspired by the
distribution model of countrytaxcalc.com (instant free calculators, comparison pages, guides, developer API)
but built for corporate tax, VAT, zakat, withholding tax and cross-border comparison rather than personal income tax.

**Principle:** a deterministic rules engine performs every calculation; AI (later) only explains. Every result carries
a line-by-line working paper, the rule ids used, each rule's review status and source, and a diagnostic list of
unresolved questions that connect to Oblique's advisory services.

## What is in the prototype

| Module | Route | API |
| --- | --- | --- |
| UAE Corporate Tax (reconciliation, SBR, QFZP + de minimis, 75% loss cap, interest cap, DMTT screen) | `/uae/corporate-tax` | `POST /api/v1/uae/corporate-tax` |
| UAE and KSA VAT (add / extract / period return / registration) | `/vat?j=AE`, `/vat?j=SA` | `POST /api/v1/vat` |
| KSA Zakat and Income Tax (2024 Regulations base, mixed ownership, 25% loss cap) | `/ksa/zakat-income-tax` | `POST /api/v1/ksa/zakat-income-tax` |
| KSA Withholding Tax (categories, treaty rate, gross-up) | `/ksa/withholding-tax` | `POST /api/v1/ksa/withholding-tax` |
| GCC comparison engine (AE, SA, BH, OM, QA, KW) | `/gcc/compare` | `POST /api/v1/gcc/compare` |
| Move to the UAE comparison (GB, HK, SG, IN, US, AU, DE, ZA origin engines; PK disabled pending verification) | `/move`, `/move/{origin}-to-uae` | `POST /api/v1/move-to-uae` |
| Personal income tax calculators per origin country | `/personal-tax`, `/personal-tax/{code}` | `POST /api/v1/personal-tax` |
| Tax exposure diagnostic (10 questions, deadline precedence, no score) | `/diagnose` | `POST /api/v1/diagnostic` |
| PDF working papers (server recomputes the figures; branded; every calculator) | button on every result | `POST /api/v1/pdf` |
| Consent-led lead capture (gates only the PDF; contact + separate marketing consent; honeypot; rate limit) | dialog on every result | `POST /api/v1/leads`, `GET /api/v1/leads/config` |
| Arabic versions of the home page, UAE and KSA calculators, their guides and the diagnostic (right-to-left, `/ar/` prefix, catalogue in `app/i18n/ar.json`) | `/ar/...` | same API |
| Three entry paths, journeys and services (decision-led lead journey) | `/start/business`, `/start/gcc`, `/journeys/*`, `/services` | `GET /api/v1/services` |
| Privacy page | `/privacy` | — |
| Jurisdiction guides and 15 head-to-head comparison pages | `/guides`, `/guides/{code}`, `/compare/{A}-vs-{B}` | `GET /api/v1/rules` |
| Methodology, API docs, disclaimer, sitemap | `/methodology`, `/api`, `/docs` | `GET /api/v1/health` |

## Run it

```bash
pip install fastapi "uvicorn[standard]" jinja2 pydantic pytest httpx
uvicorn app.main:app --reload     # development
python -m app                     # production-style start; reads PORT from the environment
# open http://127.0.0.1:8000  (Swagger at /docs)
python -m pytest -q          # 64 tests; every tax figure checked by hand first
SITE_INDEXABLE=true python -m app   # only after expert sign-off: removes noindex
```

## Lead capture configuration

Nothing is collected until at least one destination is set. Set the variables on the host (Railway → Variables):

| Variable | Effect |
| --- | --- |
| `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_SENDER`, `LEAD_EMAIL_TO` | **Recommended for Oblique:** send from your own Microsoft 365 mailbox (e.g. tax@obliqueconsult.com) via Microsoft Graph, PDF attached, reply-to set to the visitor. No DNS changes. Setup in docs/DEPLOY.md; full go-live list in docs/SETUP_CHECKLIST.md |
| `RESEND_API_KEY`, `LEAD_EMAIL_TO` (comma-separated), optional `LEAD_EMAIL_FROM` | Alternative: email via Resend with the PDF attached (needs SPF/DKIM DNS records for the sending domain) |
| `LEAD_WEBHOOK_URL`, optional `LEAD_WEBHOOK_SECRET`, `LEAD_WEBHOOK_INCLUDE_PDF=true` | JSON POST per enquiry (Zapier, Make, n8n, Slack); HMAC-SHA256 signature in `X-Signature-256` |
| `HUBSPOT_PORTAL_ID`, `HUBSPOT_FORM_GUID`, optional `HUBSPOT_SUBSCRIPTION_TYPE_ID` | Submit to a HubSpot form with legal-consent fields |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, optional `SUPABASE_TABLE` | Insert one row per enquiry or rule-change subscription into a Supabase table (service role, server-side only; DDL in docs/SETUP_CHECKLIST.md) |
| `LEADS_SQLITE_PATH` | Append to a SQLite file (local testing; Railway's disk is not persistent) |
| `APP_SECRET` | Stable key for PDF tokens and IP hashing (set one; otherwise a random key per restart) |
| `LEAD_RATE_LIMIT_PER_HOUR` | Default 5 enquiries per IP per hour |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET` | Cloudflare Turnstile on the enquiry and notification forms (off when unset; the CSP and privacy page adjust) |
| `SITE_URL` | Public origin, e.g. `https://tax.obliqueconsult.com`; used for canonical links, the sitemap and social preview tags (falls back to the request host) |
| `FX_FEED` | `on` (default): ECB euro reference rates via the AED peg, cached six hours, dated table as fallback. `off`: dated table only |

What is recorded and why is on `/privacy`; consent texts and version live in `app/leads.py` (bump `CONSENT_VERSION` when the wording changes).
When no destination is configured the dialog is hidden and the PDF downloads directly.

## Deploy

The app is a single stateless FastAPI service; no database, no secrets.

- **Render:** connect the repo, Render reads `render.yaml` (health check `/api/v1/health`).
- **Railway / Fly / any Docker host:** `docker build -t oblique-tax . && docker run -p 8000:8000 oblique-tax` (uses `Dockerfile`; Railway also reads `railway.json`).
- **Heroku-style:** `Procfile` is included.
- Set `SITE_INDEXABLE=true` only after the rules have expert sign-off; until then every page is `noindex`.
- Put it behind HTTPS (and HSTS) at the proxy; the app already sets CSP and the other security headers.

## Project layout (plain-English)

```
app/
  rules/        ae.json, sa.json, gcc.json, personal.json  <- every rate, threshold, date, source, review status (edit these, not code)
  engine/       core.py (Decimal money, trace, scope gate), uae_ct.py, vat.py, ksa_zakat.py, ksa_wht.py, gcc_compare.py,
                personal_tax.py (8 origin countries), relocation.py (move to UAE), diagnostic.py
  api/routes.py JSON API under /api/v1
  main.py       page routes (FastAPI + Jinja templates)
  templates/    HTML pages; _result_shell.html is the shared results panel
  static/       site.css (Oblique brand tokens), fonts.css + fonts/ (self-hosted Satoshi, Inter), calc.js, img/ (Oblique logos)
tests/          test_engine.py, test_api.py, test_v4_port_and_relocation.py (scope gate, Decimal, headers, personal tax, relocation, diagnostic)
docs/           EVALUATION.md (CountryTaxCalc eval), COMPARISON_V4.md, BRAND.md, DECISIONS.md, LAUNCH_GATES.md, QA_REPORT.md, ROADMAP.md
```

### How a rule works
Each rule in `app/rules/*.json` looks like this. The engine reads `parameters`; the UI shows the rest.

```json
"small_business_relief": {
  "rule_id": "ae.ct.small_business_relief",
  "effective_from": "2023-06-01", "effective_to": "2026-12-31",
  "review_status": "pending_verification",
  "verification_note": "Reported extension to 31 Dec 2029 (MD 131/2026) not yet confirmed against MoF text.",
  "source_reference": "Ministerial Decision No. 73 of 2023",
  "parameters": {"revenue_threshold": 3000000}
}
```

Review statuses: `verified` (legal text checked; Oblique's interpretation where needed, in line with the prevailing practitioner view), `verified_secondary` (consistent practitioner sources),
`pending_verification` (reported, unconfirmed, or sources conflict), `draft_law` (not in force).
The results badge shows the *worst* status among the rules a calculation used.

## Behaviours ported from the V4 review (8 Nov 2026)
- **Scope gate:** every calculator has "special regime?" and "scope confirmed" controls. Until answered, the API returns `outcome: REVIEW_REQUIRED` with reasons and the UI greys the figure (still visible for order of magnitude).
- **Decimal arithmetic** end to end; half-up rounding to the currency's minor unit (3 decimals for BHD, OMR, KWD).
- **Privacy and security:** self-hosted fonts, zero third-party requests, CSP and defensive headers, JSON-only same-origin 64 KB POSTs, unknown fields rejected, validation errors never echo input, `noindex` until `SITE_INDEXABLE=true`.
- **Accessibility:** skip link, `main` landmark, `noscript`, `aria-live` results, `aria-busy` forms, focus to results on submit, reduced-motion rule.
- **Governance:** decision log, launch gates and rule lifecycle, QA report.
- **Desktop-calculator disclaimer** on every result and in the footer, with a "get in touch for precise figures" CTA.

## Known simplifications (also shown on /methodology)
- UAE CT: single period, no Tax Group, DMTT top-up uses taxable income as a proxy for GloBE income.
- KSA zakat: Article 28 upper-limit base not applied (formula unconfirmed); closing balances without proration.
- GCC comparison: UAE zero band applied in input currency; KSA zakat uses profit as proxy base; treaty rates ignored.
- Move to the UAE: full-year single employment-income origin tax; no split-year, exit tax or retained-income computation; indicative FX; no residence determination.
- No authentication, rate limiting, persistence, PDF export, enquiry form or Simpla integration yet (see docs/ROADMAP.md and docs/LAUNCH_GATES.md).
