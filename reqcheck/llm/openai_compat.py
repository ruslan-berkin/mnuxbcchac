"""OpenAI-совместимый провайдер (OpenAI, OpenRouter, Ollama, vLLM)."""

from __future__ import annotations

import json

from reqcheck.llm.base import (EmptyResponseError, LLMClient, LLMTruncatedError, call_with_retries,
                               inline_schema)


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
    return any(k in name for k in ("timeout", "connection", "emptyresponse")), retry_after


class OpenAICompatClient(LLMClient):
    provider = "openai_compat"

    def __init__(self, api_key: str, model: str, base_url: str | None = None, *, client=None,
                 timeout_s: float = 120.0, attempts: int = 5, sleep=None,
                 provider: str = "openai_compat", max_output_tokens: int | None = None) -> None:
        self.provider = provider
        self.model = model
        self._send_temperature = True
        self._tok_param: str | None = "max_completion_tokens" if max_output_tokens else None
        self._max_out = max_output_tokens
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
            if self._tok_param and self._max_out:
                params[self._tok_param] = self._max_out
            try:
                resp = self._client.chat.completions.create(**params)
            except Exception as exc:
                msg = str(exc)
                if getattr(exc, "status_code", None) != 400:
                    raise
                # Модель или сервер не принимает параметр: отключаем его и повторяем один раз.
                if "temperature" in msg and self._send_temperature:
                    self._send_temperature = False  # например, рассуждающие модели gpt-5.x
                elif self._tok_param and self._tok_param in msg:
                    # у новых моделей max_completion_tokens, у старых серверов max_tokens, иначе без лимита
                    self._tok_param = "max_tokens" if self._tok_param == "max_completion_tokens" else None
                elif ("response_format" in msg or "Failed to validate JSON" in msg) and self._json_mode:
                    self._json_mode = False
                else:
                    raise
                return call()
            if not getattr(resp, "choices", None):
                raise EmptyResponseError("провайдер вернул пустой список choices")
            choice = resp.choices[0]
            finish = getattr(choice, "finish_reason", None)
            if finish == "length":
                raise LLMTruncatedError("Ответ модели обрезан по лимиту длины (finish_reason=length).")
            if finish == "content_filter":
                raise LLMTruncatedError("Ответ модели отклонён фильтром безопасности провайдера.")
            text = choice.message.content or ""
            if not text.strip():
                raise EmptyResponseError("провайдер вернул пустой ответ")
            return text

        kwargs = {"sleep": self._sleep} if self._sleep else {}
        return call_with_retries(call, classify, attempts=self._attempts, **kwargs)
