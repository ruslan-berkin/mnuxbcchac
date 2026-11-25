"""OpenAI-совместимый провайдер (OpenAI, OpenRouter, Ollama, vLLM)."""

from __future__ import annotations

import json

from reqcheck.llm.base import LLMClient, call_with_retries, inline_schema


def classify(exc: BaseException) -> tuple[bool, float | None]:
    status = getattr(exc, "status_code", None)
    retry_after = None
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers is not None:
        try:
            retry_after = float(headers.get("retry-after"))
        except (TypeError, ValueError):
            retry_after = None
    if isinstance(status, int):
        return (status == 429 or status >= 500 or status == 408), retry_after
    name = type(exc).__name__.lower()
    return any(k in name for k in ("timeout", "connection")), retry_after


class OpenAICompatClient(LLMClient):
    provider = "openai_compat"

    def __init__(self, api_key: str, model: str, base_url: str | None = None, *, client=None,
                 timeout_s: float = 120.0, attempts: int = 5, sleep=None,
                 provider: str = "openai_compat") -> None:
        self.provider = provider
        self.model = model
        self._send_temperature = True
        self._json_mode = True
        self._attempts = attempts
        self._sleep = sleep
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s, max_retries=0)
        self._client = client

    def complete(self, system: str, prompt: str, schema: dict) -> str:
        schema_text = json.dumps(inline_schema(schema), ensure_ascii=False)
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"{prompt}\n\nВерни только JSON строго по схеме:\n{schema_text}"},
        ]

        def call() -> str:
            params: dict = {"model": self.model, "messages": messages}
            if self._send_temperature:
                params["temperature"] = 0
            if self._json_mode:
                params["response_format"] = {"type": "json_object"}
            try:
                resp = self._client.chat.completions.create(**params)
            except Exception as exc:
                msg = str(exc)
                if getattr(exc, "status_code", None) != 400:
                    raise
                # Модель или сервер не принимает параметр: отключаем его и повторяем один раз.
                if "temperature" in msg and self._send_temperature:
                    self._send_temperature = False  # например, рассуждающие модели gpt-5.x
                elif ("response_format" in msg or "Failed to validate JSON" in msg) and self._json_mode:
                    self._json_mode = False
                else:
                    raise
                return call()
            return resp.choices[0].message.content or ""

        kwargs = {"sleep": self._sleep} if self._sleep else {}
        return call_with_retries(call, classify, attempts=self._attempts, **kwargs)
