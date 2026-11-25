"""check_set: перекрёстные проверки набора и полнота — несколькими узкими проходами."""

from __future__ import annotations

import logging
import re

from reqcheck.criteria import SET_CODES
from reqcheck.llm.base import LLMClient, LLMValidationError, load_prompt, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.schemas import SetOut
from reqcheck.models import Anchor, Document, Finding, Requirement
from reqcheck.parallel import pmap
from reqcheck.prompting import data_block, document_block, system_prompt

log = logging.getLogger("reqcheck.set")


def load_lenses() -> list[tuple[str, str]]:
    """Проходы из prompts/lenses.md: «## имя» и текст до следующего заголовка."""
    parts = re.split(r"(?m)^## (\w+)\s*$", load_prompt("lenses"))
    return [(parts[i], parts[i + 1].strip()) for i in range(1, len(parts) - 1, 2)]


def _listing(reqs: list[Requirement]) -> str:
    return "\n".join(
        f"{r.id} [{r.source_id or '—'}] ({r.kind}): {r.quote}" for r in reqs) or "(нет)"


def _run_lens(
    name: str, focus: str, doc: Document, reqs: list[Requirement], prior: list[Finding],
    client: LLMClient, cache: DiskCache | None, system: str,
) -> tuple[list[Finding], dict[str, str], str | None]:
    known = {r.id for r in reqs}
    already = "\n".join(f"- [{f.criterion}] {f.problem[:160]}" for f in prior) or "(пока ничего)"
    prompt = (f"Список требований, выделенных из документа (номера R-xx присвоены программой; данные):\n"
              f"{data_block(_listing(reqs))}\n\nФОКУС ПРОХОДА «{name}»:\n{focus}\n\n"
              f"Уже найдено другими проходами (не повторяй; данные):\n{data_block(already)}\n\n"
              f"{document_block(doc.full_text)}")
    try:
        out = structured_call(client, system, prompt, SetOut, cache)
    except LLMValidationError as exc:
        msg = f"Проход «{name}» проверки набора не выполнен: {exc.human or 'ответ модели не прошёл проверку схемы'}."
        log.error("%s %s", msg, exc)
        return [], {}, msg
    findings: list[Finding] = []
    for lf in out.findings:
        if lf.criterion not in SET_CODES:
            log.warning("check_set[%s]: код %s не из набора S-*, замечание отброшено", name, lf.criterion)
            continue
        findings.append(Finding(
            id="", scope="set", requirement_ids=[i for i in lf.requirement_ids if i in known],
            criterion=lf.criterion, severity=lf.severity, quotes=lf.quotes,
            anchors=[Anchor(line_start=1, line_end=1)], problem=lf.problem, fix=lf.fix,
            question=lf.question, source="llm"))
    log.info("check_set[%s]: замечаний %d", name, len(findings))
    conclusions = {c.code: c.conclusion for c in out.conclusions if c.code in SET_CODES and c.conclusion.strip()}
    return findings, conclusions, None


def check_set(
    doc: Document, reqs: list[Requirement], client: LLMClient, cache: DiskCache | None = None,
    workers: int = 1,
) -> tuple[list[Finding], dict[str, str], list[str]]:
    """Вернуть (замечания, {S-код: вывод}, предупреждения о сбоях проходов).

    Первые проходы независимы и идут параллельно; последний (итоговый) видит всё найденное
    и даёт выводы по критериям, поэтому запускается после них.
    """
    system = system_prompt("check_set", "set")
    lenses = load_lenses()
    head, last = lenses[:-1], lenses[-1]
    findings: list[Finding] = []
    conclusions: dict[str, str] = {}
    warnings: list[str] = []
    results = pmap(lambda ln: _run_lens(ln[0], ln[1], doc, reqs, [], client, cache, system), head, workers)
    results.append(_run_lens(last[0], last[1], doc, reqs, [f for fs, _, _ in results for f in fs],
                             client, cache, system))
    for fs, concl, warn in results:  # порядок проходов фиксирован
        findings.extend(fs)
        conclusions.update(concl)
        if warn:
            warnings.append(warn)
    final_failed = results[-1][2] is not None
    if final_failed:  # без итогового прохода выводам по критериям верить нельзя
        conclusions = {c: "Не проверено: итоговый проход проверки набора не выполнен." for c in SET_CODES}
    return findings, conclusions, warnings
