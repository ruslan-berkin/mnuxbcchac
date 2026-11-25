from __future__ import annotations

from reqcheck.config import Settings
from reqcheck.errors import LLMUnavailableError
from reqcheck.llm.base import LLMClient, LLMValidationError, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.fake import FakeLLM
from reqcheck.llm.fallback import FallbackLLM


def build_client(settings: Settings, attempts: int = 5) -> LLMClient:
    if settings.provider == "fake":
        return FakeLLM(model=settings.model or "fake-model")
    if not settings.has_key:
        raise LLMUnavailableError("Не заданы ключ и ID модели для выбранного провайдера (см. .env.example).")
    assert settings.api_key and settings.model
    if settings.provider == "gemini":
        from reqcheck.llm.gemini import GeminiClient

        return GeminiClient(settings.api_key, settings.model, attempts=attempts)
    if settings.provider == "groq":
        from reqcheck.llm.openai_compat import OpenAICompatClient

        return OpenAICompatClient(settings.api_key, settings.model, settings.base_url,
                                  provider="groq", attempts=attempts)
    if settings.provider == "openai_compat":
        from reqcheck.llm.openai_compat import OpenAICompatClient

        return OpenAICompatClient(settings.api_key, settings.model, settings.base_url, attempts=attempts)
    raise LLMUnavailableError(f"Неизвестный провайдер «{settings.provider}».")


__all__ = ["build_client", "FallbackLLM", "LLMClient", "LLMValidationError", "FakeLLM", "DiskCache", "structured_call"]
