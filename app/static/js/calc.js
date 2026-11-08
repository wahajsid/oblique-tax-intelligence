/* Shared calculator runtime: serialise the form, POST to the API, render the
   result shell (tiles, review banner, flags, trace, rules). Pages declare a config
   via initCalc(). Accessibility: aria-busy on the form while a request runs,
   aria-live results region, focus moved to results on explicit submit. */
(function () {
  const fmt = (n, cur, dec) => (n === null || n === undefined || n === '') ? '—'
    : (cur ? cur + ' ' : '') + Number(n).toLocaleString('en', { minimumFractionDigits: dec ?? (Number.isInteger(n) ? 0 : 2), maximumFractionDigits: dec ?? 2 });
  const pct = (x) => (x === null || x === undefined) ? '—' : (x * 100).toFixed(2) + '%';
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const labels = { verified: 'Verified', verified_secondary: 'Verified (secondary sources)', pending_verification: 'Pending verification', draft_law: 'Includes draft law' };

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
    badge.textContent = labels[res.review_status] || res.review_status;

    const banner = document.getElementById('review-banner');
    if (banner) {
      banner.hidden = !review;
      banner.innerHTML = review ? `<b>Review required before relying on this figure.</b><ul>${(res.review_reasons || []).map(r => `<li>${esc(r)}</li>`).join('')}</ul>
        <span class="small">The figure below is shown greyed out so you can see the order of magnitude. Confirm the scope in the form, or <a href="${esc(cfg.contactUrl || '#')}" target="_blank" rel="noopener">ask Oblique to confirm it for you</a>.</span>` : '';
    }
    const outcome = document.getElementById('outcome-label');
    if (outcome) outcome.textContent = review ? 'Review required' : 'Illustrative estimate';

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

  function prefillFromURL(form) {
    const q = new URLSearchParams(location.search);
    for (const el of form.elements) {
      if (!el.name || !q.has(el.name)) continue;
      const v = q.get(el.name);
      if (el.type === 'checkbox') el.checked = (v === '1' || v === 'true');
      else el.value = v;
    }
  }
  function deepLink(form) {
    const q = new URLSearchParams();
    for (const el of form.elements) {
      if (!el.name || el.type === 'hidden') continue;
      if (el.type === 'checkbox') { if (el.checked) q.set(el.name, '1'); }
      else if (el.value !== '' && el.value !== (el.defaultValue ?? '')) q.set(el.name, el.value);
    }
    const u = new URL(location.href); u.search = q.toString();
    return u.toString();
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
      if (!r.ok) { err.textContent = typeof json.detail === 'string' ? json.detail : (json.detail || []).map(d => `${d.field || d.loc?.slice(-1)[0] || ''}: ${d.message || d.msg}`).join('; '); return; }
      (cfg.render || render)(json, cfg);
    } catch (e) { err.textContent = 'Could not reach the calculation service. Nothing was saved.'; }
    finally { form.removeAttribute('aria-busy'); }
  }

  window.initCalc = function (cfg) {
    const form = document.getElementById(cfg.form);
    prefillFromURL(form);
    form.addEventListener('submit', (e) => { e.preventDefault(); cfg._explicit = true; run(cfg); });
    let t; form.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => run(cfg), 350); });
    document.getElementById('btn-copy')?.addEventListener('click', (e) => { navigator.clipboard.writeText(document.getElementById('results').dataset.json || ''); e.target.textContent = 'Copied'; setTimeout(() => e.target.textContent = 'Copy JSON', 1500); });
    document.getElementById('btn-print')?.addEventListener('click', () => window.print());
    document.getElementById('btn-link')?.addEventListener('click', (e) => {
      const url = deepLink(form); navigator.clipboard.writeText(url); history.replaceState(null, '', url);
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
