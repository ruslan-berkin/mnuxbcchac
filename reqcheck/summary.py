"""Детерминированные итоги: нумерация замечаний, сводка, вердикт, приоритеты."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from reqcheck.models import Finding, LLMMode, Report, Verdict

SEVERITY_RANK = {"critical": 0, "major": 1, "minor": 2}
SEVERITY_RU = {"critical": "критичное", "major": "существенное", "minor": "незначительное"}


def finalize_findings(findings: list[Finding]) -> list[Finding]:
    """Дедупликация, стабильная сортировка и сквозная нумерация D-001…"""
    seen: set[tuple] = set()
    unique: list[Finding] = []
    for f in findings:
        key = (f.rule or f.problem, f.criterion, tuple(f.quotes), tuple(f.requirement_ids))
        if key not in seen:
            seen.add(key)
            unique.append(f)
    unique.sort(key=lambda f: (
        f.anchors[0].line_start if f.anchors else 0, SEVERITY_RANK[f.severity], f.criterion))
    return [f.model_copy(update={"id": f"D-{i:03d}"}) for i, f in enumerate(unique, start=1)]


def compute_verdict(findings: list[Finding], mode: LLMMode) -> Verdict:
    crit = sum(f.severity == "critical" for f in findings)
    major = sum(f.severity == "major" for f in findings)
    if crit:
        v = Verdict(code="blocked",
                    text=f"Нельзя начинать разработку без исправлений: критичных дефектов {crit}.")
    elif major:
        v = Verdict(code="caveats",
                    text=f"Можно начинать с оговорками: критичных дефектов нет, существенных замечаний {major}.")
    else:
        v = Verdict(code="ok", text="Можно начинать разработку: критичных и существенных замечаний нет.")
    if mode == "lint-only":
        v = Verdict(code=v.code, text=v.text + " Вердикт получен только по правилам без LLM "
                    "и не заменяет полную проверку.")
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
        requirements_with_findings=len(affected),
    )
