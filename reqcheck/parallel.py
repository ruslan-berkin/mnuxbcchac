"""Параллельные вызовы LLM с детерминированным порядком результатов."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")
DEFAULT_WORKERS = 4


def default_workers() -> int:
    try:
        return max(1, int(os.getenv("REQCHECK_WORKERS", DEFAULT_WORKERS)))
    except ValueError:
        return DEFAULT_WORKERS


def pmap(fn: Callable[[T], R], items: Sequence[T], workers: int = 1) -> list[R]:
    """map с потоками: результаты идут в порядке items, ошибка первого по порядку пробрасывается.

    Порядок результатов не зависит от того, какой поток закончил первым, поэтому отчёт
    воспроизводим. Невыполненные задачи при ошибке отменяются.
    """
    if workers <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as ex:
        futures = [ex.submit(fn, x) for x in items]
        try:
            return [f.result() for f in futures]
        except BaseException:
            for f in futures:
                f.cancel()
            raise
