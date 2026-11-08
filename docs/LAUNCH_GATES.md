# Launch gates and rule lifecycle

Nothing in this repository is expert-approved. The site ships with `noindex` and a 503 enquiries endpoint until the gates below are passed.

## Rule lifecycle

| Status in `app/rules/*.json` | Meaning | Who can set it |
|---|---|---|
| `draft_law` | Announced or in the legislative process; not in force | Anyone, with the source |
| `pending_verification` | Reported in credible sources but unconfirmed, or sources conflict | Anyone, with a `verification_note` |
| `verified_secondary` | Consistent across the main practitioner sources; legal text not yet checked line by line | Reviewer, with sources |
| `verified` | Checked against the legal text; where interpretation is needed, Oblique's reading, in line with the prevailing practitioner view | Named qualified reviewer only, with date and source URL |

The results badge shows the worst status among the rules a calculation used. `enabled: false` on a personal-tax country hides it from visitors.

## Gates before public launch

1. **Tax review.** A qualified GCC reviewer confirms every `pending_verification` and `verified_secondary` rule against primary text, including: UAE Small Business Relief end date (MD 131/2026), QFZP de minimis under the 2025 decisions, KSA zakat Article 28 upper limit (the calculator stays review-required and shows a permanent flag until `ARTICLE_28_IMPLEMENTED` is flipped after implementation and sign-off), KSA WHT table, Bahrain draft CIT, Oman PIT 2028, Kuwait DMTT law number.
2. **Personal tax review.** Per-country specialists confirm GB, HK, SG, IN, US, AU, DE, ZA engines and enable PK once the FBR table is verified. Decide whether to model EPF (India), CPF ages (Singapore), Scottish rates (UK), state tax tables (US) and German contribution deductibility precisely.
3. **FX.** Done: ECB euro reference rates through the USD peg, with the dated table as a labelled fallback (`app/fx.py`). Remaining: reviewer confirms the peg handling and the six-hour cache is acceptable.
4. **Wording.** Legal review of the disclaimer, scope-gate text, advisory hooks and relocation residence flags. Partner review of the service catalogue (`app/services.py`): scope, deliverables, exclusions and the complimentary-call promise.
4a. **Journeys.** Done: the three cross-border journeys were reviewed and approved by the Oblique Consult tax team on 8 November 2026 and show 'Reviewed by'. Any future edit to `app/journeys.py` content should reset the status to draft until re-approved.
5. **Privacy.** The enquiry form is built and documented on /privacy (controller Oblique Consult, consent-based, 24-month retention, hashed IP only). Before enabling a destination: counsel review of the consent and privacy wording, confirm the processor list (Resend / HubSpot / automation tool) and the data location, and name the person who handles access and deletion requests. Set `APP_SECRET` on the host.
6. **Security.** Move inline scripts to files and drop `'unsafe-inline'` from the CSP; add rate limiting and a streaming body cap at the proxy; dependency lockfile and vulnerability scan; independent test.
7. **Accessibility and browsers.** Screen-reader pass (NVDA/VoiceOver), keyboard-only run through every calculator, Safari and Firefox checks, 320 px width.
8. **SEO switch.** Set `SITE_INDEXABLE=true`, verify robots.txt and sitemap (which now carries hreflang pairs for the Arabic pages), add per-page `dateModified`, register Search Console.
8a. **Arabic review.** An Arabic-speaking member of the tax team reads `app/i18n/ar.json` (about 590 strings) for terminology (ضريبة الشركات، الوعاء الزكوي، الاحتساب العكسي, etc.) and tone, then flips `_meta.reviewed_by`. Remaining English on Arabic pages: legal source references, rule descriptions and source citations in the rules panel, and the PDF working paper.
9. **Analytics.** If added, first-party and cookieless, with calculator-level events; update the privacy page.
10. **Hosting.** Behind obliqueconsult.com (`/tax-intelligence` path or subdomain) with HTTPS, HSTS and the headers above preserved by the proxy.

## Not gates, but next

PDF/Excel working papers, Free Zone eligibility questionnaire, TP risk analyzer, full GloBE/DMTT computation, Simpla explanations grounded on the trace, API keys and tiers, more origin countries (Canada, Egypt, Philippines, Pakistan).
