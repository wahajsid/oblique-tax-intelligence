"""HTTP-level tests through the FastAPI app (no server needed)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_rules():
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/api/v1/rules/ae").json()["jurisdiction"] == "AE"
    assert client.get("/api/v1/rules/xx").status_code == 404


def test_uae_ct_endpoint_contract():
    r = client.post("/api/v1/uae/corporate-tax", json={"accounting_profit": 1_000_000, "revenue": 10_000_000})
    assert r.status_code == 200
    d = r.json()
    assert d["outputs"]["corporate_tax_payable"] == 56_250.0
    assert {"trace", "flags", "rules", "review_status", "disclaimer", "ruleset_version"} <= set(d)


def test_validation_error_is_422():
    assert client.post("/api/v1/uae/corporate-tax", json={"accounting_profit": "abc"}).status_code == 422
    assert client.post("/api/v1/ksa/withholding-tax", json={"payments": [{"category": "bogus", "amount": 10}]}).status_code == 422


def test_gcc_compare_endpoint():
    r = client.post("/api/v1/gcc/compare", json={"taxable_profit": 1_000_000, "jurisdictions": ["AE", "SA"]})
    assert r.status_code == 200
    assert [x["code"] for x in r.json()["rows"]] == ["AE", "SA"]


def test_pages_render():
    for path in ["/", "/uae/corporate-tax", "/vat?j=AE", "/vat?j=SA", "/ksa/zakat-income-tax", "/ksa/withholding-tax",
                 "/gcc/compare", "/guides", "/guides/QA", "/compare/AE-vs-SA", "/methodology", "/api", "/disclaimer", "/sitemap.xml", "/robots.txt"]:
        assert client.get(path).status_code == 200, path
    assert client.get("/guides/ZZ").status_code == 404
    assert client.get("/compare/AE-vs-AE").status_code == 404


def test_sitemap_lists_pairs():
    body = client.get("/sitemap.xml").text
    assert "/compare/AE-vs-SA" in body and "/guides/KW" in body
