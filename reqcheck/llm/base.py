"""Абстракция провайдера LLM и структурированный вызов с одним ремонтным повтором."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from importlib import resources
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from reqcheck.errors import LLMUnavailableError
from reqcheck.llm.cache import DiskCache

log = logging.getLogger("reqcheck.llm")
T = TypeVar("T", bound=BaseModel)


class LLMValidationError(Exception):
    """Ответ модели не прошёл схему даже после повторного запроса."""


class LLMClient(ABC):
    provider: str
    model: str

    @abstractmethod
    def complete(self, system: str, prompt: str, schema: dict) -> str:
        """Вернуть сырой текст ответа (ожидается JSON по схеме). temperature=0.

        Должен бросать LLMUnavailableError, если сервис недоступен после ретраев.
        """


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
    key = DiskCache.make_key(client.provider, client.model, system, prompt, schema.__name__)
    if cache is not None:
        hit = cache.get(key)
        if hit is not None:
            log.info("LLM cache hit %s", key[:12])
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

    if cache is not None:
        cache.put(key, result.model_dump_json())
    return result


__all__ = ["LLMClient", "LLMUnavailableError", "LLMValidationError", "structured_call", "load_prompt"]
