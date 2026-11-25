"""verify: независимая перепроверка критичных замечаний и утверждений о противоречиях (отсев ложных)."""

from __future__ import annotations

import logging

from reqcheck.llm.base import LLMClient, LLMValidationError, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.schemas import VerifyOut
from reqcheck.models import Document, Finding
from reqcheck.prompting import document_block, system_prompt
from reqcheck.summary import SEVERITY_RANK

log = logging.getLogger("reqcheck.verify")

# Утверждения о противоречии и некорректности опасны, если ложны: проверяем их всегда.
VERIFY_CODES = {"COR", "S-CON"}


def needs_verification(f: Finding) -> bool:
    return f.source == "llm" and (f.severity == "critical" or f.criterion in VERIFY_CODES)


def verify_critical(
    doc: Document, findings: list[Finding], client: LLMClient, cache: DiskCache | None = None,
) -> tuple[list[Finding], int, list[str]]:
    """Критичные замечания и утверждения о противоречиях (COR, S-CON) от LLM проверяются отдельным запросом.

    rejected → замечание снимается; confirmed → серьёзность не выше той, что назвал проверяющий.
    Если перепроверка не удалась, замечание остаётся (не теряем найденное), с предупреждением.
    """
    system = system_prompt("verify")
    out: list[Finding] = []
    rejected = 0
    warnings: list[str] = []
    for f in findings:
        if not needs_verification(f):
            out.append(f)
            continue
        prompt = (f"Замечание {f.id} [{f.criterion}, {f.severity}]\nЦитаты:\n"
                  + "\n".join(f"- {q}" for q in f.quotes)
                  + f"\nПроблема: {f.problem}\nИсправление: {f.fix}\n\n{document_block(doc.full_text)}")
        try:
            v = structured_call(client, system, prompt, VerifyOut, cache)
        except LLMValidationError as exc:
            log.error("verify: %s не перепроверено: %s", f.id, exc)
            warnings.append(f"Критичное замечание {f.id} не удалось перепроверить: оставлено без изменений.")
            out.append(f)
            continue
        if v.verdict == "rejected":
            rejected += 1
            log.warning("verify: снято %s (%s): %s", f.id, f.criterion, v.reason[:300])
            continue
        sev = v.severity if SEVERITY_RANK[v.severity] >= SEVERITY_RANK[f.severity] else f.severity
        if sev != f.severity:
            log.info("verify: %s понижено %s → %s: %s", f.id, f.severity, sev, v.reason[:200])
        out.append(f.model_copy(update={"severity": sev}))
    return out, rejected, warnings
