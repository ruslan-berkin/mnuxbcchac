"""consolidate: объединение смысловых дублей.

LLM предлагает группы замечаний об одном дефекте; код проверяет группы (общая цитата,
общее требование или соседние строки), объединяет и не теряет цитаты, требования и вопросы.
"""

from __future__ import annotations

import logging

from reqcheck.ground import normalize
from reqcheck.llm.base import LLMClient, LLMValidationError, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.schemas import ConsolidateOut
from reqcheck.models import Finding
from reqcheck.prompting import data_block, system_prompt
from reqcheck.summary import SEVERITY_RANK

log = logging.getLogger("reqcheck.consolidate")
MAX_BATCH = 150
MAX_QUOTES = 4
NEAR_LINES = 3


def _related(a: Finding, b: Finding) -> bool:
    """Группе нельзя верить на слово: связь должна быть видна в данных."""
    if set(a.requirement_ids) & set(b.requirement_ids):
        return True
    qa = [normalize(q) for q in a.quotes]
    qb = [normalize(q) for q in b.quotes]
    if any(x and y and (x in y or y in x) for x in qa for y in qb):
        return True
    return any(abs(x.line_start - y.line_start) <= NEAR_LINES for x in a.anchors for y in b.anchors)


def merge_group(group: list[Finding], primary: Finding) -> Finding:
    others = [f for f in group if f is not primary]
    reqs = list(dict.fromkeys(r for f in group for r in f.requirement_ids))
    quotes, anchors = list(primary.quotes), list(primary.anchors)
    seen = {normalize(q) for q in quotes}
    for f in others:
        for q, a in zip(f.quotes, f.anchors):
            if normalize(q) not in seen and len(quotes) < MAX_QUOTES:
                seen.add(normalize(q))
                quotes.append(q)
                anchors.append(a)
    sev = min((f.severity for f in group), key=lambda s: SEVERITY_RANK[s])
    extra_codes = [c for c in dict.fromkeys(f.criterion for f in others) if c != primary.criterion]
    problem = primary.problem
    if extra_codes:
        problem += f" Тот же дефект затрагивает критерии: {', '.join(extra_codes)}."
    question = primary.question or next((f.question for f in others if f.question), None)
    return primary.model_copy(update={
        "requirement_ids": reqs, "quotes": quotes, "anchors": anchors,
        "severity": sev, "problem": problem, "question": question})


def consolidate(
    findings: list[Finding], client: LLMClient, cache: DiskCache | None = None,
) -> tuple[list[Finding], int, list[str]]:
    """Вернуть (замечания без дублей, сколько замечаний слито, предупреждения)."""
    if len(findings) < 2:
        return findings, 0, []
    system = system_prompt("consolidate")
    by_id = {f.id: f for f in findings}
    merged_away: set[str] = set()
    replaced: dict[str, Finding] = {}
    warnings: list[str] = []
    for i in range(0, len(findings), MAX_BATCH):
        part = findings[i:i + MAX_BATCH]
        listing = "\n".join(
            f"{f.id} [{f.criterion}, {f.severity}] требования: {','.join(f.requirement_ids) or '—'} | "
            f"цитата: {f.quotes[0][:140]} | проблема: {f.problem[:220]}" for f in part)
        try:
            out = structured_call(client, system, f"Замечания (данные):\n{data_block(listing)}", ConsolidateOut, cache)
        except LLMValidationError as exc:
            log.error("consolidate: ответ не прошёл схему: %s", exc)
            warnings.append(f"Объединение дублей не выполнено: {exc.human or 'ответ модели не прошёл проверку схемы'}.")
            continue
        used: set[str] = set()
        allowed = {f.id for f in part}
        for g in out.groups:
            ids = list(dict.fromkeys(g.ids))
            if len(ids) < 2 or g.primary not in ids or any(x not in allowed or x in used for x in ids):
                log.warning("consolidate: группа %s отклонена (неверные ID)", g.ids)
                continue
            primary = by_id[g.primary]
            members = [by_id[x] for x in ids]
            if not all(m is primary or _related(primary, m) for m in members):
                log.warning("consolidate: группа %s отклонена: нет видимой связи с %s", ids, g.primary)
                continue
            used.update(ids)
            replaced[g.primary] = merge_group(members, primary)
            merged_away.update(x for x in ids if x != g.primary)
            log.info("consolidate: %s слиты в %s", [x for x in ids if x != g.primary], g.primary)
    result = [replaced.get(f.id, f) for f in findings if f.id not in merged_away]
    return result, len(merged_away), warnings
