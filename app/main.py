"""Oblique Tax Intelligence web application.

Run locally:  uvicorn app.main:app --reload
API docs:     /docs (Swagger) and /redoc

Privacy and security posture (ported from the V4 review):
- No cookies, no storage, no analytics, no third-party scripts or fonts (fonts are self-hosted).
- Strict CSP and defensive headers on every response; API responses are no-store.
- JSON-only POSTs, 64 KB body cap, same-origin check on browser POSTs, unknown fields rejected.
- Validation errors never echo the submitted values.
- SITE_INDEXABLE=false (default) adds noindex until the rules carry expert sign-off.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import __version__
from app.api.routes import router as api_router
from app import journeys, services
from app.engine import diagnostic, gcc_compare, ksa_wht, personal_tax
from app.engine.core import load_rules

BASE = Path(__file__).resolve().parent
INDEXABLE = os.environ.get("SITE_INDEXABLE", "false").lower() in ("1", "true", "yes")
MAX_BODY = 64 * 1024

app = FastAPI(
    title="Oblique Tax Intelligence API",
    version=__version__,
    description=("Deterministic GCC business-tax and relocation calculations with a full working-paper trace. "
                 "Desktop estimates only; not tax advice. Nothing is persisted."),
    contact={"name": "Oblique Consult", "url": "https://www.obliqueconsult.com/"},
)
app.include_router(api_router)
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "font-src 'self'; connect-src 'self'; frame-src https://play.obliqueconsult.com; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
# 'unsafe-inline' is needed for the small per-page <script> blocks and Swagger UI; move them to files before production.


@app.middleware("http")
async def safety(request: Request, call_next):
    if request.method == "POST":
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > MAX_BODY:
            return JSONResponse({"detail": "Request too large."}, status_code=413)
        if not request.headers.get("content-type", "").startswith("application/json"):
            return JSONResponse({"detail": "JSON requests only."}, status_code=415)
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Cross-origin requests are disabled."}, status_code=403)
    response = await call_next(request)
    response.headers.update({
        "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
        "Content-Security-Policy": CSP,
    })
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    if not INDEXABLE:
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    # Report which fields failed and why, but never echo the submitted values.
    detail = [{"field": ".".join(str(p) for p in e.get("loc", []) if p != "body"), "message": e.get("msg", "invalid")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": detail})


SITE = {"name": "Oblique Tax Intelligence", "company": "Oblique Consult", "tagline": "Tax clarity. In seconds.",
        "company_url": "https://www.obliqueconsult.com/", "contact_url": "https://www.obliqueconsult.com/contact-us",
        "game_url": "https://play.obliqueconsult.com", "game_utm": "?utm_source=tax-tools",
        "booking_url": "https://calendly.com/alina-obliqueconsult/30min",
        "version": __version__, "indexable": INDEXABLE,
        "rules_versions": {"AE": load_rules("ae")["ruleset_version"], "SA": load_rules("sa")["ruleset_version"],
                           "GCC": gcc_compare.profiles()["ruleset_version"], "Personal": personal_tax.rules()["ruleset_version"]}}

MODULES = [
    {"slug": "uae/corporate-tax", "title": "UAE Corporate Tax", "audience": "CFO, finance manager, business owner",
     "blurb": "From accounting profit to tax due. Reliefs, Free Zone status, losses, Pillar Two screen.", "priority": "P0", "jur": "AE"},
    {"slug": "vat?j=AE", "title": "UAE VAT", "audience": "Finance, tax, operations",
     "blurb": "Add it, strip it, or run a full return with reverse charge and partial exemption.", "priority": "P0", "jur": "AE"},
    {"slug": "ksa/zakat-income-tax", "title": "KSA Zakat & Income Tax", "audience": "CFO, tax director",
     "blurb": "The zakat base under the 2024 Regulations, split between zakat and 20% income tax by ownership.", "priority": "P0", "jur": "SA"},
    {"slug": "ksa/withholding-tax", "title": "KSA VAT & Withholding Tax", "audience": "Tax, procurement, treasury",
     "blurb": "Withholding on payments abroad, by category, with treaty rates and gross-up.", "priority": "P0", "jur": "SA"},
    {"slug": "gcc/compare", "title": "GCC Tax Comparison", "audience": "Regional CFO, MNC",
     "blurb": "One operation, six countries. Scope and Pillar Two shown separately, not blended.", "priority": "P0", "jur": "GCC"},
    {"slug": "move", "title": "Move to the UAE", "audience": "Founders, executives, expatriates",
     "blurb": "Your tax at home against the UAE. Eight countries to move from.", "priority": "P0", "jur": "Relocation"},
    {"slug": "diagnose", "title": "Tax Exposure Diagnostic", "audience": "Anyone unsure where to start",
     "blurb": "Ten questions. One ordered action list.", "priority": "P0", "jur": "GCC"},
    {"slug": "uae/corporate-tax#free-zone", "title": "UAE Free Zone Eligibility", "audience": "Tax director, business owner",
     "blurb": "The de minimis test, inside the Corporate Tax calculator.", "priority": "P1", "jur": "AE"},
]


def ctx(request: Request, **kw) -> dict:
    return {"request": request, "site": SITE, "modules": MODULES, **kw}


def page(request: Request, name: str, status_code: int = 200, **kw):
    return templates.TemplateResponse(request, name, ctx(request, **kw), status_code=status_code)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    quick = gcc_compare.compare(gcc_compare.GCCScenario())
    return page(request, "home.html", quick=quick, profiles=gcc_compare.profiles(), origins=personal_tax.enabled_countries())


@app.get("/uae/corporate-tax", response_class=HTMLResponse)
def page_uae_ct(request: Request):
    return page(request, "uae_ct.html", rules=load_rules("ae"))


@app.get("/vat", response_class=HTMLResponse)
def page_vat(request: Request, j: str = "AE"):
    j = j.upper() if j.upper() in ("AE", "SA") else "AE"
    return page(request, "vat.html", jur=j, rules=load_rules(j))


@app.get("/ksa/zakat-income-tax", response_class=HTMLResponse)
def page_ksa_zakat(request: Request):
    return page(request, "ksa_zakat.html", rules=load_rules("sa"))


@app.get("/ksa/withholding-tax", response_class=HTMLResponse)
def page_ksa_wht(request: Request):
    return page(request, "ksa_wht.html", categories=ksa_wht.categories(), rules=load_rules("sa"))


@app.get("/gcc/compare", response_class=HTMLResponse)
def page_gcc(request: Request):
    return page(request, "gcc_compare.html", profiles=gcc_compare.profiles())


@app.get("/move", response_class=HTMLResponse)
def page_move(request: Request, origin: str | None = None):
    origins = personal_tax.enabled_countries()
    sel = origin.upper() if origin and origin.upper() in origins else "GB"
    return page(request, "move.html", origins=origins, selected=sel, fx=personal_tax.rules()["fx"], personal=personal_tax.rules())


@app.get("/move/{origin}-to-uae", response_class=HTMLResponse)
def page_move_origin(request: Request, origin: str):
    origins = personal_tax.enabled_countries()
    code = {v["name"].lower().replace(" ", "-").replace("-sar", ""): c for c, v in origins.items()} | {c.lower(): c for c in origins} | {"uk": "GB", "usa": "US", "united-states": "US", "united-kingdom": "GB", "hong-kong": "HK"}
    sel = code.get(origin.lower())
    if not sel:
        return page(request, "404.html", status_code=404)
    return page(request, "move.html", origins=origins, selected=sel, fx=personal_tax.rules()["fx"], personal=personal_tax.rules())


@app.get("/personal-tax", response_class=HTMLResponse)
def page_personal_index(request: Request):
    return page(request, "personal_index.html", origins=personal_tax.enabled_countries(), personal=personal_tax.rules())


@app.get("/personal-tax/{code}", response_class=HTMLResponse)
def page_personal(request: Request, code: str):
    origins = personal_tax.enabled_countries()
    code = code.upper()
    if code not in origins:
        return page(request, "404.html", status_code=404)
    return page(request, "personal_tax.html", code=code, c=origins[code], personal=personal_tax.rules())


@app.get("/diagnose", response_class=HTMLResponse)
def page_diagnose(request: Request, profile: str = "business"):
    profile = profile if profile in ("business", "gcc", "personal") else "business"
    return page(request, "diagnose.html", questions=diagnostic.question_list(), profile=profile)


PATHS = {
    "business": {"title": "Check my business tax", "lead": "UAE Corporate Tax, VAT, Saudi zakat. Start with the number, then see what is still open.",
                 "tools": [("UAE Corporate Tax", "/uae/corporate-tax", "From accounting profit to tax due, with reliefs and Free Zone status."), ("UAE VAT", "/vat?j=AE", "Add it, strip it, or run the return."),
                           ("KSA Zakat & Income Tax", "/ksa/zakat-income-tax", "The base, the split, the bill."), ("KSA VAT", "/vat?j=SA", "15%, returns and registration.")],
                 "diagnostic": "business", "journeys": ["free-zone-selling-to-mainland"], "services": ["uae_ct_review", "free_zone_review", "sbr_check", "vat_registration", "zakat_computation", "einvoicing_readiness"]},
    "gcc": {"title": "Expand or trade across the GCC", "lead": "One operation, several tax systems. Compare them, price a cross-border deal, find the exposure.",
            "tools": [("GCC comparison", "/gcc/compare", "Six countries side by side, scope and Pillar Two kept apart."), ("KSA Withholding Tax", "/ksa/withholding-tax", "What a Saudi customer will deduct, and when a treaty stops it."),
                      ("KSA VAT", "/vat?j=SA", "Reverse charge and registration."), ("UAE Corporate Tax", "/uae/corporate-tax", "Including the foreign tax credit.")],
            "diagnostic": "gcc", "journeys": ["uae-saudi-transactions"], "services": ["uae_ksa_transaction", "wht_treaty", "tp_documentation", "dmtt_assessment"]},
}


@app.get("/start/{path}", response_class=HTMLResponse)
def start_path(request: Request, path: str):
    if path == "move":
        return page_move(request)
    if path not in PATHS:
        return page(request, "404.html", status_code=404)
    p = PATHS[path]
    return page(request, "path.html", path=path, p=p, journeys=[journeys.get(s) for s in p["journeys"]], services=[services.get(s) for s in p["services"]])


@app.get("/journeys", response_class=HTMLResponse)
def journeys_index(request: Request):
    return page(request, "journeys.html", items=[journeys.get(s) for s in journeys.JOURNEYS])


@app.get("/journeys/{slug}", response_class=HTMLResponse)
def journey_page(request: Request, slug: str):
    if slug not in journeys.JOURNEYS:
        return page(request, "404.html", status_code=404)
    j = journeys.get(slug)
    return page(request, "journey.html", j=j, service=services.get(j["service"]))


@app.get("/services", response_class=HTMLResponse)
def services_index(request: Request):
    return page(request, "services.html", business=[services.get(s) for s, v in services.SERVICES.items() if v["audience"] == "business"],
                personal=[services.get(s) for s, v in services.SERVICES.items() if v["audience"] == "personal"])


@app.get("/guides", response_class=HTMLResponse)
def guides_index(request: Request):
    return page(request, "guides.html", profiles=gcc_compare.profiles(), origins=personal_tax.enabled_countries())


@app.get("/guides/{code}", response_class=HTMLResponse)
def guide(request: Request, code: str):
    data = gcc_compare.profiles()
    code = code.upper()
    if code not in data["jurisdictions"]:
        return page(request, "404.html", status_code=404)
    rules = load_rules(code) if code in ("AE", "SA") else None
    return page(request, "guide.html", code=code, p=data["jurisdictions"][code], profiles=data, rules=rules)


@app.get("/compare/{a}-vs-{b}", response_class=HTMLResponse)
def compare_pair(request: Request, a: str, b: str):
    data = gcc_compare.profiles()
    a, b = a.upper(), b.upper()
    if a not in data["jurisdictions"] or b not in data["jurisdictions"] or a == b:
        return page(request, "404.html", status_code=404)
    result = gcc_compare.compare(gcc_compare.GCCScenario(jurisdictions=[a, b]))
    return page(request, "compare_pair.html", a=a, b=b, pa=data["jurisdictions"][a], pb=data["jurisdictions"][b], result=result)


@app.get("/methodology", response_class=HTMLResponse)
def methodology(request: Request):
    return page(request, "methodology.html", ae=load_rules("ae"), sa=load_rules("sa"), gcc=gcc_compare.profiles(), personal=personal_tax.rules())


@app.get("/api", response_class=HTMLResponse)
def api_page(request: Request):
    return page(request, "api.html")


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return page(request, "privacy.html")


@app.get("/disclaimer", response_class=HTMLResponse)
def disclaimer(request: Request):
    return page(request, "disclaimer.html")


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    if INDEXABLE:
        return "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n"
    return "User-agent: *\nDisallow: /\n"


@app.get("/sitemap.xml")
def sitemap(request: Request):
    base = str(request.base_url).rstrip("/")
    codes = list(gcc_compare.profiles()["jurisdictions"])
    origins = personal_tax.enabled_countries()
    urls = ["/", "/uae/corporate-tax", "/vat", "/ksa/zakat-income-tax", "/ksa/withholding-tax", "/gcc/compare", "/move", "/diagnose",
            "/personal-tax", "/guides", "/methodology", "/api", "/privacy", "/disclaimer", "/start/business", "/start/gcc", "/journeys", "/services"]
    urls += [f"/journeys/{s}" for s in journeys.JOURNEYS]
    urls += [f"/guides/{c}" for c in codes]
    urls += [f"/compare/{a}-vs-{b}" for i, a in enumerate(codes) for b in codes[i + 1:]]
    urls += [f"/move/{c.lower()}-to-uae" for c in origins] + [f"/personal-tax/{c}" for c in origins]
    body = "".join(f"<url><loc>{base}{u}</loc></url>" for u in urls)
    return HTMLResponse(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>', media_type="application/xml")
