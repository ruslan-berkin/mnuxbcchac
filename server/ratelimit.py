"""Лимиты платного ключа: на весь сайт и на IP за сутки (UTC). Счётчики в памяти процесса.

Первый адрес X-Forwarded-For (SITE.md §5) клиент может подделать, поэтому у каждого действия
есть и общий суточный потолок на весь сайт: он ограничивает расход даже при подделке адреса.
"""

from __future__ import annotations

import os
import threading
from collections import Counter
from datetime import datetime, timezone


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


# действие -> (переменная и значение на IP, переменная и значение на весь сайт)
RULES = {
    "run": (("SITE_RUNS_PER_IP", 1), ("SITE_DAILY_RUNS", 5)),
    "chat": (("SITE_CHAT_PER_IP", 40), ("SITE_DAILY_CHAT", 300)),
    "recheck": (("SITE_RECHECK_PER_IP", 5), ("SITE_DAILY_RECHECK", 40)),
}


class LimitExceeded(Exception):
    pass


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._day = ""
        self._by_ip: Counter[tuple[str, str]] = Counter()
        self._total: Counter[str] = Counter()

    def _roll(self) -> None:
        today = datetime.now(timezone.utc).date().isoformat()
        if today != self._day:
            self._day = today
            self._by_ip.clear()
            self._total.clear()

    def take(self, action: str, ip: str) -> None:
        """Списать одно действие или бросить LimitExceeded с понятным сообщением."""
        (ip_var, ip_default), (all_var, all_default) = RULES[action]
        with self._lock:
            self._roll()
            if self._total[action] >= _env_int(all_var, all_default):
                raise LimitExceeded("Суточный лимит сайта исчерпан. Откройте пример: он работает без ограничений.")
            if self._by_ip[(action, ip)] >= _env_int(ip_var, ip_default):
                raise LimitExceeded("Ваш суточный лимит на это действие исчерпан. Откройте пример: он доступен всегда.")
            self._total[action] += 1
            self._by_ip[(action, ip)] += 1

    def refund(self, action: str, ip: str) -> None:
        with self._lock:
            if self._total[action] > 0:
                self._total[action] -= 1
            if self._by_ip[(action, ip)] > 0:
                self._by_ip[(action, ip)] -= 1


def client_ip(forwarded_for: str | None, peer: str | None) -> str:
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first[:64]
    return peer or "unknown"
