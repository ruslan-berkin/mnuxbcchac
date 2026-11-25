"""Отчёт не должен выглядеть полным и чистым, если проверка неполная."""

import json
import re

import pytest
from pydantic import ValidationError

from reqcheck.checks import lint
from reqcheck.errors import LLMUnavailableError
from reqcheck.ingest import load_document
from reqcheck.llm import FakeLLM, structured_call
from reqcheck.llm.base import LLMValidationError, is_quota_exhausted
from reqcheck.llm.schemas import ConsolidateOut, EachOut, QOut, SegOut, SetOut, VerifyOut
from reqcheck.models import Finding
from reqcheck.pipeline import run
from reqcheck.summary import compute_verdict
from tests.test_pipeline_llm import SETTINGS, SEG, finding, make_doc, scripted, stage

CLEAN = "# Док\n\nВерсия 1.0 от 01.01.2026.\n\n* **FR-1.** Система создаёт заказ за 2 секунды после оплаты.\n"


def make_clean(tmp_path, text=CLEAN):
    p = tmp_path / "doc.md"
    p.write_text(text, encoding="utf-8")
    return p


@pytest.mark.parametrize("schema", [EachOut, SetOut, SegOut, QOut, ConsolidateOut, VerifyOut])
def test_schemas_reject_empty_and_foreign_json(schema):
    with pytest.raises(ValidationError):
        schema.model_validate_json("{}")
    with pytest.raises(ValidationError):
        schema.model_validate_json('{"issues": [], "findings": [], "requirements": [], "groups": [], "questions": [], '
                                   '"conclusions": [], "verdict": "confirmed"}')


def test_empty_object_from_model_goes_to_repair_then_unchecked(tmp_path):
    calls = {"each": 0}

    def each(prompt):
        calls["each"] += 1
        return "{}"

    llm = scripted(seg={"requirements": []}, each=each, set_={"findings": [], "conclusions": []})
    rep = run(make_clean(tmp_path), tmp_path / "r.md", SETTINGS, client=llm, use_cache=False, workers=1)
    assert calls["each"] == 2 and set(rep.unchecked) == {"R-01"}
    text = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert "⏳ не проверено" in text and "✅ без замечаний" not in text
    assert rep.verdict.code == "incomplete" and rep.incomplete_reasons


def test_empty_answer_is_not_cached(tmp_path):
    llm = FakeLLM(["{}", "{}"])
    from reqcheck.llm import DiskCache
    cache = DiskCache(tmp_path)
    with pytest.raises(LLMValidationError):
        structured_call(llm, "s", "p", EachOut, cache)
    assert not list(tmp_path.glob("*.json"))


def test_zero_requirements_in_full_mode_is_incomplete_not_clean(tmp_path):
    doc = make_clean(tmp_path, "# Док\n\nВерсия 1.0 от 01.01.2026.\n\nСистема создаёт заказ.\n")
    llm = scripted(seg={"requirements": []}, each={"findings": []}, set_={"findings": [], "conclusions": []})
    rep = run(doc, tmp_path / "r.md", SETTINGS, client=llm, use_cache=False, workers=1)
    text = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert rep.requirements == [] and rep.verdict.code == "incomplete"
    assert text.count("Не проверено: требования не выделены") == 8
    assert "Можно начинать разработку:" not in text


def test_failed_final_set_pass_marks_all_conclusions_unchecked(tmp_path):
    set_ = lambda prompt: "битый" if "«quality»" in prompt else {"conclusions": [], "findings": []}
    llm = scripted(seg={"requirements": []}, each={"findings": []}, set_=set_)
    rep = run(make_clean(tmp_path), tmp_path / "r.md", SETTINGS, client=llm, use_cache=False, workers=1)
    assert all(v.startswith("Не проверено") for v in rep.set_conclusions.values()) and len(rep.set_conclusions) == 8
    assert rep.verdict.code == "incomplete"


def test_verdict_never_ok_when_incomplete():
    f = lambda sev: Finding(id="D-001", scope="set", criterion="S-CON", severity=sev, quotes=["q"], anchors=[],
                            problem="p", fix="f", source="llm")
    assert compute_verdict([], "full").code == "ok"
    v = compute_verdict([], "full", ["не проверено требований: 3"])
    assert v.code == "incomplete" and "не проверено требований: 3" in v.text and "можно начинать" in v.text.lower()
    v = compute_verdict([f("major")], "full", ["x"])
    assert v.code == "caveats" and "неполная" in v.text
    v = compute_verdict([f("critical")], "full", ["x"])
    assert v.code == "blocked" and "неполная" in v.text


def test_dropped_findings_are_visible_per_requirement_and_in_summary(tmp_path):
    each = {"findings": [finding(["R-01"], "UNA", "major", ["Выдуманная цитата которой совсем нет в документе"])]}
    llm = scripted(seg={"requirements": []}, each=each, set_={"findings": [], "conclusions": []})
    rep = run(make_clean(tmp_path), tmp_path / "r.md", SETTINGS, client=llm, use_cache=False, workers=1)
    text = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert rep.dropped_by_requirement == {"R-01": 1}
    assert "замечания были, но не прошли проверку цитат (1)" in text and "✅ без замечаний" not in text
    assert "замечания: цитата не найдена в документе: 1" in text


def test_high_drop_ratio_makes_run_incomplete(tmp_path):
    fakes = [finding(["R-0%d" % i], "UNA", "major", [f"Выдуманная цитата номер {i} вовсе без следа в тексте"]) for i in range(1, 3)]
    p = make_clean(tmp_path, "# Док\n\nВерсия 1.0 от 01.01.2026.\n\n" + "\n\n".join(
        f"FR-{i}. Система делает действие {i} за 2 секунды после оплаты." for i in range(1, 7)) + "\n")
    each = {"findings": [finding([f"R-0{i}"], "UNA", "major", [f"Выдуманная цитата {i} без следа в тексте документа"]) for i in range(1, 7)]}
    llm = scripted(seg={"requirements": []}, each=each, set_={"findings": [], "conclusions": []})
    rep = run(p, tmp_path / "r.md", SETTINGS, client=llm, use_cache=False, workers=1)
    assert any("отброшено" in r and "замечаний LLM" in r for r in rep.incomplete_reasons)
    assert rep.verdict.code == "incomplete"


def test_foreign_ids_in_multi_requirement_batch_are_counted_and_batch_flagged(tmp_path):
    p = make_clean(tmp_path, "# Док\n\nВерсия 1.0 от 01.01.2026.\n\n* **FR-1.** Система делает А.\n* **FR-2.** Система делает Б.\n")
    each = {"findings": [finding(["R-99"], "UNA", "major", ["Система делает А."])]}
    llm = scripted(seg={"requirements": []}, each=each, set_={"findings": [], "conclusions": []})
    rep = run(p, tmp_path / "r.md", SETTINGS, client=llm, use_cache=False, workers=1)
    assert set(rep.unchecked) == {"R-01", "R-02"}
    assert rep.drop_breakdown["ответ модели: ID вне пачки или критерий вне списка"] == 1


def test_verifier_notes_listed_in_report(tmp_path):
    each = {"findings": [finding(["R-01"], "VER", "critical", ["Система создаёт заказ за 2 секунды после оплаты."])]}
    llm = scripted(seg={"requirements": []}, each=each, set_={"findings": [], "conclusions": []},
                   verify={"verdict": "rejected", "severity": "major", "reason": "исключение описано в Ф-2"})
    rep = run(make_clean(tmp_path), tmp_path / "r.md", SETTINGS, client=llm, use_cache=False, workers=1)
    text = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert rep.verifier_notes and "исключение описано в Ф-2" in text and "Изменено при независимой перепроверке" in text


def test_set_findings_make_requirement_status_not_clean(tmp_path):
    set_ = {"conclusions": [], "findings": [finding(["R-01"], "S-CON", "major", ["Система создаёт заказ за 2 секунды после оплаты."])]}
    llm = scripted(seg={"requirements": []}, each={"findings": []}, set_=set_)
    run(make_clean(tmp_path), tmp_path / "r.md", SETTINGS, client=llm, use_cache=False, workers=1)
    text = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert "### R-01 (FR-1): ⚠️ есть замечания к набору (раздел 4)" in text


# ---- падения на пользовательском вводе и у провайдеров

def test_dotted_capital_i_does_not_crash_ground(tmp_path):
    from reqcheck.ground import GroundIndex, normalize
    p = tmp_path / "t.md"
    p.write_text("İstanbul и ß текст ﬁnal про оплату заказа клиентом İ\n\nКонец İ\n", encoding="utf-8")
    d = load_document(p)
    idx = GroundIndex(d)
    assert len(idx.text) == len(idx.pos)
    m = idx.find("оплату заказа клиентом")
    assert m and m.text == "оплату заказа клиентом"
    assert normalize("İ") == "i"


def test_gemini_per_minute_429_is_retried_not_treated_as_quota():
    per_minute = ("429 RESOURCE_EXHAUSTED. You exceeded your current quota, please check your plan and billing "
                  "details. retryDelay: 12s")
    assert not is_quota_exhausted(Exception(per_minute))
    assert is_quota_exhausted(Exception("GenerateRequestsPerDayPerProjectPerModel-FreeTier exceeded"))
    assert is_quota_exhausted(Exception("Error code: 429 - You have no credits remaining."))
    assert is_quota_exhausted(Exception("{'code': 'insufficient_quota'}"))


def test_corrupt_or_old_schema_cache_entry_is_a_miss(tmp_path):
    from reqcheck.llm import DiskCache
    from reqcheck.llm.base import schema_fingerprint
    cache = DiskCache(tmp_path)
    llm = FakeLLM([json.dumps({"findings": []})])
    key = DiskCache.make_key(llm.provider, llm.model, "s", "p", schema_fingerprint(EachOut))
    cache.put(key, '{"устаревший": "формат"}')  # валидный JSON, но не по схеме
    assert structured_call(llm, "s", "p", EachOut, cache).findings == []
    assert len(llm.calls) == 1 and cache.get(key) == '{"findings":[]}'


def test_cache_write_failure_does_not_lose_the_paid_answer(tmp_path):
    class BrokenCache:
        namespace = ""

        def get(self, key):
            return None

        def put(self, key, response):
            raise OSError("read-only file system")

        def delete(self, key):
            pass

    llm = FakeLLM([json.dumps({"findings": []})])
    assert structured_call(llm, "s", "p", EachOut, BrokenCache()).findings == []


def test_schema_change_changes_cache_key():
    from reqcheck.llm.base import schema_fingerprint
    from pydantic import BaseModel

    class A(BaseModel):
        x: int

    class B(BaseModel):
        x: int
        y: int

    B.__name__ = "A"
    assert schema_fingerprint(A) != schema_fingerprint(B)


@pytest.mark.parametrize("stage_name,marker", [("verify", "НЕЗАВИСИМАЯ ПЕРЕПРОВЕРКА"), ("questions", "УТОЧНЯЮЩИЕ ВОПРОСЫ"),
                                               ("consolidate", "КОНСОЛИДАЦИЯ ДУБЛЕЙ")])
def test_optional_stage_outage_keeps_paid_report(tmp_path, stage_name, marker):
    each = {"findings": [finding(["R-01"], "VER", "critical", ["Система создаёт заказ за 2 секунды после оплаты."],
                                 question=None),
                         finding(["R-01"], "UNA", "major", ["Система создаёт заказ за 2 секунды после оплаты."],
                                 question=None, problem="Другая проблема")]}

    def handler(system, prompt):
        if marker in system:
            raise LLMUnavailableError("LLM недоступна")
        s = stage(system)
        data = {"segment": {"requirements": []}, "each": each, "set": {"findings": [], "conclusions": []},
                "verify": {"verdict": "confirmed", "severity": "critical", "reason": "ок"},
                "questions": {"questions": []}, "consolidate": {"groups": []}}[s]
        return json.dumps(data, ensure_ascii=False)

    rep = run(make_clean(tmp_path), tmp_path / "r.md", SETTINGS, client=FakeLLM(handler=handler), use_cache=False, workers=1)
    assert (tmp_path / "r.md").exists() and rep.findings
    assert any("не выполнен" in w and "LLM недоступна" in w for w in rep.warnings)


def test_mandatory_stage_outage_still_exits_with_5(tmp_path):
    def handler(system, prompt):
        raise LLMUnavailableError("down")

    with pytest.raises(LLMUnavailableError) as e:
        run(make_clean(tmp_path), tmp_path / "r.md", SETTINGS, client=FakeLLM(handler=handler), use_cache=False, workers=1)
    assert e.value.exit_code == 5


def test_one_broken_lint_rule_does_not_kill_the_run(tmp_path, monkeypatch):
    def boom(doc, reqs):
        raise IndexError("кривая таблица")

    monkeypatch.setattr(lint, "RULES", [boom, lint.rule_vague_words])
    p = tmp_path / "d.md"
    p.write_text("# T\n\nВерсия 1.0 от 01.01.2026.\n\nЭто быстро.\n", encoding="utf-8")
    rep = run(p, tmp_path / "r.md", SETTINGS, lint_only=True)
    assert any(f.rule == "vague_words" for f in rep.findings)
    assert any("boom" in w for w in rep.warnings)


def test_cp1251_and_utf16_files_are_decoded_with_warning(tmp_path):
    p = tmp_path / "w.txt"
    p.write_bytes("Система создаёт заказ за 2 секунды после оплаты.".encode("cp1251"))
    d = load_document(p)
    assert "Система создаёт заказ" in d.full_text and any("windows-1251" in w for w in d.warnings)
    q = tmp_path / "u.txt"
    q.write_bytes("﻿Система работает.".encode("utf-16"))
    assert "Система работает." in load_document(q).full_text
    junk = tmp_path / "j.txt"
    junk.write_bytes(bytes(range(128, 256)) * 3 + b"\x98")  # cp1251 не определена для 0x98
    from reqcheck.errors import InputFileError
    try:
        load_document(junk)
    except InputFileError:
        pass


def test_pdf_with_blank_page_and_table_failure_are_reported(tmp_path, monkeypatch):
    import pymupdf
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "FR-1. The system shall respond quickly to every request.", fontsize=11)
    doc.new_page()  # пустая страница: скан без текстового слоя
    path = tmp_path / "scan.pdf"
    doc.save(str(path))
    d = load_document(path)
    assert any("Страницы без текстового слоя: 2" in w for w in d.warnings) and d.incomplete
    rep = run(path, tmp_path / "r.md", SETTINGS, lint_only=True)
    assert any("без текстового слоя" in w for w in rep.warnings)

    def broken(self, *a, **k):
        raise RuntimeError("find_tables сломался")

    monkeypatch.setattr(pymupdf.Page, "find_tables", broken)
    d2 = load_document(path)
    assert any("Таблицы не разобраны" in w for w in d2.warnings)
