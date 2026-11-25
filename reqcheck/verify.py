"""verify: независимая перепроверка критичных замечаний и утверждений о противоречиях (отсев ложных)."""

from __future__ import annotations

import logging

from reqcheck.llm.base import LLMClient, LLMValidationError, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.schemas import VerifyOut
from reqcheck.models import Document, Finding
from reqcheck.parallel import pmap
from reqcheck.prompting import data_block, document_block, system_prompt
from reqcheck.summary import SEVERITY_RANK

log = logging.getLogger("reqcheck.verify")

# Утверждения о противоречии и некорректности опасны, если ложны: проверяем их всегда.
VERIFY_CODES = {"COR", "S-CON"}


def needs_verification(f: Finding) -> bool:
    return f.source == "llm" and (f.severity == "critical" or f.criterion in VERIFY_CODES)


def _verify_one(f: Finding, doc: Document, client: LLMClient, cache: DiskCache | None, system: str):
    finding_text = (f"Замечание [{f.criterion}, {f.severity}]\nЦитаты:\n" + "\n".join(f"- {q}" for q in f.quotes)
                    + f"\nПроблема: {f.problem}\nИсправление: {f.fix}")
    prompt = f"Замечание для перепроверки (данные):\n{data_block(finding_text)}\n\n{document_block(doc.full_text)}"
    try:
        return structured_call(client, system, prompt, VerifyOut, cache)
    except LLMValidationError as exc:
        log.error("verify: %s не перепроверено: %s", f.id, exc)
        return None


def verify_critical(
    doc: Document, findings: list[Finding], client: LLMClient, cache: DiskCache | None = None,
    workers: int = 1, max_verified: int = 10**9,
) -> tuple[list[Finding], list[dict[str, str]], list[str]]:
    """Критичные замечания и утверждения о противоречиях (COR, S-CON) от LLM проверяются отдельным запросом.

    rejected → замечание снимается; confirmed → серьёзность не выше той, что назвал проверяющий.
    Если перепроверка не удалась, замечание остаётся (не теряем найденное), с предупреждением.
    """
    system = system_prompt("verify")
    todo = [f for f in findings if needs_verification(f)]
    skipped_over_limit = len(todo) - max_verified
    todo = todo[:max_verified]
    verdicts = dict(zip((f.id for f in todo),
                        pmap(lambda f: _verify_one(f, doc, client, cache, system), todo, workers)))
    out: list[Finding] = []
    notes: list[dict[str, str]] = []
    warnings: list[str] = []
    if skipped_over_limit > 0:
        warnings.append(f"Перепроверено {max_verified} критичных замечаний, ещё {skipped_over_limit} оставлены без перепроверки (лимит).")
    for f in findings:
        if f.id not in verdicts:
            out.append(f)
            continue
        v = verdicts[f.id]
        if v is None:
            warnings.append(f"Критичное замечание {f.id} не удалось перепроверить: оставлено без изменений.")
            out.append(f)
            continue
        if v.verdict == "rejected":
            notes.append({"action": "снято", "criterion": f.criterion, "quote": f.quotes[0][:160],
                          "reason": v.reason[:300]})
            log.warning("verify: снято %s (%s): %s", f.id, f.criterion, v.reason[:300])
            continue
        asked = v.severity or f.severity  # не назвал — оставляем исходную
        sev = asked if SEVERITY_RANK[asked] >= SEVERITY_RANK[f.severity] else f.severity
        if sev != f.severity:
            notes.append({"action": f"понижено {f.severity} → {sev}", "criterion": f.criterion,
                          "quote": f.quotes[0][:160], "reason": v.reason[:300]})
            log.info("verify: %s понижено %s → %s: %s", f.id, f.severity, sev, v.reason[:200])
        out.append(f.model_copy(update={"severity": sev}))
    return out, notes, warnings
