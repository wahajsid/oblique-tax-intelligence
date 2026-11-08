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
  function associateLabels(root) {
    // Give every input/select/textarea an id and point its label at it (screen readers, click-to-focus).
    let i = 0;
    root.querySelectorAll('.field').forEach(f => {
      const label = f.querySelector('label'); const ctl = f.querySelector('input, select, textarea');
      if (!label || !ctl) return;
      if (!ctl.id) ctl.id = (ctl.name || 'field') + '-' + (++i);
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
  window.fmtMoney = fmt; window.fmtPct = pct; window.escHtml = esc; window.renderResult = render;
})();

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
    $('lead-title').textContent = pending.interest === 'expert_review' ? 'Talk to Oblique about this' : 'Your working paper, as a PDF';
    $('lead-submit').textContent = pending.interest === 'expert_review' ? 'Send' : 'Send my working paper';
    setTimeout(() => $('lead-name').focus(), 50);
  }
  function closeModal() {
    const m = $('lead-modal'); if (!m || m.hidden) return;
    m.hidden = true; document.body.style.overflow = ''; if (lastFocus) lastFocus.focus();
  }
  window.requestWorkingPaper = async function (ctx) {
    pending = ctx;
    const c = await loadConfig();
    if (!c.enabled) {  // no destination configured: the PDF is simply free
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
        context: { calculator: pending.calculator, inputs: pending.inputs, page_url: location.href }, website: f.get('website') || '' };
      try {
        const r = await fetch('/api/v1/leads', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'omit', body: JSON.stringify(body) });
        const j = await r.json();
        if (!r.ok) { err.textContent = typeof j.detail === 'string' ? j.detail : (j.detail || []).map(d => `${d.field}: ${d.message}`).join('; '); return; }
        await fetchPdf(pending, j.pdf_token);
        form.hidden = true; const ok = $('lead-success'); ok.hidden = false; ok.textContent = (j.message || 'Thank you.') + ' Your PDF is downloading.';
        setTimeout(closeModal, 4000);
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
