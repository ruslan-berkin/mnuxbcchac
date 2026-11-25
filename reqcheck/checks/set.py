"""check_set: перекрёстные проверки набора и полнота — несколькими узкими проходами."""

from __future__ import annotations

import logging
import re

from reqcheck.criteria import SET_CODES
from reqcheck.llm.base import LLMClient, LLMValidationError, load_prompt, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.schemas import SetOut
from reqcheck.models import Anchor, Document, Finding, Requirement
from reqcheck.prompting import document_block, system_prompt

log = logging.getLogger("reqcheck.set")


def load_lenses() -> list[tuple[str, str]]:
    """Проходы из prompts/lenses.md: «## имя» и текст до следующего заголовка."""
    parts = re.split(r"(?m)^## (\w+)\s*$", load_prompt("lenses"))
    return [(parts[i], parts[i + 1].strip()) for i in range(1, len(parts) - 1, 2)]


def _listing(reqs: list[Requirement]) -> str:
    return "\n".join(
        f"{r.id} [{r.source_id or '—'}] ({r.kind}): {r.quote}" for r in reqs) or "(нет)"


def check_set(
    doc: Document, reqs: list[Requirement], client: LLMClient, cache: DiskCache | None = None,
) -> tuple[list[Finding], dict[str, str], list[str]]:
    """Вернуть (замечания, {S-код: вывод}, предупреждения о сбоях проходов)."""
    system = system_prompt("check_set", "set")
    known = {r.id for r in reqs}
    findings: list[Finding] = []
    conclusions: dict[str, str] = {}
    warnings: list[str] = []
    lenses = load_lenses()
    for name, focus in lenses:
        already = "\n".join(f"- [{f.criterion}] {f.problem[:160]}" for f in findings) or "(пока ничего)"
        prompt = (f"Список требований, выделенных из документа (номера R-xx присвоены программой):\n"
                  f"{_listing(reqs)}\n\nФОКУС ПРОХОДА «{name}»:\n{focus}\n\n"
                  f"Уже найдено другими проходами (не повторяй):\n{already}\n\n{document_block(doc.full_text)}")
        try:
            out = structured_call(client, system, prompt, SetOut, cache)
        except LLMValidationError as exc:
            msg = f"Проход «{name}» проверки набора не выполнен: ответ модели не прошёл проверку схемы."
            log.error("%s %s", msg, exc)
            warnings.append(msg)
            continue
        added = 0
        for lf in out.findings:
            if lf.criterion not in SET_CODES:
                log.warning("check_set[%s]: код %s не из набора S-*, замечание отброшено", name, lf.criterion)
                continue
            findings.append(Finding(
                id="", scope="set", requirement_ids=[i for i in lf.requirement_ids if i in known],
                criterion=lf.criterion, severity=lf.severity, quotes=lf.quotes,
                anchors=[Anchor(line_start=1, line_end=1)], problem=lf.problem, fix=lf.fix,
                question=lf.question, source="llm"))
            added += 1
        for c in out.conclusions:
            if c.code in SET_CODES and c.conclusion.strip():
                conclusions[c.code] = c.conclusion
        log.info("check_set[%s]: замечаний %d", name, added)
    for code in SET_CODES:
        conclusions.setdefault(code, "Не проверено: сбой прохода проверки набора." if warnings
                               else "Замечаний нет.")
    return findings, conclusions, warnings
