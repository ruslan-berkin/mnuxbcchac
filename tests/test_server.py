"""Сервер сайта: health, пример без LLM, заголовки безопасности, раздача статики."""

import json

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from reqcheck.ground import normalize  # noqa: E402
from server.main import create_app, load_example  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_example_cache():
    load_example.cache_clear()
    yield
    load_example.cache_clear()


@pytest.fixture
def web_dir(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "index.html").write_text("<h1>лендинг</h1>", encoding="utf-8")
    (tmp_path / "app" / "index.html").write_text("<h1>платформа</h1>", encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(web_dir):
    return TestClient(create_app(web_dir))


def test_health_reports_live_flag(client, monkeypatch):
    monkeypatch.delenv("SITE_LIVE", raising=False)
    assert client.get("/api/health").json()["live"] is True
    monkeypatch.setenv("SITE_LIVE", "0")
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["live"] is False


def test_example_serves_committed_report_and_document_without_llm(client, repo_root, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = client.get("/api/example")
    assert r.status_code == 200
    data = r.json()
    committed = json.loads((repo_root / "reports" / "report.json").read_text(encoding="utf-8"))
    assert data["report"] == committed
    assert data["document"]["lines"] and data["document"]["sha256"] == committed["passport"]["document_sha256"]


def test_every_example_quote_is_on_its_anchor_lines(client):
    """Подсветка цитат в /app опирается на это: цитата лежит ровно в строках якоря."""
    data = client.get("/api/example").json()
    lines = data["document"]["lines"]
    for f in data["report"]["findings"]:
        for quote, a in zip(f["quotes"], f["anchors"]):
            segment = normalize(" ".join(lines[a["line_start"] - 1 : a["line_end"]]))
            assert normalize(quote) in segment, (f["id"], quote, a)


def test_example_response_has_no_secrets_or_server_paths(client, monkeypatch, repo_root):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret-value-000000")
    body = client.get("/api/example").text
    assert "sk-test-secret" not in body and str(repo_root) not in body


def test_security_headers_on_api_and_static(client):
    for path in ("/api/health", "/", "/app/"):
        h = client.get(path).headers
        assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in h["content-security-policy"]


def test_static_pages_and_unknown_api(client):
    assert "лендинг" in client.get("/").text
    assert "платформа" in client.get("/app/").text
    assert client.get("/app").status_code == 200  # редирект на /app/ с тем же содержимым
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json()["detail"] == "Нет такого метода API."
    assert client.get("/docs").status_code == 404  # схема API наружу не публикуется


def test_static_does_not_escape_web_dir(client):
    for path in ("/..%2f..%2fREADME.md", "/%2e%2e/%2e%2e/.env", "/../server/main.py"):
        r = client.get(path)
        assert r.status_code == 404 or "лендинг" in r.text


def test_example_failure_is_a_clean_503(web_dir, monkeypatch, tmp_path):
    monkeypatch.setattr("server.main.EXAMPLE_REPORT", tmp_path / "missing.json")
    r = TestClient(create_app(web_dir)).get("/api/example")
    assert r.status_code == 503 and str(tmp_path) not in r.text
