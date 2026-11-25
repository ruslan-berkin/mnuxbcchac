"""Фейковый провайдер для тестов и CI: отвечает заранее заданными ответами."""

from __future__ import annotations

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
            return "{}"
        return self._queue.pop(0)
