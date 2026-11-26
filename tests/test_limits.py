"""Лимиты ввода, бюджет прогона, линейная сложность правил."""

import threading
import time
import zipfile

import pytest

from reqcheck.checks.lint import rule_dangling_references, rule_mixed_units, run_lint_safe
from reqcheck.errors import BudgetExceededError, InputFileError, InputTooLargeError
from reqcheck.ingest import load_document, safe_display_name
from reqcheck.limits import Limits
from reqcheck.llm import FakeLLM
from reqcheck.llm.base import MAX_RETRY_AFTER, call_with_retries
from reqcheck.parallel import clamp_workers, pmap
from reqcheck.pipeline import run
from reqcheck.segment import segment_explicit
from reqcheck.summary import finalize_findings
from tests.test_pipeline_llm import SETTINGS, make_doc


def test_file_size_chars_and_lines_limits(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("строка текста\n" * 200, encoding="utf-8")
    with pytest.raises(InputTooLargeError) as e:
        load_document(p, Limits(max_file_bytes=100))
    assert e.value.exit_code == 2
    with pytest.raises(InputTooLargeError):
        load_document(p, Limits(max_chars=500))
    with pytest.raises(InputTooLargeError):
        load_document(p, Limits(max_lines=50))
    assert load_document(p, Limits()).format == "txt"


def test_page_limit_and_signature_checks(sample_pdf, tmp_path):
    with pytest.raises(InputTooLargeError):
        load_document(sample_pdf, Limits(max_pages=1))
    fake_pdf = tmp_path / "x.pdf"
    fake_pdf.write_text("просто текст", encoding="utf-8")
    with pytest.raises(InputFileError):
        load_document(fake_pdf)
    fake_docx = tmp_path / "x.docx"
    fake_docx.write_text("не zip", encoding="utf-8")
    with pytest.raises(InputFileError):
        load_document(fake_docx)
    binary = tmp_path / "b.txt"
    binary.write_bytes(b"abc\x00\x01\x02def")
    with pytest.raises(InputFileError):
        load_document(binary)


def test_docx_zip_bomb_rejected_before_parsing(tmp_path):
    p = tmp_path / "bomb.docx"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", b"0" * (6 * 1024 * 1024))  # 6 МБ нулей сжимаются до килобайт
    with pytest.raises(InputTooLargeError):
        load_document(p, Limits(max_uncompressed_bytes=1024 * 1024))


def test_parser_error_text_is_not_leaked(tmp_path):
    p = tmp_path / "broken.pdf"
    p.write_bytes(b"%PDF-1.7 \x00 broken garbage instead of a document")
    with pytest.raises(InputFileError) as e:
        load_document(p)
    assert str(tmp_path) not in str(e.value)


def test_safe_display_name_strips_dirs_and_control_chars():
    assert safe_display_name("/srv/uploads/abc123/Отчёт.pdf") == "Отчёт.pdf"
    assert safe_display_name("..\\..\\evil‮gnp.exe") == "evilgnp.exe"
    assert len(safe_display_name("a" * 500)) == 120
    assert safe_display_name("") == "document"


def test_passport_path_defaults_to_file_name_not_server_path(tmp_path):
    sub = tmp_path / "secret_dir"
    sub.mkdir()
    doc = make_doc(sub)
    rep = run(doc, tmp_path / "r.md", SETTINGS, lint_only=True)
    assert rep.passport.document_path == "doc.md" and "secret_dir" not in (tmp_path / "r.md").read_text(encoding="utf-8")
    rep = run(doc, tmp_path / "r2.md", SETTINGS, lint_only=True, display_name="/x/y/Мой файл.md")
    assert rep.passport.document_path == "Мой файл.md"


def test_too_many_requirements_rejected(tmp_path):
    p = tmp_path / "many.md"
    p.write_text("\n\n".join(f"FR-{i}. Система делает {i}." for i in range(1, 60)), encoding="utf-8")
    with pytest.raises(InputTooLargeError):
        run(p, tmp_path / "r.md", SETTINGS, lint_only=True, limits=Limits(max_requirements=10))


def test_llm_call_budget_stops_run_with_exit_6(tmp_path):
    with pytest.raises(BudgetExceededError) as e:
        run(make_doc(tmp_path), tmp_path / "r.md", SETTINGS, client=FakeLLM(), use_cache=False,
            limits=Limits(max_llm_calls=1), workers=1)
    assert e.value.exit_code == 6


def test_prompt_volume_and_deadline_budget(tmp_path):
    with pytest.raises(BudgetExceededError):
        run(make_doc(tmp_path), tmp_path / "r.md", SETTINGS, client=FakeLLM(), use_cache=False,
            limits=Limits(max_prompt_chars=500), workers=1)
    with pytest.raises(BudgetExceededError):
        run(make_doc(tmp_path), tmp_path / "r2.md", SETTINGS, client=FakeLLM(), use_cache=False,
            limits=Limits(deadline_s=0.0), workers=1)


def test_cache_hits_do_not_spend_budget(tmp_path):
    cache_dir = tmp_path / "c"
    first = FakeLLM()
    run(make_doc(tmp_path), tmp_path / "a.md", SETTINGS, client=first, cache_dir=cache_dir, workers=1)
    second = FakeLLM()
    rep = run(make_doc(tmp_path), tmp_path / "b.md", SETTINGS, client=second, cache_dir=cache_dir,
              workers=1, limits=Limits(max_llm_calls=0))
    assert second.calls == [] and rep.passport.llm_mode == "full"


def test_web_limits_are_stricter_than_defaults():
    d, w = Limits(), Limits.web()
    assert w.max_file_bytes < d.max_file_bytes and w.max_llm_calls < d.max_llm_calls
    assert w.deadline_s < d.deadline_s and w.max_requirements < d.max_requirements


def test_limits_from_env(monkeypatch):
    monkeypatch.setenv("REQCHECK_MAX_PAGES", "7")
    monkeypatch.setenv("REQCHECK_DEADLINE_S", "12.5")
    lim = Limits.from_env()
    assert lim.max_pages == 7 and lim.deadline_s == 12.5


def test_lint_flood_is_capped_per_rule(tmp_path):
    p = tmp_path / "flood.md"
    p.write_text("\n\n".join("Это быстро и удобно." for _ in range(300)), encoding="utf-8")
    d = load_document(p)
    found, failed, truncated = run_lint_safe(d, segment_explicit(d), per_rule_cap=40)
    assert len([f for f in found if f.rule == "vague_words"]) == 40
    assert "rule_vague_words" in truncated and failed == []


def test_findings_cap_reports_hidden_count(tmp_path):
    p = tmp_path / "flood.md"
    p.write_text("\n\n".join(f"Это быстро {i}." for i in range(80)), encoding="utf-8")
    rep = run(p, tmp_path / "r.md", SETTINGS, lint_only=True, limits=Limits(max_findings=10, max_lint_per_rule=500))
    assert len(rep.findings) == 10 and any("скрыто" in w for w in rep.warnings)


def test_workers_clamped_to_eight():
    assert clamp_workers(500) == 8 and clamp_workers(0) == 1
    lock, state = threading.Lock(), {"now": 0, "max": 0}

    def work(_):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(0.05)
        with lock:
            state["now"] -= 1

    pmap(work, list(range(40)), workers=500)
    assert state["max"] <= 8


def test_pmap_cancels_queue_on_first_error():
    started = []

    def work(i):
        started.append(i)
        if i == 0:
            raise ValueError("boom")
        time.sleep(0.2)

    with pytest.raises(ValueError):
        pmap(work, list(range(30)), workers=2)
    assert len(started) < 30  # очередь отменена, не все задачи успели начаться


def test_retry_after_is_capped():
    sleeps = []

    class Err(Exception):
        status_code = 429

    attempts = []

    def fn():
        attempts.append(1)
        if len(attempts) < 2:
            raise Err("retryDelay: 99999s")
        return "ok"

    from reqcheck.llm.gemini import classify
    assert call_with_retries(fn, classify, sleep=sleeps.append, base_delay=1) == "ok"
    assert sleeps and max(sleeps) <= MAX_RETRY_AFTER


def test_lint_rules_scale_linearly(tmp_path):
    p = tmp_path / "big.md"
    n = 20000
    p.write_text("\n".join(f"см. раздел 9999.{i % 50} и далее" for i in range(n)) + "\n", encoding="utf-8")
    d = load_document(p, Limits(max_lines=10**6, max_chars=10**8))
    t = time.monotonic()
    rule_dangling_references(d, [])
    assert time.monotonic() - t < 5
    p2 = tmp_path / "units.md"
    p2.write_text("\n".join(["Сумма в тиынах." if i % 2 else "Лимит в тенге." for i in range(20000)]), encoding="utf-8")
    d2 = load_document(p2, Limits(max_lines=10**6, max_chars=10**8))
    t = time.monotonic()
    rule_mixed_units(d2, [])
    assert time.monotonic() - t < 3


def test_dedupe_scales(tmp_path):
    from tests.test_summary_render import _f

    fs = [_f("major", crit="UNA", reqs=(), q=f"цитата-{i:05d}-конец", line=i) for i in range(1500)]
    t = time.monotonic()
    out = finalize_findings(fs)
    assert len(out) == 1500 and time.monotonic() - t < 10


def test_web_limits_accept_env_overrides(monkeypatch):
    monkeypatch.setenv("REQCHECK_PARSE_MEMORY_MB", "900")
    monkeypatch.setenv("REQCHECK_PDF_LAYOUT", "0")
    lim = Limits.from_env(Limits.web())
    assert lim.parse_memory_mb == 900 and lim.pdf_layout is False
    assert lim.max_pages == Limits.web().max_pages  # остальные значения остаются веб-лимитами


def test_pdf_parses_with_layout_off_and_on(repo_root):
    pdf = repo_root / "examples" / "input" / "requirements.pdf"
    off = load_document(pdf, Limits(sandbox=False, pdf_layout=False))
    on = load_document(pdf, Limits(sandbox=False, pdf_layout=True))
    assert any("Ф-3" in line for line in off.lines) and any("Ф-3" in line for line in on.lines)
    assert abs(len(off.lines) - len(on.lines)) <= 3
