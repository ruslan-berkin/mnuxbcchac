"""Лимиты ввода и бюджет прогона: защита от больших файлов и неконтролируемых расходов на LLM."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, fields

from reqcheck.errors import BudgetExceededError
from reqcheck.llm.base import LLMClient


@dataclass(frozen=True)
class Limits:
    max_file_bytes: int = 25 * 1024 * 1024
    max_uncompressed_bytes: int = 200 * 1024 * 1024  # DOCX после распаковки
    max_zip_entries: int = 5000
    max_pages: int = 300
    max_chars: int = 600_000
    max_lines: int = 30_000
    max_table_rows: int = 5000
    max_requirements: int = 400
    max_findings: int = 300
    max_lint_per_rule: int = 40
    max_verified: int = 30
    max_fuzzy_lookups: int = 300
    max_llm_calls: int = 500
    max_prompt_chars: int = 12_000_000
    deadline_s: float = 3600.0
    max_workers: int = 8

    @classmethod
    def from_env(cls) -> "Limits":
        """REQCHECK_MAX_<ИМЯ> (в верхнем регистре) переопределяет значение по умолчанию."""
        base = cls()
        kw = {}
        for f in fields(cls):
            raw = os.getenv(f"REQCHECK_{f.name.upper()}")
            if raw:
                try:
                    kw[f.name] = type(getattr(base, f.name))(float(raw))
                except ValueError:
                    pass
        return cls(**{**base.__dict__, **kw})

    @classmethod
    def web(cls) -> "Limits":
        """Жёсткие значения для публичного сайта с платным ключом."""
        return cls(max_file_bytes=5 * 1024 * 1024, max_uncompressed_bytes=50 * 1024 * 1024, max_pages=60,
                   max_chars=150_000, max_lines=8_000, max_requirements=120, max_findings=120,
                   max_verified=12, max_llm_calls=150, max_prompt_chars=2_500_000, deadline_s=600.0,
                   max_workers=4)


class Budget:
    """Общий счётчик на прогон: вызовы, объём промптов, время. Потокобезопасен."""

    def __init__(self, limits: Limits) -> None:
        self.limits = limits
        self.calls = 0
        self.chars = 0
        self.started = time.monotonic()
        self._lock = threading.Lock()

    def check_deadline(self) -> None:
        if time.monotonic() - self.started > self.limits.deadline_s:
            raise BudgetExceededError(f"Превышено время прогона ({self.limits.deadline_s:.0f} с).")

    def charge(self, prompt_chars: int) -> None:
        self.check_deadline()
        with self._lock:
            self.calls += 1
            self.chars += prompt_chars
            if self.calls > self.limits.max_llm_calls:
                raise BudgetExceededError(f"Превышено число вызовов LLM ({self.limits.max_llm_calls}).")
            if self.chars > self.limits.max_prompt_chars:
                raise BudgetExceededError(
                    f"Превышен объём отправленного в LLM текста ({self.limits.max_prompt_chars} символов).")


class BudgetedLLM(LLMClient):
    """Обёртка: каждый реальный вызов модели (не попадание в кэш) списывается с бюджета."""

    def __init__(self, inner: LLMClient, budget: Budget) -> None:
        self.inner = inner
        self.budget = budget

    @property
    def provider(self) -> str:  # type: ignore[override]
        return self.inner.provider

    @property
    def model(self) -> str:  # type: ignore[override]
        return self.inner.model

    def cache_identities(self) -> list[tuple[str, str]]:
        return self.inner.cache_identities()

    def complete(self, system: str, prompt: str, schema: dict) -> str:
        self.budget.charge(len(system) + len(prompt))
        return self.inner.complete(system, prompt, schema)
