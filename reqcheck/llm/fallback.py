"""Цепочка провайдеров: при недоступности основного вызов идёт к запасному."""

from __future__ import annotations

import logging
import threading

from reqcheck.errors import LLMUnavailableError
from reqcheck.llm.base import LLMClient

log = logging.getLogger("reqcheck.llm")


class FallbackLLM(LLMClient):
    """provider/model — это тот, кто ответил последним (или основной, пока ответов не было)."""

    def __init__(self, clients: list[LLMClient]) -> None:
        assert clients
        self.clients = clients
        self._dead: set[int] = set()
        self._lock = threading.Lock()  # complete() вызывается из нескольких потоков
        self._current = clients[0]
        self.used: list[tuple[str, str]] = []  # кто реально отвечал, в порядке первого ответа
        self.switches: list[str] = []

    @property
    def provider(self) -> str:  # type: ignore[override]
        return self._current.provider

    @property
    def model(self) -> str:  # type: ignore[override]
        return self._current.model

    def cache_identities(self) -> list[tuple[str, str]]:
        return [ident for c in self.clients for ident in c.cache_identities()]

    def complete(self, system: str, prompt: str, schema: dict) -> str:
        errors: list[str] = []
        for i, c in enumerate(self.clients):
            with self._lock:
                dead = i in self._dead
            if dead:
                continue
            try:
                text = c.complete(system, prompt, schema)
            except LLMUnavailableError as exc:
                errors.append(f"{c.provider}/{c.model}: {exc}")
                with self._lock:
                    if getattr(exc, "transient", False):
                        self._dead.add(i)  # лимит/сбой не прошли после ретраев: до конца прогона не трогаем
                    nxt = next((x for j, x in enumerate(self.clients) if j > i and j not in self._dead), None)
                    if nxt is not None:
                        msg = f"{c.provider}/{c.model} недоступен, переключение на {nxt.provider}/{nxt.model}"
                        if msg not in self.switches:
                            log.warning("%s: %s", msg, str(exc)[:200])
                            self.switches.append(msg)
                continue
            with self._lock:
                self._current = c
                ident = (c.provider, c.model)
                if ident not in self.used:
                    self.used.append(ident)
            return text
        raise LLMUnavailableError("Все провайдеры недоступны: " + "; ".join(errors))
