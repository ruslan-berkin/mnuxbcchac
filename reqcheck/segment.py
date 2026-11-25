"""segment: нарезка документа на требования.

Гибрид: явные ID ищутся регулярками, остальные требования выделяет LLM.
У каждого требования обязательна цитата, которая проверяется по тексту (ground).
"""

from __future__ import annotations

import logging
import re

from reqcheck.errors import InputTooLargeError
from reqcheck.ground import ground_requirements
from reqcheck.limits import Limits
from reqcheck.llm.base import LLMClient, LLMValidationError, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.schemas import SegOut
from reqcheck.models import Anchor, Document, Requirement, RequirementKind
from reqcheck.parallel import pmap
from reqcheck.prompting import data_block, document_block, system_prompt

log = logging.getLogger("reqcheck.segment")
CHUNK_CHARS = 24000

# Начало строки: маркер списка / ячейка таблицы / жирный шрифт — затем ID.
_PREFIX = re.compile(r"^\s*(?:\|\s*)?(?:[*+•\-–]\s+|\d+[.)]\s+)?[*_]*")
_ID = re.compile(
    r"(?P<id>REQ[-_‑–]\w+(?:[.\-]\w+)*|[A-ZА-ЯЁ]{1,6}[-‑–]\d+(?:\.\d+)*)[*_]*[.:)]?[*_]*(?=\s|\||$)"
)
_NOT_IDS = {"UTF", "SHA", "ISO", "IEEE", "RFC", "HTTP", "HTTPS", "MD", "ГОСТ", "ISO/IEC", "TLS", "AES"}

_KIND_BY_PREFIX: dict[str, RequirementKind] = {
    "Ф": "functional", "ФТ": "functional", "FR": "functional", "F": "functional",
    "НФТ": "nonfunctional", "НФ": "nonfunctional", "NFR": "nonfunctional", "NF": "nonfunctional",
}  # fmt: skip


def _kind(source_id: str) -> RequirementKind:
    prefix = re.split(r"[-‑–_]", source_id, maxsplit=1)[0].upper()
    return _KIND_BY_PREFIX.get(prefix, "other")


def _match_id(line: str) -> tuple[str, str] | None:
    """Вернуть (id, текст после id) для строки, начинающейся с явного ID."""
    start = _PREFIX.match(line).end()  # type: ignore[union-attr]
    m = _ID.match(line, start)
    if not m:
        return None
    sid = m.group("id").replace("‑", "-").replace("–", "-")
    if re.split(r"[-_]", sid, maxsplit=1)[0] in _NOT_IDS:
        return None
    return sid, line[m.end():].strip(" *_|")


def _strip_marker(line: str) -> str:
    return line[re.match(r"^\s*(?:[*+•\-–]\s+)?", line).end():].rstrip()  # type: ignore[union-attr]


def segment_explicit(doc: Document) -> list[Requirement]:
    """Найти требования с явными ID. Нумерация R-01… идёт в порядке документа."""
    found: list[dict] = []
    for block in doc.blocks:
        cur: dict | None = None
        for offset, line in enumerate(block.text.split("\n")):
            line_no = block.anchor.line_start + offset
            hit = _match_id(line)
            if hit:
                cur = {"sid": hit[0], "rest": [hit[1]], "quote": [_strip_marker(line)],
                       "start": line_no, "end": line_no, "block": block}
                found.append(cur)
            elif cur is not None and line.strip():
                cur["quote"].append(line.strip())
                cur["rest"].append(line.strip())
                cur["end"] = line_no
    reqs: list[Requirement] = []
    for n, item in enumerate(found, start=1):
        a = item["block"].anchor
        summary = re.sub(r"\s+", " ", " ".join(item["rest"])).strip(" *_")
        reqs.append(Requirement(
            id=f"R-{n:02d}",
            source_id=item["sid"],
            kind=_kind(item["sid"]),
            quote=" ".join(item["quote"]),
            summary=summary[:200] + ("…" if len(summary) > 200 else ""),
            anchor=Anchor(section=a.section, page=a.page,
                          line_start=item["start"], line_end=item["end"]),
        ))
    return reqs


def _renumber(reqs: list[Requirement]) -> list[Requirement]:
    reqs = sorted(reqs, key=lambda r: (r.anchor.line_start, r.anchor.line_end))
    return [r.model_copy(update={"id": f"R-{i:02d}"}) for i, r in enumerate(reqs, start=1)]


def chunks(doc: Document, max_chars: int = CHUNK_CHARS) -> list[str]:
    """Документ целиком, если помещается; иначе по блокам (без разрыва блока)."""
    if len(doc.full_text) <= max_chars:
        return [doc.full_text]
    out: list[str] = []
    cur: list[str] = []
    size = 0
    for b in doc.blocks:
        if cur and size + len(b.text) > max_chars:
            out.append("\n".join(cur))
            cur, size = [], 0
        cur.append(b.text)
        size += len(b.text) + 1
    if cur:
        out.append("\n".join(cur))
    return out


def segment(
    doc: Document, client: LLMClient | None, cache: DiskCache | None = None, workers: int = 1,
    limits: Limits | None = None,
) -> tuple[list[Requirement], int, list[str]]:
    """Вернуть (требования R-01…, число отброшенных по цитате, предупреждения)."""
    limits = limits or Limits()
    explicit = segment_explicit(doc)
    if len(explicit) > limits.max_requirements:
        raise InputTooLargeError(
            f"В документе {len(explicit)} требований с номерами при лимите {limits.max_requirements}.")
    warnings: list[str] = []
    dropped = 0
    llm_reqs: list[Requirement] = []
    if client is not None:
        known = "\n".join(f"- {r.source_id}: {r.summary[:100]}" for r in explicit) or "(нет)"
        system = system_prompt("segment")
        def run_chunk(arg):
            n, part = arg
            prompt = (f"Уже найденные требования с номерами (не повторяй; данные):\n{data_block(known)}\n\n"
                      f"Выдели остальные требования из документа.\n\n{document_block(part)}")
            try:
                return n, structured_call(client, system, prompt, SegOut, cache)
            except LLMValidationError as exc:
                msg = f"Сегментация LLM (часть {n}) не прошла проверку схемы: {exc}"
                log.error(msg)
                warnings.append(msg + ". Требования без номеров из этой части не выделены.")
                return n, None

        for _, out in pmap(run_chunk, list(enumerate(chunks(doc), start=1)), workers):
            if out is None:
                continue
            for item in out.requirements:
                llm_reqs.append(Requirement(
                    id="", source_id=item.source_id, kind=item.kind, quote=item.quote,
                    summary=item.summary, anchor=Anchor(line_start=1, line_end=1)))
        llm_reqs, dropped = ground_requirements(doc, llm_reqs)

    taken = [(r.anchor.line_start, r.anchor.line_end) for r in explicit]
    explicit_ids = {r.source_id for r in explicit}
    merged = list(explicit)
    seen_quotes = {r.quote for r in explicit}
    for r in llm_reqs:
        overlaps = any(r.anchor.line_start <= e and s <= r.anchor.line_end for s, e in taken)
        if overlaps or r.quote in seen_quotes or (r.source_id and r.source_id in explicit_ids):
            continue
        seen_quotes.add(r.quote)
        merged.append(r)
    if len(merged) > limits.max_requirements:
        raise InputTooLargeError(
            f"Выделено {len(merged)} требований при лимите {limits.max_requirements}.")
    log.info("segment: явных %d, от LLM %d, итого %d, отброшено по цитате %d",
             len(explicit), len(merged) - len(explicit), len(merged), dropped)
    return _renumber(merged), dropped, warnings
