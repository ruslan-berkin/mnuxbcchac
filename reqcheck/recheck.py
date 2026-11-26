"""Перепроверка с ответами аналитика: LLM оценивает только замечания с ответами, вердикт считает код."""

from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import BaseModel, Field

from reqcheck.llm.base import LLMClient, LLMValidationError, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.schemas import RecheckOut
from reqcheck.models import Document, Finding, Report, Verdict
from reqcheck.parallel import pmap
from reqcheck.prompting import data_block, document_block, system_prompt
from reqcheck.summary import compute_verdict

log = logging.getLogger("reqcheck.recheck")

MAX_ANSWERS = 30
MAX_ANSWER_CHARS = 1000
BATCH = 8
Status = Literal["resolved", "partial", "open"]


class RecheckItem(BaseModel):
    finding_id: str
    status: Status
    reason: str


class RecheckResult(BaseModel):
    items: list[RecheckItem]
    verdict_before: Verdict
    verdict_after: Verdict
    skipped: list[str] = Field(default_factory=list)  # ответы без соответствующего замечания или сверх лимита


_ANSWER_LINE = re.compile(r"^\s*(?:[-*]\s*)?(D-\d{3,4})\s*[:：—-]\s*(.*)$")


def parse_answers(text: str) -> dict[str, str]:
    """Формат: «D-013: ответ»; строки без номера продолжают предыдущий ответ."""
    answers: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        m = _ANSWER_LINE.match(line)
        if m:
            current = m.group(1)
            answers[current] = m.group(2).strip()
        elif current and line.strip() and not line.lstrip().startswith("#"):
            answers[current] = f"{answers[current]} {line.strip()}".strip()
    return {k: v for k, v in answers.items() if v}


def recheck(
    report: Report, doc: Document, answers: dict[str, str], client: LLMClient,
    cache: DiskCache | None = None, workers: int = 1,
) -> RecheckResult:
    by_id = {f.id: f for f in report.findings}
    given = {k: v.strip()[:MAX_ANSWER_CHARS] for k, v in answers.items() if v and v.strip()}
    targets = [by_id[k] for k in sorted(given) if k in by_id]
    skipped = sorted(set(given) - set(by_id)) + [f.id for f in targets[MAX_ANSWERS:]]
    targets = targets[:MAX_ANSWERS]
    system = system_prompt("recheck")

    def run_batch(batch: list[Finding]) -> list[RecheckItem]:
        listing = "\n\n".join(
            f"{f.id} [{f.criterion}, {f.severity}]\nЦитаты: " + " | ".join(f.quotes) +
            f"\nПроблема: {f.problem}\nВопрос: {f.question or '—'}\nОтвет аналитика: {given[f.id]}"
            for f in batch)
        prompt = f"Замечания и ответы (данные):\n{data_block(listing)}\n\n{document_block(doc.full_text)}"
        try:
            out = structured_call(client, system, prompt, RecheckOut, cache)
        except LLMValidationError as exc:
            log.error("recheck: ответ не прошёл схему: %s", exc)
            return [RecheckItem(finding_id=f.id, status="open",
                                reason="Не удалось проверить: " + (exc.human or "ответ модели не по формату."))
                    for f in batch]
        got = {i.finding_id: i for i in out.items}
        return [
            RecheckItem(finding_id=f.id, status=got[f.id].status, reason=got[f.id].reason)
            if f.id in got else
            RecheckItem(finding_id=f.id, status="open", reason="Модель не вернула оценку этого замечания.")
            for f in batch
        ]

    batches = [targets[i : i + BATCH] for i in range(0, len(targets), BATCH)]
    items = [item for part in pmap(run_batch, batches, workers) for item in part]
    closed = {i.finding_id for i in items if i.status == "resolved"}
    # partial и open остаются с прежней серьёзностью: вердикт улучшают только закрытые замечания
    remaining = [f for f in report.findings if f.id not in closed]
    after = compute_verdict(remaining, report.passport.llm_mode, report.incomplete_reasons)
    return RecheckResult(items=items, verdict_before=report.verdict, verdict_after=after, skipped=skipped)


def render_recheck(result: RecheckResult) -> str:
    """Короткий Markdown с результатом (рядом с отчётом)."""
    from reqcheck.render import inline

    names = {"resolved": "закрыто", "partial": "частично", "open": "осталось"}
    lines = ["# Перепроверка с ответами аналитика", "",
             f"**Вердикт было:** {inline(result.verdict_before.text)}", "",
             f"**Вердикт стало:** {inline(result.verdict_after.text)}", "",
             "| Замечание | Статус | Причина |", "| :--- | :--- | :--- |"]
    lines += [f"| {i.finding_id} | {names[i.status]} | {inline(i.reason).replace('|', '/')} |" for i in result.items]
    if result.skipped:
        lines += ["", "Не проверялись (нет такого замечания или сверх лимита): " + ", ".join(result.skipped) + "."]
    return "\n".join(lines) + "\n"
