"""Провайдер Google Gemini (google-genai): JSON по схеме, temperature=0, ретраи."""

from __future__ import annotations

import re

from reqcheck.llm.base import (EmptyResponseError, LLMClient, LLMTruncatedError, call_with_retries,
                               inline_schema)

_RETRY_DELAY = re.compile(r"retry(?:Delay|-after)\W+(\d+(?:\.\d+)?)", re.IGNORECASE)


def classify(exc: BaseException) -> tuple[bool, float | None]:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    text = str(exc)
    m = _RETRY_DELAY.search(text)
    retry_after = float(m.group(1)) if m else None
    if isinstance(code, int):
        return (code == 429 or code >= 500 or code == 408), retry_after
    name = type(exc).__name__.lower()
    return any(k in name for k in ("timeout", "connect", "network", "remoteprotocol", "emptyresponse")), retry_after


class GeminiClient(LLMClient):
    provider = "gemini"

    def __init__(self, api_key: str, model: str, *, client=None, timeout_s: float = 180.0,
                 attempts: int = 5, sleep=None, thinking_level: str | None = "low",
                 max_output_tokens: int | None = None) -> None:
        """thinking_level: «low» ускоряет рассуждающие модели (по умолчанию они упираются в таймаут);
        None — не передавать параметр."""
        self.model = model
        self._thinking_level = thinking_level
        self._max_out = max_output_tokens
        self._attempts = attempts
        self._sleep = sleep
        if client is None:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key,
                                  http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))
        self._client = client

    def complete(self, system: str, prompt: str, schema: dict) -> str:
        from google.genai import types

        def make_config(thinking: bool) -> types.GenerateContentConfig:
            extra = {}
            if self._max_out:
                extra["max_output_tokens"] = self._max_out
            if thinking and self._thinking_level:
                extra["thinking_config"] = types.ThinkingConfig(thinking_level=self._thinking_level)
            return types.GenerateContentConfig(
                system_instruction=system,
                temperature=0,
                response_mime_type="application/json",
                response_json_schema=inline_schema(schema),
                **extra,
            )

        def call() -> str:
            try:
                resp = self._client.models.generate_content(
                    model=self.model, contents=prompt, config=make_config(True))
            except Exception as exc:
                # Модель не знает thinking_level: один раз повторяем без него.
                if getattr(exc, "code", None) == 400 and "thinking" in str(exc).lower() and self._thinking_level:
                    self._thinking_level = None
                    resp = self._client.models.generate_content(
                        model=self.model, contents=prompt, config=make_config(False))
                else:
                    raise
            candidates = getattr(resp, "candidates", None) or []
            finish = getattr(candidates[0], "finish_reason", None) if candidates else None
            fname = str(getattr(finish, "name", finish or "")).upper()
            if fname == "MAX_TOKENS":
                raise LLMTruncatedError("Ответ модели обрезан по лимиту длины (MAX_TOKENS).")
            if fname in {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "RECITATION"}:
                raise LLMTruncatedError("Ответ модели заблокирован фильтром безопасности провайдера.")
            text = resp.text or ""
            if not text.strip():
                raise EmptyResponseError("провайдер вернул пустой ответ")
            return text

        kwargs = {"sleep": self._sleep} if self._sleep else {}
        return call_with_retries(call, classify, attempts=self._attempts, **kwargs)
