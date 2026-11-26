"""ground: каждая цитата должна реально быть в документе.

Нормализация (регистр, пробелы, кавычки, тире, ё/е, неразрывные пробелы, разметка Markdown),
затем точное совпадение, затем fuzzy (rapidfuzz, порог 90). Замечание с выдуманной
цитатой отбрасывается. Найденная цитата заменяется дословным фрагментом документа.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from reqcheck.models import Anchor, Document, Finding, Requirement

log = logging.getLogger("reqcheck.ground")

FUZZY_THRESHOLD = 90.0
MIN_FUZZY_LEN = 15
SHORT_QUOTE_LEN = 12  # короче этого искать только целыми словами
MIN_QUOTE_LEN = 6  # «при», «все» находятся в любом документе и ничего не доказывают

_QUOTES = {c: '"' for c in "«»“”„‟″'’‘`"}
_DASHES = {c: "-" for c in "‐‑‒–—―−"}
_SPACES = {c: " " for c in "       ​﻿\t"}
_MARKUP = set("*_|#")  # разметка Markdown, не часть текста


def _norm_char(ch: str) -> str:
    ch = _SPACES.get(ch, ch)
    ch = _QUOTES.get(ch, ch)
    ch = _DASHES.get(ch, ch)
    ch = ch.lower()
    if len(ch) != 1:  # «İ».lower() даёт два символа и сдвинул бы карту позиций
        ch = ch[0]
    return "е" if ch == "ё" else ch


# Модель иногда копирует в цитату служебный префикс списка из промпта: «R-01 [Ф-1] (functional): …».
_LISTING_PREFIX = re.compile(r"^\s*R-\d+\s*\[[^\]]*\]\s*\([^)]*\)\s*:\s*")


def clean_quote(quote: str) -> str:
    return _LISTING_PREFIX.sub("", quote)


def normalize(text: str) -> str:
    out: list[str] = []
    for ch in text:
        if ch in _MARKUP:
            ch = " "
        ch = _norm_char(ch)
        if ch.isspace():
            if out and out[-1] != " ":
                out.append(" ")
        else:
            out.append(ch)
    return "".join(out).strip()


@dataclass
class GroundMatch:
    method: str  # "exact" | "fuzzy"
    score: float
    line_start: int
    line_end: int
    text: str  # дословный фрагмент документа


class GroundIndex:
    """Нормализованный текст документа с отображением позиций обратно в строки."""

    def __init__(self, doc: Document, max_fuzzy: int = 300) -> None:
        self.doc = doc
        self._fuzzy_left = max_fuzzy  # fuzzy-поиск по всему документу дорог: бюджет на прогон
        chars: list[str] = []
        self.pos: list[tuple[int, int]] = []  # (индекс строки 0-based, индекс символа в строке)
        for li, line in enumerate(doc.lines):
            if chars and chars[-1] != " ":
                chars.append(" ")
                self.pos.append((li - 1 if li else 0, len(doc.lines[li - 1]) if li else 0))
            for ci, ch in enumerate(line):
                if ch in _MARKUP:
                    ch = " "
                ch = _norm_char(ch)
                if ch.isspace():
                    if chars and chars[-1] != " ":
                        chars.append(" ")
                        self.pos.append((li, ci))
                else:
                    chars.append(ch)
                    self.pos.append((li, ci))
        self.text = "".join(chars)

    def _span(self, start: int, end: int) -> tuple[int, int, str]:
        while start < end and self.text[start] == " ":
            start += 1
        while end > start and self.text[end - 1] == " ":
            end -= 1
        (l0, c0), (l1, c1) = self.pos[start], self.pos[end - 1]
        lines = self.doc.lines
        if l0 == l1:
            raw = lines[l0][c0:c1 + 1]
        else:
            raw = " ".join([lines[l0][c0:]] + lines[l0 + 1:l1] + [lines[l1][:c1 + 1]])
        return l0 + 1, l1 + 1, " ".join(raw.split())

    def _occurrences(self, nq: str) -> list[int]:
        """Позиции точных вхождений (не больше 200); короткие цитаты только по границам слов."""
        out, start = [], 0
        while len(out) < 200:
            i = self.text.find(nq, start)
            if i < 0:
                break
            start = i + 1
            if len(nq) < SHORT_QUOTE_LEN:
                before = self.text[i - 1] if i > 0 else " "
                after = self.text[i + len(nq)] if i + len(nq) < len(self.text) else " "
                if before.isalnum() or after.isalnum():
                    continue
            out.append(i)
        return out

    def find(self, quote: str, near_line: int | None = None) -> GroundMatch | None:
        """Найти цитату. Если вхождений несколько, берётся ближайшее к near_line, иначе первое."""
        nq = normalize(clean_quote(quote))
        if len(nq) < MIN_QUOTE_LEN:
            return None
        occ = self._occurrences(nq)
        if occ:
            i = occ[0] if near_line is None else min(occ, key=lambda k: abs(self.pos[k][0] + 1 - near_line))
            l0, l1, raw = self._span(i, i + len(nq))
            return GroundMatch("exact", 100.0, l0, l1, raw)
        if len(nq) < MIN_FUZZY_LEN:
            return None
        if self._fuzzy_left <= 0:
            log.warning("ground: исчерпан бюджет fuzzy-поиска, цитата %r не искалась", nq[:80])
            return None
        self._fuzzy_left -= 1
        al = fuzz.partial_ratio_alignment(nq, self.text, score_cutoff=FUZZY_THRESHOLD)
        if al is None or al.score < FUZZY_THRESHOLD or al.dest_end <= al.dest_start:
            return None
        l0, l1, raw = self._span(al.dest_start, al.dest_end)
        return GroundMatch("fuzzy", float(al.score), l0, l1, raw)

    def locate(self, quote: str, near_line: int | None = None) -> list[tuple[int, int, int]]:
        """Где именно лежит цитата: (номер строки, начало, конец) в символах строки; для подсветки в интерфейсе.

        Берётся вхождение, ближайшее к near_line. Пустой список, если точного вхождения нет.
        """
        nq = normalize(clean_quote(quote))
        if len(nq) < MIN_QUOTE_LEN:
            return []
        occ = self._occurrences(nq)
        if not occ:
            return []
        i = occ[0] if near_line is None else min(occ, key=lambda k: abs(self.pos[k][0] + 1 - near_line))
        spans: dict[int, list[int]] = {}
        for k in range(i, i + len(nq)):
            if self.text[k] == " ":
                continue
            line, col = self.pos[k]
            lo_hi = spans.setdefault(line, [col, col + 1])
            lo_hi[0] = min(lo_hi[0], col)
            lo_hi[1] = max(lo_hi[1], col + 1)
        return [(line + 1, lo, hi) for line, (lo, hi) in sorted(spans.items())]

    def anchor_for(self, line_start: int, line_end: int) -> Anchor:
        for b in self.doc.blocks:
            a = b.anchor
            if a.line_start <= line_start <= a.line_end:
                return Anchor(section=a.section, page=a.page, line_start=line_start, line_end=line_end)
        return Anchor(line_start=line_start, line_end=line_end)


def ground_findings_detailed(
    doc: Document, findings: list[Finding], req_lines: dict[str, int] | None = None
) -> tuple[list[Finding], list[Finding]]:
    """Вернуть (замечания с проверенными цитатами и якорями, отброшенные замечания)."""
    index = GroundIndex(doc)
    kept: list[Finding] = []
    dropped: list[Finding] = []
    for f in findings:
        # Повторяющаяся фраза привязывается к ближайшему вхождению: у замечаний линтера это их строка,
        # у остальных строка первого требования; иначе первое вхождение.
        if f.source == "lint" and f.anchors:
            nears = [a.line_start for a in f.anchors] + [f.anchors[0].line_start] * len(f.quotes)
        else:
            near = (req_lines or {}).get(f.requirement_ids[0]) if f.requirement_ids else None
            nears = [near] * len(f.quotes)
        matches = [index.find(q, nears[i]) for i, q in enumerate(f.quotes)] if f.quotes else []
        if not matches or any(m is None for m in matches):
            dropped.append(f)
            bad = [q for q, m in zip(f.quotes, matches) if m is None] or ["<нет цитат>"]
            log.warning("ground: отброшено замечание (%s, %s, %s): цитата не найдена в документе: %r",
                        f.source, f.criterion, ",".join(f.requirement_ids) or "набор", bad[0][:120])
            continue
        ms: list[GroundMatch] = matches  # type: ignore[assignment]
        for q, m in zip(f.quotes, ms):
            if m.method == "fuzzy":
                log.info("ground: fuzzy %.0f%% для цитаты %r", m.score, q[:80])
        kept.append(f.model_copy(update={
            "quotes": [m.text for m in ms],
            "anchors": [index.anchor_for(m.line_start, m.line_end) for m in ms],
        }))
    return kept, dropped


def ground_findings(doc: Document, findings: list[Finding]) -> tuple[list[Finding], int]:
    """Вернуть (замечания с проверенными цитатами и якорями, число отброшенных)."""
    kept, dropped = ground_findings_detailed(doc, findings)
    return kept, len(dropped)


def ground_requirements(doc: Document, reqs: list[Requirement]) -> tuple[list[Requirement], int]:
    index = GroundIndex(doc)
    kept: list[Requirement] = []
    dropped = 0
    for r in reqs:
        m = index.find(r.quote)
        if m is None:
            dropped += 1
            log.warning("ground: отброшено требование %s: цитата не найдена: %r", r.source_id or "—", r.quote[:120])
            continue
        kept.append(r.model_copy(update={
            "quote": m.text, "anchor": index.anchor_for(m.line_start, m.line_end)}))
    return kept, dropped

