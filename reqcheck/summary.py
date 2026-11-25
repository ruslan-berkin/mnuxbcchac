"""Детерминированные итоги: нумерация замечаний, сводка, вердикт, приоритеты."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from reqcheck.ground import normalize
from reqcheck.models import Finding, LLMMode, Report, Verdict

SEVERITY_RANK = {"critical": 0, "major": 1, "minor": 2}
SEVERITY_RU = {"critical": "критичное", "major": "существенное", "minor": "незначительное"}


CRITICAL_CODES = {"VER", "CMP", "S-CON", "S-CMP"}
MINOR_ONLY_CODES = {"CNF"}


def normalize_severity(f: Finding) -> Finding:
    """critical только для VER/CMP/S-CON/S-CMP; CNF (оформление) не выше minor."""
    sev = f.severity
    if sev == "critical" and f.criterion not in CRITICAL_CODES:
        sev = "major"
    if f.criterion in MINOR_ONLY_CODES:
        sev = "minor"
    return f if sev == f.severity else f.model_copy(update={"severity": sev})


def _same_requirements(a: Finding, b: Finding) -> bool:
    ra, rb = set(a.requirement_ids), set(b.requirement_ids)
    return not ra or not rb or bool(ra & rb)


def _dedupe(findings: list[Finding]) -> list[Finding]:
    """Дубль: тот же критерий, согласованные требования и общая цитата (одна содержит другую).

    Цитаты нормализуются один раз на замечание, сравнение идёт только внутри критерия.
    """
    kept: list[tuple[Finding, list[str]]] = []
    by_crit: dict[str, list[int]] = {}
    for f in findings:
        quotes = [q for q in (normalize(x) for x in f.quotes) if q]
        dup = next((i for i in by_crit.get(f.criterion, [])
                    if _same_requirements(f, kept[i][0])
                    and any(x in y or y in x for x in quotes for y in kept[i][1])), None)
        if dup is None:
            by_crit.setdefault(f.criterion, []).append(len(kept))
            kept.append((f, quotes))
            continue
        old = kept[dup][0]
        # оставляем более серьёзное; при равенстве предпочитаем LLM (содержательнее формулировка)
        if (SEVERITY_RANK[f.severity], f.source != "llm") < (SEVERITY_RANK[old.severity], old.source != "llm"):
            kept[dup] = (f, quotes)
    return [f for f, _ in kept]


def finalize_findings(findings: list[Finding]) -> list[Finding]:
    """Нормализация серьёзности, дедупликация, стабильная сортировка и нумерация D-001…"""
    unique = _dedupe([normalize_severity(f) for f in findings])
    unique.sort(key=lambda f: (
        f.anchors[0].line_start if f.anchors else 0, SEVERITY_RANK[f.severity], f.criterion, f.problem))
    return [f.model_copy(update={"id": f"D-{i:03d}"}) for i, f in enumerate(unique, start=1)]


def compute_verdict(findings: list[Finding], mode: LLMMode, incomplete: Sequence[str] = ()) -> Verdict:
    """Вердикт по правилам. Неполная проверка никогда не даёт «можно начинать»."""
    crit = sum(f.severity == "critical" for f in findings)
    major = sum(f.severity == "major" for f in findings)
    note = ""
    if incomplete:
        note = " Проверка неполная: " + "; ".join(list(incomplete)[:5]) + "."
    if crit:
        v = Verdict(code="blocked",
                    text=f"Нельзя начинать разработку без исправлений: критичных дефектов {crit}." + note)
    elif major:
        v = Verdict(code="caveats",
                    text=f"Можно начинать с оговорками: критичных дефектов нет, существенных замечаний {major}." + note)
    elif incomplete:
        v = Verdict(code="incomplete",
                    text="Вердикт «можно начинать» дать нельзя: проверка выполнена не полностью, "
                         "а в проверенной части критичных и существенных замечаний нет." + note)
    else:
        v = Verdict(code="ok", text="Можно начинать разработку: критичных и существенных замечаний нет.")
    if mode == "lint-only":
        v = Verdict(code=v.code if v.code != "ok" else "incomplete",
                    text=v.text + " Вердикт получен только по правилам без LLM и не заменяет полную проверку.")
    return v


def top_priorities(findings: list[Finding], n: int = 5) -> list[Finding]:
    """Что исправить в первую очередь: серьёзность, затем число затронутых требований."""
    return sorted(
        findings,
        key=lambda f: (SEVERITY_RANK[f.severity], -len(f.requirement_ids), f.id),
    )[:n]


@dataclass
class Summary:
    requirements_total: int
    findings_total: int
    by_severity: dict[str, int]
    by_criterion: dict[str, int]
    critical: list[Finding]
    dropped: int
    rejected: int
    merged: int
    requirements_with_findings: int


def build_summary(report: Report) -> Summary:
    sev = Counter(f.severity for f in report.findings)
    crit = Counter(f.criterion for f in report.findings)
    affected = {rid for f in report.findings for rid in f.requirement_ids}
    return Summary(
        requirements_total=len(report.requirements),
        findings_total=len(report.findings),
        by_severity={k: sev.get(k, 0) for k in ("critical", "major", "minor")},
        by_criterion=dict(sorted(crit.items())),
        critical=[f for f in report.findings if f.severity == "critical"],
        dropped=report.dropped_count,
        rejected=report.verifier_rejected,
        merged=report.merged_count,
        requirements_with_findings=len(affected),
    )
