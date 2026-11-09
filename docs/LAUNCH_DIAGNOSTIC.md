# Pre-launch diagnostic, 9 November 2026

Method: a headless-browser crawl of all 85 pages on desktop and a 390 px phone, 22 end-to-end checks with a lead destination configured, and the 119-test suite. The live Railway host was not reachable from the build environment, so this is the build that will deploy, not the deployed site.

## Result

| Check | Result |
|---|---|
| Pages returning 200 | 85 of 85, no broken internal links |
| JavaScript errors | none |
| Third-party requests | none (Turnstile loads only if its keys are set) |
| Inputs without a label, images without alt text | none |
| Horizontal overflow on a phone | none (one found and fixed on the Arabic changes page) |
| Median page load, local | about 0.6 s; home is 6 KB compressed plus about 190 KB of fonts and assets |
| End-to-end | calculators compute on load; PDF form sends, downloads and offers the booking link; service buttons open a dialog named after the service; share links restore inputs; theme and language switches work; diagnostic and rule-change subscription work |
| Automated tests | 119 pass |

## Fixed during this diagnostic

1. **No social preview or canonical tags.** A link pasted into LinkedIn or WhatsApp showed a bare URL. Every page now has canonical, Open Graph and Twitter tags and a branded 1200×630 preview image.
2. **Arabic pages reused English titles and descriptions.** They now have their own.
3. **Phone visitors could not reach half the site.** The header hid Move to UAE, Diagnostic and Guides with no menu. A mobile menu now lists every tool, the guides, the journeys and a booking button.
4. **Arabic changes page scrolled sideways by 8,800 px** on phones because of the hidden spam-trap field. Fixed for both forms.
5. **/docs and /redoc were broken** by the site's own security policy and pulled files from a CDN. Removed; the API page and the OpenAPI schema remain.
6. **No compression, no asset caching, no HSTS.** Added gzip, year-long caching for versioned assets and HSTS behind HTTPS.
7. **Titles and descriptions**: the home title was 98 characters; 60 pages shared one 189-character description. Shortened and written per page.
8. **404 page** now points to the three most used tools.

## Working well

- **The number arrives before any ask.** Every calculator computes on load with a realistic example. Nothing is gated except the PDF.
- **The working is shown.** Each line carries its formula and rule id, and each rule its source and date. This is the main differentiator from CountryTaxCalc and from most Gulf calculators.
- **Honesty about limits.** Verified and review-required are separate; zakat stays review-required until the tax team signs off. A CFO will trust this more than a confident wrong number.
- **Three clear entry decisions** on the home page, each leading to tools, a journey and a matching service.
- **Enquiry in three fields**, with inputs attached only on consent and a booking link straight after.
- **Privacy posture**: no cookies, no trackers, no third-party calls, inputs not stored.
- **Arabic**, right-to-left, across the UAE and Saudi pages.
- **Depth where it matters**: Small Business Relief to 2029 with the prior-period condition, the Free Zone de minimis test, zakat Articles 25, 27 and 28 from the regulation text, treaty rates and gross-up on Saudi withholding.

## To improve: experience

| # | Issue | Why it matters | Effort |
|---|---|---|---|
| 1 | Long forms on first view. Zakat shows 14 fields, Move 13, UAE Corporate Tax 8. | A first-time visitor wants one number from one or two inputs. Lead with profit and revenue; fold the rest under "Refine". | Half a day |
| 2 | No presets. | "Free Zone trader, AED 3m revenue", "Mainland services, AED 12m" as one-tap examples teach the tool faster than labels. | Half a day |
| 3 | Zakat is always amber. | Correct today, but it looks broken beside the UAE pages. Sign-off of the worked cases lifts it. | Reviewer time |
| 4 | Results sit below the form on a phone. | After tapping Calculate the visitor must scroll. Scroll to the headline number automatically on explicit submit. | One hour |
| 5 | Dates are shown as 2026-11-09. | Read as "9 November 2026" for a UK and Gulf audience. | One hour |
| 6 | GCC comparison is a table. | Give it the bar treatment the home hero has, with the visitor's own figure. | Half a day |
| 7 | Arabic is unreviewed and the PDF is English only. | A native review, then an Arabic PDF. | Reviewer time plus one day |

## To improve: attracting and converting customers

| # | Action | Why | Effort |
|---|---|---|---|
| 1 | **Measure from day one.** There is no analytics, by design. Add a first-party, cookieless event counter (page viewed, calculation run, PDF requested, call clicked) written to Supabase. | Without it nobody can say which tool earns enquiries. | Half a day |
| 2 | **WhatsApp.** Add a click-to-chat button beside "Book a call". | In the UAE and Saudi Arabia it is the default first contact for owner-managed businesses. Needs the firm's WhatsApp Business number. | One hour |
| 3 | **Names and faces.** Put the reviewing partner's name, photo and one line of credentials beside the confidence panel and on the services page. | "Oblique Consult tax team" is anonymous. People hire people. | One hour once supplied |
| 4 | **Proof.** "150+ audits cleared, zero penalties" appears once at the foot of the home page. Move it under the hero and add two client lines or logos if permitted. | Trust before the first number. | One hour |
| 5 | **Entry points from the main site.** Nav item "Tax tools"; a home-page band; and on each Framer service page a deep link to the matching calculator with `?utm_source=website`. | The tools only earn if the main site sends people to them. Source is already captured with each enquiry. | Framer work, one to two hours |
| 6 | **One article per calculator.** "Small Business Relief to 2029: who still qualifies", "Zakat base under the 2024 Regulations", "What 0% really saves a UK founder". Each links to its tool. | This is how search finds the calculators; the pages themselves are thin on prose. | Ongoing |
| 7 | **Email the result.** Offer "send this to my inbox" as a lighter step than the PDF form. | Captures visitors not ready to talk. | Half a day |
| 8 | **Rule-change emails.** The subscription form collects addresses; someone must send the emails. Assign an owner and a template. | An unused list is a broken promise. | Process |
| 9 | **LinkedIn launch.** The preview image is ready. Post the UK-founder journey and the SBR-to-2029 change first. | Both are timely and specific. | Process |

## Launch-day checklist

1. Railway variables: `APP_SECRET`, `LEAD_EMAIL_TO` with the Microsoft 365 or Resend set, `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`, and **`SITE_URL=https://tax.obliqueconsult.com`** (new: drives canonical and preview URLs).
2. DNS: CNAME `tax` to the Railway domain; add the custom domain in Railway and wait for the certificate.
3. Send one test enquiry and one rule-change subscription; confirm the email, the PDF attachment and the Supabase row.
4. Paste the home URL into LinkedIn's Post Inspector to confirm the preview.
5. On a phone: open the menu, run UAE Corporate Tax, request the PDF.
6. On the move page, confirm the rate line reads "ECB reference rate of <date>".
7. Framer: add the nav and footer links. On the game host, allow framing from the tax subdomain if the leaderboard should show.
8. Indexing: keep `SITE_INDEXABLE=false` for the first days. The site is fully usable from the main site while hidden from search. Flip it after the Arabic review and the zakat sign-off.

## Known and accepted

- Zakat is review-required until `ZAKAT_BASE_SIGNED_OFF` is flipped.
- India rules are verified against practitioner sources, not the Finance Act text.
- The API has no keys or limits and is unpromoted.
- Pakistan is listed but disabled.
