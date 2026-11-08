# Deploying and connecting Oblique Tax Intelligence

Plain-English runbook. Everything below is done in web dashboards; nothing needs a terminal.

## 1. How deployment works now

Railway is connected to the GitHub repository `wahajsid/oblique-tax-intelligence`. **Every push to `main` builds and deploys automatically** within two or three minutes. You do not need to do anything to "deploy" a change; to check one, open Railway → your service → **Deployments** and look for the newest entry with the commit message, then open the service URL.

If a deployment ever shows "Crashed", click it → **View logs**; the first red lines say why. Send them to me.

## 2. Settings to add in Railway (Variables tab)

Open the service → **Variables** → **New Variable**. Add these now:

| Variable | Value | Why |
| --- | --- | --- |
| `APP_SECRET` | any long random string (40+ characters; a password generator is fine) | signs the PDF download tokens and hashes IPs; without it a new key is made on every restart |
| `SITE_INDEXABLE` | leave unset (or `false`) until the tax team has signed off the rules; then `true` | controls `noindex` and robots.txt |

Then add the email variables from section 4. Railway redeploys automatically when variables change.

## 3. Put it on your domain

The domain map for Oblique's three properties (DNS is at Hover):

| Address | What | Hosted on | DNS record at Hover |
| --- | --- | --- | --- |
| `obliqueconsult.com`, `www` | the website | Framer | already set; do not touch |
| `tax.obliqueconsult.com` | these calculators (Tax Intelligence) | Railway | CNAME `tax` → the target Railway shows |
| `play.obliqueconsult.com` | the UAE tax game (repo `oblique-play`) | Vercel | CNAME `play` → `cname.vercel-dns.com` (see the game's FRAMER.md) |
| optional `tools.obliqueconsult.com` | alias of `tax.` | Railway | CNAME `tools` → same Railway target |
| optional `puzzle.obliqueconsult.com` | short link to the game's daily puzzle | Vercel redirect | per the game's FRAMER.md |

Framer cannot proxy a path like `/tax-intelligence` to another server, so subdomains are the clean option and keep the three deployments independent.

1. Railway → service → **Settings** → **Networking** → **Custom Domain** → enter `tax.obliqueconsult.com`. Railway shows a CNAME target such as `xxxxx.up.railway.app`.
2. Hover → `obliqueconsult.com` → DNS → add: **Type** CNAME, **Hostname** `tax`, **Target** the value Railway showed.
3. Wait a few minutes. Railway turns the domain green and issues the HTTPS certificate itself. Visit `https://tax.obliqueconsult.com/api/v1/health`.

Nothing in the app needs changing for the domain; links are relative and the sitemap uses the host it is served on. The game's leaderboard box on the tools home page appears automatically once the tools run on `*.obliqueconsult.com` (the game only allows framing from there).

## 4. Email delivery for enquiries (choose one)

### Option A, recommended: your Microsoft 365 mailbox (no DNS changes)

The app sends from a mailbox you own (for example `tax@obliqueconsult.com`) using Microsoft Graph, and the visitor's address is set as reply-to, so replying in Outlook goes straight to them. Steps for a Microsoft 365 admin (about 15 minutes):

1. **Create or pick the sending mailbox**, e.g. `tax@obliqueconsult.com` (a shared mailbox works and costs nothing). Decide where enquiries should land, e.g. `info@obliqueconsult.com`.
2. **Register an app**: Microsoft Entra admin center → **App registrations** → **New registration** → name "Oblique Tax Intelligence mailer", single tenant → Register. Copy the **Application (client) ID** and **Directory (tenant) ID** from the Overview page.
3. **Grant permission**: the app's **API permissions** → Add a permission → Microsoft Graph → **Application permissions** → `Mail.Send` → Add → **Grant admin consent**.
4. **Create a secret**: **Certificates & secrets** → New client secret → 24 months → copy the **Value** immediately (it is shown once).
5. **Restrict the app to the one mailbox** (recommended, Exchange admin, PowerShell):
   ```powershell
   Connect-ExchangeOnline
   New-DistributionGroup -Name "TaxIntelligenceSenders" -Type Security -Members tax@obliqueconsult.com
   New-ApplicationAccessPolicy -AppId <client id> -PolicyScopeGroupId TaxIntelligenceSenders@obliqueconsult.com -AccessRight RestrictAccess -Description "Tax Intelligence mailer"
   ```
6. **Railway → Variables**: `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_SENDER=tax@obliqueconsult.com`, `LEAD_EMAIL_TO=info@obliqueconsult.com` (comma-separate several). Save; Railway redeploys.
7. **Test**: on the live site, run any calculator, click **PDF working paper**, submit the form with your own details. The PDF downloads and the email arrives in `LEAD_EMAIL_TO` with the PDF attached and the visitor as reply-to. The lead-form confirmation shows the delivery status; a failure returns a clear error and nothing is lost silently.

### Option B: Resend (fastest if you cannot change Entra settings)

1. Create an account at resend.com → **Domains** → add `obliqueconsult.com` → add the three DNS records it shows (SPF/DKIM TXT and a CNAME) → wait for "Verified".
2. **API Keys** → create one (sending only).
3. Railway → Variables: `RESEND_API_KEY`, `LEAD_EMAIL_TO=info@obliqueconsult.com`, `LEAD_EMAIL_FROM=Oblique Tax Intelligence <tax@obliqueconsult.com>`.

Either option can run alongside `LEAD_WEBHOOK_URL` (Zapier/Make) or a HubSpot form if you later want leads in a CRM too; every configured destination receives each enquiry.

## 5. Navigation across the three properties

**On obliqueconsult.com (Framer).** Two links in the top menu, side by side after Services: **Tax Tools** → `https://tax.obliqueconsult.com/?utm_source=website` and **Tax Game** → `https://play.obliqueconsult.com/?utm_source=website` (the game's FRAMER.md already specifies its links and the two embed boxes). Then:

- **Services → Corporate Tax page**: two buttons under the intro, "Calculate it" → `tax.../uae/corporate-tax` and "Test yourself" → `play.../quiz/ct`. Same pattern on the VAT page with `/vat?j=AE` and `/quiz/vat`. The zakat service page gets "Calculate it" → `tax.../ksa/zakat-income-tax`.
- **Home page**: one strip with three cards, left to right: Calculators (`tax.`), Move to the UAE (`tax.../move`), Today's puzzle (the game's spot-the-error embed box). The leaderboard embed suits the LaunchPad or About page rather than the home page.
- **Footer, Resources column**: Tax calculators · Move to the UAE · UAE Tax Game · Privacy.
- **Articles**: end each UAE CT or VAT article with the matching calculator link and the matching quiz link; the diagnostic (`tax.../diagnose`) is the universal call-to-action for everything else.

**On tax.obliqueconsult.com (these tools).** Already done in the code: "Tax Game" in the top nav and footer, a quiz strip on the home page with the game's leaderboard box, and a "try today's quiz" line under the UAE Corporate Tax and VAT results. Links carry `?utm_source=tax-tools` so players who came from the calculators show up separately in HubSpot.

**On play.obliqueconsult.com (the game).** Worth adding in the game's own nav and after each quiz: "Work it out properly" → `https://tax.obliqueconsult.com/uae/corporate-tax?utm_source=game` (or `/vat?j=AE` after a VAT quiz), and "Talk to Oblique" → the contact page. That closes the loop: play → calculate → enquire.

**Lead capture note.** The game already feeds HubSpot. If you want calculator enquiries in the same place, set `HUBSPOT_PORTAL_ID` and `HUBSPOT_FORM_GUID` on the tools alongside the Microsoft 365 email variables; every enquiry then goes to both.

Leave `SITE_INDEXABLE` off until sign-off; the Framer links still work, search engines simply will not list the tool pages yet.

## 6. Checklist before announcing

- [ ] `APP_SECRET` set
- [ ] email destination configured and tested end to end
- [ ] custom domain green in Railway, `https://tax.obliqueconsult.com/api/v1/health` returns ok
- [ ] Framer nav and footer links added
- [ ] tax team reviewed `docs/LAUNCH_GATES.md` items 1 to 4
- [ ] `SITE_INDEXABLE=true` when ready to be found in search
