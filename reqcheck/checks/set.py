"""check_set: перекрёстные проверки набора и полнота."""

from __future__ import annotations

import logging

from reqcheck.criteria import SET_CODES
from reqcheck.llm.base import LLMClient, LLMValidationError, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.schemas import SetOut
from reqcheck.models import Anchor, Document, Finding, Requirement
from reqcheck.prompting import document_block, system_prompt

log = logging.getLogger("reqcheck.set")


def check_set(
    doc: Document, reqs: list[Requirement], client: LLMClient, cache: DiskCache | None = None,
) -> tuple[list[Finding], dict[str, str], str | None]:
    """Вернуть (замечания, {S-код: вывод}, предупреждение при сбое этапа)."""
    system = system_prompt("check_set", "set")
    listing = "\n".join(
        f"{r.id} [{r.source_id or 'без номера'}] ({r.kind}): {r.quote}" for r in reqs) or "(нет)"
    prompt = (f"Список требований, выделенных из документа:\n{listing}\n\n"
              f"Проверь набор целиком.\n\n{document_block(doc.full_text)}")
    try:
        out = structured_call(client, system, prompt, SetOut, cache)
    except LLMValidationError as exc:
        msg = f"Проверка набора не выполнена: ответ модели не прошёл проверку схемы ({exc})."
        log.error(msg)
        return [], {c: "Не проверено: сбой этапа проверки набора." for c in SET_CODES}, msg
    known = {r.id for r in reqs}
    findings: list[Finding] = []
    for lf in out.findings:
        if lf.criterion not in SET_CODES:
            log.warning("check_set: код %s не из набора S-*, замечание отброшено", lf.criterion)
            continue
        findings.append(Finding(
            id="", scope="set", requirement_ids=[i for i in lf.requirement_ids if i in known],
            criterion=lf.criterion, severity=lf.severity, quotes=lf.quotes,
            anchors=[Anchor(line_start=1, line_end=1)], problem=lf.problem, fix=lf.fix,
            question=lf.question, source="llm"))
    conclusions = {c.code: c.conclusion for c in out.conclusions if c.code in SET_CODES}
    return findings, conclusions, None
