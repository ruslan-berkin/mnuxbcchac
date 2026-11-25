from pathlib import Path

from reqcheck.models import Anchor, Finding, Report, Requirement, RunPassport, Verdict
from reqcheck.render import SECTION_TITLES, render_report
from reqcheck.summary import compute_verdict, finalize_findings, top_priorities


def _f(sev="minor", crit="UNA", reqs=("R-01",), line=1, q="цитата", question="Вопрос?", scope=None):
    return Finding(id="", scope=scope or ("requirement" if reqs else "set"),
                   requirement_ids=list(reqs), criterion=crit, severity=sev, quotes=[q],
                   anchors=[Anchor(section="Раздел", line_start=line, line_end=line)],
                   problem="Проблема", fix="Исправить", question=question, source="lint", rule="r")


def test_verdict_rules():
    assert compute_verdict([_f("critical")], "full").code == "blocked"
    assert compute_verdict([_f("major"), _f("minor")], "full").code == "caveats"
    assert compute_verdict([_f("minor")], "full").code == "ok"
    assert compute_verdict([], "full").code == "ok"
    assert "без LLM" in compute_verdict([], "lint-only").text


def test_finalize_dedups_numbers_and_orders():
    out = finalize_findings([_f(line=5, q="b"), _f(line=2, q="a"), _f(line=2, q="a")])
    assert [f.id for f in out] == ["D-001", "D-002"]
    assert out[0].quotes == ["a"]


def test_top_priorities_by_severity_then_affected():
    fs = finalize_findings([
        _f("minor", q="m", line=1), _f("major", reqs=("R-01",), q="x", line=2),
        _f("major", reqs=("R-01", "R-02"), q="y", line=3), _f("critical", crit="VER", q="z", line=4)])
    top = top_priorities(fs, 3)
    assert [f.severity for f in top] == ["critical", "major", "major"]
    assert len(top[1].requirement_ids) == 2


def make_report(mode="full", findings=None, unchecked=None):
    reqs = [Requirement(id="R-01", source_id="Ф-1", kind="functional", quote="Ф-1. Текст | с чертой",
                        summary="Текст", anchor=Anchor(section="Раздел", page=1, line_start=1, line_end=1)),
            Requirement(id="R-02", source_id=None, kind="other", quote="Без номера",
                        summary="Без номера", anchor=Anchor(line_start=3, line_end=4))]
    fs = finalize_findings(findings if findings is not None else [
        _f("critical", crit="VER"), _f("major", crit="S-CON", reqs=("R-01", "R-02"), scope="set", line=3, q="q2"),
        _f("minor", crit="S-CMP", reqs=(), line=4, q="q3")])
    return Report(
        passport=RunPassport(document_title="Док", document_path="x.pdf", document_sha256="a" * 64,
                             run_datetime="2026-01-01T00:00:00+05:00", model_provider="fake",
                             model_id="fake-model", agent_version="v0-test", llm_mode=mode),
        requirements=reqs, findings=fs, dropped_count=2, verdict=compute_verdict(fs, mode),
        unchecked=unchecked or {}, set_conclusions={"S-TRC": "Ссылки не ведут к разделам."})


def test_render_has_eight_sections_in_order():
    text = render_report(make_report())
    import re
    found = re.findall(r"(?m)^## \d+\. (.*)$", text)
    assert found == SECTION_TITLES
    assert "Отброшено при проверке цитат: 2" in text
    assert "Нельзя начинать разработку без исправлений" in text
    assert "Ссылки не ведут к разделам." in text
    assert "Текст \\| с чертой" in text  # экранирование в таблице
    assert "без номера" in text


def test_render_unchecked_marked_not_silent():
    text = render_report(make_report(unchecked={"R-02": "невалидный JSON после повтора"}))
    assert "⏳ не проверено" in text and "невалидный JSON после повтора" in text
    assert "Не проверено из-за ошибок LLM: 1" in text


def test_render_lint_only_notes_no_llm():
    text = render_report(make_report(mode="lint-only", findings=[]))
    assert "Режим lint-only" in text and "Не оценивалось" in text


def test_fake_report_passes_self_check(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "self_check", Path(__file__).resolve().parent.parent / "scripts" / "self_check.py")
    sc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sc)
    rep = make_report()
    out = tmp_path / "r.md"
    out.write_text(render_report(rep), encoding="utf-8")
    out.with_suffix(".json").write_text(rep.model_dump_json(), encoding="utf-8")
    out.with_suffix(".log").write_text("", encoding="utf-8")
    assert sc.check_report(out) == []
    # ломаем: убираем цитату у замечания
    broken = out.read_text(encoding="utf-8").replace("  - Цитата: «цитата»", "  - Цитата:", 1)
    out.write_text(broken, encoding="utf-8")
    assert any("Цитата" in e for e in sc.check_report(out))
    # ломаем порядок разделов
    swapped = render_report(rep).replace("## 6.", "## 9.")
    out.write_text(swapped, encoding="utf-8")
    assert any("Разделы отчёта" in e for e in sc.check_report(out))
