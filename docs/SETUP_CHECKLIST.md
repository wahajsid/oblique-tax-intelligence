# Setup checklist

Everything that has to happen outside this repository before the site is promoted. Owner: Wahaj. Nothing here needs code changes unless marked.

## 1. Go live with enquiries (one hour)

Pick a mailbox route and set the variables in Railway → service → Variables. The form, the PDF gate and the rule-change subscription all switch on by themselves.

| Variable | Value | Notes |
|---|---|---|
| `APP_SECRET` | 32+ random characters | Signs PDF tokens. Generate with `openssl rand -hex 32`. |
| `SITE_URL` | `https://tax.obliqueconsult.com` | Public origin for canonical links, the sitemap and social previews. No trailing slash. |
| `LEAD_EMAIL_TO` | `info@obliqueconsult.com, wahaj@obliqueconsult.com` | Comma-separated. |
| **Microsoft 365 route** | | Sends from a real @obliqueconsult.com mailbox via Graph. |
| `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET` | From Entra app registration | Application permission `Mail.Send`, admin-consented; restrict with an ApplicationAccessPolicy to the sender mailbox. |
| `MS_SENDER` | `tax@obliqueconsult.com` | Create this shared mailbox or use an existing one. |
| **or Resend route** | | 15 minutes, no Entra work. |
| `RESEND_API_KEY` | From resend.com | Verify the `obliqueconsult.com` domain (SPF + DKIM DNS records Resend gives you). |
| `LEAD_EMAIL_FROM` | `Oblique Tax Intelligence <tax@obliqueconsult.com>` | Must be on the verified domain. |

Test: submit the PDF form on `/uae/corporate-tax`, confirm the email arrives with the PDF attached, then try `/changes` and confirm a "Rule-change subscriber" email.

## 2. Durable record of leads: Supabase (30 minutes)

Railway's filesystem is wiped on each deploy, so SQLite is only for local testing. Supabase's free tier is enough.

1. Create a project at supabase.com (region: Frankfurt or Mumbai, closest to the UAE).
2. SQL editor → run:

```sql
create table public.leads (
  id uuid primary key,
  received_at timestamptz not null,
  kind text not null check (kind in ('enquiry','subscription')),
  name text, email text not null, phone text, company text, message text,
  interest text, profile text, service text, calculator text, source text, page_url text, summary text,
  consent_contact jsonb, consent_marketing jsonb,
  inputs jsonb, ip_hash text, retention text,
  status text default 'new', owner text, notes text
);
alter table public.leads enable row level security;
-- No policies: only the service role (used server-side) can read or write.
create index on public.leads (received_at desc);
create index on public.leads (email);
```

3. Project settings → API: copy the project URL and the **service_role** key (never the anon key; never put it in the front end).
4. Railway variables: `SUPABASE_URL=https://<project>.supabase.co`, `SUPABASE_SERVICE_KEY=<service_role>`. Optional `SUPABASE_TABLE` if you name it differently.
5. **Usage counter.** In the same SQL editor, add the table the cookieless counter writes to (event name, page, calculator, source, language, time; no IP and no identifier):

```sql
create table public.events (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  name text not null, path text, calculator text, source text, lang text, detail text
);
alter table public.events enable row level security;   -- service role only
create index on public.events (at desc);
create index on public.events (name, at desc);

-- Daily view for a quick look
create view public.events_daily as
  select date_trunc('day', at)::date as day, name, coalesce(nullif(calculator, ''), path) as page, source, count(*) as n
  from public.events group by 1, 2, 3, 4;
```

   No variable is needed beyond `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`. Optional: set `STATS_TOKEN` to a long random string and open `/api/v1/stats?token=<it>` for counts since the last deploy.
6. Supabase → Table editor → leads: you now have a working lead list with `status`, `owner`, `notes` columns to run follow-up from. Add team members as project viewers.

Later, if you want a CRM: keep Supabase as the record and add `HUBSPOT_PORTAL_ID` + `HUBSPOT_FORM_GUID`, or a Zapier/Make `LEAD_WEBHOOK_URL`. Every configured destination receives every enquiry.

## 3. Domain and DNS (30 minutes, then wait for propagation)

| Record | Value |
|---|---|
| `tax.obliqueconsult.com` CNAME | the Railway domain (Railway → Settings → Domains → Add) |
| `play.obliqueconsult.com` CNAME | the game's host |
| Resend/M365 SPF, DKIM, DMARC | as issued; one SPF record only, merge includes |

Then on the Framer site add "Tax tools" to the main nav and footer pointing at the subdomain (see docs/DEPLOY.md for placement).

## 4. Search and indexing (after tax sign-off only)

- Set `SITE_INDEXABLE=true` in Railway. Until then every page is `noindex`.
- Google Search Console: add `tax.obliqueconsult.com`, submit `/sitemap.xml`.
- Bing Webmaster Tools: same.

## 5. People and reviews

- [ ] Arabic: an Arabic-speaking member of the team reads `app/i18n/ar.json` and flips `_meta.reviewed_by`.
- [ ] Rules: a named reviewer signs off the `verified_secondary` and `pending_verification` rules listed in docs/LAUNCH_GATES.md gate 1. The confidence panel shows their name.
- [ ] India: read the Finance Act 2026 and section 156 of the Income-tax Act 2025 once; then flip the India rules to `verified`.
- [ ] Legal: disclaimer, privacy page, two consent texts (contact, updates). Name the person who handles access and deletion requests.
- [ ] Services: partner review of `app/services.py` (scope, deliverables, exclusions, the free-call promise).
- [ ] Reviewer card: edit `app/team.json` (name, role, credential) and add a square photo to `app/static/img/team/`, then set `photo` to its file name. With no photo the initials show. Empty the name to hide the card.
- [ ] WhatsApp: the button uses +971 50 687 3135. Override with `WHATSAPP_NUMBER` in Railway; set it empty to hide.
- [ ] Framer: add the links in docs/FRAMER_LINKS.md.
- [ ] Calendly: confirm `https://calendly.com/alina-obliqueconsult/30min` is the booking link you want on every page, or change `booking_url` in `app/main.py`.

## 6. Keys and third-party APIs you may want later (none required today)

| Need | Option | Variable |
|---|---|---|
| Exchange rates with a date | Done: ECB daily reference rates, no key. Set `FX_FEED=off` only to force the dated table | none |
| Rule-change emails to subscribers | Resend Broadcasts or M365 mail merge from the Supabase list | none; export from Supabase |
| Spam protection if the honeypot is not enough | Done: Cloudflare Turnstile. Create a widget at dash.cloudflare.com → Turnstile for `tax.obliqueconsult.com` (and the Railway host while testing), mode Managed | `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET` |
| Public API access for partners | API keys table in Supabase + per-key rate limit | code change; keep unpromoted until then |
| Error monitoring | Sentry (self-hosted or EU region) | `SENTRY_DSN` (code change; update privacy page) |
| Analytics | First-party page counter in the app, or Plausible EU | update privacy page first |
| Simpla explanations on results | Anthropic API, grounded on the trace | `ANTHROPIC_API_KEY` (code change; roadmap) |

## 7. Operations

- Railway: enable health checks on `/api/v1/health`, set restart policy, add a second replica if traffic justifies it.
- Backups: Supabase daily backups are on by default for paid plans; on the free tier export the leads table monthly.
- Secrets rotation: `APP_SECRET`, mail keys and the Supabase service key once a year or on staff change.
- Keep `docs/DECISIONS.md` and the rules changelogs current; the `/changes` page renders from them.
