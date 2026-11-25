"""check_each: проверка отдельных требований (батчи ≤5 в пределах одного раздела)."""

from __future__ import annotations

import logging

from reqcheck.criteria import REQUIREMENT_CODES
from reqcheck.llm.base import LLMClient, LLMValidationError, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.schemas import EachOut
from reqcheck.models import Anchor, Document, Finding, Requirement
from reqcheck.prompting import document_block, system_prompt

log = logging.getLogger("reqcheck.each")
BATCH = 5
CONTEXT_CHARS = 3500


def batches(reqs: list[Requirement], size: int = BATCH) -> list[list[Requirement]]:
    out: list[list[Requirement]] = []
    for r in reqs:
        if out and len(out[-1]) < size and out[-1][-1].anchor.section == r.anchor.section:
            out[-1].append(r)
        else:
            out.append([r])
    return out


def section_context(doc: Document, section: str) -> str:
    parts, size = [], 0
    for b in doc.blocks:
        if b.anchor.section == section:
            if size + len(b.text) > CONTEXT_CHARS:
                break
            parts.append(b.text)
            size += len(b.text) + 1
    return "\n".join(parts)


def check_each(
    doc: Document, reqs: list[Requirement], client: LLMClient, cache: DiskCache | None = None,
) -> tuple[list[Finding], dict[str, str]]:
    """Вернуть (замечания без якорей-проверки, {R-xx: причина «не проверено»})."""
    system = system_prompt("check_each", "requirement")
    findings: list[Finding] = []
    unchecked: dict[str, str] = {}
    for batch in batches(reqs):
        ids = {r.id for r in batch}
        section = batch[0].anchor.section or "(без раздела)"
        listing = "\n".join(
            f"{r.id} [{r.source_id or '—'}] ({r.kind}): {r.quote}" for r in batch)
        prompt = (f"Раздел документа: «{section}»\n\nКонтекст раздела:\n"
                  f"{document_block(section_context(doc, batch[0].anchor.section))}\n\n"
                  f"Требования для проверки:\n{listing}")
        try:
            out = structured_call(client, system, prompt, EachOut, cache)
        except LLMValidationError as exc:
            reason = "ответ модели не прошёл проверку схемы даже после повторного запроса"
            log.error("check_each: %s для %s: %s", reason, sorted(ids), exc)
            for rid in ids:
                unchecked[rid] = reason
            continue
        for lf in out.findings:
            rids = [i for i in lf.requirement_ids if i in ids]
            if len(rids) != len(lf.requirement_ids):
                log.warning("check_each: ID вне батча %s отброшены",
                            [i for i in lf.requirement_ids if i not in ids])
            if not rids:
                rids = [batch[0].id] if len(batch) == 1 else []
            if not rids or lf.criterion not in REQUIREMENT_CODES:
                log.warning("check_each: замечание отброшено (ids=%s, criterion=%s)",
                            lf.requirement_ids, lf.criterion)
                continue
            findings.append(Finding(
                id="", scope="requirement", requirement_ids=rids, criterion=lf.criterion,
                severity=lf.severity, quotes=lf.quotes, anchors=[Anchor(line_start=1, line_end=1)],
                problem=lf.problem, fix=lf.fix, question=lf.question, source="llm"))
    return findings, unchecked
