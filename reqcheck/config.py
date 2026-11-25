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


def load_env_file() -> None:
    """Только для CLI: подхватить .env из текущей папки. Библиотечный код окружение не читает из файлов:
    сервер задаёт настройки явно (переменные окружения процесса или Settings)."""
    load_dotenv(find_dotenv(usecwd=True))


def _check_model_allowed(model: str | None) -> None:
    allow = [m.strip() for m in (os.getenv("REQCHECK_MODEL_ALLOWLIST") or "").split(",") if m.strip()]
    if allow and model and model not in allow:
        raise ValueError(f"Модель «{model}» не входит в список разрешённых (REQCHECK_MODEL_ALLOWLIST).")


def load_settings(provider: str | None = None, model: str | None = None) -> Settings:
    st = _load_settings(provider, model)
    _check_model_allowed(st.model)
    return st


def _load_settings(provider: str | None = None, model: str | None = None) -> Settings:
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


def load_chain(
    provider: str | None = None, model: str | None = None, *, fallback: bool = True,
) -> tuple[Settings, list[Settings], list[str]]:
    """Основной провайдер и запасные (только с ключами) + заметки для отчёта.

    LLM_FALLBACK=groq,gemini задаёт порядок явно; «none» отключает. Иначе запасными
    становятся все остальные провайдеры, у которых в .env есть ключ и модель.
    """
    primary = load_settings(provider, model)
    notes: list[str] = []
    if primary.provider == "fake" or not fallback:
        return primary, [], notes
    raw = (os.getenv("LLM_FALLBACK") or "").strip().lower()
    if raw == "none":
        return primary, [], notes
    names = [n.strip() for n in raw.split(",") if n.strip()] or [
        n for n in PROVIDERS if n not in (primary.provider, "fake")]
    others = []
    for n in names:
        if n == primary.provider or n not in PROVIDERS or n == "fake":
            continue
        st = load_settings(n)
        if st.has_key:
            others.append(st)
    if not primary.has_key and others:
        notes.append(f"У основного провайдера «{primary.provider}» нет ключа или модели, "
                     f"использован «{others[0].provider}».")
        return others[0], others[1:], notes
    return primary, others, notes
