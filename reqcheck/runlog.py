"""Лог прогона, изолированный от других прогонов в том же процессе.

Один общий обработчик на логгере `reqcheck` направляет записи в файл того прогона, чей id лежит
в contextvar (потоки пула получают копию контекста в `pmap`). Записи вне прогона отбрасываются.
Все сообщения проходят через редактор секретов.
"""

from __future__ import annotations

import contextvars
import logging
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from reqcheck.redact import redact

CURRENT_RUN: contextvars.ContextVar[str | None] = contextvars.ContextVar("reqcheck_run", default=None)
_handlers: dict[str, logging.Handler] = {}
_lock = threading.Lock()
_installed = False


class _Router(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        handler = _handlers.get(CURRENT_RUN.get() or "")
        if handler is not None:
            handler.handle(record)


class _Redact(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def _install() -> None:
    global _installed
    with _lock:
        if not _installed:
            root = logging.getLogger("reqcheck")
            root.addHandler(_Router())
            root.setLevel(logging.INFO)  # один раз при первом прогоне, не на каждый
            _installed = True


@contextmanager
def run_log(log_path: Path) -> Iterator[str]:
    _install()
    run_id = uuid.uuid4().hex
    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(_Redact())
    with _lock:
        _handlers[run_id] = handler
    token = CURRENT_RUN.set(run_id)
    try:
        yield run_id
    finally:
        CURRENT_RUN.reset(token)
        with _lock:
            _handlers.pop(run_id, None)
        handler.close()
