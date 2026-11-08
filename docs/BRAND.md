# Oblique Consult — Brand & Content Profile

Source: https://www.obliqueconsult.com/ (crawled 2026-11-07 with curl + Playwright/Chromium, desktop 1440x900, DPR 1).
Raw per-page JSON/text dumps: `/tmp/claude-0/-home-user/1c11056b-72c9-5786-97ee-05d013dc364b/scratchpad/oblique-raw/` (18 pages).
Scripts: `/tmp/claude-0/-home-user/1c11056b-72c9-5786-97ee-05d013dc364b/scratchpad/oblique-scripts/crawl.js`, `probe.js`.

Note: the site's assets are served from `framerusercontent.com`; that host had to be allowlisted in the sandbox before fonts, images and logos would load (the first crawl rendered with fallback fonts and broken images; all figures below are from the second, fully-loaded crawl).

---

## 1. Design tokens

All values are computed styles read via Playwright (hex converted from rgb). Framer stores the palette as opaque `--token-<uuid>` custom properties on `:root`; the names below are mine, the values are theirs.

```css
:root {
  /* ---- Surfaces ---- */
  --obco-bg-dark:            #0b0d12;   /* dominant page background (body, most sections, footer) — Framer token */
  --obco-bg-light:           #ffffff;   /* nav bar, home hero, contact/health-check hero */
  --obco-bg-card:            #0b0d12;   /* service/value cards: same as page bg, bordered */
  --obco-bg-pill:            rgba(240, 240, 250, 0.04); /* article category pill (#f0f0fa @ 4%) */
  --obco-bg-input:           #f5f5f5;   /* approx — form field fill (visual); computed input bg is transparent on wrapper */

  /* ---- Borders / dividers ---- */
  --obco-border-card:        rgba(255, 255, 255, 0.16); /* service cards, FAQ rows (also token #ffffff1f) */
  --obco-border-dark:        #262a3a;   /* secondary divider colour found in markup */
  --obco-border-token:       #333945;   /* Framer palette token (also used at 30%: #3339454d) */

  /* ---- Text ---- */
  --obco-text-on-dark:       #d4d5d6;   /* body copy on dark (most-used text colour) — token */
  --obco-text-on-dark-strong:#f0f0fa;   /* headings / card titles on dark — token */
  --obco-text-white:         #ffffff;   /* large section H2s ("Services We Offer"), footer copyright */
  --obco-text-on-light:      #141428;   /* headings + nav + body on white sections — token */
  --obco-text-on-light-alt:  #0b0d12;   /* contact-page H1/H2, button labels */
  --obco-text-muted:         #707070;   /* footer column headings ("Quick Links", "Services") */
  --obco-text-eyebrow:       #d3e0d5;   /* "ABOUT US" / "CONTACT US" eyebrow label — token */
  --obco-text-body-light-80: rgba(20, 20, 40, 0.8); /* intro paragraph on white card */

  /* ---- Accents ---- */
  --obco-accent-cyan:        #adebf2;   /* primary accent: button gradient base, hero stripe band, card borders — token */
  --obco-accent-cyan-bright: #a8f6ff;   /* big stat numbers "40+ / 150+ / 50+" (80px) */
  --obco-accent-cyan-pale:   #daffff;   /* sampled from hero stripe band highlight */
  --obco-accent-green:       #aff58a;   /* SVG quote-mark icons, star icons — token */
  --obco-accent-green-2:     #74e984;   /* token; LaunchPad page highlight text */
  --obco-accent-teal:        #33d9b7;   /* green CTA gradient start (LaunchPad CSS gradient) */
  --obco-accent-lime:        #97f264;   /* green CTA gradient end */
  --obco-accent-yellow:      #f7d268;   /* "View More Articles" gradient mid-stop */
  --obco-accent-orange:      #ffac47;   /* "View More Articles" gradient start */
  --obco-accent-indigo:      #3c3c7f;   /* footer "Work With Oblique" gradient start */
  --obco-accent-blue:        #0b6cfa;   /* Framer palette token (not observed in rendered pages) */
  --obco-accent-blue-2:      #4a93ff;   /* Framer palette token (not observed) */

  /* ---- Button gradients (computed background-image) ---- */
  --obco-btn-primary:   linear-gradient(11deg, #adebf2 0%, #adebf2 29.2%, #ffffff 106%);          /* "View Our Services", "Get Started Now" on service pages */
  --obco-btn-secondary: linear-gradient(11deg, #ffac47 -61%, #fcba54 14%, #f7d268 54%, #f7d469 74%, #f9eca7 106%); /* "View More Articles" */
  --obco-btn-green:     linear-gradient(11deg, #33d9b7 -61%, #33d9b7 14%, #97f264 54%, #97f264 74%, #ffffff 106%); /* LaunchPad; home "Get Started Now" is an image, sampled #3fdaaa -> #8bef6f */
  --obco-btn-footer:    linear-gradient(343deg, #3c3c7f -78%, #adebf2 40%, #ffffff 100%);         /* footer "Work With Oblique" */
  --obco-btn-submit-bg: #333333;  /* health-check form "Submit" */
  --obco-btn-submit-fg: #ffffff;

  /* ---- Radii ---- */
  --obco-radius-pill:   60px;   /* gradient CTA buttons (padding 8px 16px, h 40px) */
  --obco-radius-btn:    14px;   /* footer "Work With Oblique" */
  --obco-radius-submit: 10px;   /* form submit */
  --obco-radius-card:   20px;   /* contact / health-check white form card */
  --obco-radius-pill-tag: 100px;/* article category tag */
  --obco-radius-service-card: 0px; /* service cards are square-cornered, 1px border */

  /* ---- Typography ---- */
  --obco-font-heading: "Satoshi", "Satoshi Placeholder", sans-serif;
  --obco-font-body:    "Satoshi", "Satoshi Placeholder", sans-serif;
  --obco-font-label:   "Inter", "Inter Placeholder", sans-serif;   /* eyebrows, dates, team titles, copyright */
  --obco-font-arabic:  "Noto Sans Arabic", sans-serif;              /* language switcher; /ar/ site */

  --obco-h1-size: 70px;  --obco-h1-weight: 500; --obco-h1-lh: 77px;   --obco-h1-ls: -2.1px;   /* home hero */
  --obco-h1-inner-size: 56px; /* inner pages: 50–56px, weight 500, ls -1.5 to -1.7px */
  --obco-h2-size: 60px;  --obco-h2-weight: 400; --obco-h2-lh: 66px;   --obco-h2-ls: -2.4px;   /* section titles */
  --obco-h2-small: 30px; /* weight 400–500, lh 36px */
  --obco-h3-card: 22px;  /* weight 500, lh 28.6–30.8px, ls -0.2px */
  --obco-stat: 80px;     /* weight 400, colour #a8f6ff */
  --obco-body: 18px;     /* weight 400, lh 27px */
  --obco-lead: 22px;     /* weight 500 */
  --obco-ui: 16px;       /* buttons/links, weight 500 */
  --obco-nav: 15px;      /* weight 500 */
  --obco-eyebrow: 14px;  /* Inter 400, uppercase, ls 1.4px (about-page eyebrow: Satoshi 16px/500, ls 2.4px) */

  /* ---- Layout ---- */
  --obco-container: 1200px;
  --obco-nav-height: 61px;  /* white nav, no border/shadow */
}
```

### Font sources
- **Satoshi** (Fontshare, proxied by Framer) — weights 400/500/700 + italics. Example `@font-face` src:
  - 500: `https://framerusercontent.com/third-party-assets/fontshare/wf/P2LQKHE6KA6ZP4AAGN72KDWMHH6ZH3TA/ZC32TK2P7FPS5GFTL46EU6KQJA24ZYDB/7AHDUZ4A7LFLVFUIFSARGIWCRQJHISQP.woff2`
  - 700: `https://framerusercontent.com/third-party-assets/fontshare/wf/LAFFD4SDUCDVQEXFPDC7C53EQ4ZELWQI/PXCT3G6LO6ICM5I3NTYENYPWJAECAWDD/GHM6WVH6MILNYOOCXHXB5GTSGNTMGXZR.woff2`
  - 400: `https://framerusercontent.com/third-party-assets/fontshare/wf/TTX2Z3BF3P6Y5BQT3IV2VNOK6FL22KUT/7QYRJOI3JIMYHGY6CH7SOIFRQLZOLNJ6/KFIAZD4RUMEZIYV6FQ3T3GP5PDBDB6JY.woff2`
  - Public equivalent: https://www.fontshare.com/fonts/satoshi
- **Inter** — self-hosted by Framer at `https://framerusercontent.com/assets/*.woff2` (e.g. 400: `https://framerusercontent.com/assets/GrgcKwrN6d3Uz8EwcLHZxwEfC4.woff2`).
- **Noto Sans Arabic** 600 — Google Fonts: `https://fonts.gstatic.com/s/notosansarabic/v33/nwpCtLGrOAZMl5nJ_wfgRg3DrWFZWsnVBJ_sS6tlqHHFlj41v4o.woff2`
- Also preloaded but not used in computed styles on crawled pages: DM Sans and Poppins (fonts.gstatic.com).

### Logos & favicon (downloaded)
| File | Source URL | Notes |
|---|---|---|
| `/tmp/claude-0/-home-user/1c11056b-72c9-5786-97ee-05d013dc364b/scratchpad/oblique-brand/logo-obco-blue.svg` | https://framerusercontent.com/images/59vQNAimEDc7LjUOs2vROhsSZU.svg | Nav logo, wordmark "ob/co", fill `#14141e`, 1011x386 viewBox (alt "Obco Logo blue") |
| `.../oblique-brand/logo-oblique-consult.svg` | https://framerusercontent.com/images/IEllsoYByxWvzHldWJUzdw94E.svg | Footer wordmark "oblique/consult", fill `#f0f0fa` (light, for dark bg) |
| `.../oblique-brand/logo-oblique-consult-alt.svg` | https://framerusercontent.com/images/Lkl0y0Y0jqZcGzMzsH3WaJJiSQ.svg | Footer wordmark alt variant, fill `#f0f0fa` |
| `.../oblique-brand/logo-obco-slash-white.png` | https://framerusercontent.com/images/tLae0ikUAN1gST4Ee8hs5cQAkA.png | White "/" slash glyph, 224x563, used as decorative divider |
| `.../oblique-brand/favicon.png` | https://framerusercontent.com/images/fvfjzT6nUczNYNac2FzUSYrU9Y.png | 1501x1501 PNG; used for `rel=icon` (light+dark) and apple-touch-icon |
| `.../oblique-brand/og-image.png` | https://framerusercontent.com/assets/tmg6hZ2PoNfFAFaxpkfGokzey4.png | 1200x630 Open Graph/Twitter image |

Brand mark: the slash "/" is the recurring motif — short form **ob/co**, long form **oblique/consult**. Nav uses the dark mark on white; footer uses the light wordmark at ~200px on `#0b0d12`.

### Screenshots (full page, 1440 wide, DPR 1)
- `/tmp/claude-0/-home-user/1c11056b-72c9-5786-97ee-05d013dc364b/scratchpad/oblique-brand/screenshot-home.png` (1440x7206)
- `/tmp/claude-0/-home-user/1c11056b-72c9-5786-97ee-05d013dc364b/scratchpad/oblique-brand/screenshot-our-services.png` (1440x2368)
- `/tmp/claude-0/-home-user/1c11056b-72c9-5786-97ee-05d013dc364b/scratchpad/oblique-brand/screenshot-about-us.png` (1440x8229)
- `/tmp/claude-0/-home-user/1c11056b-72c9-5786-97ee-05d013dc364b/scratchpad/oblique-brand/screenshot-contact-us.png` (1440x2125)
- `/tmp/claude-0/-home-user/1c11056b-72c9-5786-97ee-05d013dc364b/scratchpad/oblique-brand/screenshot-free-tax-healthcheck.png`

Visual pattern: white nav + white hero (dark text) → long near-black (`#0b0d12`) body with bordered cards → dark footer. Light pages (contact, health-check) use a white-to-green (`#ffffff` → ~`#9ef07a`) diagonal-stripe background image with a white rounded (20px) form card. Home hero is followed by a cyan diagonal-stripe band (`#adebf2`/`#daffff`) holding a white intro card. CTAs are pill gradients; the home/about "Get Started Now" is a skewed parallelogram image (teal→lime). Photos: Burj Khalifa in the "Ready to Transform" CTA block; team headshots on white.

---

## 2. Brand voice

**Tagline / H1:** "Tax. Accounting. Advisory. Solutions."
**Hero sub:** "Our expert team delivers the finance transformation you didn't know you needed."
**Meta description:** "A trusted accounting and tax consulting services provider, Oblique Consult offers expert, AI-driven financial management solutions to businesses of all sizes."
**Title tag:** "Oblique Consult | Corporate Tax & VAT Advisory in Dubai, UAE"
**Recurring CTA block:** "Ready to Transform Your Financial Future?" / "Don't let financial complexities hold you back. Reach out today, and let's write your success story together." → button "Get Started Now". Nav CTA: "Work With Oblique". Contact CTA: "Book a Consultation" (Calendly).
**Proof points (repeated on home/about/health-check):** "40+ Years of combined experience between the founders", "150+ Tax audits cleared in UAE and KSA with zero penalties", "50+ High-value clients with a combined revenue of AED 2 billion", "Trusted by 50+ high-value clients" (5 stars), "100% Client Retention Rate".
**Testimonials:** Estée Lauder Companies Inc. ("Oblique Consult are partners. Not another agency."), Snapchat, Kitchen Park Restaurant LLC. Client logo strip: Estée Lauder, Petronas, Richemont, RSA Global, Magnati, Dubai Investments, Madame Tussauds, Armed Forces Officers Club, Snapchat.

**One-paragraph summary:** Oblique Consult positions itself as a boutique, founder-led GCC tax, accounting and advisory firm that behaves like a partner rather than a vendor: confident, plain-spoken and benefit-first ("We see tax compliance as more than just a requirement—it's your key to global success"), with repeated emphasis on senior attention, same-day responsiveness, zero-penalty audit track record and "AI-driven"/"technology-driven" finance transformation. Copy is second-person, short-sentence, aspirational ("write your success story"), and leans on hard numbers and blue-chip client names for credibility; the LaunchPad startup page switches to a deliberately irreverent, slang-heavy register ("Tax Advisory that Doesn't Suck", "Slide into our DMs", "number ninjas"). Values named on the About page: Integrity, Ownership, Partnership, Innovation, Reflection. Bilingual (English/Arabic site at /ar/).

### Services (exactly as named on the site)
Top-level cards (home & /services/our-services), each with its one-line description:
1. **Corporate Tax** — "We see tax compliance as more than just a requirement—it's your key to global success."
2. **VAT** — "We make VAT a catalyst for business transformation."
3. **Accounting** — "We provide accounting solutions that drive growth."
4. **Risk & Finance Advisory** — "We transform your business risks into opportunities."
5. **Finance Transformation** — "Put an end to the status quo. Embrace digital transformation in finance."
6. **Career Development** — "We equip your workforce for future success."
Additional service pages not in the cards: **Corporate Services** (/services/corporate-services) and **Corporate Tax Compliance** landing page (/services/corporate-tax-compliance, also -ae variant).

Sub-services (H2s on each service page):
- Corporate Tax: Corporate Tax; Zakat Services; Double Tax Avoidance; Transfer Pricing; Tax Structuring (incl. Planning & Strategy, Compliance & Return Preparation, Tax Risk Management & Dispute Resolution, Cross-Border Tax Structuring, Withholding Tax Management, M&A Tax Planning & Due Diligence, Restructuring & Reorganization Tax Advice).
- VAT: VAT Implementation and Registration; VAT Return Preparation & Filing; VAT Planning and Structure; VAT Audit Support and Dispute Resolution; Cross-Border VAT Advisory; VAT Technology Solutions; VAT Health Checks and Risk Management.
- Accounting: Bookkeeping; Seamless Accounting System Integration; IFRS and US GAAP Advisory; Convergence of IFRS and US GAAP; Financial Reporting; Audit Support.
- Risk & Finance Advisory: Internal Audit; Risk Assessment and Mapping; Policy and Procedures.
- Finance Transformation: AI-Driven Process Optimization; Paperless Initiatives; Real-Time Reporting Solutions; Data Analytics for Finance; Robotic Process Automation (RPA).
- Career Development: Learning and Development; Executive Recruitment; Talent Acquisition and Recruitment.
- Corporate Services: Administrative and Government Support (licensing, PRO, visas, attestation); Business Setup and Formation; Human Resources Support (payroll, recruitment); Corporate Banking Setup and Onboarding (bank account opening, KYC).
- Programs/tools: **LaunchPad Program** for startups ("Disrupt. Scale. Conquer. We've got your financial back." — 50% off first 6 months, 3-year partnership, mentions a "DIY Quote Generator / online calculator" — no calculator link found on the page); **Free 30-minute tax healthcheck** lead-gen form (/free-tax-healthcheck: Name, Phone (+971), Email, Company, Industry → Submit); FAQ page; Articles (categories: UAE Corporate Tax, VAT, GCC Tax, Compliance & Regulation, Accounting & Audit, Business Advisory).

### Jurisdictions mentioned
UAE (dominant; Dubai, Sharjah, mainland and free zones, DIFC, ADGM, FTA), KSA / Saudi Arabia (Zakat, ZATCA e-invoicing), GCC (stated ambition to expand across the GCC; "5 countries"), Qatar, Bahrain (article content), Middle East. Regulatory references: FTA, ZATCA, PDPL, Pillar Two, ESR, goAML.

### Simpla / Simpla.ai
One mention, on the About page founder bio: "It's his future-forward vision that led to the development of **Simpla AI**, a personal financial advisor for entrepreneurs." No link to simpla.ai and no other reference anywhere on the crawled site. Not found on home, services or footer.

### Team (About page, "Meet the Team")
- **Wahaj Siddiqui** — Founder (18+ years; ex-KPMG, Etihad Airways, Al Hilal Bank, Emirates Airlines)
- Arslan Ahmad — Senior Manager
- Mohsin Ali Awan — Accounting Lead
- Aidarous Mohammed — Senior Advisor - Accounts & Tax
- Syed Adil — Assistant Manager
- Nikhil Mahendran — Tax Advisor
- KR Ashtalakshmi — Senior Tax Advisor
- Muhammad Ahmed — Associate
- Adnan Yousaf — Associate
- Anjana Padmanabhan — Intern
Company facts: founded 2018, "proud team of 20", 50+ clients, 5 countries, offices in Dubai and Sharjah.

### Contact details
- Phone: +971 50 687 3135
- Email: info@obliqueconsult.com
- Dubai Office: Office 203, Ajmal Sarah Tower, Dubailand Residential Complex, Dubai, UAE.
- Sharjah Office: Office 10, Level 1, Sharjah Media City, Sharjah, UAE.
- Booking: https://calendly.com/alina-obliqueconsult/30min

### Social links (footer "Follow us")
- LinkedIn: https://www.linkedin.com/company/obliqueconsult/posts/?feedView=all
- Instagram: https://www.instagram.com/consultoblique/
- Facebook: https://www.facebook.com/obliqueconsult

### Legal footer text
"© Oblique Consult 2026" · "Website by Dantone". Footer links: About Us, LaunchPad Program, Articles, Privacy Policy, Terms of Service. Privacy policy cites GCC data-protection laws incl. the UAE PDPL; Terms define Services as "tax advisory, accounting, risk and finance advisory, and finance transformation services". **Not determined:** registered legal entity name/licence number (not stated anywhere on the site; only "Oblique Consult" and the short form "OBCO").

---

## 3. Tech stack
- **Framer** (static export; `<meta name="generator" content="Framer bf2f4e6">`; runtime bundles from `framerusercontent.com/sites/4Fvirb2gw8x3TyThQLS2RD/` — React + Motion (framer-motion) modules; `events.framer.com` analytics; Framer CMS for articles).
- Localisation: English (`/`) and Arabic (`/ar/`), language switcher with twemoji flag SVG from cdnjs.
- Analytics/marketing: Google Analytics 4 (`G-SGLW2GW098` via gtag), Hotjar (site 4931984), LinkedIn Insight Tag.
- Forms: Framer native form (health check); contact page uses Calendly.
- Fonts via Framer's Fontshare proxy + Google Fonts; images via framerusercontent.com CDN.
- Sitemaps: `/sitemap.xml` → `sitemap_en.xml` (66 URLs) + `sitemap_ar.xml`.

## 4. Could not determine / caveats
- Exact hex of the home-page green "Get Started Now" CTA: it is a raster image; sampled pixels run ~#3fdaaa → #8bef6f (matches the CSS gradient #33d9b7→#97f264 used on the LaunchPad page).
- Hover/active button states (not probed).
- Legal entity name, trade licence, VAT/TRN number: not published on the site.
- Body `<body>` computed colour is `#000000`/12px sans-serif default; all real text styles are set per Framer text node (values above are from those nodes).
- Framer palette tokens present in CSS but not seen rendered on crawled pages: #0b6cfa, #4a93ff, #f26207, #d8674f, #48b19d, #d486f1, #faf7f1, #f2eee3, #ebebe6, #1c1f1e, #50524e, #888, #fbfafb.
