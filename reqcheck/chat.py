"""Чат по отчёту: документ и отчёт — данные; цитаты из документа в ответе проверяются на лету."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from typing import Literal

from pydantic import BaseModel, Field

from reqcheck.ground import GroundIndex, normalize
from reqcheck.llm.base import LLMClient
from reqcheck.models import Document, Report
from reqcheck.prompting import data_block, document_block, neutralize, system_prompt

log = logging.getLogger("reqcheck.chat")

MAX_HISTORY = 12
MAX_MESSAGE_CHARS = 2000
MAX_ANSWER_CHARS = 1000
MAX_QUOTE_HOLD = 600
MISSING_QUOTE = "[цитата не найдена в документе]"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


def report_digest(report: Report) -> str:
    """Отчёт в компактном виде для промпта."""
    lines = [f"Вердикт: {report.verdict.text}", "", "ТРЕБОВАНИЯ:"]
    lines += [f"{r.id} [{r.source_id or '—'}] {r.quote[:300]}" for r in report.requirements]
    lines += ["", "ЗАМЕЧАНИЯ:"]
    for f in report.findings:
        lines.append(
            f"{f.id} {f.severity} {f.criterion} требования: {', '.join(f.requirement_ids) or '—'} | "
            f"цитаты: {' / '.join(q[:200] for q in f.quotes[:3])} | проблема: {f.problem[:400]} | "
            f"исправление: {f.fix[:300]}" + (f" | вопрос: {f.question[:300]}" if f.question else ""))
    return "\n".join(lines)


def build_prompt(
    report: Report, doc: Document, messages: Sequence[ChatMessage], answers: dict[str, str] | None = None,
) -> str:
    history = messages[-MAX_HISTORY:]
    dialog = "\n".join(
        f"{'Аналитик' if m.role == 'user' else 'Агент'}: {neutralize(m.content[:MAX_MESSAGE_CHARS])}"
        for m in history)
    parts = [f"Отчёт о проверке (данные):\n{data_block(report_digest(report))}",
             f"Документ:\n{document_block(doc.full_text)}"]
    if answers:
        listed = "\n".join(f"{k}: {v[:MAX_ANSWER_CHARS]}" for k, v in list(answers.items())[:40])
        parts.append(f"Ответы аналитика на вопросы (данные):\n{data_block(listed)}")
    parts.append(f"Диалог (отвечай на последнюю реплику аналитика):\n{dialog}")
    return "\n\n".join(parts)


class QuoteGuard:
    """Пропускает поток текста, задерживая «цитаты» до закрывающей кавычки и проверяя их по документу."""

    def __init__(self, doc: Document) -> None:
        self.index = GroundIndex(doc, max_fuzzy=40)
        self._hold = ""
        self._depth = 0
        self._overflow = False
        self.removed = 0

    def _verified(self, inner: str) -> bool:
        parts = [p for p in inner.replace("...", "…").split("…") if p.strip()]
        for part in parts or [inner]:
            norm = normalize(part)
            if len(norm) < 6:  # короткие названия полей и обозначения
                continue
            if self.index.find(part) is None:
                return False
        return True

    def feed(self, chunk: str) -> str:
        out: list[str] = []
        for ch in chunk:
            if self._depth == 0:
                if ch == "«":
                    self._depth, self._hold, self._overflow = 1, ch, False
                else:
                    out.append(ch)
                continue
            if ch == "«":
                self._depth += 1
            elif ch == "»":
                self._depth -= 1
            if not self._overflow:
                self._hold += ch
                if len(self._hold) > MAX_QUOTE_HOLD:
                    self._overflow = True
            if self._depth == 0:
                if not self._overflow and self._verified(self._hold[1:-1]):
                    out.append(self._hold)
                else:
                    self.removed += 1
                    log.warning("chat: вырезана неподтверждённая цитата %r", self._hold[:120])
                    out.append(MISSING_QUOTE)
                self._hold = ""
        return "".join(out)

    def flush(self) -> str:
        if self._depth == 0:
            return ""
        self._depth, self._hold = 0, ""
        self.removed += 1
        return MISSING_QUOTE


def chat_reply(
    report: Report, doc: Document, messages: Sequence[ChatMessage], client: LLMClient,
    answers: dict[str, str] | None = None, max_output_tokens: int | None = None,
) -> Iterator[str]:
    """Ответ агента по частям. Последняя реплика должна быть от аналитика."""
    if not messages or messages[-1].role != "user" or not messages[-1].content.strip():
        raise ValueError("Последняя реплика должна быть непустым сообщением пользователя.")
    guard = QuoteGuard(doc)
    system = system_prompt("chat")
    for chunk in client.stream_text(system, build_prompt(report, doc, messages, answers), max_output_tokens):
        safe = guard.feed(chunk)
        if safe:
            yield safe
    tail = guard.flush()
    if tail:
        yield tail
