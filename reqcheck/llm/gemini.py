"""Провайдер Google Gemini (google-genai): JSON по схеме, temperature=0, ретраи."""

from __future__ import annotations

import re

from reqcheck.llm.base import LLMClient, call_with_retries, inline_schema

_RETRY_DELAY = re.compile(r"retry(?:Delay|-after)\W+(\d+(?:\.\d+)?)", re.IGNORECASE)


def classify(exc: BaseException) -> tuple[bool, float | None]:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    text = str(exc)
    m = _RETRY_DELAY.search(text)
    retry_after = float(m.group(1)) if m else None
    if isinstance(code, int):
        return (code == 429 or code >= 500 or code == 408), retry_after
    name = type(exc).__name__.lower()
    return any(k in name for k in ("timeout", "connect", "network", "remoteprotocol")), retry_after


class GeminiClient(LLMClient):
    provider = "gemini"

    def __init__(self, api_key: str, model: str, *, client=None, timeout_s: float = 120.0,
                 attempts: int = 5, sleep=None) -> None:
        self.model = model
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

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            response_mime_type="application/json",
            response_json_schema=inline_schema(schema),
        )

        def call() -> str:
            resp = self._client.models.generate_content(model=self.model, contents=prompt, config=config)
            return resp.text or ""

        kwargs = {"sleep": self._sleep} if self._sleep else {}
        return call_with_retries(call, classify, attempts=self._attempts, **kwargs)
