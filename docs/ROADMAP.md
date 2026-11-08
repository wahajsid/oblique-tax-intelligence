# Roadmap (from prototype to the platform in the strategy brief)

| Phase | Scope | Status |
| --- | --- | --- |
| 1. Foundation | Brand tokens, rules architecture, trace/flag model, test harness | Done in prototype |
| 2. Core MVP | UAE CT, UAE/KSA VAT, KSA Zakat + CIT, KSA WHT, GCC comparison, Move-to-UAE (8 origins), diagnostic | Done in prototype (indicative rules; expert review of every `pending_verification` item needed) |
| 3. Distribution | Guide pages, pairwise comparison pages, sitemap, schema.org | Basic versions done; needs editorial content per jurisdiction, FAQ blocks, Arabic (/ar/) |
| 4. Professional intelligence | Simpla explanations grounded on the trace, source retrieval, PDF/Excel working papers, expert review workflow | Not started |
| 5. Enterprise | Accounts, saved scenarios, API keys + rate limits, CRM lead capture (email for detailed report), ERP integration | Not started |

## Immediate next steps
1. Tax team review of `app/rules/*.json`: confirm or correct each `pending_verification` / `verified_secondary` item and set `review_status: verified` with the primary source.
2. Add Free Zone eligibility questionnaire (substance, audited FS, qualifying activities list) as its own P1 module.
3. Add Transfer Pricing risk analyzer and DMTT/Pillar Two screening with real GloBE inputs (covered taxes, SBIE).
4. Lead capture: decide controller, lawful basis and retention first (docs/LAUNCH_GATES.md); gate only the downloadable working paper, never the on-screen result.
5. Enable Pakistan once the FBR TY2027 table is verified; add Canada, Egypt, Philippines origins.
5. Deploy behind obliqueconsult.com/tax-intelligence (Framer can proxy or link out); add GA4 events per calculator.
