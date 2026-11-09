"""JSON API, versioned under /api/v1. Every calculation response carries a trace,
rule metadata, an outcome (ILLUSTRATIVE_ESTIMATE or REVIEW_REQUIRED) and the
desktop-estimate disclaimer. Nothing is persisted."""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from typing import Any

from app import events, leads, pdf

from app.engine import diagnostic, gcc_compare, ksa_wht, ksa_zakat, personal_tax, relocation, uae_ct, vat
from app.engine.core import load_rules

router = APIRouter(prefix="/api/v1", tags=["calculators"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "rulesets": {j: load_rules(j)["ruleset_version"] for j in ("ae", "sa")},
            "personal_ruleset": personal_tax.rules()["ruleset_version"], "persistence_enabled": False,
            "lead_delivery_enabled": False, "expert_approved_rules": 0}


@router.get("/rules")
def rules_index() -> dict:
    return {"jurisdictions": ["ae", "sa"], "gcc_profiles": gcc_compare.profiles(), "personal": personal_tax.rules()}


@router.get("/rules/{jurisdiction}")
def rules(jurisdiction: str) -> dict:
    if jurisdiction.lower() == "personal":
        return personal_tax.rules()
    try:
        return load_rules(jurisdiction)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/uae/corporate-tax")
def uae_corporate_tax(body: uae_ct.UAECorporateTaxInput) -> dict:
    return uae_ct.calculate(body).as_dict()


@router.post("/vat")
def vat_calc(body: vat.VATInput) -> dict:
    return vat.calculate(body).as_dict()


@router.post("/ksa/zakat-income-tax")
def ksa_zakat_income_tax(body: ksa_zakat.KSAZakatInput) -> dict:
    return ksa_zakat.calculate(body).as_dict()


@router.post("/ksa/withholding-tax")
def ksa_withholding_tax(body: ksa_wht.KSAWHTInput) -> dict:
    try:
        return ksa_wht.calculate(body).as_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/ksa/withholding-tax/categories")
def ksa_wht_categories() -> dict:
    return ksa_wht.categories()


@router.post("/gcc/compare")
def gcc_comparison(body: gcc_compare.GCCScenario) -> dict:
    try:
        return gcc_compare.compare(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/personal-tax/countries")
def personal_countries() -> dict:
    return {c: {"name": v["name"], "currency": v["currency"], "flag": v["flag"], "tax_year": v["tax_year"], "review_status": v["review_status"]}
            for c, v in personal_tax.enabled_countries().items()}


@router.post("/personal-tax")
def personal_tax_calc(body: personal_tax.PersonalTaxInput) -> dict:
    try:
        return personal_tax.calculate(body).as_dict()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/move-to-uae")
def move_to_uae(body: relocation.RelocationInput) -> dict:
    try:
        return relocation.compare(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/diagnostic/questions")
def diagnostic_questions(profile: diagnostic.Profile | None = None) -> dict:
    return diagnostic.questions(profile)


@router.post("/diagnostic")
def diagnostic_run(body: diagnostic.DiagnosticInput) -> dict:
    try:
        return diagnostic.run(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ------------------------------------------------------------ leads + PDF -----
def _client_ip(request: Request) -> str:
    return (request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "unknown"))


def _pdf_filename(calculator: str) -> str:
    return f"oblique-working-paper-{calculator.replace('_', '-')}.pdf"


@router.get("/services")
def services_index() -> dict:
    from app import services as svc
    return {k: svc.get(k) for k in svc.SERVICES}


@router.get("/leads/config")
def leads_config() -> dict:
    return leads.public_config()


@router.post("/leads")
def create_lead(body: leads.LeadInput, request: Request) -> dict:
    if not leads.enabled():
        raise HTTPException(status_code=503, detail="Enquiries are not enabled on this deployment. Nothing was stored or sent.")
    if body.website:  # honeypot: pretend success, deliver nothing
        return {"status": "received", "lead_id": "ok", "pdf_token": None, "delivery": {}}
    ip = _client_ip(request)
    if leads.rate_limited(ip):
        raise HTTPException(status_code=429, detail="Too many enquiries from this connection. Please try again in an hour or email info@obliqueconsult.com.")
    if leads.turnstile_enabled() and not leads.verify_turnstile(body.turnstile_token, ip):
        raise HTTPException(status_code=400, detail="The spam check did not pass. Please try again, or email info@obliqueconsult.com.")
    record = leads.make_record(body, ip)
    pdf_bytes = None
    summary = f"Enquiry via {body.context.calculator}"
    if body.context.calculator in pdf.REGISTRY and body.context.shared_inputs and body.context.inputs:
        try:
            pdf_bytes, result = pdf.render_pdf(body.context.calculator, body.context.inputs, source_url=body.context.page_url, prepared_for=record["name"])
            summary = f"{pdf.REGISTRY[body.context.calculator][2]} working paper requested"
            if result.get("outcome"):
                summary += f" (outcome: {result['outcome']})"
        except Exception as exc:  # noqa: BLE001 - a bad context must not block the enquiry itself
            summary += f" (working paper could not be generated: {type(exc).__name__})"
    try:
        delivery = leads.deliver(record, summary, pdf_bytes, _pdf_filename(body.context.calculator))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail="We could not record your enquiry right now. Please email info@obliqueconsult.com.") from exc
    return {"status": "received", "lead_id": record["id"], "pdf_token": leads.pdf_token(record["id"]) if pdf_bytes else None, "delivery": delivery, "booking_url": "https://calendly.com/alina-obliqueconsult/30min",
            "message": f"Thanks, {record['name'].split(' ')[0]}. We will be in touch at {record['email']}."}


class PdfRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    calculator: str = Field(..., max_length=40)
    inputs: dict[str, Any] = Field(default_factory=dict)
    page_url: str = Field("", max_length=2000)
    token: str | None = Field(None, max_length=120)


@router.post("/pdf", responses={200: {"content": {"application/pdf": {}}}})
def working_paper(body: PdfRequest) -> Response:
    """Branded PDF working paper. When lead capture is enabled, a token from POST /leads is required."""
    if leads.enabled() and not (body.token and leads.verify_pdf_token(body.token)):
        raise HTTPException(status_code=403, detail="The PDF working paper is sent after the short enquiry form. The on-screen result stays free.")
    try:
        data, _ = pdf.render_pdf(body.calculator, body.inputs, source_url=body.page_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # pydantic validation of inputs
        raise HTTPException(status_code=422, detail=f"Could not recompute the working paper: {type(exc).__name__}") from exc
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{_pdf_filename(body.calculator)}"', "Cache-Control": "no-store"})


@router.post("/event", status_code=202)
def track_event(body: events.EventInput, request: Request, background: BackgroundTasks) -> dict:
    """Cookieless usage counter: event name, page and calculator only. No IP, no identifier, no inputs."""
    if request.headers.get("dnt") == "1" or request.headers.get("sec-gpc") == "1":
        return {"status": "not counted"}
    ip = request.client.host if request.client else "0.0.0.0"
    if events.throttled(leads.ip_hash(ip)):
        return {"status": "not counted"}
    background.add_task(events.store, events.record(body))
    return {"status": "counted"}


@router.get("/stats", include_in_schema=False)
def stats(token: str = "") -> dict:
    expected = os.environ.get("STATS_TOKEN", "")
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=404, detail="Not found")
    return events.summary()


@router.post("/subscribe")
def subscribe(body: leads.SubscribeInput, request: Request) -> dict:
    """Rule-change notifications. Uses the same delivery sinks and consent handling as enquiries."""
    if not leads.enabled():
        raise HTTPException(status_code=503, detail="Rule-change notifications are not switched on yet. Follow the changes page or email info@obliqueconsult.com.")
    if body.website:
        return {"status": "received"}
    ip = request.client.host if request.client else "0.0.0.0"
    if leads.rate_limited(ip):
        raise HTTPException(status_code=429, detail="Too many requests from this connection. Please try again in an hour.")
    if leads.turnstile_enabled() and not leads.verify_turnstile(body.turnstile_token, ip):
        raise HTTPException(status_code=400, detail="The spam check did not pass. Please try again, or email info@obliqueconsult.com.")
    record = leads.make_subscription_record(body, ip)
    try:
        delivery = leads.deliver(record, "Rule-change subscription: " + ", ".join(body.topics), None, "")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="We could not record your request right now. Please email info@obliqueconsult.com.") from exc
    return {"status": "received", "delivery": delivery}


@router.post("/enquiries")
def enquiries() -> None:
    raise HTTPException(status_code=410, detail="Use POST /api/v1/leads.")
