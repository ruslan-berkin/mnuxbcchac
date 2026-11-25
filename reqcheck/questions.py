"""Уточняющие вопросы: добить вопросы к critical/major замечаниям, где модель их не дала."""

from __future__ import annotations

import logging

from reqcheck.llm.base import LLMClient, LLMValidationError, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.schemas import QOut
from reqcheck.models import Finding
from reqcheck.prompting import system_prompt

log = logging.getLogger("reqcheck.questions")
BATCH = 10


def needs_question(f: Finding) -> bool:
    return f.severity in ("critical", "major") and not (f.question and f.question.strip())


def ensure_questions(
    findings: list[Finding], client: LLMClient, cache: DiskCache | None = None,
) -> tuple[list[Finding], list[str]]:
    todo = [f for f in findings if needs_question(f)]
    warnings: list[str] = []
    answers: dict[str, str] = {}
    system = system_prompt("questions")
    for i in range(0, len(todo), BATCH):
        part = todo[i:i + BATCH]
        listing = "\n\n".join(
            f"{f.id} [{f.criterion}, {f.severity}]\nЦитаты: " + " | ".join(f.quotes) +
            f"\nПроблема: {f.problem}" for f in part)
        try:
            out = structured_call(client, system, f"Замечания:\n\n{listing}", QOut, cache)
        except LLMValidationError as exc:
            log.error("questions: ответ не прошёл схему: %s", exc)
            warnings.append("Часть уточняющих вопросов не сформирована: ответ модели не прошёл проверку схемы.")
            continue
        ids = {f.id for f in part}
        answers.update({q.finding_id: q.question for q in out.questions if q.finding_id in ids and q.question.strip()})
    result = [f.model_copy(update={"question": answers[f.id]}) if f.id in answers else f for f in findings]
    missing = [f.id for f in result if needs_question(f)]
    if missing:
        warnings.append(f"Нет вопроса к замечаниям: {', '.join(missing)}.")
    return result, warnings
