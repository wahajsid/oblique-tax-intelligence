# CountryTaxCalc.com: detailed evaluation and what Oblique Tax Intelligence does differently

Evaluated 7 November 2026 by crawling the live site (2,633 sitemap URLs), fetching page HTML, running the calculator
in headless Chromium at 1440x900 and 390x844, downloading the JavaScript bundles and probing the public API.
Screenshots: `docs/screenshots/countrytaxcalc/`. Full URL list: `docs/countrytaxcalc-sitemap-urls.txt`.
The complete technical report follows the summary.

## Executive summary

CountryTaxCalc is a one-person (author "Daniel", UK), Astro-built, Vercel-hosted static site whose entire value is a
single client-side TypeScript tax engine (100 country calculators, 420 KB bundle) reused by a paid API, wrapped in a
very large programmatic SEO footprint and monetised by Raptive ads, disclosed affiliates, API tiers (USD 19/49/149 per
month) and a USD 1,500 per month site sponsorship against a claimed 60,000+ monthly pageviews.

| Area | Verdict | Evidence |
| --- | --- | --- |
| Calculator | Good engine, weak product layer | Per-country statutory components are correct on spot checks (UK, US, Germany), but country pages are not calculators (they redirect to the home tool), the deep-link CTA is broken (`country=DE` vs select values by name, so users land with no result), the Tax Optimization Score crashes with `countries is not defined`, "Export" offers no export, and marginal rate / converted gross are never shown. |
| Distribution | Its real asset | 978 pairwise comparison pages, 704 US pages, 111 calculator + 111 hub pages, 16 topic hubs, strong internal linking, breadcrumb + Article + WebApplication schema, "Updated October 2026 · Verified by Daniel" bylines. |
| Trust | Mixed | Excellent quantified API changelog and legal pages; but a stale methodology page (2025 data, "20+ countries"), static FX rates labelled "updated daily", identical schema dates across all articles, inconsistent page counts, and hand-typed approximate numbers on comparison pages that can drift from the engine. |
| API | Well designed, under-delivered | Tiered endpoints, rate-limit headers, Postman collection, versioning policy; but the advertised OpenAPI spec is not published and free keys are issued by email only. |
| Design/front-end | Coherent but unpolished | Indigo-purple gradient on slate neutrals, Inter/Newsreader/JetBrains Mono; no dark mode; horizontal overflow on most mobile templates; Arial fallback inside the main form; ~600 KB un-split JS on the home page; emoji as icons. |
| Depth | The gap Oblique can own | Methodology assumes single employed resident, standard deduction, no treaties, no investment income. No corporate tax, VAT, zakat, withholding, transfer pricing or Pillar Two anywhere. |

Lesson for Oblique: calculators are distribution assets. CountryTaxCalc proves instant, free, no-sign-up calculations
plus templated comparison and guide pages attract international search traffic. It also proves that breadth without
governance erodes trust. Oblique should copy the distribution model and the single-engine architecture, and compete on
depth, verification and professional follow-through in the GCC.

## How the prototype in this repository responds

| CountryTaxCalc finding | Oblique Tax Intelligence prototype |
| --- | --- |
| One shared engine for site and API | One Python rules engine (`app/engine`) serves both the pages and `/api/v1`; OpenAPI is published at `/openapi.json` and `/docs`. |
| Per-country `last_updated` / `source_url` metadata | Every rule in `app/rules/*.json` carries effective dates, source reference, source URL and a four-level review status; the results badge shows the worst status used. |
| Country pages that are not calculators; broken deep links | Every calculator lives on its own page and updates as you type; URL query parameters pre-fill the form and "Copy link" produces a shareable deep link keyed on field names. |
| Hidden working (no marginal rate, no converted gross, no breakdown) | Line-by-line working paper with formula and rule id on each step, copy-as-JSON and print. |
| Optimisation score that oversimplifies (and crashes) | No single score. The GCC comparison keeps statutory tax, scope, VAT and DMTT separate and prints its caveat. The "tax exposure diagnostic" flags unresolved questions instead. |
| Hand-typed comparison numbers | Pairwise comparison pages and the home-page table are generated from the engine at request time. |
| Stale methodology page | `/methodology` is rendered from the same JSON rules the engine uses, so it cannot drift. |
| Ads and affiliates | None. Monetisation path is advisory conversion: every result ends in "Request an expert-validated assessment". |
| Programmatic breadth (111 countries) | Six GCC jurisdictions, five calculators, 6 guides, 15 comparison pages; built to expand. |
| Mobile overflow, no dark mode | Dark Oblique brand by default, responsive down to 390 px, tested in headless Chromium. |

Not yet replicated (see `docs/ROADMAP.md`): newsletter/lead capture, downloadable PDF/Excel working papers, API keys
and rate limiting, editorial guide content per jurisdiction, Arabic, GA4 events, Simpla explanations.

---

# Full technical report
# CountryTaxCalc.com — product / UX / technical evaluation

Evaluated 2026-11-07 from a sandbox (curl + Playwright/Chromium, 1440x900 desktop and 390x844 mobile, deviceScaleFactor 1). All raw material is under `/tmp/claude-0/-home-user/1c11056b-72c9-5786-97ee-05d013dc364b/scratchpad/ctc-eval/` (`html/`, `text/`, `js/`, `api/`, `shots/`, `*.json`) and scripts under `/tmp/claude-0/-home-user/1c11056b-72c9-5786-97ee-05d013dc364b/scratchpad/ctc-scripts/`.

**Sandbox caveat (affects a few findings):** the sandbox proxy blocked `cdn.jsdelivr.net` (Chart.js), `ads.adthrive.com` (Raptive ads), `googletagmanager.com` and `flagcdn.com`. So charts and ads never rendered in my sessions; the calculator logic itself is first-party and ran fine. Anything that depends on those hosts is marked "could not be verified".

---

## 1. Site map and information architecture

### Crawl setup
- `robots.txt`: `Allow: /` for all agents, crawl-delay 10 for AhrefsBot/SemrushBot/MJ12bot/DotBot, points to `sitemap-index.xml` ("Last updated: April 27, 2026").
- `/sitemap.xml` is a sitemap index with one child, `/sitemap-0.xml` (504 KB). Every URL carries `changefreq=weekly`, `priority=0.7` and the same `lastmod` (`2026-11-07T20:59:47Z`, i.e. the build time) — the sitemap is generated at build and carries no real per-page freshness signal.
- **2,633 URLs** in total, all with trailing slashes, all on `https://www.countrytaxcalc.com`.

### URL counts by section (from the sitemap)
| Section | URLs | URL pattern / notes |
|---|---|---|
| `/tax-guides/…` | 2,401 | the content engine |
| — `/tax-guides/compare/` | 979 | index + 978 pairwise pages: `{a}-vs-{b}/`, plus 37 `{a}-vs-{b}-retirement/` variants. 409 match a US-state-vs-state pattern; ~569 are country-vs-country and Canadian-province pairs (e.g. `germany-vs-uk/`, `alberta-vs-ontario/`). Both directions often exist as separate pages (`germany-vs-uk/` and `uk-vs-germany/` are distinct articles with different copy). |
| — `/tax-guides/usa/` | 705 | index + 704 US pages. Recurring slug families: `{state}-tax-guide-2026` (183 matches for `tax-guide-2026`), `{state}-property-tax…` (66), `{state}-sales-tax` (52), `{state}-income-tax-guide-2026` (52), `{state}-capital-gains-tax` (43), `{state}-state-tax-refund` (29), `{state}-retirement-income-tax-2026` (18), plus topical pages (`401k-contribution-limits-2026`, `529-college-savings-tax-guide-by-state-2026`, `retirement-tax-planning-hub-2026`…). |
| — `/tax-guides/countries/` | 112 | index + 111 country "hubs" (`/tax-guides/countries/germany/`). `/tax-guides/usa/` 308-redirects to `/tax-guides/countries/usa/`. |
| — flat `/tax-guides/{slug}/` | 519 | 16 hub pages ending `-hub/` (expat, contractor, digital-nomad, salary-take-home-pay, relocation, best-countries, wealth-inheritance-estate, retirement-pension, capital-gains, crypto, equity-stock-options, dividend, special-tax-regimes, us-expat, tax-residency…), 19 city pages `{city}-salary-take-home-pay-2026/`, 9 `us-to-{country}-salary-equivalent…` pages, `{country}-tax-guide/`, visa/expat/relocation guides, `vat-rates-by-country-2026`, `zero-income-tax-countries-2026`, etc. |
| — regional sub-folders | 15 canada, 14 africa (`{country}-paye-guide-2026`), 7 international, 6 netherlands, 5 uk/spain/germany, 4 portugal/australia, 2 turkey/south-korea/japan/france, 1 vietnam | |
| `/tax-calculator/…` | 200 | index + 111 country calculators (`/tax-calculator/{country}/`, slugs like `uae`, `uk`, `germany`; `united-kingdom` and `united-arab-emirates` 404), `/tax-calculator/usa/` (74: index, 50 states, `washington-dc`, and 22 topical calculators e.g. `rsu-calculator`, `self-employment-1099`, `no-tax-on-tips`, `property-tax-calculator-by-state`, `best-states-for-retirees-taxes`), `/tax-calculator/canada/` (14: index + 13 provinces/territories), `/tax-calculator/netherlands/` (3: index, `30-percent-ruling`, `moving-impact`). |
| `/tax-api/…` | 11 | hub + 10 SEO guides (`global-income-tax-api`, `free-income-tax-api`, `best-income-tax-api`, `python-…`, `javascript-…`, `tax-api-for-hr-software`, `…-relocation-tools`, `salary-comparison-api`, `calculate-take-home-pay-api`, `build-vs-buy-tax-calculator`). |
| `/api/`, `/api/changelog/` | 2 | developer docs + changelog |
| `/api-access/`, `/api-access/success/` | 2 | pricing / checkout landing |
| `/tools/` | 4 | `salary-equivalent/`, `retirement-report/` (+ `generate/`, `success/`) |
| `/reports/` | 2 | `digital-nomad-tax-rankings-2026/`, `state-tax-migration-2022/` |
| `/legal/` | 4 | `disclaimer/`, `privacy/`, `affiliate-disclosure/`, `api-terms/` |
| singletons | 7 | `/`, `/about/`, `/authors/daniel/`, `/advertise/`, `/contact/`, `/methodology/`, `/newsletter-preview/` (an internal component preview page that is indexed — title "Newsletter CTA Preview — Internal") |

### Navigation (observed in rendered header)
- Primary nav: **Calculator** (→ `/`, the interactive multi-country tool), **Calculators** mega-menu (All Countries, US States, Canada Provinces, UK, Germany, Australia, France, Spain, Netherlands, Singapore, UAE, RSU Calculator), **Compare** (Compare Index, US States), **Tax Guides** (~25 hub links), plus About / API / Advertise, a search button and a purple "Start a calculation" CTA.
- A dismissible top bar promotes "The Tax Brief — real effective rates for 111+ countries — bi-weekly, free" with an inline email field.
- Footer: 4 link columns (Calculators / Compare / Tax Guides / About), trust strip ("Free to use · No sign-up required · 111+ countries · Updated for 2026 · Site last built November 2026"), a one-line disclaimer and legal links.
- **Broken/odd routing:** several nav and footer links are 308 redirects rather than real pages: `/tax-calculator/rsu/` → `/tax-calculator/` (the index, not the actual RSU tool at `/tax-calculator/usa/rsu-calculator/`), `/tax-guides/compare/us-states/` → `/tax-guides/compare/`, `/tax-guides/salary/`, `/moving-abroad/`, `/country-hubs/`, `/specialist/` → their hub equivalents, `/disclaimer/` → `/legal/disclaimer/`.

### Page templates identified
1. Home (`/`) — hero + live multi-country calculator + marketing sections + FAQ.
2. Country calculator landing (`/tax-calculator/{country}/`) — SEO page with a single-field mini form that hands off to the home calculator.
3. Country hub (`/tax-guides/countries/{country}/`) — facts card, quick 4-country comparison table, link clusters.
4. Comparison article (`/tax-guides/compare/{a}-vs-{b}/`) — "Big Picture / Savings by Income / Pros & Cons / FAQ / Related".
5. Collection/index pages (`/tax-calculator/`, `/tax-guides/`, `/tax-guides/compare/`, `/tax-guides/countries/`).
6. API marketing/docs (`/tax-api/*`, `/api-access/`, `/api/`).
7. Standalone tools (`/tools/salary-equivalent/`, `/tax-calculator/usa/rsu-calculator/`) with their own Astro island scripts.
8. Legacy static pages (`/methodology/` uses a different, older layout with no site nav/footer and no Astro CSS).

---

## 2. Calculator: inputs, outputs, interactions, calculation flow

### 2a. Country calculator pages (e.g. `/tax-calculator/germany/`)
These are **content pages, not calculators**. The only form is:
- `input#ctc-income` (type number, min 0, max 10,000,000, label "ANNUAL GROSS SALARY", prefilled 75000) and `button#ctc-btn` "Calculate My Germany Tax →".
- The inline handler does `window.location.href = "/?country=DE&income=75000"` (plus `&state=`/`&province=` for jurisdictions). Nothing is computed on the page.
- **Bug observed:** the home calculator's URL handler sets `countrySelect.value = params.get("country")`, but the `<select>` option values are country *names* ("Germany"), not ISO codes. Loading `/?country=DE&income=75000` left the select empty and produced **no results** (verified in `home-calc-flow.json`, `deepState.country == ""`), whereas `/?country=Germany&income=75000` auto-calculated correctly. So the primary CTA on every country page lands users on the home page with the income filled but no country and no result. (I did not test every country; UK's page passes `GB` by the same mechanism.)
- Other content on the page: "Key Insight" callout, "Quick Facts (2026)" cards (allowance, rates, SS %, Soli, filing deadline), a bracket table with "Source: German Federal Ministry of Finance (BMF)", an affiliate block (Greenback, Deel), static tables "Take-Home Pay by Income Level" / "Social Security Breakdown at €60,000" / "Ehegattensplitting example", "Compare Germany Taxes" link grid, 8 FAQs, newsletter CTA, share buttons, and an "Updated October 2026 · Verified by Daniel" footer note.
- UAE page is the same template with "0% income tax" messaging; UK page similar.

### 2b. The real calculator (home page `/`)
Visible controls (from DOM enumeration, `calc-home-inspect.json`):
| Control | Default | Options / notes |
|---|---|---|
| `input#income` "Annual Income" (number, step 1000, placeholder "Enter your annual income") | 50000 | |
| `select#baseCurrency` "Income Currency" | **GBP** | 39 currencies with flag emoji (USD, GBP, EUR, INR, CAD, AUD, JPY, KES, GHS, EGP, ETB, UGX, TZS, MAD, XOF, BRL, ZAR, MXN, THB, IDR, NOK, CHF, SGD, AED, NZD, HKD, PLN, MYR, PHP, VND, KRW, TRY, SAR, TWD, SEK, DKK, ARS, COP, NGN) |
| `select#countrySelect` "Country to Calculate" | United Kingdom | 111 countries (values are names, UK listed first and again alphabetically) |
| `select#stateSelect` "State/Province" | hidden until US/Canada chosen | 52 options for US ("Select…", 50 states, DC) |
| `select#localitySelect` "County / City (optional)" | hidden | engine exports `LOCALITIES` (NYC, Yonkers, Maryland counties seen in code) |
| `button#calcBtn` "🧮 Calculate Estimate", `#addBtn` "➕ Add Country", `#clearBtn` "🗑️ Clear All" | | |
| "📊 Advanced Analysis (Optional)" checkboxes (persisted to `localStorage.featureToggles`) | all off | Monthly Breakdown · Tax Freedom Day · Real Purchasing Power · Tax Savings Comparison (2+ countries) · Purchasing Power Comparison (2+ countries) · Tax Optimization Score ("Rate your country vs all 111+") |
| Sort bar (appears after results) | | 💰 Highest Take-Home · 💡 Lowest Tax Rate · 🗓️ Earliest Freedom Day · 🔤 A-Z |
| "📤 Export & Share" | | Twitter, Facebook, LinkedIn, WhatsApp, Copy Link only — **no PDF/CSV/print export** despite the heading |

Result blocks per country card (`div.tax-card`), observed with £75,000 / GBP base:
- rank badge, country name, remove ×, big **Effective tax rate** (e.g. UK 27.9%, Germany 40.7%, US federal-only 20.7%)
- a `canvas#chart-{country}` (Chart.js doughnut presumably — could not render in sandbox)
- breakdown rows, country-specific labels: UK → "Income Tax £17,432 (23.2%)", "National Insurance (8%) £3,016", "National Insurance (2% above UEL) £495"; Germany → Income Tax, Rentenversicherung, Krankenversicherung, Pflegeversicherung, Arbeitslosenversicherung; US → Federal Tax, Social Security Tax, Medicare Tax (+ warning "⚠️ State/Provincial Tax Not Included … State taxes can add 0-13%")
- "Total Tax", "Net Income (Annual)", "Effective Tax Rate"
- optional: "💰 Monthly Take-Home", "🗓️ TAX FREEDOM DAY — April 12 — You work for the government until this date, then for yourself", "🌟 Excellent Purchasing Power (Estimated): Take-Home (USD) $71,360 − Living Costs $16,000 = Real Disposable Income $55,360/year, Monthly $4,613"
- With 2+ countries: "💰 Tax Savings Analysis" (lowest vs highest tax, annual savings £14,934 / "41.6% less tax", 10-year savings, freedom-day difference) and "💵 Real Purchasing Power Comparison" (best vs lowest value, "$10,625 more per year to spend").
- **Not displayed:** the converted gross income in local currency (entering £75,000 for Germany silently calculates on €88,202; the card never shows that figure), marginal rate, employer cost, monthly gross, or per-bracket breakdown.
- **Tax Optimization Score never renders:** `displayTaxOptimizationScore` throws `ReferenceError: countries is not defined` (`tax-calculator.min.js:1:168787`) on every calculation — the function iterates `Object.keys(countries)` but the data object is named `countryData`. Console error reproduced on every run; it is a code bug, not a sandbox artefact.
- "Chart.js not loaded yet" warnings were sandbox-induced (CDN blocked).

Sanity check of outputs (my own arithmetic, 2026 rules as published on the site): UK £75,000 → income tax £17,432 (= 20%×£37,700 + 40%×£24,730), NI £3,016 + £495 — consistent. US $99,006 (converted) → federal $12,951 with $16,100 standard deduction and 10/12/22% bands — consistent. Germany figures are consistent with the GBP→EUR conversion (pension €8,203 = 9.3% × €88,202).

### 2c. Calculation flow: entirely client-side
- Zero XHR/fetch during calculation; the only requests after input change were `flagcdn.com/w40/{cc}.png` flag images. Home page FAQ states "Is any of my data stored or sent to a server?" — answer is no, and the author page says "Calculator inputs are processed locally in your browser and never sent to our servers". Verified.
- Two first-party bundles: `tax-engine-bundle.js` (420 KB, esbuild IIFE exposing `window.TaxEngine`; source comments show it is compiled from `../backend/api/src/calculators/{country}.ts` — i.e. **the same TypeScript calculators as the paid API**, 100 `calculate{Country}Tax` exports + `CANADA_JURISDICTIONS`, `LOCALITIES`, `resolveCanadaJurisdiction`) and `tax-calculator.min.js` (181 KB; UI, `const countryData = {...}` with 100 country records carrying `engineData` metadata `{tax_year: 2026, last_updated, source_url, calculation_type:"progressive", notes}`, `costOfLiving` constants, and per-country `calculate{X}WithEngine` adapters). `last_updated` values range 2026-01-12 → 2026-10-15 (83 of 100 in October 2026).
- Exchange rates are **hard-coded** in the bundle (`exchangeRates = {USD:1, GBP:.757532, EUR:.890869 …}`, `exchangeRatesDate = "2026-10-02"`, sources "ecb"/"peg"/"secondary: open.er-api.com 2026-10-05"); `fetchExchangeRates()` only logs "📊 Exchange rates loaded successfully". The UI nonetheless says "💱 Exchange rates updated daily" — this claim is not true as implemented (rates update only on redeploy).
- "Living costs" used by Purchasing Power are a single static number per country (`costOfLiving: 14e3` for Germany, 16,000 UK, 18,000 US) — a very coarse proxy with no source shown.

### 2d. Other calculators
- `/tax-calculator/usa/rsu-calculator/` ("RSU Tax Calculator 2026: Estimate Tax + Withholding Gap"): inputs `rsu-salary`, `rsu-vest`, `rsu-state` (select), `rsu-filing` (select); outputs federal/state/SS/Medicare on vest, total, "Company federal income tax withholding (22% up to $1M; 37% on any excess)", "Federal withholding gap", net RSU value, effective rate on vest; its own Astro island script. Sections: Quick Facts, worked examples, "withholding gap" explainer, by-state table, "How This Calculator Works", FAQ.
- `/tools/salary-equivalent/` ("find the gross salary you need in any country or US state to match your current take-home pay. 5 countries + all 50 states") with its own island script.

### 2e. Accuracy caveats stated by the site (quotes)
- Under the calculator: "Estimates for informational purposes only. Tax situations vary based on individual circumstances. Consult a qualified tax professional for accurate advice."
- Methodology: single taxpayer, no dependents, standard deduction, employment income only, full-year resident; does not calculate itemised deductions, credits, self-employment tax, investment income/CGT, treaties, employer pensions, "Local/city taxes (except US state taxes)", wealth/property taxes, part-year residency. "the actual amount you owe could be significantly different from our estimates."
- Footer on every page: "Not tax advice. Calculations are estimates for informational purposes only."
- US card warns when no state selected. Germany page tables state "No church tax", "childless employee" assumptions.
- **Staleness problem:** `/methodology/` still says "20+ countries", lists data years 2025 / 2024-25, "USA: Standard deduction ($15,000 for 2025)", "Germany: Grundfreibetrag (€11,784)", "Last major update: December 2025" — contradicting the rest of the site (111 countries, 2026 rates, Grundfreibetrag €12,348). The `/api/` docs example also shows Germany `last_updated: 2026-04-15` with brackets starting at €11,784 (2024 value) and a 2-bracket schedule, inconsistent with the Germany page's €12,348 / four-zone description.

---

## 3. Comparison and guide pages: structure, template, SEO patterns

### Comparison article template (`/tax-guides/compare/germany-vs-uk/`, `/california-vs-texas/`)
- Purple gradient hero: eyebrow "HEAD-TO-HEAD TAX COMPARISON · 2026", flags, "COUNTRY A Germany VS COUNTRY B UK" (the H1 literally contains the words "COUNTRY A/COUNTRY B"), byline "Daniel · CountryTaxCalc · Updated October 2026", two CTAs ("Calculate your take-home →", "See all comparisons →").
- Sticky jump-nav pills: Overview · Big Picture · By Income · Pros & Cons · FAQ · Related.
- Amber "💡 OVERVIEW" callout (~120 words).
- Section 01 "The Big Picture": two side-by-side cards (top rate + one-line caveat) and a "TYPICAL ANNUAL DIFFERENCE … ~€10,800 / ~€900/month back in your pocket" hero number.
- Section 02 "Tax Savings by Income Level": a 5-row table-like grid (gross income, A tax, B tax, savings, 10-year) with approximate ("~") figures and a highlighted "trap" row. These are **static hand-written numbers** (`tables=0`, no script), not generated from the engine.
- Affiliate card (Deel on international pairs; Taxhub on state pairs; Greenback/Deel on country calculators) with Trustpilot rating/review count, "⚠ For employers … only" fit warning, and "reader-supported" disclosure.
- "Pros & Cons" two columns (4 + 4 bullets each), FAQ (5 Q&As), "Related Comparisons" chip cloud (~20 links), "From the brief" ticker + newsletter form, share buttons.
- ~140 links per page, essentially all internal (1 external = the affiliate link). Body links by section: ~47 to `/tax-guides/*`, ~25 to `/tax-calculator/*`, ~20 to other compare pages.
- No interactive calculator and no live chart on comparison pages.

### Country hub template (`/tax-guides/countries/germany/`)
- Short page (2,415 px tall on desktop): headline facts strip ("Income tax 14–45% · Tax-free allowance €12,348 · Tax year Jan–Dec · Filing deadline 31 Jul"), 4 quick-action buttons, "Germany Tax Facts — 2026" definition grid (6 items), "Quick Country Comparison — at €80,000" table (Germany / Netherlands / UK / UAE take-home, effective rate, delta), three link clusters (Comparison Guides, Salary Guides, Moving from Germany), a "⚠ 2026 Germany Tax Changes" box, "Last Updated: October 2026 · Daniel".
- Only Organization + BreadcrumbList schema; no Article.

### Index pages
- `/tax-guides/countries/` — 111 hub cards (country link + calculator link each), no H2s.
- `/tax-guides/compare/` — "⭐ Most Popular State Comparisons", "🔍 Browse by State", "🍁 Browse by Province" (meta description claims "526 side-by-side tax breakdowns" while the sitemap has 978).
- `/tax-calculator/` — "Popular calculators" then regional groups (Europe, Americas, Asia, Middle East, Africa, Oceania, Special Territories); 278 internal links.

### SEO patterns
- Titles: `{A} vs {B} Taxes Compared (2026) | Tax Calculator`; `{Country} Income Tax Calculator 2026 – …`; `{Country} Income Tax Guide 2026 | Rates, Calculators & Comparisons`; year "2026" in nearly every title/H1/slug.
- H1s on calculator pages carry a flag emoji ("🇩🇪 Germany Income Tax Calculator 2026"); exactly one H1 per page.
- Meta descriptions are specific and number-heavy (e.g. "Texas has no state income tax (0%). California tops at 13.3%…").
- Canonicals self-referencing with trailing slash; `/newsletter-preview/` is indexable.
- JSON-LD: Organization on every page; Article (author Person "Daniel" → `/authors/daniel/`, publisher Organization, `datePublished = dateModified = 2026-10-01` on every article I checked — a bulk date, not per-page) + BreadcrumbList on articles; WebApplication (FinanceApplication, price 0) on calculator pages; FAQPage (26 items), HowTo on home; CollectionPage on indexes; ContactPage on contact; Person on about/author. FAQ sections on article pages are **not** marked up as FAQPage (only the home page is).
- Internal linking: every template ends with a related-links block; the header mega-menu alone injects ~60 links; comparison pages link in both directions; country calculator pages link to city salary pages and hubs. Breadcrumbs rendered visibly and in schema.
- "Updated October 2026" is printed in page bylines but is not reflected in sitemap lastmod.

---

## 4. API

### Surface
- Base URL `https://api.countrytaxcalc.com/api/v1/`. The bare host root and any non-`/api/v1` path 308-redirect to `www.countrytaxcalc.com` (e.g. `/docs` → `www…/docs`, `/openapi.json` → `www…/openapi.json`, both then 404/redirect); **no OpenAPI/Swagger file is exposed** even though pages say "OpenAPI 3.0.3". A Postman collection exists at `https://www.countrytaxcalc.com/postman-collection.json` (16 KB, v2.1, apikey auth on header `X-API-Key`).
- Headers on API responses: `server: Vercel`, `x-vercel-id`, `cf-ray` (Cloudflare in front), CORS `*` with `X-API-Key` allowed, `GET, POST, OPTIONS`. The marketing claim "Cloudflare Workers global edge deployment" could not be verified from headers (they look like a Vercel function behind Cloudflare).
- Auth: header `X-API-Key: ctc_[32 hex]`. Rate-limit headers `X-RateLimit-Limit/Remaining/Reset/Used` on authenticated responses; burst limit → 429 with `Retry-After`. (Not verifiable without a key; I did not sign up.)

### Endpoints (from `/api/` docs; tier per pricing table)
| Endpoint | Tier | Purpose |
|---|---|---|
| `GET /api/v1/health` | public | status + db |
| `GET /api/v1/countries` | public (key optional) | list with currency metadata |
| `GET /api/v1/countries/{code}` | Starter+ | metadata, jurisdictions |
| `GET /api/v1/countries/{code}/rates` | Starter+ | raw brackets/deductions/social contributions; `?year=` historical (Growth+); cached 1 h |
| `POST /api/v1/calculate` | Free+ | body `{country (ISO2 or name), income (>0, ≤100,000,000), currency?, jurisdiction?, tax_year?}` |
| `GET /api/v1/summary?income=` | Growth+ | all 111 ranked by effective rate (income treated as nominal local-currency amount) |
| `POST /api/v1/compare` | Pro+ | up to 20 countries, `summary` object with best/worst/10-year savings |
Error codes documented: 400, 401, 403 (includes `upgrade_url`), 404, 422 (fx pair unavailable), 429, 500. Versioning promise: v1 supported ≥12 months after v2, additive changes only, 90-day deprecation emails.

### Live responses (unauthenticated, captured 2026-11-07)
```
GET /api/v1/health → 200
{"status":"healthy","timestamp":"2026-11-07T21:53:22.123Z","database":"connected"}

GET /api/v1/countries → 200 (16,173 bytes) {"countries":[...111 items...],"total":111}
{"country_code":"AL","country_name":"Albania","currency":"ALL","currency_symbol":"L","currency_name":"Albanian Lek","has_jurisdictions":false}
{"country_code":"AG","country_name":"Antigua and Barbuda","currency":"XCD","currency_symbol":"EC$","currency_name":"East Caribbean Dollar","has_jurisdictions":false}
… only CA and US have has_jurisdictions:true

GET /api/v1/ , /countries/DE , /countries/DE/rates , /summary , POST /calculate → 401
{"error":"Unauthorized","message":"An API key is required. Get access at https://countrytaxcalc.com/api-access/","code":401}
```
Documented `POST /calculate` response shape (from docs, not live): `country, country_code, tax_year, currency, gross_income, currency_conversion{input_income,input_currency,local_currency,exchange_rate,converted_income,fx_source:"frankfurter"|"exchangerate-api",fx_rate_age_hours}, breakdown{taxable_income, national_income_tax{amount,effective_rate,marginal_rate}, social_contributions[], special_taxes[]}, totals{total_tax,net_income,effective_tax_rate,take_home_percentage,monthly_net_income}, metadata{accuracy_confidence (0.95 verified / 0.70 fallback), data_source, last_updated}`. Changelog says responses also carry `engine_version`.

### Pricing (from `/api-access/`)
| Plan | Price | Requests/mo | Burst | Overage | Endpoints | Support |
|---|---|---|---|---|---|---|
| Free | $0 | 1,000 (hard cap) | 10/min | — | /calculate, /countries list | docs only; **requires visible "Powered by CountryTaxCalc.com" attribution** (Terms §2A); key obtained by **emailing** daniel@countrytaxcalc.com |
| Starter | $19/mo | 50,000 | 60/min | $0.80/1k | + country detail, rates | email 72 h |
| Growth | $49/mo ("Most popular") | 500,000 | 200/min | $0.60/1k | + /summary, historical years | email 48 h |
| Pro | $149/mo | 2,000,000 | 600/min | $0.40/1k | + /compare (20) | priority 8 h |
| Enterprise | custom | — | — | — | SLA, dedicated contact, annual contract | |
Annual billing at 17 % discount (no overage; 429 at cap; 80 %/95 % warning emails). 7-day money-back on first payment. Page showed a static error string "Something went wrong starting checkout" in the HTML (checkout appears to be a client-side flow I did not trigger). Terms: England & Wales law; "AS IS"; logs retained 90 days after cancellation; downstream consumer products must carry a disclaimer (§9).

### Changelog signal
`/api/changelog/` is substantive and dated: e.g. 2026-11-03 North Dakota bracket correction with before/after dollar impacts; 2026-10-15 "All 175 jurisdictions checked against independent reference calculations" listing ~57 rebuilt calculators; 2026-10-09 UK additional-rate threshold fix ("overstated by a constant £629 above £125,140"); 2026-07-06 auth system launch. This is the strongest trust artefact on the site.

---

## 5. Design system

### Tokens (from `:root` in `global-enhancements.css` / Astro CSS)
- Brand gradient `--ctc-primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%)` (`--indigo: #667eea`, `--purple: #764ba2`); secondary `#f093fb→#f5576c`; accent `#4facfe→#00f2fe`.
- Ink/text: `--ink #0f172a`, `--ink-2 #1e293b`, `--muted #64748b`, `--ctc-text-primary #1f2937`, `--ctc-text-secondary #6b7280`, `--ctc-text-muted #9ca3af`.
- Surfaces: `--surface #f8fafc` (body bg), `--white #ffffff`, `--ctc-bg-primary #fafbfc`; borders `--line #e2e8f0`, `--line-soft #eef2f7`, `--ctc-border-color #e5e7eb`; footer/stats band `#1e293b`.
- Semantic: success `#10b981`, warning/amber `#f59e0b` (+ `--amber-bg #fef3c7`, `--amber-ink #78350f`), error `#ef4444`; blue `#2563eb`/`#3b82f6` used for links/badges.
- Radii `8 / 12 / 16 / 20 px` (`--ctc-radius-sm…xl`), calculator card 24 px, result cards 16 px, inputs/buttons 12 px; shadows sm/md/lg/xl (Tailwind-like values); transitions 0.15/0.3/0.5 s cubic-bezier(0.4,0,0.2,1).
- Computed examples: body `#f8fafc` / `#0f172a` 16 px Inter, line-height 1.6; header nav links `#334155` 14.5 px/500; primary CTA `#calcBtn` white on the indigo→purple gradient, 16 px/600, padding 16×32, radius 12; secondary buttons white with 2 px `#e5e7eb` border; inputs white, 2 px `#e5e7eb`, 16 px padding; top-bar CTA amber `#f59e0b` on dark text `#1f1300`; stats band `#1e293b` with 76 px white numerals.

### Typography
- Google Fonts: **Inter** 400/500/600/700 (body/UI), **Newsreader** 400/500/600 serif (H1 on sub-pages, 42 px/500), **JetBrains Mono** 400–700 (code, tables, eyebrows). Home H1 is Inter 64 px/700 (not Newsreader) — two heading systems coexist.
- Inconsistency: the home calculator inputs/buttons compute to `font-family: Arial` (legacy CSS in `tax-calculator.min.js` era), H2 on calculator pages fall back to the system stack — the design tokens are not applied everywhere. 48 text nodes under 12 px on the home page.

### Components inventory
Top announcement bar with inline email form · sticky header with mega-menus and search · gradient hero cards · eyebrow/label caps text · stat tiles · "calc-card" form panel · result "tax-card" with rank badge, big-number stat, doughnut canvas, key/value breakdown rows, coloured feature sub-blocks (yellow freedom-day, green purchasing-power) · comparison panels (green "lowest"/red "highest", orange best-value) · toast notifications · sort pill bar · jump-nav pills · "insight" callout (amber) · fact grids · pros/cons two-column lists · FAQ accordion-style list · affiliate card (badge, Trustpilot stars, warning line, CTA) · "From the brief" ticker + newsletter form · share button row (Twitter/Facebook/LinkedIn/WhatsApp/Copy) · link chip clouds · pricing cards + feature matrix · code tabs (cURL/Python/JS/PHP) · dark footer.

### Modes and responsiveness
- **No dark mode**: no `prefers-color-scheme` rule, no `data-theme`, no toggle. `prefers-reduced-motion` and `prefers-contrast: high` rules exist.
- Breakpoints seen: 1100, 900, 768, 700, 640, 600, 560, 480, 400 px (max-width). Hamburger drawer at 390 px.
- **Horizontal overflow bug on mobile across templates**: at 390 px the document scroll width is 532 px on `/`, 460 on `/tax-calculator/germany/`, 621 on `/api/`, 628 on `/tax-api/global-income-tax-api/`, 554 on `/tax-guides/countries/`, 439 on comparison pages. Causes: the announcement bar `.sb-inner` does not wrap, and the off-canvas mobile drawer header (`.mob-drawer-header`, width 320) sits outside the viewport without `overflow-x: hidden` on `html`. On `/tax-calculator/` the same drawer makes even the 1440 px desktop page 1,791 px wide. The mobile screenshots (which capture the full scroll width) show the pages rendered wider than the phone.
- Full-page heights on mobile are very long (home 12,886 px; `/tax-calculator/` 17,646 px; salary-equivalent 19,186 px).

### Accessibility observations (home page unless stated)
- `lang="en"`, one H1, all buttons have accessible names, form controls have labels, `:focus-visible` styles exist, `aria-live` region present (1), nav labelled "Page sections".
- Missing: no `<main>` landmark on home (`main:0`, `header:0`), no skip link, chart canvases have no `role`/`aria-label`, heading level skips, emoji used as meaning-bearing icons in labels/headings ("🧮 Calculate Estimate", "🇩🇪 Germany …"), 5–13 tap targets under 24 px per page, colour-only coding of green/red comparison panels, small 11–13 px eyebrow text. Contrast of `#64748b` on `#f8fafc` (~4.6:1) passes AA for body; the amber-on-dark-brown top bar CTA is fine; I did not run a full contrast audit.

---

## 6. Tech stack and performance

- **Framework:** Astro static site (`/_astro/*.css`, `data-astro-cid-*` attributes, island scripts like `SalaryEquivalentCalculator.astro_astro_type_script_…js`; an HTML comment leaks "api-access/index.astro verified 2026-07-08"). No React/Vue runtime detected on content pages. Home calculator is vanilla JS (two hand-rolled bundles) + Chart.js from jsDelivr.
- **Hosting:** Vercel (`server: Vercel`, `x-vercel-cache: HIT`, `x-vercel-id: iad1::…`, `/_vercel/insights/script.js`); API also on Vercel with Cloudflare in front (`cf-ray`, NEL reporting). Static HTML served with `cache-control: public, max-age=0, must-revalidate` + ETag; HSTS, `x-frame-options: SAMEORIGIN`, `nosniff`, `referrer-policy: strict-origin-when-cross-origin`, `permissions-policy` set. Security headers are decent; no CSP.
- **Third parties:** GA4 (`G-TERVRK2DWX`), Raptive/AdThrive ads (`ads.adthrive.com/sites/6a03752b8048b47e58c824d4/ads.min.js` on every page — ad slots could not be rendered in the sandbox, so ad density is unverified), Google Fonts (3 families), flagcdn.com (flags), jsDelivr (Chart.js), Vercel Insights.
- **Page weight:** HTML is heavy because the mega-menu and inline CSS/JS are repeated: home 177 KB, calculator landing 95–112 KB, comparison ~100 KB, compare index 270 KB, `/tax-calculator/` 172 KB. Home additionally loads 420 KB + 181 KB + 9 KB first-party JS (≈610 KB uncompressed, not code-split) + Chart.js. Sub-pages load ~16 KB of inline scripts and 4 stylesheets. Fonts ~3 woff2 files.
- **Requests:** 10–12 requests to network-idle on calculator/comparison pages in the sandbox (document, 4 CSS, gtag, ads, fonts CSS + 3 woff2, Vercel insights) — the ad network's downstream requests are excluded because the host was blocked. Load-to-idle 0.9–1.5 s from the sandbox (US-East); `/tax-guides/countries/` was slowest at ~3–4 s.
- Robots-friendly, trailing-slash canonical URLs, 308 redirects for legacy paths, custom 404 page (`/404/` canonical, links to calculators).

---

## 7. Monetisation and trust signals

- **Ads:** Raptive (formerly AdThrive) script on every page ("Raptive Head Tag", "Raptive Email Link ID" comments). `/advertise/` sells a "Presenting Partner" site-wide placement at **$1,500/month, 3-month minimum**, "60,000+ monthly pageviews" (home page copy elsewhere says "65,000+"), "GA4 rolling 30-day average as of August 2026", category exclusivity at +25 %, read-only GA report offered to prospects. Home page has a "Building something? Tax data for 111 countries via API — from $19/month" promo.
- **Affiliates:** disclosed partners — Universal Tax Professionals, Greenback Expat Tax Services, Taxes for Expats, Deel, Taxhub, SafetyWing. Cards appear mid-article on comparison and calculator pages with Trustpilot numbers ("last verified: April 16, 2026. We re-verify every 6 months") and a "Not right for…" fit warning. Methodology and author pages state editorial independence; every affiliate block carries a "reader-supported" line.
- **API subscriptions** ($19/$49/$149, see §4) and an Enterprise tier.
- **Newsletter** "The Tax Brief" (bi-weekly) pushed via top bar and in-article forms; a `/newsletter-preview/` internal page is public.
- **Trust/E-E-A-T:** single named author "Daniel", UK-based, with `/authors/daniel/` profile and Person schema; About page with "/about.json"-style facts; statements "We use AI to help research and draft content; all rates and figures are reviewed against official government sources before publishing"; Source lines on bracket tables; "Updated October 2026 · Verified by Daniel" on calculator pages; detailed, quantified API changelog; legal pages (Disclaimer with IRS Circular 230 section, Privacy, Affiliate Disclosure, API Terms). Contact email used everywhere (daniel@countrytaxcalc.com).
- **Trust detractors:** stale methodology page (2025 data, "20+ countries"); "exchange rates updated daily" claim vs static rates; identical `datePublished/dateModified` (2026-10-01) across articles; inconsistent counts ("526 comparisons" vs 978 pages; "1,000+" vs "1,400+" vs "2,100+ pages"); bulk-generated 1,000+ guide pages (`{state}-sales-tax`, `{city}-salary-take-home-pay-2026`) that will read as programmatic SEO to Google; API docs examples with outdated bracket data.

---

## 8. Strengths, weaknesses, features to replicate vs skip

### Strengths
1. True client-side multi-country calculator with per-country labelled components (NI bands, German four-pillar SS, US FICA) and instant add/compare — no sign-up, verifiable privacy claim.
2. One shared TypeScript engine powers the website, and the paid API (bundled with esbuild) — single source of truth, per-country `source_url`/`last_updated` metadata.
3. Very large, consistently templated SEO footprint (2,633 URLs: 978 comparisons, 704 US pages, 111 calculators + 111 hubs, 16 topic hubs) with strong internal linking, breadcrumbs and schema.
4. Clear monetisation stack (Raptive ads, disclosed affiliates with fit warnings, API tiers, sponsorship rate card) and unusually transparent legal/changelog pages.
5. Developer-grade API docs: tiered endpoint matrix, rate-limit headers, error table, multi-language snippets, Postman collection, versioning policy, attribution rule.
6. Coherent visual language (indigo→purple gradient, slate neutrals, Inter/Newsreader/JetBrains Mono, rounded cards) that reads as a finance tool.

### Weaknesses
1. Country calculator pages are not calculators; their CTA deep-link is broken (`country=DE` vs select values by name) so users land with no result.
2. Tax Optimization Score crashes (`countries is not defined`); "Export" offers no export; no marginal rate, no converted gross shown, no monthly gross, no employer cost.
3. Mobile horizontal overflow on most templates; desktop overflow on `/tax-calculator/`; duplicate heading systems; Arial fallback inside the main form; no dark mode; no `<main>`/skip link; canvases without text alternative.
4. Freshness contradictions (methodology page, API doc examples, static FX with "updated daily" claim, uniform schema dates, uniform sitemap lastmod).
5. Heavy pages: ~600 KB of un-split JS on home, 100–270 KB HTML everywhere because the mega-menu is inlined; comparison pages contain hand-typed approximate numbers rather than engine output, so they can drift from the calculator.
6. Nav links that are only redirects (`/tax-calculator/rsu/`, `/tax-guides/compare/us-states/`), an indexable internal preview page, and 404s for natural slugs (`united-kingdom`, `united-arab-emirates`).
7. Free API key by e-mail only; OpenAPI file advertised but not published.

### Worth replicating
- Shared engine (TS) compiled for browser and server; per-country metadata (`tax_year`, `last_updated`, `source_url`, `accuracy_confidence`) surfaced in both UI and API.
- Client-side calculation with URL deep links (`/?country=…&income=…&state=…`) — but key on ISO codes and make the country pages host the calculator.
- Result card anatomy: rank badge, big effective-rate number, labelled statutory components, totals, optional monthly / freedom-day / purchasing-power layers, cross-country savings and 10-year framing, sort bar.
- Jurisdiction model (country → state/province → locality) and `has_jurisdictions` flag in the countries list.
- Comparison page skeleton (overview callout → big picture → by-income grid → pros/cons → FAQ → related) and country hub skeleton; breadcrumb + Article + WebApplication schema; "Updated / Verified by" bylines; quantified changelog; affiliate cards with explicit fit warnings.
- API design: tiered endpoints, `X-RateLimit-*`, 403 with `upgrade_url`, `fx_source`/`fx_rate_age_hours`, `summary` ranking endpoint, Postman collection, attribution for free tier.
- Design tokens (slate neutrals + one gradient accent + semantic amber/green/red, 12–24 px radii) and the pricing matrix layout.

### Skip or do differently
- Hand-written approximate numbers in comparison tables — generate them from the engine at build time.
- Static exchange rates labelled "daily"; static per-country "living costs" with no source — either integrate a real PPP/COL source or drop the feature.
- Separate landing-page mini-form that redirects to the home page — put the real calculator on each country page.
- Chart.js from a third-party CDN and 600 KB of monolithic JS — code-split per country / lazy-load charts.
- Emoji as UI icons, "COUNTRY A/COUNTRY B" in H1s, mega-menu inlined in every page, `/newsletter-preview/` in the sitemap, FAQPage schema only on home.
- Uniform `datePublished/dateModified` and sitemap `lastmod` — emit real per-page dates.
- Bulk programmatic pages with thin variation (`{state}-sales-tax`, 19 near-identical city salary pages) unless each has unique data.
- Email-only API key issuance; publish the OpenAPI spec you advertise.

---

## Screenshot files
Directory: `docs/screenshots/countrytaxcalc/ (selected) ` (desktop = 1440 wide full-page; mobile = 390 viewport full-page — files wider than 390 px reflect the overflow bug)

- home-desktop.png (1440x6907), home-mobile.png (532x12886)
- home-calc-uk-75000-desktop.png, home-calc-uk-75000-advanced-desktop.png, home-calc-multi-desktop.png, home-calc-3countries-all-features-desktop.png (1440x12360), home-calc-uk-75000-mobile.png, home-deeplink-de-75000-desktop.png (shows the broken `country=DE` deep link), calc-home-after-75000-desktop.png, calc-home-after-250000-desktop.png
- tax-calculator-desktop.png (1791x6929 — desktop overflow), tax-calculator-mobile.png (459x17646)
- calc-germany-desktop.png (1440x8584), calc-germany-mobile.png (461x16769), calc-germany-after-75000-desktop.png, calc-germany-after-250000-desktop.png
- calc-uk-desktop.png, calc-uk-mobile.png, calc-uk-after-75000-desktop.png, calc-uk-after-250000-desktop.png
- calc-uae-desktop.png, calc-uae-mobile.png
- calc-rsu-desktop.png / calc-rsu-mobile.png (what `/tax-calculator/rsu/` actually serves = the `/tax-calculator/` index after redirect); calc-rsu-real-desktop.png / calc-rsu-real-mobile.png (`/tax-calculator/usa/rsu-calculator/`)
- guides-countries-desktop.png, guides-countries-mobile.png (554 wide), guide-germany-desktop.png, guide-germany-mobile.png
- compare-index-desktop.png, compare-index-mobile.png (`/tax-guides/compare/us-states/` redirects here), compare-germany-vs-uk-desktop.png, compare-germany-vs-uk-mobile.png, compare-california-vs-texas-desktop.png, compare-california-vs-texas-mobile.png
- tax-api-desktop.png, tax-api-mobile.png, api-access-desktop.png, api-access-mobile.png, tax-api-global-desktop.png, tax-api-global-mobile.png (628 wide), api-desktop.png, api-mobile.png (621 wide)
- methodology-desktop.png, methodology-mobile.png, disclaimer-desktop.png, disclaimer-mobile.png, about-desktop.png, about-mobile.png, authors-daniel-desktop.png, authors-daniel-mobile.png, advertise-desktop.png, advertise-mobile.png, tools-salary-equivalent-desktop.png, tools-salary-equivalent-mobile.png

Supporting data: `sitemap-urls.txt` (2,633 URLs), `fetch-log.txt`, `perf.json`, `calc-home-inspect.json`, `calc-germany-inspect.json`, `calc-uk-inspect.json`, `home-calc-flow.json`, `home-calc-flow2.json`, `api/real_*.json` (live API responses + headers), `api/probe-log.txt`, `js/` (downloaded bundles), `html/` and `text/` (page sources and text extractions).
