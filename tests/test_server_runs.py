"""Живые прогоны, лимиты, чат (SSE) и перепроверка через API: на фейковой LLM."""

import json
import re
import time

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from reqcheck.llm import FakeLLM  # noqa: E402
from server.jobs import JobManager  # noqa: E402
from server.main import create_app, example_parts, load_example, server_settings  # noqa: E402
from server.ratelimit import RateLimiter, client_ip  # noqa: E402

H = {"x-sau": "1"}
DOC = ("# Док\n\nВерсия 1.0 от 01.01.2026.\n\n* **FR-1.** Клиент получает push за 5 секунд после оплаты.\n"
       "* **FR-2.** Система отвечает быстро.\n").encode()


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.delenv("SITE_LIVE", raising=False)
    for var in ("SITE_DAILY_RUNS", "SITE_RUNS_PER_IP", "SITE_CHAT_PER_IP", "SITE_DAILY_CHAT",
                "SITE_RECHECK_PER_IP", "SITE_DAILY_RECHECK"):
        monkeypatch.delenv(var, raising=False)
    for f in (load_example, example_parts):
        f.cache_clear()


@pytest.fixture
def manager(tmp_path):
    return JobManager(server_settings, base_dir=tmp_path / "runs")


@pytest.fixture
def client(tmp_path, manager):
    return TestClient(create_app(tmp_path / "noweb", jobs=manager, limiter=RateLimiter()))


def upload(client, content=DOC, name="тз.md", headers=H, ip=None):
    h = dict(headers)
    if ip:
        h["x-forwarded-for"] = ip
    return client.post("/api/runs", files={"file": (name, content, "text/markdown")}, headers=h)


def wait_done(client, run_id, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        body = client.get(f"/api/runs/{run_id}").json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.1)
    raise AssertionError("прогон не завершился")


def test_full_run_status_report_and_downloads(client, manager):
    r = upload(client)
    assert r.status_code == 202, r.text
    run_id = r.json()["run_id"]
    assert re.fullmatch(r"[0-9a-f]{32}", run_id)
    body = wait_done(client, run_id)
    assert body["status"] == "done" and body["error"] is None
    assert body["stages_done"][0] == "ingest" and "render" in body["stages_done"]
    assert body["report"]["passport"]["llm_mode"] == "full"
    assert body["report"]["passport"]["document_path"] == "тз.md"  # имя пользователя, без путей сервера
    assert body["document"]["lines"][4].startswith("* **FR-1.**")
    assert body["view"]["highlights"] and "top_questions" in body["view"]
    md = client.get(f"/api/runs/{run_id}/report.md")
    assert md.status_code == 200 and md.text.startswith("# Отчёт о проверке")
    assert client.get(f"/api/runs/{run_id}/report.json").json()["verdict"]
    assert client.get(f"/api/runs/{run_id}/report.log").status_code == 404  # лог не отдаётся
    job = manager.get(run_id)
    assert not list(job.directory.glob("upload*"))  # загруженный файл удалён
    assert str(manager.base) not in json.dumps(body, ensure_ascii=False)


def test_upload_validation(client, monkeypatch):
    assert upload(client, headers={}).status_code == 403  # без заголовка: межсайтовая форма не пройдёт
    assert upload(client, name="a.exe").status_code == 415
    assert upload(client, content=b"x" * (5 * 1024 * 1024 + 10)).status_code == 413
    assert upload(client, content=b"   ").status_code == 400
    monkeypatch.setenv("SITE_LIVE", "0")
    r = upload(client)
    assert r.status_code == 503 and "пример" in r.json()["detail"].lower()


def test_no_key_means_no_live_runs(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai_compat")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert upload(client).status_code == 503


def test_broken_document_ends_with_clean_error(client, manager):
    r = upload(client, content=b"%PDF-1.7 broken", name="x.pdf")
    body = wait_done(client, r.json()["run_id"])
    assert body["status"] == "error" and "upload" not in body["error"] and "x.pdf" in body["error"]
    assert str(manager.base) not in body["error"]


def test_unknown_and_malformed_run_ids(client):
    assert client.get("/api/runs/" + "0" * 32).status_code == 404
    assert client.get("/api/runs/../../etc").status_code in (404, 422)
    assert client.get("/api/runs/" + "g" * 32 + "/report.md").status_code == 404


def test_run_limit_per_ip_and_global(client, monkeypatch):
    monkeypatch.setenv("SITE_RUNS_PER_IP", "1")
    assert upload(client, ip="1.1.1.1").status_code == 202
    r = upload(client, ip="1.1.1.1")
    assert r.status_code == 429 and "пример" in r.json()["detail"].lower()
    assert upload(client, ip="2.2.2.2").status_code == 202
    monkeypatch.setenv("SITE_DAILY_RUNS", "2")
    assert upload(client, ip="3.3.3.3").status_code == 429  # общий потолок сайта


def test_daily_runs_zero_disables_runs(client, monkeypatch):
    monkeypatch.setenv("SITE_DAILY_RUNS", "0")
    assert upload(client).status_code == 429


def test_queue_full_is_429_and_not_charged(tmp_path, monkeypatch):
    mgr = JobManager(server_settings, base_dir=tmp_path / "q", max_queue=0)
    limiter = RateLimiter()
    c = TestClient(create_app(tmp_path / "noweb", jobs=mgr, limiter=limiter))
    monkeypatch.setenv("SITE_RUNS_PER_IP", "1")
    assert upload(c).status_code == 429
    mgr.max_queue = 5
    assert upload(c).status_code == 202  # лимит не был списан за отклонённый запрос


def test_expired_results_are_removed(client, manager):
    run_id = upload(client).json()["run_id"]
    wait_done(client, run_id)
    directory = manager.get(run_id).directory
    manager.ttl_s = 0
    time.sleep(0.01)
    assert client.get(f"/api/runs/{run_id}").status_code == 404 and not directory.exists()


def test_client_ip_uses_first_forwarded_address():
    assert client_ip("9.9.9.9, 10.0.0.1", "127.0.0.1") == "9.9.9.9"
    assert client_ip(None, "127.0.0.1") == "127.0.0.1"
    assert client_ip("", None) == "unknown"


def sse(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


def chat(client, run_id="example", question="Почему это критично?", headers=H, **extra):
    return client.post("/api/chat", json={"run_id": run_id, "messages": [{"role": "user", "content": question}], **extra},
                       headers=headers)


@pytest.fixture
def fake_answers(monkeypatch):
    def handler(system, prompt):
        if "ПЕРЕПРОВЕРКА С ОТВЕТАМИ" in system:
            ids = re.findall(r"(?m)^(D-\d{3}) \[", prompt)
            return json.dumps({"items": [{"finding_id": i, "status": "resolved", "reason": "ответ полный"} for i in ids]})
        return "См. D-004. Цитата: «Месяц определяется по дате совершения покупки в Алматы.» и «выдуманная фраза про банк»."

    llm = FakeLLM(handler=handler)
    monkeypatch.setattr("server.main.build_client", lambda settings, attempts=2: llm)
    return llm


def test_chat_streams_sse_over_example_with_quote_guard(client, fake_answers):
    r = chat(client)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = sse(r)
    text = "".join(e.get("delta", "") for e in events)
    assert events[-1] == {"done": True} and len(events) > 3
    assert "Месяц определяется по дате" in text and "выдуманная фраза" not in text


def test_chat_over_live_run_and_missing_run(client, fake_answers):
    run_id = upload(client).json()["run_id"]
    wait_done(client, run_id)
    assert chat(client, run_id).status_code == 200
    assert chat(client, "0" * 32).status_code == 404


def test_chat_validation_and_limits(client, fake_answers, monkeypatch):
    assert chat(client, headers={}).status_code == 403
    assert chat(client, question="   ").status_code == 400
    assert chat(client, question="x" * 3000).status_code == 413
    monkeypatch.setenv("SITE_CHAT_PER_IP", "1")
    assert chat(client).status_code == 200
    assert chat(client).status_code == 429
    monkeypatch.setenv("SITE_LIVE", "0")
    assert chat(client).status_code == 503


def test_chat_errors_are_sent_as_event_without_details(client, monkeypatch):
    class Boom(FakeLLM):
        def stream_text(self, *a, **k):
            raise RuntimeError("секрет sk-aaaaaaaaaaaaaaaaaaaaaaaa в пути /srv/x")
            yield  # pragma: no cover

    monkeypatch.setattr("server.main.build_client", lambda settings, attempts=2: Boom())
    events = sse(chat(client))
    assert events == [{"error": "Не удалось получить ответ модели. Попробуйте ещё раз."}]


def test_recheck_endpoint_returns_verdict_before_and_after(client, fake_answers, monkeypatch):
    example = client.get("/api/example").json()
    crit = [f["id"] for f in example["report"]["findings"] if f["severity"] == "critical"]
    r = client.post("/api/recheck", json={"run_id": "example", "answers": {i: "ответ" for i in crit}}, headers=H)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict_before"]["code"] == "blocked" and body["verdict_after"]["code"] == "caveats"
    assert {i["status"] for i in body["items"]} == {"resolved"}
    assert client.post("/api/recheck", json={"run_id": "example", "answers": {crit[0]: " "}}, headers=H).status_code == 400
    assert client.post("/api/recheck", json={"run_id": "example", "answers": {crit[0]: "x"}}).status_code == 403
    monkeypatch.setenv("SITE_RECHECK_PER_IP", "1")
    assert client.post("/api/recheck", json={"run_id": "example", "answers": {crit[0]: "x"}}, headers=H).status_code == 429


def test_key_never_appears_in_responses(client, monkeypatch, fake_answers):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-live-secret-000000000000")
    for response in (client.get("/api/health"), client.get("/api/example"), chat(client)):
        assert "sk-live-secret" not in response.text
