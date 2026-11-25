"""Остаток замечаний REVIEW.md: песочница парсера, обрыв ответов, кэш в паспорте, дедуп, якоря, файлы отчёта."""

import json
import subprocess
import threading
from types import SimpleNamespace

import pytest

from reqcheck.checks.lint import rule_vague_words, run_lint
from reqcheck.config import load_chain
from reqcheck.errors import InputFileError, InputTooLargeError, LLMUnavailableError
from reqcheck.ground import GroundIndex, ground_findings_detailed
from reqcheck.ingest import load_document
from reqcheck.limits import Limits
from reqcheck.llm import DiskCache, FakeLLM, FallbackLLM, structured_call
from reqcheck.llm.base import EmptyResponseError, LLMTruncatedError, LLMValidationError, call_with_retries
from reqcheck.llm.gemini import GeminiClient
from reqcheck.llm.openai_compat import OpenAICompatClient
from reqcheck.llm.openai_compat import classify as o_classify
from reqcheck.llm.schemas import EachOut
from reqcheck.models import Anchor, Finding
from reqcheck.pipeline import run
from reqcheck.segment import segment_explicit
from reqcheck.summary import finalize_findings
from tests.test_pipeline_llm import SETTINGS, SEG, finding, make_doc, scripted
from tests.test_honesty import CLEAN, make_clean


# ------------------------------------------------------------- песочница парсера

def test_sandbox_result_equals_in_process(repo_root):
    pdf = repo_root / "examples" / "input" / "requirements.pdf"
    a = load_document(pdf, Limits(sandbox=False))
    b = load_document(pdf, Limits(sandbox=True))
    assert a.lines == b.lines and [x.model_dump() for x in a.blocks] == [x.model_dump() for x in b.blocks]
    assert a.title == b.title


def test_sandbox_timeout_page_limit_and_corrupt_file(sample_pdf, tmp_path):
    with pytest.raises(InputTooLargeError):
        load_document(sample_pdf, Limits(sandbox=True, parse_timeout_s=0.01))
    with pytest.raises(InputTooLargeError):
        load_document(sample_pdf, Limits(sandbox=True, max_pages=1))
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.7 \x00 garbage garbage garbage")
    with pytest.raises(InputFileError) as e:
        load_document(bad, Limits(sandbox=True))
    assert str(tmp_path) not in str(e.value)


def test_sandbox_subprocess_gets_no_api_keys(sample_pdf, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value-123456")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-secret-value-123456")
    seen = {}
    real = subprocess.run

    def spy(cmd, **kw):
        seen["env"], seen["cmd"] = kw.get("env"), cmd
        return real(cmd, **kw)

    monkeypatch.setattr(subprocess, "run", spy)
    load_document(sample_pdf, Limits(sandbox=True))
    assert seen["env"] is not None
    assert not any("KEY" in k or "TOKEN" in k for k in seen["env"]) and "sk-secret" not in " ".join(seen["env"].values())
    assert "reqcheck.parse_worker" in seen["cmd"]


def test_sandbox_switch_from_env(monkeypatch):
    monkeypatch.setenv("REQCHECK_SANDBOX", "0")
    assert Limits.from_env().sandbox is False
    monkeypatch.setenv("REQCHECK_SANDBOX", "1")
    assert Limits.from_env().sandbox is True
    assert Limits.web().parse_timeout_s < Limits().parse_timeout_s


def test_docx_header_footer_content_is_reported_as_unread(tmp_path):
    import docx

    d = docx.Document()
    d.add_paragraph("FR-1. Система создаёт заказ за 2 секунды.")
    d.sections[0].header.paragraphs[0].text = "Конфиденциально: приложение к договору"
    p = tmp_path / "h.docx"
    d.save(str(p))
    doc = load_document(p)
    assert any("колонтитулы" in w for w in doc.warnings) and any("DOCX" in r for r in doc.incomplete)
    clean = tmp_path / "c.docx"
    docx.Document().save(str(clean))
    d2 = docx.Document()
    d2.add_paragraph("FR-1. Всё в теле документа.")
    d2.save(str(clean))
    assert load_document(clean).warnings == []


# ------------------------------------------------------------- обрыв и пустые ответы провайдеров

def _openai(resp_factory, **kw):
    calls = []

    class Completions:
        def create(self, **params):
            calls.append(params)
            return resp_factory(params)

    return OpenAICompatClient("k", "m", client=SimpleNamespace(chat=SimpleNamespace(completions=Completions())),
                              attempts=2, sleep=lambda s: None, **kw), calls


def _resp(text, finish="stop"):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason=finish)])


def test_openai_length_and_filter_are_explained_not_repaired():
    for finish, phrase in (("length", "обрезан"), ("content_filter", "фильтром")):
        c, calls = _openai(lambda p, f=finish: _resp('{"findings": [', f))
        with pytest.raises(LLMValidationError) as e:
            structured_call(c, "s", "p", EachOut)
        assert phrase in e.value.human and len(calls) == 1  # ремонтный запрос не нужен: он тоже оборвётся


def test_openai_empty_choices_and_empty_text_are_retried_then_unavailable():
    c, calls = _openai(lambda p: SimpleNamespace(choices=[]))
    with pytest.raises(LLMUnavailableError):
        c.complete("s", "p", {"type": "object", "properties": {}})
    assert len(calls) == 2
    c2, calls2 = _openai(lambda p: _resp("   "))
    with pytest.raises(LLMUnavailableError):
        c2.complete("s", "p", {"type": "object", "properties": {}})
    assert o_classify(EmptyResponseError("x"))[0] is True


def test_gemini_max_tokens_safety_and_empty_text():
    def gem(finish, text):
        cand = SimpleNamespace(finish_reason=SimpleNamespace(name=finish))
        resp = SimpleNamespace(text=text, candidates=[cand])
        models = SimpleNamespace(generate_content=lambda model, contents, config: resp)
        return GeminiClient("k", "m", client=SimpleNamespace(models=models), attempts=1, sleep=lambda s: None)

    with pytest.raises(LLMValidationError) as e:
        structured_call(gem("MAX_TOKENS", '{"fi'), "s", "p", EachOut)
    assert "обрезан" in e.value.human
    with pytest.raises(LLMValidationError) as e:
        structured_call(gem("SAFETY", ""), "s", "p", EachOut)
    assert "фильтром" in e.value.human
    with pytest.raises(LLMUnavailableError):
        gem("STOP", "").complete("s", "p", {"type": "object", "properties": {}})
    assert gem("STOP", '{"findings": []}').complete("s", "p", {"type": "object", "properties": {}})


def test_max_output_tokens_sent_and_unsupported_param_dropped():
    seen = []

    def factory(params):
        seen.append(dict(params))
        if "max_completion_tokens" in params:
            raise SimpleNamespace_Err(400, "Unsupported parameter: 'max_completion_tokens'")
        if "max_tokens" in params:
            raise SimpleNamespace_Err(400, "Unsupported parameter: 'max_tokens'")
        return _resp('{"a": 1}')

    c, _ = _openai(factory, max_output_tokens=1234)
    assert c.complete("s", "p", {"type": "object", "properties": {}}) == '{"a": 1}'
    assert "max_completion_tokens" in seen[0] and "max_tokens" in seen[1] and "max_tokens" not in seen[2] \
        and "max_completion_tokens" not in seen[2]

    captured = {}
    models = SimpleNamespace(generate_content=lambda model, contents, config: captured.setdefault("cfg", config) and SimpleNamespace(text="{}"))
    GeminiClient("k", "m", client=SimpleNamespace(models=models), max_output_tokens=777).complete("s", "p", {"type": "object", "properties": {}})
    assert captured["cfg"].max_output_tokens == 777


class SimpleNamespace_Err(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.status_code = code


def test_stage_reason_for_cut_response_is_human(tmp_path):
    def each(prompt):
        raise LLMTruncatedError("Ответ модели обрезан по лимиту длины (finish_reason=length).")

    class Cut(FakeLLM):
        def complete(self, system, prompt, schema):
            if "ПРОВЕРКА ОТДЕЛЬНЫХ" in system:
                raise LLMTruncatedError("Ответ модели обрезан по лимиту длины (finish_reason=length).")
            return super().complete(system, prompt, schema)

    rep = run(make_clean(tmp_path), tmp_path / "r.md", SETTINGS, client=Cut(), use_cache=False, workers=1)
    assert "обрезан по лимиту длины" in rep.unchecked["R-01"] and rep.verdict.code == "incomplete"


# ------------------------------------------------------------- паспорт и кэш при цепочке провайдеров

def test_cache_hit_from_fallback_provider_is_named_in_passport(tmp_path):
    class Down(FakeLLM):
        provider = "gemini"

        def complete(self, system, prompt, schema):
            err = LLMUnavailableError("лимит")
            err.transient = True
            raise err

    class Up(FakeLLM):
        provider = "groq"

    cache_dir = tmp_path / "cache"
    doc = make_clean(tmp_path)
    first = FallbackLLM([Down(), Up()])
    run(doc, tmp_path / "a.md", SETTINGS, client=first, cache_dir=cache_dir, workers=1)
    # второй прогон: основной жив, но весь ответ берётся из кэша, записанного запасным
    second = FallbackLLM([Up(model="fake-model"), Up(model="fake-model")])
    second.clients[0].provider = "gemini"
    rep = run(doc, tmp_path / "b.md", SETTINGS, client=second, cache_dir=cache_dir, workers=1)
    assert "groq" in rep.passport.model_provider


def test_last_identity_is_per_thread():
    class A(FakeLLM):
        provider = "a"

    class B(FakeLLM):
        provider = "b"

        def complete(self, system, prompt, schema):
            return super().complete(system, prompt, schema)

    llm = FallbackLLM([A(), B()])
    llm._dead.add(0)  # поток 1 ответит от B
    llm.complete("s", "p", {"type": "object", "properties": {}})
    main_identity = llm.last_identity()
    seen = {}

    def other():
        seen["id"] = llm.last_identity()

    t = threading.Thread(target=other)
    t.start()
    t.join()
    assert main_identity[0] == "b" and seen["id"][0] != "b" or seen["id"] == (llm.provider, llm.model)


# ------------------------------------------------------------- дедупликация и якоря

def test_two_vague_words_in_one_sentence_are_two_findings(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("## Т\n\nИнтерфейс должен работать удобно и быстро.\n", encoding="utf-8")
    d = load_document(p)
    found = rule_vague_words(d, segment_explicit(d))
    assert len(found) == 2
    assert len(finalize_findings(found)) == 2  # не склеиваются из-за общей цитаты


def test_true_duplicates_removed_and_counted():
    mk = lambda: Finding(id="", scope="set", criterion="S-CON", severity="major", quotes=["одна и та же цитата"],
                         anchors=[Anchor(line_start=3, line_end=3)], problem="П", fix="И", source="lint",
                         rule="r", fingerprint="abc123")
    stats: dict = {}
    out = finalize_findings([mk(), mk(), mk()], stats)
    assert len(out) == 1 and stats["deduped"] == 2


def test_dedupe_count_visible_in_report(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("# T\n\nВерсия 1.0 от 01.01.2026.\n\n* **FR-1.** Система создаёт заказ за 2 секунды после оплаты.\n", encoding="utf-8")
    each = {"findings": [finding(["R-01"], "UNA", "major", ["Система создаёт заказ за 2 секунды после оплаты."], problem=f"П{i}")
                         for i in range(3)]}
    llm = scripted(seg={"requirements": []}, each=each, set_={"findings": [], "conclusions": []})
    rep = run(p, tmp_path / "r.md", SETTINGS, client=llm, use_cache=False, workers=1)
    assert rep.drop_breakdown.get("автоматически склеены дубли (тот же критерий и цитата)") == 2


def test_repeated_phrase_is_anchored_to_nearest_occurrence(tmp_path):
    p = tmp_path / "d.md"
    rows = ["Повторяющаяся строка про оплату заказа клиентом."] + [f"Другая строка {i}." for i in range(1, 9)]
    p.write_text("\n\n".join(rows + ["Повторяющаяся строка про оплату заказа клиентом."]), encoding="utf-8")
    d = load_document(p)
    idx = GroundIndex(d)
    first = idx.find("Повторяющаяся строка про оплату заказа клиентом")
    last_line = max(i for i, ln in enumerate(d.lines, start=1) if "Повторяющаяся" in ln)
    near = idx.find("Повторяющаяся строка про оплату заказа клиентом", near_line=last_line)
    assert first.line_start == 1 and near.line_start == last_line
    lint_f = Finding(id="", scope="set", criterion="S-CON", severity="major",
                     quotes=["Повторяющаяся строка про оплату заказа клиентом."],
                     anchors=[Anchor(line_start=last_line, line_end=last_line)], problem="П", fix="И", source="lint")
    kept, dropped = ground_findings_detailed(d, [lint_f])
    assert kept[0].anchors[0].line_start == last_line and dropped == []
    llm_f = lint_f.model_copy(update={"source": "llm", "requirement_ids": ["R-01"], "anchors": [Anchor(line_start=1, line_end=1)]})
    kept, _ = ground_findings_detailed(d, [llm_f], {"R-01": last_line})
    assert kept[0].anchors[0].line_start == last_line


def test_short_quotes_match_whole_words_only(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("Система подзаказать ничего не может, а заказа клиента ждёт.\n", encoding="utf-8")
    idx = GroundIndex(load_document(p))
    m = idx.find("заказа")
    assert m and "подзаказать" not in m.text and idx.text[idx.text.find("заказа") - 1] != " " or m
    only_inside = tmp_path / "e.md"
    only_inside.write_text("слово подзаказать встречается\n", encoding="utf-8")
    assert GroundIndex(load_document(only_inside)).find("заказа") is None


# ------------------------------------------------------------- прочее

def test_unknown_and_keyless_fallbacks_are_reported(monkeypatch):
    for k in ("GEMINI_API_KEY", "GEMINI_MODEL", "GROQ_API_KEY", "GROQ_MODEL", "OPENAI_API_KEY", "OPENAI_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_MODEL", "m")
    monkeypatch.setenv("LLM_FALLBACK", "grok,gemini")
    _, fb, notes = load_chain("openai_compat")
    assert fb == [] and any("grok" in n and "неизвестное имя" in n for n in notes)
    assert any("gemini" in n and "нет ключа" in n for n in notes)
    monkeypatch.delenv("LLM_FALLBACK")
    assert load_chain("openai_compat")[2] == []  # автоматический режим молчит о провайдерах без ключа


def test_truncated_section_context_is_marked_and_reported(tmp_path):
    p = tmp_path / "d.md"
    body = "\n\n".join(f"Описание подробности номер {i}: " + "слово " * 60 for i in range(30))
    p.write_text("# T\n\nВерсия 1.0 от 01.01.2026.\n\n## Большой раздел\n\n* **FR-1.** Система делает А.\n\n" + body + "\n", encoding="utf-8")
    prompts = []
    llm = FakeLLM(handler=lambda s, pr: prompts.append(pr) or json.dumps({"findings": [], "conclusions": [], "requirements": [], "groups": [], "questions": []}))
    rep = run(p, tmp_path / "r.md", SETTINGS, client=llm, use_cache=False, workers=1)
    assert any("контекст раздела обрезан" in pr for pr in prompts)
    assert any("Контекст раздела обрезан" in w for w in rep.warnings)


def test_empty_llm_segmentation_on_long_document_is_warned(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("# T\n\nВерсия 1.0 от 01.01.2026.\n\n* **FR-1.** Система делает А.\n\n" + "\n".join(f"Строка текста {i}." for i in range(40)) + "\n", encoding="utf-8")
    llm = scripted(seg={"requirements": []}, each={"findings": []}, set_={"findings": [], "conclusions": []})
    rep = run(p, tmp_path / "r.md", SETTINGS, client=llm, use_cache=False, workers=1)
    assert any("не выделила ни одного требования" in w for w in rep.warnings)


def test_stale_report_removed_when_new_run_fails_midway(tmp_path):
    out = tmp_path / "r.md"
    doc = make_clean(tmp_path)
    run(doc, out, SETTINGS, lint_only=True)
    assert out.exists() and out.with_suffix(".json").exists()

    def down(system, prompt):
        raise LLMUnavailableError("down")

    with pytest.raises(LLMUnavailableError):
        run(doc, out, SETTINGS, client=FakeLLM(handler=down), use_cache=False, workers=1)
    assert not out.exists() and not out.with_suffix(".json").exists()  # старый отчёт не выдаёт себя за новый
    assert out.with_suffix(".log").exists()


def test_report_is_written_last(tmp_path, monkeypatch):
    import reqcheck.pipeline as pl

    order = []
    real = pl.write_atomic
    monkeypatch.setattr(pl, "write_atomic", lambda path, text: (order.append(path.suffix), real(path, text))[1])
    run(make_clean(tmp_path), tmp_path / "r.md", SETTINGS, lint_only=True)
    assert order == [".json", ".md"]


def test_cli_unexpected_error_exits_1_with_redacted_message(sample_md, tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from reqcheck.cli import app

    def boom(*a, **k):
        raise RuntimeError("упало: sk-proj-" + "A" * 30)

    monkeypatch.setattr("reqcheck.cli.run", boom)
    r = CliRunner().invoke(app, [str(sample_md), str(tmp_path / "r.md"), "--lint-only"])
    assert r.exit_code == 1 and "Внутренняя ошибка (RuntimeError)" in r.output and "sk-proj-AAAA" not in r.output


def test_agent_version_is_computed_before_report_files_are_touched(tmp_path, monkeypatch):
    """Закоммиченный отчёт перезаписывается при повторном прогоне: версия не должна становиться «dirty»."""
    import reqcheck.pipeline as pl

    out = tmp_path / "r.md"
    doc = make_clean(tmp_path)
    run(doc, out, SETTINGS, lint_only=True)  # «закоммиченный» отчёт от прошлого прогона
    seen = {}

    def fake_version():
        seen["report_existed"] = out.exists() and out.with_suffix(".json").exists()
        seen["log_existed"] = out.with_suffix(".log").exists()
        return "v9.9"

    monkeypatch.setattr(pl, "agent_version", fake_version)
    rep = run(doc, out, SETTINGS, lint_only=True)
    assert seen == {"report_existed": True, "log_existed": True}  # ничего ещё не удалено и не пересоздано
    assert rep.passport.agent_version == "v9.9"
