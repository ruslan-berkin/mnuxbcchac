"""Фейковый провайдер для тестов и CI: отвечает заранее заданными ответами."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence

from reqcheck.llm.base import LLMClient


class FakeLLM(LLMClient):
    provider = "fake"

    def __init__(
        self,
        responses: Sequence[str] = (),
        handler: Callable[[str, str], str] | None = None,
        model: str = "fake-model",
    ) -> None:
        """responses выдаются по очереди; handler(system, prompt) имеет приоритет."""
        self.model = model
        self._queue = list(responses)
        self._handler = handler
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, prompt: str, schema: dict) -> str:
        self.calls.append((system, prompt))
        if self._handler is not None:
            return self._handler(system, prompt)
        if not self._queue:
            return json.dumps(_minimal(schema), ensure_ascii=False)
        return self._queue.pop(0)

    def stream_text(self, system: str, prompt: str, max_output_tokens: int | None = None):
        self.calls.append((system, prompt))
        if self._handler is not None:
            text = self._handler(system, prompt)
        else:
            text = self._queue.pop(0) if self._queue else ""
        for i in range(0, len(text), 5):  # мелкими кусками: проверяет склейку на границах
            yield text[i : i + 5]


def _minimal(node: dict):
    """Минимальный ответ, валидный по схеме (для CLI-режима fake и тестов)."""
    if "enum" in node:
        return node["enum"][0]
    if "anyOf" in node:
        return _minimal(next((n for n in node["anyOf"] if n.get("type") != "null"), node["anyOf"][0]))
    t = node.get("type")
    if t == "object":
        required = set(node.get("required", []))
        return {k: _minimal(v) for k, v in node.get("properties", {}).items() if k in required}
    if t == "array":
        return []
    if t == "string":
        return ""
    if t in ("integer", "number"):
        return 0
    if t == "boolean":
        return False
    return None
