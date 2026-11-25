import pytest

from reqcheck.checks.lint import (
    rule_conditional_phrases, rule_open_lists, rule_placeholders, rule_vague_words, run_lint,
)
from reqcheck.ingest import load_document
from reqcheck.segment import segment_explicit


def test_segment_md_ids_kinds_and_anchors(sample_md):
    doc = load_document(sample_md)
    reqs = segment_explicit(doc)
    assert [(r.id, r.source_id, r.kind) for r in reqs] == [
        ("R-01", "Ф-1", "functional"), ("R-02", "Ф-2", "functional")]
    r = reqs[0]
    assert r.quote in doc.lines[r.anchor.line_start - 1]
    assert r.anchor.section == "Функциональные требования"


@pytest.mark.parametrize("name,expected", [
    ("loyalty.md", ["FR-1", "FR-2", "FR-3", "NFR-1", "NFR-2"]),
    ("injection.md", ["REQ-001", "REQ-002", "REQ-003"]),
])
def test_segment_other_documents(fixtures, name, expected):
    reqs = segment_explicit(load_document(fixtures / name))
    assert [r.source_id for r in reqs] == expected
    assert all(r.quote and r.summary for r in reqs)


def test_segment_kinds_loyalty(fixtures):
    kinds = {r.source_id: r.kind for r in segment_explicit(load_document(fixtures / "loyalty.md"))}
    assert kinds["FR-2"] == "functional" and kinds["NFR-1"] == "nonfunctional"


def test_segment_ignores_non_ids(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("UTF-8 кодировка обязательна.\n\nSHA-256 используется для хэша.\n\nФ-1. Нормальное.\n")
    assert [r.source_id for r in segment_explicit(load_document(p))] == ["Ф-1"]


def test_segment_multiline_requirement(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("FR-1. Система делает\nчто-то важное.\nFR-2. Другое.\n")
    reqs = segment_explicit(load_document(p))
    assert reqs[0].quote == "FR-1. Система делает что-то важное."
    assert reqs[0].anchor.line_end == 2 and reqs[1].anchor.line_start == 3


def _doc(tmp_path, text):
    p = tmp_path / "t.md"
    p.write_text(text, encoding="utf-8")
    d = load_document(p)
    return d, segment_explicit(d)


def test_vague_inside_requirement_is_requirement_scope(tmp_path):
    d, reqs = _doc(tmp_path, "## Т\n\n* **Ф-1.** Система быстро отвечает. Остальное ясно.\n")
    f = rule_vague_words(d, reqs)
    assert len(f) == 1
    assert f[0].scope == "requirement" and f[0].requirement_ids == ["R-01"]
    assert f[0].criterion == "UNA" and f[0].severity == "major" and f[0].source == "lint"
    assert f[0].quotes[0].endswith("Система быстро отвечает.")
    assert f[0].quotes[0] in d.full_text and f[0].question


def test_vague_outside_requirement_is_set_scope(tmp_path):
    d, reqs = _doc(tmp_path, "## Цели\n\nИнтерфейс должен быть удобным и удобно устроенным.\n")
    f = rule_vague_words(d, reqs)
    assert [x.scope for x in f] == ["set"] and f[0].criterion == "S-CMH"
    assert f[0].requirement_ids == []


def test_vague_skips_headings_code_and_substrings(tmp_path):
    d, reqs = _doc(tmp_path, "# Быстро\n\n```\nбыстро\n```\n\nнедостаточно и безбыстро\n")
    assert rule_vague_words(d, reqs) == []


def test_open_lists_and_conditional_and_placeholders(tmp_path):
    d, reqs = _doc(tmp_path, (
        "## А\n\nПоддерживаются карты, счета и т.д.\n\n"
        "Отчёт формируется при необходимости.\n\n"
        "Раздел: TBD\n\nЗаполняются тестировщиками\n"))
    assert [f.rule for f in rule_open_lists(d, reqs)] == ["open_lists"]
    assert [f.rule for f in rule_conditional_phrases(d, reqs)] == ["conditional_phrases"]
    ph = rule_placeholders(d, reqs)
    assert len(ph) == 2 and all(f.criterion == "S-CMP" for f in ph)


def test_lint_on_other_fixtures(fixtures):
    for name, min_findings in [("loyalty.md", 3), ("injection.md", 1)]:
        d = load_document(fixtures / name)
        findings = run_lint(d, segment_explicit(d))
        assert len(findings) >= min_findings
        for f in findings:
            assert all(q in d.full_text for q in f.quotes)  # цитата дословно из документа


def test_lint_does_not_obey_injection(fixtures):
    d = load_document(fixtures / "injection.md")
    findings = run_lint(d, segment_explicit(d))
    assert any("удобным способом" in q or "по возможности" in q for f in findings for q in f.quotes)
