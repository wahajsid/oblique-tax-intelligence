/* Shared calculator runtime: serialise the form, POST to the API, render the
   result shell (tiles, review banner, flags, trace, rules). Pages declare a config
   via initCalc(). Accessibility: aria-busy on the form while a request runs,
   aria-live results region, focus moved to results on explicit submit. */
(function () {
  const fmt = (n, cur, dec) => (n === null || n === undefined || n === '') ? '—'
    : (cur ? cur + ' ' : '') + Number(n).toLocaleString('en', { minimumFractionDigits: dec ?? (Number.isInteger(n) ? 0 : 2), maximumFractionDigits: dec ?? 2 });
  const pct = (x) => (x === null || x === undefined) ? '—' : (x * 100).toFixed(2) + '%';
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const labels = { verified: 'Verified', verified_secondary: 'Verified against practitioner sources', pending_verification: 'Pending verification', draft_law: 'Includes draft law' };

  function serialise(form) {
    const data = {};
    for (const el of form.elements) {
      if (!el.name || el.disabled) continue;
      if (el.type === 'checkbox') data[el.name] = el.checked;
      else if (el.type === 'number') data[el.name] = el.value === '' ? (el.dataset.nullable ? null : 0) : Number(el.value);
      else data[el.name] = el.value;
    }
    return data;
  }

  function render(res, cfg) {
    const root = document.getElementById('results');
    root.hidden = false;
    const cur = res.currency, dec = res.currency_decimals ?? 2;
    const review = res.outcome === 'REVIEW_REQUIRED';
    root.classList.toggle('review-required', review);

    const badge = document.getElementById('status-badge');
    badge.className = 'badge ' + res.review_status;
    badge.textContent = 'Rules: ' + (labels[res.review_status] || res.review_status);
    badge.title = 'How well the rules used are confirmed. Separate from whether your facts fit; see the outcome label.';

    const banner = document.getElementById('review-banner');
    if (banner) {
      banner.hidden = !review;
      banner.innerHTML = review ? `<b>Review required.</b><ul>${(res.review_reasons || []).map(r => `<li>${esc(r)}</li>`).join('')}</ul>
        <span class="small">The figure is greyed so you still see the scale. Confirm the scope in the form, or <a href="${esc(cfg.contactUrl || '#')}" target="_blank" rel="noopener">ask Oblique</a>.</span>` : '';
    }
    const outcome = document.getElementById('outcome-label');
    if (outcome) { outcome.textContent = review ? 'Outcome: review required' : 'Outcome: illustrative estimate'; outcome.title = review ? 'Your facts are not yet confirmed to fit this calculator.' : 'Scope confirmed. Still an estimate, not advice.'; }

    const tiles = cfg.tiles(res.outputs, cur, dec).filter(Boolean);
    document.getElementById('tiles').innerHTML = tiles.map((t, i) =>
      `<div class="tile ${i === 0 ? 'hero-tile' : ''}"><div class="k">${esc(t[0])}</div><div class="v">${esc(t[1])}</div></div>`).join('');

    document.getElementById('flags').innerHTML = (res.flags || []).filter(f => f.code !== 'review_required').map(f =>
      `<div class="flag ${f.severity}"><b>${esc(f.title)}</b>${esc(f.detail)}${f.advisory_hook ? `<span class="hook">→ ${esc(f.advisory_hook)}</span>` : ''}</div>`).join('');

    document.getElementById('trace').innerHTML = (res.trace || []).map(s =>
      `<tr class="${s.kind || ''}"><td>${esc(s.label)}${s.formula ? `<span class="formula">${esc(s.formula)}</span>` : ''}${s.note ? `<span class="formula">${esc(s.note)}</span>` : ''}</td>
       <td class="rid">${esc(s.rule_id || '')}</td><td class="amt">${s.amount === undefined ? '' : (Math.abs(s.amount) <= 1 && !Number.isInteger(s.amount) && s.kind === 'info' ? pct(s.amount) : fmt(s.amount, null, dec))}</td></tr>`).join('');

    document.getElementById('rules').innerHTML = (res.rules || []).map(r =>
      `<li><span class="status-dot ${r.review_status}"></span><b>${esc(r.rule_id)}</b> — ${esc(r.description)}<br>
       <span class="small muted">Status: ${esc(labels[r.review_status] || r.review_status)} · Source: ${r.source_url ? `<a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.source_reference)}</a>` : esc(r.source_reference)}
       ${r.effective_from ? ` · Effective ${esc(r.effective_from)}${r.effective_to ? ' to ' + esc(r.effective_to) : ''}` : ''}${r.verification_note ? `<br><em>${esc(r.verification_note)}</em>` : ''}</span></li>`).join('');
    document.getElementById('assumptions').textContent = 'Assumptions: ' + (res.assumptions || []).join(' ');
    document.getElementById('disclaimer').textContent = res.disclaimer || '';
    window.renderNextSteps(res.next_steps || [], window._lastCalc);
    window.renderConfidence(res.confidence);
    root.dataset.json = JSON.stringify(res, null, 2);
    if (cfg._explicit) { root.focus({ preventScroll: window.innerWidth >= 960 }); if (window.innerWidth < 960) root.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    cfg._explicit = false;
  }

  function readShared() {
    // Inputs travel in the fragment (#...) so they never reach a server; accept legacy ?query links too.
    const h = location.hash.startsWith('#') ? location.hash.slice(1) : '';
    const q = new URLSearchParams(h || location.search);
    return q;
  }
  function prefillFromURL(form, cfg) {
    const q = readShared();
    let any = false;
    for (const el of form.elements) {
      if (!el.name || !q.has(el.name)) continue;
      const v = q.get(el.name); any = true;
      if (el.type === 'checkbox') el.checked = (v === '1' || v === 'true');
      else el.value = v;
    }
    if (cfg.fromShared) any = cfg.fromShared(q, form) || any;
    return any;
  }
  function deepLink(form, cfg) {
    // Encode EVERY named control (including unchecked boxes as 0) so a shared link reproduces the exact facts.
    const q = new URLSearchParams();
    for (const el of form.elements) {
      if (!el.name || el.type === 'hidden' || el.disabled) continue;
      if (el.type === 'checkbox') q.set(el.name, el.checked ? '1' : '0');
      else q.set(el.name, el.value);
    }
    if (cfg.toShared) cfg.toShared(q, form);
    const u = new URL(location.href); u.search = ''; u.hash = q.toString();
    return u.toString();
  }
  function markStale(reason) {
    const root = document.getElementById('results');
    if (!root || root.hidden) return;
    root.classList.add('stale');
    let n = document.getElementById('stale-note');
    if (!n) { n = document.createElement('div'); n.id = 'stale-note'; n.className = 'stale-note'; root.prepend(n); }
    n.innerHTML = `<b>Showing the previous result.</b> The current inputs are not valid: ${esc(reason)}. Fix the highlighted input to recalculate.`;
  }
  function clearStale() {
    const root = document.getElementById('results'); if (!root) return;
    root.classList.remove('stale'); document.getElementById('stale-note')?.remove();
  }
  let labelSeq = 0;
  function associateLabels(root) {
    // Give every input/select/textarea an id and point its label at it (screen readers, click-to-focus).
    root.querySelectorAll('.field').forEach(f => {
      const label = f.querySelector('label'); const ctl = f.querySelector('input, select, textarea');
      if (!label || !ctl) return;
      if (!ctl.id) ctl.id = (ctl.name || 'field') + '-' + (++labelSeq);
      if (!label.htmlFor) label.htmlFor = ctl.id;
      const hint = label.querySelector('.hint');
      if (hint && hint.title && !ctl.getAttribute('aria-describedby')) {
        const hid = ctl.id + '-hint'; hint.id = hid; hint.setAttribute('role', 'note'); hint.setAttribute('aria-label', hint.title); ctl.setAttribute('aria-describedby', hid);
      }
    });
  }

  async function run(cfg) {
    const form = document.getElementById(cfg.form);
    const err = document.getElementById('form-error');
    err.textContent = '';
    const body = cfg.body ? cfg.body(serialise(form), form) : serialise(form);
    form.setAttribute('aria-busy', 'true');
    try {
      const r = await fetch(cfg.endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), credentials: 'omit', cache: 'no-store' });
      const json = await r.json();
      if (!r.ok) { const msg = typeof json.detail === 'string' ? json.detail : (json.detail || []).map(d => `${d.field || d.loc?.slice(-1)[0] || ''}: ${d.message || d.msg}`).join('; '); err.textContent = msg; markStale(msg); return; }
      clearStale();
      window._lastCalc = { calculator: json.calculator, inputs: body, downloadName: cfg.downloadName };
      (cfg.render || render)(json, cfg);
    } catch (e) { err.textContent = 'Could not reach the calculation service. Nothing was saved.'; markStale('the calculation service could not be reached'); }
    finally { form.removeAttribute('aria-busy'); }
  }

  window.initCalc = function (cfg) {
    const form = document.getElementById(cfg.form);
    associateLabels(form);
    prefillFromURL(form, cfg);
    form.addEventListener('submit', (e) => { e.preventDefault(); cfg._explicit = true; run(cfg); });
    let t; form.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => run(cfg), 350); });
    document.getElementById('btn-copy')?.addEventListener('click', (e) => { navigator.clipboard.writeText(document.getElementById('results').dataset.json || ''); e.target.textContent = 'Copied'; setTimeout(() => e.target.textContent = 'Copy JSON', 1500); });
    document.getElementById('btn-print')?.addEventListener('click', () => window.print());
    document.getElementById('btn-link')?.addEventListener('click', (e) => {
      const url = deepLink(form, cfg); navigator.clipboard.writeText(url); history.replaceState(null, '', url);
      e.target.textContent = 'Link copied'; setTimeout(() => e.target.textContent = 'Copy link', 1500);
    });
    document.getElementById('btn-download')?.addEventListener('click', () => {
      const blob = new Blob([document.getElementById('results').dataset.json || '{}'], { type: 'application/json' });
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = (cfg.downloadName || 'oblique-result') + '.json'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    });
    if (cfg.autorun !== false) run(cfg);
  };
  window.fmtMoney = fmt; window.fmtPct = pct; window.escHtml = esc; window.renderResult = render; window.associateLabels = associateLabels;
  document.addEventListener('DOMContentLoaded', () => document.querySelectorAll('form').forEach(f => associateLabels(f)));
})();

/* ---- Remember where the visitor came from (utm_source), for enquiry attribution only ---- */
(function () { try { const u = new URLSearchParams(location.search).get('utm_source'); if (u) sessionStorage.setItem('utm_source', u.slice(0, 80)); } catch (e) {} })();

/* ---- Working paper (PDF) + consent-led enquiry ------------------------------ */
(function () {
  const esc = window.escHtml;
  let config = null, pending = null, lastFocus = null;
  const $ = (id) => document.getElementById(id);

  async function loadConfig() {
    if (config) return config;
    try { config = await (await fetch('/api/v1/leads/config', { cache: 'no-store' })).json(); }
    catch (e) { config = { enabled: false }; }
    return config;
  }
  function download(blob, name) {
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name + '.pdf'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  async function fetchPdf(ctx, token) {
    const r = await fetch('/api/v1/pdf', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'omit',
      body: JSON.stringify({ calculator: ctx.calculator, inputs: ctx.inputs, page_url: location.href, token: token || null }) });
    if (!r.ok) { let d = ''; try { d = (await r.json()).detail; } catch (e) {} throw new Error(typeof d === 'string' ? d : 'The working paper could not be generated.'); }
    download(await r.blob(), (ctx.downloadName || ('oblique-working-paper-' + ctx.calculator)).replace(/_/g, '-'));
  }
  function openModal() {
    const m = $('lead-modal'); if (!m) return;
    lastFocus = document.activeElement; m.hidden = false; document.body.style.overflow = 'hidden';
    $('consent-contact-text').textContent = config.consent_text.contact;
    $('consent-marketing-text').textContent = config.consent_text.marketing;
    $('lead-privacy').textContent = `${config.controller}. ${config.retention} Your inputs go with the enquiry so the adviser has context. Details on the privacy page.`;
    $('lead-error').textContent = ''; $('lead-success').hidden = true; $('lead-form').hidden = false;
    const personalDefault = ['move_to_uae', 'personal_income_tax'].includes(pending.calculator) || (pending.calculator === 'tax_exposure_diagnostic' && (pending.inputs || {}).profile === 'personal');
    const radio = document.querySelector(`#lead-form input[name=profile][value=${personalDefault ? 'personal' : 'business'}]`); if (radio) { radio.checked = true; radio.dispatchEvent(new Event('change', { bubbles: true })); }
    $('lead-title').textContent = pending.serviceTitle ? pending.serviceTitle : (pending.interest === 'expert_review' ? 'Talk to Oblique about this' : 'Your working paper, as a PDF');
    const share = $('lead-form').querySelector('input[name=share_inputs]'); const hasInputs = pending.inputs && Object.keys(pending.inputs).length > 0;
    $('share-inputs-row').hidden = !hasInputs;
    if (pending.interest === 'expert_review') { share.checked = false; share.disabled = false; $('share-inputs-note').textContent = '(optional)'; }
    else { share.checked = true; share.disabled = true; $('share-inputs-note').textContent = '(needed to build the PDF)'; }
    if (pending.audience) { const r2 = document.querySelector(`#lead-form input[name=profile][value=${pending.audience}]`); if (r2) { r2.checked = true; r2.dispatchEvent(new Event('change', { bubbles: true })); } }
    $('lead-submit').textContent = pending.interest === 'expert_review' ? 'Send' : 'Send my working paper';
    $('lead-desc').hidden = !!pending.serviceTitle;
    setTimeout(() => $('lead-name').focus(), 50);
  }
  function closeModal() {
    const m = $('lead-modal'); if (!m || m.hidden) return;
    m.hidden = true; document.body.style.overflow = ''; if (lastFocus) lastFocus.focus();
  }
  window.requestWorkingPaper = async function (ctx) {
    pending = ctx;
    const c = await loadConfig();
    if (!c.enabled) {  // no destination configured: PDFs are simply free; service enquiries go to the contact page
      if (ctx.interest === 'expert_review' || !ctx.inputs || !Object.keys(ctx.inputs).length) { location.href = document.body.dataset.contact || '/'; return; }
      try { await fetchPdf(ctx, null); } catch (e) { alert(e.message); }
      return;
    }
    openModal();
  };
  document.addEventListener('DOMContentLoaded', () => {
    const form = $('lead-form'); if (!form) return;
    $('lead-close').addEventListener('click', closeModal); $('lead-cancel').addEventListener('click', closeModal);
    form.querySelectorAll('input[name=profile]').forEach(r => r.addEventListener('change', () => { const personal = form.profile.value === 'personal'; $('lead-company-field').hidden = personal; $('lead-desc-business').hidden = personal; $('lead-desc-personal').hidden = !personal; }));
    $('lead-modal').addEventListener('click', (e) => { if (e.target === $('lead-modal')) closeModal(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!form.reportValidity()) return;
      const err = $('lead-error'); err.textContent = '';
      const btn = $('lead-submit'); const label = btn.textContent; btn.disabled = true; btn.textContent = 'Preparing your working paper…'; form.setAttribute('aria-busy', 'true');
      const f = new FormData(form);
      const body = { name: f.get('name'), email: f.get('email'), phone: f.get('phone') || '', company: f.get('company') || '', message: f.get('message') || '',
        interest: pending.interest || ({ move_to_uae: 'relocation', tax_exposure_diagnostic: 'diagnostic' }[pending.calculator] || 'working_paper'),
        profile: f.get('profile') || 'business',
        consent_contact: !!f.get('consent_contact'), consent_marketing: !!f.get('consent_marketing'), consent_version: config.consent_version,
        service: pending.service || '',
        context: { calculator: pending.calculator, inputs: (f.get('share_inputs') || pending.interest !== 'expert_review') ? pending.inputs : {}, shared_inputs: !!(f.get('share_inputs') || pending.interest !== 'expert_review'), page_url: location.href.split('#')[0], source: (sessionStorage.getItem('utm_source') || '') }, website: f.get('website') || '' };
      try {
        const r = await fetch('/api/v1/leads', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'omit', body: JSON.stringify(body) });
        const j = await r.json();
        if (!r.ok) { err.textContent = typeof j.detail === 'string' ? j.detail : (j.detail || []).map(d => `${d.field}: ${d.message}`).join('; '); return; }
        if (j.pdf_token) await fetchPdf(pending, j.pdf_token);
        form.hidden = true; const ok = $('lead-success'); ok.hidden = false;
        ok.innerHTML = `${esc(j.message || 'Thank you.')}${j.pdf_token ? ' Your PDF is downloading.' : ''}<br><a href="${esc(j.booking_url || '#')}" target="_blank" rel="noopener">Prefer to pick a time now? Book a free 30-minute call →</a>`;
        setTimeout(closeModal, 9000);
      } catch (ex) { err.textContent = ex.message || 'Something went wrong. Nothing was saved.'; }
      finally { btn.disabled = false; btn.textContent = label; form.removeAttribute('aria-busy'); }
    });
  });
  // Wire every #btn-pdf to the last calculation on the page (set by initCalc) if present.
  document.addEventListener('DOMContentLoaded', () => {
    const b = $('btn-pdf'); if (!b || b.dataset.wired) return;
    b.dataset.wired = '1';
    b.addEventListener('click', () => { if (window._lastCalc) window.requestWorkingPaper(window._lastCalc); });
  });
})();

/* ---- "Get precise figures" CTAs open the enquiry dialog when a destination is configured ---- */
(function () {
  document.addEventListener('DOMContentLoaded', async () => {
    const ctas = [...document.querySelectorAll('.results .cta-row a.btn-primary')];
    if (!ctas.length) return;
    let cfg; try { cfg = await (await fetch('/api/v1/leads/config', { cache: 'no-store' })).json(); } catch (e) { return; }
    if (!cfg.enabled) return;
    ctas.forEach(a => a.addEventListener('click', (e) => {
      if (!window._lastCalc) return;           // nothing calculated yet: fall through to the contact page
      e.preventDefault();
      window.requestWorkingPaper(Object.assign({}, window._lastCalc, { interest: 'expert_review' }));
    }));
    document.querySelectorAll('form .field').forEach(() => {});
  });
})();

/* ---- Game leaderboard embed: only where play.obliqueconsult.com allows framing ---- */
document.addEventListener('DOMContentLoaded', () => {
  const slot = document.getElementById('leaderboard-slot'); if (!slot) return;
  if (/(^|\.)obliqueconsult\.com$/.test(location.hostname)) {
    const f = document.createElement('iframe'); f.src = slot.dataset.src + (document.documentElement.getAttribute('data-theme') === 'light' ? '?theme=light' : ''); f.title = 'Monthly leaderboard'; f.loading = 'lazy'; f.width = '320'; f.height = '340'; f.style.border = '0'; f.style.background = 'transparent';
    slot.appendChild(f);
  } else {
    slot.innerHTML = `<a class="card" href="${slot.dataset.src.replace('/embed/leaderboard', '/?utm_source=tax-tools')}"><h3 style="margin:0">Monthly leaderboard</h3><p class="muted" style="margin:6px 0 0">Shown here once the tools run on tax.obliqueconsult.com. Open the game →</p></a>`;
  }
});

/* ---- Next steps (specific services) and the confidence panel ---------------- */
(function () {
  const esc = window.escHtml;
  window.renderNextSteps = function (steps, ctx) {
    const box = document.getElementById('next-steps'); if (!box) return;
    if (!steps || !steps.length) { box.hidden = true; return; }
    box.hidden = false;
    box.innerHTML = `<h3>Next step</h3>` + steps.map(s =>
      `<div class="svc-row"><div><b>${esc(s.title)}</b><span>${esc(s.for)}</span></div>
       <button class="btn btn-ghost btn-sm" type="button" data-service="${esc(s.slug)}" data-title="${esc(s.title)}" data-audience="${esc(s.audience)}">Free call →</button></div>`).join('') +
      `<p class="small muted" style="margin:8px 0 0">The calculation stays free. The review is the expert's judgement: <a href="/services">what each one includes</a>.</p>`;
  };
  window.renderConfidence = function (c) {
    const box = document.getElementById('confidence'); if (!box || !c) return;
    const labels = { verified: 'Verified', verified_secondary: 'Verified against practitioner sources', pending_verification: 'Pending verification', draft_law: 'Includes draft law' };
    const r = c.rules, t = c.calculation, f = c.fit;
    box.innerHTML = `
      <div><b>The rules</b><span class="${r.status === 'verified' ? 'ok' : 'warn'}">${esc(labels[r.status] || r.status)}</span><br>${esc(r.reviewed_by || '')}${r.reviewed_on ? ' · ' + esc(r.reviewed_on) : ''}</div>
      <div><b>The calculation</b><span class="ok">Deterministic, tested</span><br>${t.checks} automated checks for this calculator, ${t.suite_total} in total</div>
      <div><b>Your facts</b><span class="${f.confirmed ? 'ok' : 'warn'}">${f.confirmed ? 'Confirmed to fit' : 'Not yet confirmed'}</span><br>${f.confirmed ? 'Scope confirmed by you. Still an estimate, not advice.' : 'Answer the scope questions, or ask us.'}</div>`;
  };
  // Any button with data-service opens the enquiry dialog for that service.
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-service]'); if (!b) return;
    const last = window._lastCalc || {};
    window.requestWorkingPaper({ calculator: last.calculator || 'tax_exposure_diagnostic', inputs: last.inputs || {}, interest: 'expert_review',
      service: b.dataset.service, serviceTitle: b.dataset.title, audience: b.dataset.audience, downloadName: last.downloadName });
  });
})();

/* ---- Light / dark toggle (preference kept in this browser only) ---- */
(function () {
  const root = document.documentElement;
  function apply(theme, persist) {
    root.setAttribute('data-theme', theme);
    const b = document.getElementById('theme-toggle');
    if (b) { b.textContent = theme === 'light' ? '☀' : '☾'; b.setAttribute('aria-label', theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'); }
    const f = document.querySelector('#leaderboard-slot iframe');
    if (f) { const base = f.src.split('?')[0]; f.src = theme === 'light' ? base + '?theme=light' : base; }
    if (persist) { try { localStorage.setItem('theme', theme); } catch (e) {} }
  }
  document.addEventListener('DOMContentLoaded', () => {
    apply(root.getAttribute('data-theme') || 'dark', false);
    document.getElementById('theme-toggle')?.addEventListener('click', () => apply(root.getAttribute('data-theme') === 'light' ? 'dark' : 'light', true));
    try { window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', (e) => { if (!localStorage.getItem('theme')) apply(e.matches ? 'light' : 'dark', false); }); } catch (e) {}
  });
})();
