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


def test_head_tags_for_search_and_sharing(monkeypatch):
    html = client.get("/uae/corporate-tax").text
    assert '<link rel="canonical" href="http://testserver/uae/corporate-tax">' in html
    assert 'property="og:title"' in html and 'property="og:image" content="http://testserver/static/img/og.png"' in html and 'name="twitter:card"' in html
    assert '<link rel="canonical" href="http://testserver/vat?j=SA">' in client.get("/vat?j=SA").text
    assert '<link rel="canonical" href="http://testserver/diagnose">' in client.get("/diagnose?profile=personal").text
    ar = client.get("/ar/uae/corporate-tax").text
    assert '<link rel="canonical" href="http://testserver/ar/uae/corporate-tax">' in ar and "<title>حاسبة ضريبة الشركات الإماراتية 2026 |" in ar
    assert '<link rel="canonical" href="http://testserver/ar">' in client.get("/ar").text


def test_static_caching_compression_and_docs_removed():
    r = client.get("/static/css/site.css?v=abc")
    assert "immutable" in r.headers["cache-control"]
    assert client.get("/", headers={"Accept-Encoding": "gzip"}).headers.get("content-encoding") == "gzip"
    assert client.get("/docs").status_code == 404 and client.get("/redoc").status_code == 404 and client.get("/openapi.json").status_code == 200
    assert client.get("/", headers={"X-Forwarded-Proto": "https"}).headers.get("strict-transport-security")
    assert client.get("/static/img/og.png").status_code == 200
