"""Параллельные вызовы LLM с детерминированным порядком результатов."""

from __future__ import annotations

import contextvars
import os
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")
DEFAULT_WORKERS = 4
MAX_WORKERS = 8


def clamp_workers(n: int) -> int:
    return max(1, min(MAX_WORKERS, n))


def default_workers() -> int:
    try:
        return clamp_workers(int(os.getenv("REQCHECK_WORKERS", DEFAULT_WORKERS)))
    except ValueError:
        return DEFAULT_WORKERS


def pmap(fn: Callable[[T], R], items: Sequence[T], workers: int = 1) -> list[R]:
    """map с потоками: результаты идут в порядке items.

    Порядок не зависит от того, какой поток закончил первым, поэтому отчёт воспроизводим. При первой
    же ошибке очередь отменяется сразу (а не после ожидания более ранних задач). Каждая задача
    получает копию контекста: id прогона для лога доходит до потоков пула.
    """
    workers = clamp_workers(workers)
    if workers <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    ex = ThreadPoolExecutor(max_workers=min(workers, len(items)))
    try:
        futures = [ex.submit(contextvars.copy_context().run, fn, x) for x in items]
        done, pending = wait(futures, return_when=FIRST_EXCEPTION)
        for f in done:
            if f.exception() is not None:
                for p in pending:
                    p.cancel()
                raise f.exception()  # type: ignore[misc]
        return [f.result() for f in futures]
    finally:
        ex.shutdown(wait=True, cancel_futures=True)
