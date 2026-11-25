"""Детерминированные итоги: нумерация замечаний, сводка, вердикт, приоритеты."""

from __future__ import annotations

from collections import Counter
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


def _dedupe(findings: list[Finding]) -> list[Finding]:
    """Дубль: тот же критерий, те же требования и одна цитата содержит другую."""
    groups: dict[tuple, list[tuple[Finding, str]]] = {}
    kept: list[Finding] = []
    for f in findings:
        key = (f.criterion, tuple(sorted(f.requirement_ids)))
        text = normalize(" ".join(f.quotes))
        dup_of = next((g for g in groups.get(key, []) if text in g[1] or g[1] in text), None)
        if dup_of is None:
            groups.setdefault(key, []).append((f, text))
            kept.append(f)
            continue
        old = dup_of[0]
        better = (SEVERITY_RANK[f.severity], f.source != "llm") < (SEVERITY_RANK[old.severity], old.source != "llm")
        if better:
            kept[kept.index(old)] = f
            groups[key][groups[key].index(dup_of)] = (f, text)
    return kept


def finalize_findings(findings: list[Finding]) -> list[Finding]:
    """Нормализация серьёзности, дедупликация, стабильная сортировка и нумерация D-001…"""
    unique = _dedupe([normalize_severity(f) for f in findings])
    unique.sort(key=lambda f: (
        f.anchors[0].line_start if f.anchors else 0, SEVERITY_RANK[f.severity], f.criterion, f.problem))
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
