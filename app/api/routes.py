"""JSON API, versioned under /api/v1. Every calculation response carries a trace,
rule metadata, an outcome (ILLUSTRATIVE_ESTIMATE or REVIEW_REQUIRED) and the
desktop-estimate disclaimer. Nothing is persisted."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

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


@router.post("/enquiries")
def enquiries() -> None:
    raise HTTPException(status_code=503, detail="Live enquiry collection is not enabled in this build. Nothing is stored or sent.")
