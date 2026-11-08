"""Branded PDF working papers.

The server RECOMPUTES the result from the submitted inputs before rendering, so a
PDF can never carry figures that were edited in the browser. One renderer handles
every calculator by reading the common result shape (outputs, trace, flags, rules);
the relocation comparison, GCC comparison and diagnostic have small bespoke sections.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from app.engine import diagnostic, gcc_compare, ksa_wht, ksa_zakat, personal_tax, relocation, uae_ct, vat
from app.engine.core import DISCLAIMER

STATIC = Path(__file__).resolve().parent / "static" / "img"
INK = colors.HexColor("#0b0d12")
INK2 = colors.HexColor("#44546a")
MUTED = colors.HexColor("#6b7a90")
LINE = colors.HexColor("#d9dee6")
ACCENT = colors.HexColor("#0f766e")
WARN = colors.HexColor("#8a5a00")
WARN_BG = colors.HexColor("#fff7e0")
DANGER_BG = colors.HexColor("#fff1ef")
INFO_BG = colors.HexColor("#eef6fb")
SUB_BG = colors.HexColor("#f4f6f9")

# calculator key -> (input model, compute fn returning a dict)
REGISTRY: dict[str, tuple[Any, Callable[[Any], dict[str, Any]], str]] = {
    "uae_corporate_tax": (uae_ct.UAECorporateTaxInput, lambda i: uae_ct.calculate(i).as_dict(), "UAE Corporate Tax"),
    "vat": (vat.VATInput, lambda i: vat.calculate(i).as_dict(), "VAT"),
    "ksa_zakat_income_tax": (ksa_zakat.KSAZakatInput, lambda i: ksa_zakat.calculate(i).as_dict(), "KSA Zakat and Income Tax"),
    "ksa_withholding_tax": (ksa_wht.KSAWHTInput, lambda i: ksa_wht.calculate(i).as_dict(), "KSA Withholding Tax"),
    "personal_income_tax": (personal_tax.PersonalTaxInput, lambda i: personal_tax.calculate(i).as_dict(), "Personal income tax"),
    "move_to_uae": (relocation.RelocationInput, relocation.compare, "Move to the UAE comparison"),
    "gcc_compare": (gcc_compare.GCCScenario, gcc_compare.compare, "GCC tax comparison"),
    "tax_exposure_diagnostic": (diagnostic.DiagnosticInput, diagnostic.run, "Tax exposure diagnostic"),
}


def compute(calculator: str, inputs: dict[str, Any]) -> dict[str, Any]:
    if calculator not in REGISTRY:
        raise ValueError(f"Unknown calculator '{calculator}'")
    model, fn, _ = REGISTRY[calculator]
    return fn(model(**inputs))


# ---------------------------------------------------------------- styles -------
_ss = getSampleStyleSheet()
S = {
    "h1": ParagraphStyle("h1", parent=_ss["Title"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=INK, alignment=0, spaceAfter=2),
    "h2": ParagraphStyle("h2", parent=_ss["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=INK, spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("body", parent=_ss["BodyText"], fontName="Helvetica", fontSize=9, leading=12, textColor=INK),
    "small": ParagraphStyle("small", parent=_ss["BodyText"], fontName="Helvetica", fontSize=7.5, leading=10, textColor=MUTED),
    "cell": ParagraphStyle("cell", parent=_ss["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=INK),
    "cellb": ParagraphStyle("cellb", parent=_ss["BodyText"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=INK),
    "cellm": ParagraphStyle("cellm", parent=_ss["BodyText"], fontName="Helvetica", fontSize=7, leading=9, textColor=MUTED),
    "num": ParagraphStyle("num", parent=_ss["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11, textColor=INK, alignment=TA_RIGHT),
    "numb": ParagraphStyle("numb", parent=_ss["BodyText"], fontName="Helvetica-Bold", fontSize=8.5, leading=11, textColor=INK, alignment=TA_RIGHT),
    "eyebrow": ParagraphStyle("eyebrow", parent=_ss["BodyText"], fontName="Helvetica-Bold", fontSize=7.5, leading=10, textColor=ACCENT),
    "big": ParagraphStyle("big", parent=_ss["BodyText"], fontName="Helvetica-Bold", fontSize=16, leading=19, textColor=INK),
    "k": ParagraphStyle("k", parent=_ss["BodyText"], fontName="Helvetica", fontSize=7, leading=9, textColor=MUTED),
}


def _esc(s: Any) -> str:
    return str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _money(v: Any, cur: str = "", dec: int = 2) -> str:
    if v is None or v == "":
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return _esc(v)
    s = f"{f:,.{dec}f}"
    return f"{cur} {s}".strip()


def _pct(v: Any) -> str:
    return "—" if v is None else f"{float(v) * 100:.2f}%"


def _logo():
    try:
        from svglib.svglib import svg2rlg
        d = svg2rlg(str(STATIC / "logo-mark.svg"))
        scale = (8 * mm) / d.height
        d.width, d.height = d.width * scale, d.height * scale
        d.scale(scale, scale)
        return d
    except Exception:  # pragma: no cover - fallback if svglib missing
        return Paragraph("<b>ob/co</b>", S["h1"])


def _tiles(items: list[tuple[str, str]]) -> Table:
    cells = [[Paragraph(_esc(k), S["k"]), Paragraph(_esc(v), S["big"])] for k, v in items]
    rows, row = [], []
    for c in cells:
        row.append([c[0], c[1]])
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        row += [""] * (3 - len(row)); rows.append(row)
    t = Table(rows, colWidths=[57 * mm] * 3)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SUB_BG), ("BOX", (0, 0), (-1, -1), 0.25, LINE),
                           ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.white), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def _kv_table(rows: list[tuple[str, str]], widths=(60 * mm, 111 * mm)) -> Table:
    t = Table([[Paragraph(_esc(k), S["cellm"]), Paragraph(_esc(v), S["cell"])] for k, v in rows], colWidths=list(widths))
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def _trace_table(trace: list[dict[str, Any]], cur: str, dec: int) -> Table:
    data = [[Paragraph("Step", S["cellb"]), Paragraph("Rule", S["cellb"]), Paragraph("Amount", S["numb"])]]
    styles = [("LINEBELOW", (0, 0), (-1, 0), 0.6, INK), ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    for i, s in enumerate(trace, start=1):
        label = _esc(s.get("label"))
        extra = " ".join(x for x in [s.get("formula"), s.get("note")] if x)
        if extra:
            label += f"<br/><font size='7' color='#6b7a90'>{_esc(extra)}</font>"
        amt = s.get("amount")
        kind = s.get("kind", "")
        if amt is None:
            amt_s = ""
        elif kind == "info" and isinstance(amt, (int, float)) and abs(amt) <= 1 and not float(amt).is_integer():
            amt_s = _pct(amt)
        else:
            amt_s = _money(amt, "", dec)
        bold = kind in ("subtotal", "tax")
        data.append([Paragraph(label, S["cellb"] if bold else S["cell"]), Paragraph(_esc(s.get("rule_id", "")), S["cellm"]), Paragraph(amt_s, S["numb"] if bold else S["num"])])
        if kind == "subtotal":
            styles.append(("BACKGROUND", (0, i), (-1, i), SUB_BG))
    t = Table(data, colWidths=[104 * mm, 37 * mm, 30 * mm], repeatRows=1)
    t.setStyle(TableStyle(styles))
    return t


def _flags(flags: list[dict[str, Any]]) -> list[Any]:
    out: list[Any] = []
    for f in flags:
        bg = DANGER_BG if f.get("severity") == "high" else WARN_BG if f.get("severity") == "attention" else INFO_BG
        txt = f"<b>{_esc(f.get('title'))}</b><br/>{_esc(f.get('detail'))}"
        if f.get("advisory_hook"):
            txt += f"<br/><font color='#0f766e'>{_esc(f['advisory_hook'])}</font>"
        t = Table([[Paragraph(txt, S["cell"])]], colWidths=[171 * mm])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        out += [t, Spacer(1, 3)]
    return out


def _rules(rules: list[dict[str, Any]]) -> list[Any]:
    labels = {"verified": "Verified", "verified_secondary": "Verified (secondary sources)", "pending_verification": "Pending verification", "draft_law": "Draft law"}
    rows = []
    for r in rules:
        txt = f"<b>{_esc(r.get('rule_id'))}</b> — {_esc(r.get('description'))}<br/><font size='7' color='#6b7a90'>Status: {labels.get(r.get('review_status'), r.get('review_status'))} · Source: {_esc(r.get('source_reference'))}"
        if r.get("effective_from"):
            txt += f" · Effective {_esc(r['effective_from'])}" + (f" to {_esc(r['effective_to'])}" if r.get("effective_to") else "")
        if r.get("verification_note"):
            txt += f"<br/><i>{_esc(r['verification_note'])}</i>"
        txt += "</font>"
        rows.append([Paragraph(txt, S["cell"])])
    if not rows:
        return []
    t = Table(rows, colWidths=[171 * mm])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return [t]


def _header_footer(title: str, meta: str):
    def draw(canvas, doc):
        canvas.saveState()
        w, h = A4
        logo = _logo()
        try:
            from reportlab.graphics import renderPDF
            renderPDF.draw(logo, canvas, 18 * mm, h - 16 * mm)
        except Exception:
            pass
        canvas.setFont("Helvetica-Bold", 8); canvas.setFillColor(INK)
        canvas.drawString(45 * mm, h - 11 * mm, "Tax Intelligence · Working paper")
        canvas.setFont("Helvetica", 7.5); canvas.setFillColor(MUTED)
        canvas.drawString(45 * mm, h - 15 * mm, meta)
        # Oblique motif: thin rules at 11 degrees in the top-right corner, matching the website hero.
        if doc.page == 1:
            import math
            dx = math.tan(math.radians(11)) * 24 * mm
            canvas.setStrokeColor(LINE); canvas.setLineWidth(0.4)
            for i in range(7):
                x = w - 10 * mm - i * 7 * mm
                canvas.line(x, h, x - dx, h - 24 * mm)
            canvas.setLineWidth(1)
        canvas.setStrokeColor(LINE); canvas.line(18 * mm, h - 19 * mm, w - 18 * mm, h - 19 * mm)
        canvas.setFont("Helvetica", 7); canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, "Desktop estimate, not tax advice. For precise figures for your circumstances, contact Oblique Consult · obliqueconsult.com")
        canvas.drawRightString(w - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()
    return draw


# ------------------------------------------------------------- renderers -------
def _common_sections(res: dict[str, Any], headline: list[tuple[str, str]], story: list[Any]) -> None:
    cur, dec = res.get("currency", ""), res.get("currency_decimals", 2)
    if res.get("outcome") == "REVIEW_REQUIRED":
        t = Table([[Paragraph("<b>Review required before relying on this figure.</b><br/>" + "<br/>".join("• " + _esc(r) for r in res.get("review_reasons", [])), S["cell"])]], colWidths=[171 * mm])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), WARN_BG), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LINEBEFORE", (0, 0), (0, -1), 3, WARN)]))
        story += [t, Spacer(1, 6)]
    story += [_tiles(headline), Spacer(1, 8)]
    if res.get("flags"):
        story += [Paragraph("Points for review", S["h2"])] + _flags([f for f in res["flags"] if f.get("code") != "review_required"])
    story += [Paragraph("Working paper", S["h2"]), _trace_table(res.get("trace", []), cur, dec)]
    inputs = [(k.replace("_", " ").capitalize(), str(v)) for k, v in (res.get("inputs") or {}).items() if v not in (None, "", 0, False, [], {})]
    if inputs:
        story += [Paragraph("Inputs as entered", S["h2"]), _kv_table(inputs)]
    story += [Paragraph("Rules applied, review status and sources", S["h2"])] + _rules(res.get("rules", []))
    if res.get("assumptions"):
        story += [Paragraph("Assumptions", S["h2"]), Paragraph(" ".join(_esc(a) for a in res["assumptions"]), S["small"])]


def _headline_for(calc: str, o: dict[str, Any], cur: str, dec: int) -> list[tuple[str, str]]:
    if calc == "uae_corporate_tax":
        return [("Corporate Tax payable", _money(o.get("corporate_tax_payable"), cur, dec)), ("Taxable income", _money(o.get("taxable_income"), cur, dec)),
                ("Effective rate on accounting profit", _pct(o.get("effective_tax_rate_on_accounting_profit"))), ("Regime", str(o.get("regime", "")).replace("_", " ")),
                ("Post-tax profit", _money(o.get("post_tax_profit"), cur, dec)), ("Losses carried forward", _money(o.get("losses_carried_forward"), cur, dec))]
    if calc == "vat":
        if "net_vat_payable" in o:
            return [("Net VAT " + o.get("position", ""), _money(abs(float(o["net_vat_payable"])), cur, dec)), ("Output VAT", _money(o.get("output_vat"), cur, dec)),
                    ("Recoverable input VAT", _money(o.get("recoverable_input_vat"), cur, dec)), ("Recovery ratio", _pct(o.get("recovery_ratio")))]
        return [("VAT", _money(o.get("vat"), cur, dec)), ("Net", _money(o.get("net"), cur, dec)), ("Gross", _money(o.get("gross"), cur, dec))]
    if calc == "ksa_zakat_income_tax":
        return [("Total zakat and tax", _money(o.get("total_due"), cur, dec)), ("Zakat base", _money(o.get("zakat_base"), cur, dec)), ("Zakat due", _money(o.get("zakat_due"), cur, dec)),
                ("Income tax due", _money(o.get("income_tax_due"), cur, dec)), ("Adjusted net profit", _money(o.get("adjusted_net_profit"), cur, dec)), ("Effective rate on book profit", _pct(o.get("effective_rate_on_book_profit")))]
    if calc == "ksa_withholding_tax":
        return [("Total withholding tax", _money(o.get("total_wht"), cur, dec)), ("Total cost to payer", _money(o.get("total_cost_to_payer"), cur, dec))] + \
               [(f"{l['label']} @ {_pct(l['applied_rate'])}", _money(l["wht"], cur, dec)) for l in o.get("lines", [])][:4]
    if calc == "personal_income_tax":
        return [("Net take-home per year", _money(o.get("net_income"), cur, dec)), ("Income tax", _money(o.get("income_tax"), cur, dec)), ("Mandatory contributions", _money(o.get("total_contributions"), cur, dec)),
                ("Effective rate", _pct(o.get("effective_rate"))), ("Marginal income tax rate", _pct(o.get("marginal_income_tax_rate"))), ("Net per month", _money(o.get("monthly_net"), cur, dec))]
    return [(k.replace("_", " ").capitalize(), str(v)) for k, v in list(o.items())[:6] if not isinstance(v, (list, dict))]


def render_pdf(calculator: str, inputs: dict[str, Any], *, source_url: str = "", prepared_for: str | None = None) -> tuple[bytes, dict[str, Any]]:
    """Recompute and render. Returns (pdf_bytes, result_dict)."""
    if calculator not in REGISTRY:
        raise ValueError(f"Unknown calculator '{calculator}'")
    _, _, title = REGISTRY[calculator]
    res = compute(calculator, inputs)
    now = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")
    ruleset = res.get("ruleset_version") or res.get("origin", {}).get("tax_year", "")
    meta = f"Generated {now} · Ruleset {ruleset} · Deterministic rules engine" + (f" · Prepared for {prepared_for}" if prepared_for else "")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=24 * mm, bottomMargin=18 * mm,
                            title=f"Oblique Tax Intelligence · {title}", author="Oblique Consult", subject="Working paper (desktop estimate)")
    story: list[Any] = [Paragraph("OBLIQUE TAX INTELLIGENCE", S["eyebrow"]), Paragraph(_esc(title), S["h1"])]

    if calculator == "move_to_uae":
        o, u, c = res["origin"], res["uae"], res["comparison"]
        story.append(Paragraph(f"{_esc(o['name'])} to the United Arab Emirates · {_esc(o['tax_year'])}", S["body"]))
        gain = float(c["annual_net_gain_aed"])
        story += [Spacer(1, 6), _tiles([("Estimated annual net gain from moving" if gain >= 0 else "Estimated annual net cost of moving", _money(abs(gain), "AED")),
                                        ("Tax saved per year", _money(c["annual_tax_saved_aed"], "AED")), ("First year after one-off costs", _money(c["first_year_gain_aed"], "AED")),
                                        (f"{c['years']}-year total (undiscounted)", _money(c["horizon_gain_aed"], "AED")), ("Payback on one-off costs", f"{c['payback_months']} months" if c["payback_months"] is not None else "—"),
                                        ("FX used (AED per " + o["currency"] + ")", f"{c['fx_aed_per_unit']} ({'your rate' if c['fx_overridden'] else 'indicative ' + c['fx_as_of']})")]), Spacer(1, 8)]
        side = [[Paragraph(f"<b>{_esc(o['name'])} today</b>", S["cellb"]), Paragraph("<b>United Arab Emirates</b>", S["cellb"])],
                [Paragraph(f"Gross income {_money(o['gross_local'], o['currency'])}<br/>Income tax + contributions − {_money(o['tax_local'], o['currency'])}<br/>Effective rate {_pct(o['effective_rate'])} · marginal {_pct(o['marginal_income_tax_rate'])}<br/><b>Net per year {_money(o['net_local'], o['currency'])}</b> ({_money(o['net_aed'], 'AED')})<br/>Net per month {_money(o['monthly_net_local'], o['currency'])}", S["cell"]),
                 Paragraph(f"Gross package {_money(u['gross_aed'], 'AED')}<br/>{'Residual US tax after FEIE' if u.get('residual_us') else 'Personal income tax'} − {_money(u['tax_aed'], 'AED')}<br/>Extra annual living costs − {_money(u['additional_costs_aed'], 'AED')}<br/><b>Net per year {_money(u['net_aed'], 'AED')}</b><br/>Net per month {_money(u['monthly_net_aed'], 'AED')}<br/><font size='7' color='#6b7a90'>{_esc(' '.join(u['notes']))}</font>", S["cell"])]]
        t = Table(side, colWidths=[85.5 * mm, 85.5 * mm])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.25, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.25, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, 0), SUB_BG), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story += [t, Paragraph("What to settle before the saving is real", S["h2"])] + _flags(res["flags"])
        story += [Paragraph(f"Working paper: {_esc(o['name'])} tax computation", S["h2"]), _trace_table(o["result"]["trace"], o["currency"], 2)]
        if u.get("residual_us"):
            story += [Paragraph("Working paper: residual US tax after moving", S["h2"]), _trace_table(u["residual_us"]["trace"], "USD", 2)]
        story += [Paragraph("Rules applied, review status and sources", S["h2"])] + _rules(res["rules"])
        story += [Paragraph("Assumptions", S["h2"]), Paragraph(" ".join(_esc(a) for a in res["assumptions"]), S["small"])]
    elif calculator == "gcc_compare":
        s = res["scenario"]
        story.append(Paragraph(f"Scenario: profit {_money(s['taxable_profit'], res['currency'])}, revenue {_money(s['revenue'], res['currency'])}, non-GCC ownership {s['foreign_ownership_pct']}%", S["body"]))
        data = [[Paragraph(h, S["cellb"]) for h in ["Jurisdiction", "CIT / income tax", "Zakat", "WHT", "DMTT top-up", "Total", "Effective", "VAT"]]]
        for r in res["rows"]:
            data.append([Paragraph(_esc(r["name"]), S["cell"]), Paragraph(_money(r["corporate_tax"]), S["num"]), Paragraph(_money(r["zakat"]), S["num"]), Paragraph(_money(r["withholding_tax"]), S["num"]),
                         Paragraph(_money(r["dmtt_top_up"]) if r["dmtt_in_scope"] else "n/a", S["num"]), Paragraph(_money(r["total_direct_tax"]), S["numb"]), Paragraph(_pct(r["effective_rate_on_profit"]), S["num"]),
                         Paragraph(f"{r['vat_rate']*100:.0f}%" if r["vat_implemented"] else "None", S["cell"])])
        t = Table(data, colWidths=[36 * mm, 22 * mm, 20 * mm, 20 * mm, 22 * mm, 22 * mm, 16 * mm, 13 * mm], repeatRows=1)
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, 0), 0.6, INK), ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story += [Spacer(1, 6), t, Spacer(1, 6), Paragraph(_esc(res["caveat"]), S["small"])]
        for r in res["rows"]:
            story += [Paragraph(_esc(r["name"]) + f" · {_esc(r['cit_scope'])}", S["h2"]), _trace_table(r["trace"], "", 2)]
    elif calculator == "tax_exposure_diagnostic":
        story += [Paragraph(f"Profile: {res['profile']} · Priority: <b>{_esc(res['priority'])}</b> · {res['open_items']} open items", S["body"]), Spacer(1, 6)]
        for i, a in enumerate(res["actions"], start=1):
            story += [KeepTogether([Paragraph(f"{i}. {_esc(a['label'])} <font size='7' color='#6b7a90'>({_esc(a['answer'])})</font>", S["cellb"]), Paragraph(_esc(a["action"]), S["cell"]), Paragraph(_esc(a["advisory_hook"]), S["small"]), Spacer(1, 4)])]
        story += [Paragraph(_esc(res["methodology"] + " " + " ".join(res["warnings"])), S["small"])]
    else:
        o = res.get("outputs", {})
        cur, dec = res.get("currency", ""), res.get("currency_decimals", 2)
        sub = f"{_esc(res.get('jurisdiction', ''))} · ruleset {_esc(ruleset)}"
        if calculator == "personal_income_tax":
            sub = f"{_esc(o.get('country_name'))} · {_esc(o.get('tax_year'))}"
        story += [Paragraph(sub, S["body"]), Spacer(1, 6)]
        _common_sections(res, _headline_for(calculator, o, cur, dec), story)

    story += [Spacer(1, 10), Paragraph("Desktop calculator", S["h2"]), Paragraph(_esc(DISCLAIMER), S["small"]),
              Paragraph("For a reviewed position based on your facts, contact Oblique Consult: obliqueconsult.com · info@obliqueconsult.com · +971 50 687 3135", S["small"])]
    if source_url:
        story.append(Paragraph(f"Reproduce this calculation: {_esc(source_url)}", S["small"]))
    hf = _header_footer(title, meta)
    doc.build(story, onFirstPage=hf, onLaterPages=hf)
    return buf.getvalue(), res
