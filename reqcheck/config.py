"""Настройки из окружения и .env. ID моделей в коде не хранятся."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv

PROVIDERS = ("gemini", "groq", "openai_compat", "fake")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


@dataclass(frozen=True)
class Settings:
    provider: str
    model: str | None
    api_key: str | None
    base_url: str | None = None

    @property
    def has_key(self) -> bool:
        if self.provider == "fake":
            return True
        return bool(self.api_key) and bool(self.model)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value.startswith("your_"):
        return None  # значение-заглушка из .env.example
    return value


def load_settings(provider: str | None = None, model: str | None = None) -> Settings:
    load_dotenv(find_dotenv(usecwd=True))  # .env берётся из текущей папки запуска
    prov = (provider or os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
    if prov == "gemini":
        return Settings(prov, model or _clean(os.getenv("GEMINI_MODEL")),
                        _clean(os.getenv("GEMINI_API_KEY")))
    if prov == "groq":
        return Settings(prov, model or _clean(os.getenv("GROQ_MODEL")),
                        _clean(os.getenv("GROQ_API_KEY")),
                        _clean(os.getenv("GROQ_BASE_URL")) or GROQ_BASE_URL)
    if prov == "openai_compat":
        return Settings(prov, model or _clean(os.getenv("OPENAI_MODEL")),
                        _clean(os.getenv("OPENAI_API_KEY")), _clean(os.getenv("OPENAI_BASE_URL")))
    if prov == "fake":
        return Settings(prov, model or "fake-model", "fake")
    raise ValueError(f"Неизвестный провайдер «{prov}». Допустимы: {', '.join(PROVIDERS)}")
