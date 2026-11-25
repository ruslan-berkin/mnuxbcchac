"""Настройки из окружения и .env. ID моделей в коде не хранятся."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

PROVIDERS = ("gemini", "openai_compat", "fake")


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
    load_dotenv()
    prov = (provider or os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
    if prov == "gemini":
        return Settings(prov, model or _clean(os.getenv("GEMINI_MODEL")),
                        _clean(os.getenv("GEMINI_API_KEY")))
    if prov == "openai_compat":
        return Settings(prov, model or _clean(os.getenv("OPENAI_MODEL")),
                        _clean(os.getenv("OPENAI_API_KEY")), _clean(os.getenv("OPENAI_BASE_URL")))
    if prov == "fake":
        return Settings(prov, model or "fake-model", "fake")
    raise ValueError(f"Неизвестный провайдер «{prov}». Допустимы: {', '.join(PROVIDERS)}")
