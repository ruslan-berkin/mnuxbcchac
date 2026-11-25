from __future__ import annotations

from reqcheck.config import Settings
from reqcheck.errors import LLMUnavailableError
from reqcheck.llm.base import LLMClient, LLMValidationError, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.fake import FakeLLM


def build_client(settings: Settings) -> LLMClient:
    if settings.provider == "fake":
        return FakeLLM(model=settings.model or "fake-model")
    if not settings.has_key:
        raise LLMUnavailableError("Не заданы ключ и ID модели для выбранного провайдера (см. .env.example).")
    assert settings.api_key and settings.model
    if settings.provider == "gemini":
        from reqcheck.llm.gemini import GeminiClient

        return GeminiClient(settings.api_key, settings.model)
    if settings.provider == "groq":
        from reqcheck.llm.openai_compat import OpenAICompatClient

        return OpenAICompatClient(settings.api_key, settings.model, settings.base_url, provider="groq")
    if settings.provider == "openai_compat":
        from reqcheck.llm.openai_compat import OpenAICompatClient

        return OpenAICompatClient(settings.api_key, settings.model, settings.base_url)
    raise LLMUnavailableError(f"Неизвестный провайдер «{settings.provider}».")


__all__ = ["build_client", "LLMClient", "LLMValidationError", "FakeLLM", "DiskCache", "structured_call"]
