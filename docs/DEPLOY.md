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

Recommended address: **`tax.obliqueconsult.com`**. The main site runs on Framer, which cannot proxy a path like `/tax-intelligence` to another server, so a subdomain is the clean option and keeps the two deployments independent.

1. Railway → service → **Settings** → **Networking** → **Custom Domain** → enter `tax.obliqueconsult.com`. Railway shows a CNAME target such as `xxxxx.up.railway.app`.
2. Open the DNS for `obliqueconsult.com` (wherever the domain's nameservers point: usually the registrar, or Cloudflare). Add a record: **Type** CNAME, **Name** `tax`, **Target** the value Railway showed, **Proxy** off (DNS only) if Cloudflare asks.
3. Wait a few minutes. Railway turns the domain green and issues the HTTPS certificate itself. Visit `https://tax.obliqueconsult.com/api/v1/health`.
4. Optional later: add `tools.obliqueconsult.com` the same way as a second alias.

Nothing in the app needs changing for the domain; links are relative and the sitemap uses the host it is served on.

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

## 5. Linking from obliqueconsult.com (Framer)

Navigation changes to make in Framer:

- **Top nav**: add **"Tax Tools"** (or "Tax Intelligence") linking to `https://tax.obliqueconsult.com`, placed after "Services" and before "Insights/Articles". Open in the same tab; the tool's header links back to the main site.
- **Services → Corporate Tax and VAT pages**: a short block "Try the calculator" linking to the matching tool (`/uae/corporate-tax`, `/vat?j=AE`, `/ksa/zakat-income-tax`).
- **Footer**: under Resources, add "Tax calculators" and "Move to the UAE calculator" (`/move`).
- **Articles**: each UAE CT or VAT article can end with the relevant calculator link; the diagnostic (`/diagnose`) is a good universal call-to-action.
- **Home page**: one card in the services grid or a strip above the footer: "Free GCC tax calculators and the UAE relocation comparison".

Leave `SITE_INDEXABLE` off until sign-off; the Framer links still work, search engines simply will not list the tool pages yet.

## 6. Checklist before announcing

- [ ] `APP_SECRET` set
- [ ] email destination configured and tested end to end
- [ ] custom domain green in Railway, `https://tax.obliqueconsult.com/api/v1/health` returns ok
- [ ] Framer nav and footer links added
- [ ] tax team reviewed `docs/LAUNCH_GATES.md` items 1 to 4
- [ ] `SITE_INDEXABLE=true` when ready to be found in search
