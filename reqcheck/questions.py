"""Уточняющие вопросы: добить вопросы к critical/major замечаниям, где модель их не дала."""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel

from reqcheck.ground import normalize
from reqcheck.llm.base import LLMClient, LLMValidationError, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.schemas import QOut
from reqcheck.models import Finding
from reqcheck.parallel import pmap
from reqcheck.prompting import data_block, system_prompt

log = logging.getLogger("reqcheck.questions")
BATCH = 10


def needs_question(f: Finding) -> bool:
    return f.severity in ("critical", "major") and not (f.question and f.question.strip())


def _ask(part: list[Finding], client: LLMClient, cache: DiskCache | None, system: str) -> dict[str, str] | None:
    listing = "\n\n".join(
        f"{f.id} [{f.criterion}, {f.severity}]\nЦитаты: " + " | ".join(f.quotes) +
        f"\nПроблема: {f.problem}" for f in part)
    try:
        out = structured_call(client, system, f"Замечания (данные):\n{data_block(listing)}", QOut, cache)
    except LLMValidationError as exc:
        log.error("questions: ответ не прошёл схему: %s", exc)
        return None
    ids = {f.id for f in part}
    return {q.finding_id: q.question for q in out.questions if q.finding_id in ids and q.question.strip()}


def ensure_questions(
    findings: list[Finding], client: LLMClient, cache: DiskCache | None = None, workers: int = 1,
) -> tuple[list[Finding], list[str]]:
    todo = [f for f in findings if needs_question(f)]
    warnings: list[str] = []
    answers: dict[str, str] = {}
    system = system_prompt("questions")
    parts = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    for got in pmap(lambda part: _ask(part, client, cache, system), parts, workers):
        if got is None:
            warnings.append("Часть уточняющих вопросов не сформирована: ответ модели не прошёл проверку схемы или оборван.")
        else:
            answers.update(got)
    result = [f.model_copy(update={"question": answers[f.id]}) if f.id in answers else f for f in findings]
    missing = [f.id for f in result if needs_question(f)]
    if missing:
        warnings.append(f"Нет вопроса к замечаниям: {', '.join(missing)}.")
    return result, warnings


# ------------------------------------------------------------ главные (блокирующие) вопросы

_YES_NO = re.compile(r"^(?:должен|должна|должно|должны|нужно|следует|может|можно|является|требуется|будет)\b[^?]*\bли\b",
                     re.IGNORECASE)
# «…, если A или B?» — это условие вопроса, а не выбор между двумя ответами
_CONDITION = re.compile(r"^(?:если|когда|где|пока|чтобы|при условии|в случае)\b", re.IGNORECASE)
# «…ли …, и если да, по какому адресу?» — одного «Да» мало
_FOLLOW_UP = re.compile(r"\bесли (?:да|нет)\b", re.IGNORECASE)
# Две кнопки — только когда вариантов ровно два: «…: A или B?» либо «…, A или B?» с единственной запятой
_ALTERNATIVE = re.compile(r"^([^,?;]{2,60}?)\s+или\s+([^,?;]{2,60}?)\?$", re.IGNORECASE)
_LEAD = re.compile(r"[:—]")


def _two_choices(q: str) -> list[str]:
    if len(re.findall(r"\bили\b", q, re.IGNORECASE)) != 1:
        return []
    marks = list(_LEAD.finditer(q))
    if marks:
        tail = q[marks[-1].end():]
    elif q.count(",") == 1:
        tail = q.split(",", 1)[1]
    else:
        return []
    m = _ALTERNATIVE.match(tail.strip())
    if not m or _CONDITION.match(m.group(1).strip()):
        return []
    return [part.strip().capitalize() if part.strip().islower() else part.strip() for part in m.groups()]


def answer_options(question: str) -> list[str]:
    """Варианты ответа кнопками — только когда они однозначно видны в самом вопросе."""
    q = question.strip()
    if choices := _two_choices(q):
        return choices
    if _YES_NO.match(q) and " или " not in q.lower() and not _FOLLOW_UP.search(q):
        return ["Да", "Нет"]
    return []


class TopQuestion(BaseModel):
    finding_id: str
    question: str
    severity: str
    requirement_ids: list[str]
    options: list[str] = []


def _same_topic(a: Finding, b: Finding) -> bool:
    """Одна тема: общая цитата или заметно пересекающиеся требования."""
    qa = [normalize(q) for q in a.quotes]
    qb = [normalize(q) for q in b.quotes]
    if any(x and y and (x in y or y in x) for x in qa for y in qb):
        return True
    ra, rb = set(a.requirement_ids), set(b.requirement_ids)
    return bool(ra and rb) and len(ra & rb) / len(ra | rb) >= 0.5


def top_questions(findings: list[Finding], n: int = 10) -> list[TopQuestion]:
    """Блокирующие вопросы: все критичные (без них вердикт не изменить), затем существенные по одному на тему."""
    rank = {"critical": 0, "major": 1, "minor": 2}
    pool = sorted(
        (f for f in findings if f.question and f.severity in ("critical", "major")),
        key=lambda f: (rank[f.severity], -len(f.requirement_ids), f.id),
    )
    chosen: list[Finding] = []
    for f in pool:
        if f.severity != "critical" and (len(chosen) >= n or any(_same_topic(f, g) for g in chosen)):
            continue
        chosen.append(f)
    return [TopQuestion(finding_id=f.id, question=f.question or "", severity=f.severity,
                        requirement_ids=f.requirement_ids, options=answer_options(f.question or ""))
            for f in chosen]
