import json

from reqcheck.consolidate import consolidate, merge_group
from reqcheck.llm import FakeLLM
from reqcheck.models import Anchor, Finding


def F(i, crit="UNA", sev="major", reqs=("R-01",), q="цитата один", line=5, question=None, problem="Проблема"):
    return Finding(id=f"D-{i:03d}", scope="requirement" if reqs else "set", requirement_ids=list(reqs),
                   criterion=crit, severity=sev, quotes=[q], anchors=[Anchor(line_start=line, line_end=line)],
                   problem=problem, fix="Исправить", question=question, source="llm")


def llm(groups):
    return FakeLLM([json.dumps({"groups": groups})])


def test_merges_same_defect_keeps_quotes_requirements_question_and_max_severity():
    a = F(1, "UNA", "major", ("R-01",), "общая фраза", question=None)
    b = F(2, "CMP", "critical", ("R-02",), "общая фраза", question="Какой статус считается проведённым?")
    out, n, w = consolidate([a, b], llm([{"ids": ["D-001", "D-002"], "primary": "D-001"}]))
    assert n == 1 and w == [] and len(out) == 1
    m = out[0]
    assert m.id == "D-001" and m.severity == "critical"
    assert m.requirement_ids == ["R-01", "R-02"]
    assert m.question == "Какой статус считается проведённым?"
    assert "CMP" in m.problem and m.criterion == "UNA"


def test_merge_adds_new_quotes_with_anchors_up_to_limit():
    a = F(1, q="фраза а", line=5)
    b = F(2, "CMP", q="фраза б", line=6)
    m = merge_group([a, b], a)
    assert m.quotes == ["фраза а", "фраза б"] and [x.line_start for x in m.anchors] == [5, 6]
    many = [F(i, "CMP", q=f"цитата {i}", line=5) for i in range(2, 9)]
    assert len(merge_group([a, *many], a).quotes) == 4


def test_unrelated_group_is_rejected_by_code():
    a = F(1, reqs=("R-01",), q="первая", line=5)
    b = F(2, "CMP", reqs=("R-09",), q="совсем другая", line=90)
    out, n, _ = consolidate([a, b], llm([{"ids": ["D-001", "D-002"], "primary": "D-001"}]))
    assert n == 0 and len(out) == 2


def test_invalid_groups_ignored():
    a, b, c = F(1), F(2, "CMP"), F(3, "VER")
    groups = [{"ids": ["D-001"], "primary": "D-001"},                 # одиночка
              {"ids": ["D-001", "D-002"], "primary": "D-003"},        # primary вне группы
              {"ids": ["D-001", "D-777"], "primary": "D-001"},        # чужой ID
              {"ids": ["D-002", "D-003"], "primary": "D-002"},        # корректная
              {"ids": ["D-003", "D-001"], "primary": "D-003"}]        # D-003 уже использован
    out, n, _ = consolidate([a, b, c], llm(groups))
    assert n == 1 and sorted(f.id for f in out) == ["D-001", "D-002"]


def test_schema_failure_keeps_everything_with_warning():
    out, n, w = consolidate([F(1), F(2, "CMP")], FakeLLM(["не json", "снова не json"]))
    assert n == 0 and len(out) == 2 and "не выполнено" in w[0]


def test_single_finding_no_call():
    fake = FakeLLM()
    out, n, _ = consolidate([F(1)], fake)
    assert out and n == 0 and fake.calls == []


def test_pipeline_reports_merged_count(tmp_path):
    from tests.test_pipeline_llm import SETTINGS, finding, make_doc, scripted
    from reqcheck.pipeline import run

    each = {"findings": [
        finding(["R-01"], "UNA", "major", ["Система создаёт заказ за 2 секунды после оплаты."]),
        finding(["R-01"], "CMP", "major", ["Система создаёт заказ за 2 секунды после оплаты."], problem="Другое слово")]}
    llm_ = scripted(seg={"requirements": []}, each=each, set_={"findings": [], "conclusions": []},
                    consolidate_=lambda p: {"groups": [{"ids": [i for i in __import__("re").findall(r"D-\d{3}", p)][:2],
                                                         "primary": __import__("re").findall(r"D-\d{3}", p)[0]}]})
    rep = run(make_doc(tmp_path), tmp_path / "r.md", SETTINGS, client=llm_, use_cache=False)
    assert rep.merged_count >= 1
    assert "Объединено дублей: " in (tmp_path / "r.md").read_text(encoding="utf-8")
    ids = [f.id for f in rep.findings]
    assert ids == [f"D-{i:03d}" for i in range(1, len(ids) + 1)]
