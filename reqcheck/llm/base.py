"""Абстракция провайдера LLM и структурированный вызов с одним ремонтным повтором."""

from __future__ import annotations

import hashlib
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
from reqcheck.redact import redact

log = logging.getLogger("reqcheck.llm")
T = TypeVar("T", bound=BaseModel)


class LLMValidationError(Exception):
    """Ответ модели не прошёл схему даже после повторного запроса (или не мог быть получен целиком).

    `human` — понятная причина для отчёта (обрезан по длине, заблокирован фильтром); None — просто не по схеме.
    """

    def __init__(self, message: str = "", human: str | None = None) -> None:
        super().__init__(message)
        self.human = human


class LLMTruncatedError(Exception):
    """Провайдер вернул неполный или заблокированный ответ (длина, фильтр безопасности)."""


class EmptyResponseError(Exception):
    """Провайдер вернул пустой ответ (нет choices/candidates или пустой текст): повторяем как сбой сервиса."""


class LLMClient(ABC):
    provider: str
    model: str

    def cache_identities(self) -> list[tuple[str, str]]:
        """Под какими (провайдер, модель) искать ответ в кэше."""
        return [(self.provider, self.model)]

    def last_identity(self) -> tuple[str, str]:
        """Кто ответил на последний вызов в ЭТОМ потоке (для ключа кэша и паспорта)."""
        return self.provider, self.model

    def note_cache_hit(self, provider: str, model: str) -> None:
        """Ответ взят из кэша под этой идентичностью: клиенты с цепочкой запоминают это для паспорта."""

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


MAX_RETRY_AFTER = 120.0  # дольше провайдера не ждём: длинный retryDelay держал бы поток часами
_QUOTA = re.compile(r"insufficient_quota|no credits remaining|per ?day|limit:\s*0\b", re.IGNORECASE)


def is_quota_exhausted(exc: BaseException) -> bool:
    """Баланс закончился или квота суточная/нулевая: повторять бессмысленно.

    Обычный 429 «в минуту» (с retryDelay) сюда не попадает: его надо ждать и повторять.
    Слово «billing» не признак: Gemini пишет его в каждом 429.
    """
    return bool(_QUOTA.search(str(exc)))


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
        return max(min(retry_after or 0.0, MAX_RETRY_AFTER), backoff)

    def retryable(exc: BaseException) -> bool:
        return classify(exc)[0] and not is_quota_exhausted(exc)

    retrying = Retrying(
        stop=stop_after_attempt(attempts),
        wait=wait,
        retry=retry_if_exception(retryable),
        sleep=sleep,
        reraise=True,
        before_sleep=lambda st: log.warning(
            "LLM: попытка %d не удалась (%s), повтор", st.attempt_number, str(st.outcome.exception())[:200]),
    )
    try:
        return retrying(fn)
    except LLMTruncatedError:
        raise  # не сбой сервиса: повторять бессмысленно, причина нужна как есть
    except Exception as exc:
        err = LLMUnavailableError(f"LLM недоступна после {attempts} попыток: {redact(str(exc)[:300])}")
        # True: провайдер «лёг» (лимиты/5xx не прошли после ретраев или закончились кредиты)
        err.transient = classify(exc)[0] or is_quota_exhausted(exc)
        raise err from exc


def schema_fingerprint(schema: type[BaseModel]) -> str:
    """Имя и хеш схемы: смена схемы не должна подхватывать старые записи кэша."""
    body = json.dumps(schema.model_json_schema(), sort_keys=True, ensure_ascii=False)
    return f"{schema.__name__}:{hashlib.sha256(body.encode()).hexdigest()[:12]}"


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
    fingerprint = schema_fingerprint(schema)

    def key_for(provider: str, model: str) -> str:
        return DiskCache.make_key(provider, model, system, prompt, fingerprint,
                                  namespace=cache.namespace if cache is not None else "")

    if cache is not None:
        for prov, mod in client.cache_identities():
            key = key_for(prov, mod)
            hit = cache.get(key)
            if hit is None:
                continue
            try:
                parsed = schema.model_validate_json(hit)
            except (ValidationError, ValueError):
                log.warning("LLM cache: запись %s не подходит под схему %s, считаем промахом", key[:12], schema.__name__)
                cache.delete(key)
                continue
            log.info("LLM cache hit %s (%s/%s)", key[:12], prov, mod)
            client.note_cache_hit(prov, mod)
            return parsed

    json_schema = schema.model_json_schema()
    log.info("LLM вызов: %s, промпт %d симв.", schema.__name__, len(system) + len(prompt))
    t0 = time.monotonic()
    try:
        raw = client.complete(system, prompt, json_schema)
    except LLMUnavailableError:
        log.error("LLM вызов не удался за %.0f с: %s", time.monotonic() - t0, schema.__name__)
        raise
    except LLMTruncatedError as exc:  # повтор того же запроса даст то же: ремонт не запускаем
        raise LLMValidationError(str(exc), human=str(exc)) from exc
    log.info("LLM ответ: %s за %.0f с, %d симв.", schema.__name__, time.monotonic() - t0, len(raw))
    try:
        result = _parse(raw, schema)
    except (ValidationError, json.JSONDecodeError) as first_error:
        log.warning("Невалидный ответ LLM, повторный запрос: %s", str(first_error)[:300])
        repair = load_prompt("repair").format(error=str(first_error)[:1500], previous=raw[:4000])
        try:
            raw2 = client.complete(system, f"{prompt}\n\n{repair}", json_schema)
        except LLMTruncatedError as exc:
            raise LLMValidationError(str(exc), human=str(exc)) from exc
        try:
            result = _parse(raw2, schema)
        except (ValidationError, json.JSONDecodeError) as second_error:
            raise LLMValidationError(str(second_error)[:500]) from second_error

    if cache is not None:  # кладём под тем провайдером, который реально ответил
        try:
            cache.put(key_for(*client.last_identity()), result.model_dump_json())
        except OSError as exc:  # диск полон, нет прав: оплаченный ответ не теряем
            log.warning("LLM cache: не удалось записать (%s)", redact(exc))
    return result


__all__ = ["LLMClient", "LLMUnavailableError", "LLMValidationError", "structured_call", "load_prompt"]
