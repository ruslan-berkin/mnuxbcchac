"""Абстракция провайдера LLM и структурированный вызов с одним ремонтным повтором."""

from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from importlib import resources
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from tenacity import Retrying, retry_if_exception, stop_after_attempt

from reqcheck.errors import LLMUnavailableError
from reqcheck.llm.cache import DiskCache

log = logging.getLogger("reqcheck.llm")
T = TypeVar("T", bound=BaseModel)


class LLMValidationError(Exception):
    """Ответ модели не прошёл схему даже после повторного запроса."""


class LLMClient(ABC):
    provider: str
    model: str

    def cache_identities(self) -> list[tuple[str, str]]:
        """Под какими (провайдер, модель) искать ответ в кэше."""
        return [(self.provider, self.model)]

    @abstractmethod
    def complete(self, system: str, prompt: str, schema: dict) -> str:
        """Вернуть сырой текст ответа (ожидается JSON по схеме). temperature=0.

        Должен бросать LLMUnavailableError, если сервис недоступен после ретраев.
        """


def inline_schema(schema: dict) -> dict:
    """Развернуть $ref/$defs (pydantic) в плоскую JSON-схему, понятную всем провайдерам."""
    defs = schema.get("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].rsplit("/", 1)[-1]])
            return {k: walk(v) for k, v in node.items() if k not in ("$defs", "title", "default")}
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(schema)


# (retryable, retry_after_seconds)
Classifier = Callable[[BaseException], tuple[bool, float | None]]


def call_with_retries(
    fn: Callable[[], str],
    classify: Classifier,
    *,
    attempts: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Ретраи с экспоненциальным backoff на 429/5xx/таймаут; для 429 учитывается retry-after."""

    def wait(state) -> float:
        exc = state.outcome.exception()
        _, retry_after = classify(exc)
        backoff = min(max_delay, base_delay * 2 ** (state.attempt_number - 1))
        return max(retry_after or 0.0, backoff)

    retrying = Retrying(
        stop=stop_after_attempt(attempts),
        wait=wait,
        retry=retry_if_exception(lambda e: classify(e)[0]),
        sleep=sleep,
        reraise=True,
        before_sleep=lambda st: log.warning(
            "LLM: попытка %d не удалась (%s), повтор", st.attempt_number, str(st.outcome.exception())[:200]),
    )
    try:
        return retrying(fn)
    except Exception as exc:
        err = LLMUnavailableError(f"LLM недоступна после {attempts} попыток: {str(exc)[:300]}")
        err.transient = classify(exc)[0]  # True: лимиты/5xx не прошли после ретраев
        raise err from exc


def load_prompt(name: str) -> str:
    return resources.files("reqcheck.prompts").joinpath(f"{name}.md").read_text(encoding="utf-8")


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _parse(raw: str, schema: type[T]) -> T:
    text = _FENCE.sub("", raw.strip())
    return schema.model_validate_json(text)


def structured_call(
    client: LLMClient,
    system: str,
    prompt: str,
    schema: type[T],
    cache: DiskCache | None = None,
) -> T:
    """Вызвать LLM, провалидировать по схеме; при ошибке один раз попросить исправить.

    В кэш попадают только валидные ответы.
    """
    def key_for(provider: str, model: str) -> str:
        return DiskCache.make_key(provider, model, system, prompt, schema.__name__)

    if cache is not None:
        for prov, mod in client.cache_identities():
            hit = cache.get(key_for(prov, mod))
            if hit is not None:
                log.info("LLM cache hit %s (%s/%s)", key_for(prov, mod)[:12], prov, mod)
                return schema.model_validate_json(hit)

    json_schema = schema.model_json_schema()
    raw = client.complete(system, prompt, json_schema)
    try:
        result = _parse(raw, schema)
    except (ValidationError, json.JSONDecodeError) as first_error:
        log.warning("Невалидный ответ LLM, повторный запрос: %s", str(first_error)[:300])
        repair = load_prompt("repair").format(error=str(first_error)[:1500], previous=raw[:4000])
        raw2 = client.complete(system, f"{prompt}\n\n{repair}", json_schema)
        try:
            result = _parse(raw2, schema)
        except (ValidationError, json.JSONDecodeError) as second_error:
            raise LLMValidationError(str(second_error)[:500]) from second_error

    if cache is not None:  # кладём под тем провайдером, который реально ответил
        cache.put(key_for(client.provider, client.model), result.model_dump_json())
    return result


__all__ = ["LLMClient", "LLMUnavailableError", "LLMValidationError", "structured_call", "load_prompt"]
