from __future__ import annotations

from reqcheck.config import Settings
from reqcheck.errors import LLMUnavailableError
from reqcheck.llm.base import LLMClient, LLMValidationError, structured_call
from reqcheck.llm.cache import DiskCache
from reqcheck.llm.fake import FakeLLM


def build_client(settings: Settings) -> LLMClient:
    if settings.provider == "fake":
        return FakeLLM(model=settings.model or "fake-model")
    # Реальные провайдеры (gemini, openai_compat) подключаются в Фазе 2.
    raise LLMUnavailableError(
        f"Провайдер «{settings.provider}» ещё не реализован в этой версии каркаса."
    )


__all__ = ["build_client", "LLMClient", "LLMValidationError", "FakeLLM", "DiskCache", "structured_call"]
