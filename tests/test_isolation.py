"""Изоляция прогонов друг от друга: логи, кэш, окружение, секреты, пути вывода."""

import json
import logging
import os
import threading
import time

import pytest

from reqcheck.config import Settings, load_settings
from reqcheck.errors import InputFileError, LLMUnavailableError
from reqcheck.llm import DiskCache, FakeLLM
from reqcheck.llm.base import call_with_retries, structured_call
from reqcheck.pipeline import run
from reqcheck.redact import redact
from tests.test_pipeline_llm import SETTINGS, finding, scripted

DOC_A = "# A\n\nВерсия 1.0 от 01.01.2026.\n\n* **FR-1.** Система Альфа создаёт заказ за 2 секунды после оплаты.\n"
DOC_B = "# B\n\nВерсия 1.0 от 01.01.2026.\n\n* **FR-1.** Система Бета отправляет письмо клиенту после регистрации.\n"


def _llm_with_fake_quote(marker):
    """Модель «выдумывает» цитату с уникальным маркером: ground пишет её в лог прогона."""
    each = {"findings": [finding(["R-01"], "UNA", "major", [f"Выдуманная цитата {marker} которой нет в документе"])]}
    return scripted(seg={"requirements": []}, each=each, set_={"findings": [], "conclusions": []})


def test_concurrent_runs_write_only_their_own_logs(tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.md"
    (tmp_path / "da.md").write_text(DOC_A, encoding="utf-8")
    (tmp_path / "db.md").write_text(DOC_B, encoding="utf-8")
    barrier = threading.Barrier(2)
    errors = []

    def go(doc, out, marker):
        try:
            barrier.wait()
            run(tmp_path / doc, out, SETTINGS, client=_llm_with_fake_quote(marker), use_cache=False, workers=4)
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    ts = [threading.Thread(target=go, args=("da.md", a, "МАРКЕР-АЛЬФА")),
          threading.Thread(target=go, args=("db.md", b, "МАРКЕР-БЕТА"))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors
    log_a, log_b = a.with_suffix(".log").read_text(encoding="utf-8"), b.with_suffix(".log").read_text(encoding="utf-8")
    assert "МАРКЕР-АЛЬФА" in log_a and "МАРКЕР-БЕТА" not in log_a
    assert "МАРКЕР-БЕТА" in log_b and "МАРКЕР-АЛЬФА" not in log_b
    # записи из потоков пула тоже попадают в лог своего прогона
    assert "LLM вызов" in log_a and "LLM вызов" in log_b
    assert "Система Бета" not in log_a and "Система Альфа" not in log_b


def test_no_per_run_handlers_left_and_global_logger_untouched(tmp_path):
    root = logging.getLogger("reqcheck")
    (tmp_path / "d.md").write_text(DOC_A, encoding="utf-8")
    run(tmp_path / "d.md", tmp_path / "r1.md", SETTINGS, lint_only=True)
    n = len(root.handlers)
    level = root.level
    for i in range(3):
        run(tmp_path / "d.md", tmp_path / f"x{i}.md", SETTINGS, lint_only=True)
    assert len(root.handlers) == n and root.level == level
    assert not any(isinstance(h, logging.FileHandler) for h in root.handlers)


def test_logs_outside_a_run_go_nowhere(tmp_path, capsys):
    logging.getLogger("reqcheck.ground").warning("секретная строка вне прогона")
    assert "секретная строка" not in capsys.readouterr().err


def test_secrets_redacted_in_log_and_errors(tmp_path):
    fake_key = "sk-proj-" + "A" * 30
    assert fake_key not in redact(f"Incorrect API key provided: {fake_key}")
    assert "AIza" not in redact("key=AIza" + "B" * 30)
    assert "gsk_" not in redact("gsk_" + "C" * 30)
    assert "Bearer abcdef" not in redact("Authorization: Bearer abcdefghijkl")

    class Err(Exception):
        status_code = 401

    def fn():
        raise Err(f"Incorrect API key provided: {fake_key}. org-ABCDEFGH12")

    with pytest.raises(LLMUnavailableError) as e:
        call_with_retries(fn, lambda exc: (False, None), sleep=lambda s: None)
    assert fake_key not in str(e.value) and "org-ABCDEFGH12" not in str(e.value)

    (tmp_path / "d.md").write_text(DOC_A, encoding="utf-8")

    class Leaky(FakeLLM):
        def complete(self, system, prompt, schema):
            logging.getLogger("reqcheck.test").error("ключ %s утёк", fake_key)
            return super().complete(system, prompt, schema)

    out = tmp_path / "r.md"
    run(tmp_path / "d.md", out, SETTINGS, client=Leaky(), use_cache=False, workers=1)
    assert fake_key not in out.with_suffix(".log").read_text(encoding="utf-8")


def test_output_paths_must_be_distinct(tmp_path):
    (tmp_path / "d.md").write_text(DOC_A, encoding="utf-8")
    for bad in ("report.json", "report.log"):
        with pytest.raises(InputFileError):
            run(tmp_path / "d.md", tmp_path / bad, SETTINGS, lint_only=True)
    run(tmp_path / "d.md", tmp_path / "report", SETTINGS, lint_only=True)  # без суффикса допустимо
    assert (tmp_path / "report.json").exists() and (tmp_path / "report").exists()


def test_report_files_are_readable_by_other_users(tmp_path):
    (tmp_path / "d.md").write_text(DOC_A, encoding="utf-8")
    run(tmp_path / "d.md", tmp_path / "r.md", SETTINGS, lint_only=True)
    for suffix in (".md", ".json"):
        assert (tmp_path / f"r{suffix}").stat().st_mode & 0o044 == 0o044


def test_library_does_not_read_dotenv_files(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("GEMINI_API_KEY=real-key-from-file\nGEMINI_MODEL=m\nOPENAI_BASE_URL=https://evil.example\n")
    monkeypatch.chdir(tmp_path)
    for k in ("GEMINI_API_KEY", "GEMINI_MODEL", "OPENAI_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    st = load_settings("gemini")
    assert st.api_key is None and not st.has_key
    assert os.getenv("OPENAI_BASE_URL") is None


def test_model_allowlist(monkeypatch):
    monkeypatch.setenv("REQCHECK_MODEL_ALLOWLIST", "cheap-model,other")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_MODEL", "expensive-model")
    with pytest.raises(ValueError):
        load_settings("openai_compat")
    assert load_settings("openai_compat", "cheap-model").model == "cheap-model"


def test_cache_namespaces_do_not_share_entries(tmp_path):
    a = DiskCache(tmp_path, namespace="user-a")
    b = DiskCache(tmp_path, namespace="user-b")
    k_a = DiskCache.make_key("p", "m", "s", "prompt", "S", namespace="user-a")
    k_b = DiskCache.make_key("p", "m", "s", "prompt", "S", namespace="user-b")
    assert k_a != k_b and a.root != b.root
    a.put(k_a, '{"x": 1}')
    assert a.get(k_a) and b.get(k_a) is None and b.get(k_b) is None


def test_cache_ttl_and_size_cap(tmp_path):
    c = DiskCache(tmp_path, ttl_s=0.05)
    c.put("k1", "v")
    assert c.get("k1") == "v"
    time.sleep(0.1)
    assert c.get("k1") is None and not (tmp_path / "k1.json").exists()
    small = DiskCache(tmp_path / "s", max_bytes=2000)
    for i in range(30):
        small.put(f"key{i:02d}", "x" * 300)
        time.sleep(0.001)
    total = sum(p.stat().st_size for p in small.root.glob("*.json"))
    assert total <= 2000 and len(list(small.root.glob("*.json"))) < 30


def test_cache_path_is_absolute_and_configurable(tmp_path, monkeypatch):
    monkeypatch.setenv("REQCHECK_CACHE_DIR", str(tmp_path / "cc"))
    assert DiskCache().root == (tmp_path / "cc").resolve() and DiskCache().root.is_absolute()


def test_per_tenant_cache_namespace_in_run(tmp_path):
    (tmp_path / "d.md").write_text(DOC_A, encoding="utf-8")
    cache_dir = tmp_path / "cache"
    first, second = FakeLLM(), FakeLLM()
    run(tmp_path / "d.md", tmp_path / "a.md", SETTINGS, client=first, cache_dir=cache_dir, cache_namespace="u1", workers=1)
    run(tmp_path / "d.md", tmp_path / "b.md", SETTINGS, client=second, cache_dir=cache_dir, cache_namespace="u2", workers=1)
    assert first.calls and second.calls  # арендатор u2 не получает кэш u1
    third = FakeLLM()
    run(tmp_path / "d.md", tmp_path / "c.md", SETTINGS, client=third, cache_dir=cache_dir, cache_namespace="u1", workers=1)
    assert third.calls == []
