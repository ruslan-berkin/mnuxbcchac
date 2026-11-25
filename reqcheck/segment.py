"""segment: нарезка документа на требования.

Фаза 1: только явные ID (регулярки). Фаза 2 добавит LLM для требований без номеров.
"""

from __future__ import annotations

import re

from reqcheck.models import Anchor, Document, Requirement, RequirementKind

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
