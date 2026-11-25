"""Дисковый кэш ответов LLM: <root>/<sha256(namespace+provider+model+prompt)>.json.

Для сайта: отдельный каталог и соль на арендатора, TTL и потолок размера с вытеснением старых записей.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path


def default_cache_dir() -> Path:
    return Path(os.getenv("REQCHECK_CACHE_DIR") or (Path.cwd() / ".cache" / "llm")).resolve()


class DiskCache:
    def __init__(
        self,
        root: str | Path | None = None,
        *,
        namespace: str = "",
        ttl_s: float = 90 * 86400,
        max_bytes: int = 500 * 1024 * 1024,
    ) -> None:
        base = Path(root) if root is not None else default_cache_dir()
        self.namespace = namespace
        self.root = base / hashlib.sha256(namespace.encode()).hexdigest()[:16] if namespace else base
        self.ttl_s = ttl_s
        self.max_bytes = max_bytes

    @staticmethod
    def make_key(provider: str, model: str, system: str, prompt: str, schema_name: str = "",
                 namespace: str = "") -> str:
        h = hashlib.sha256()
        for part in (namespace, provider, model, schema_name, system, prompt):
            h.update(part.encode("utf-8"))
            h.update(b"\x00")
        return h.hexdigest()

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> str | None:
        p = self._path(key)
        try:
            if time.time() - p.stat().st_mtime > self.ttl_s:
                p.unlink(missing_ok=True)
                return None
            return json.loads(p.read_text(encoding="utf-8"))["response"]
        except (OSError, ValueError, KeyError, TypeError):
            return None  # нет файла или битый кэш = промах

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def put(self, key: str, response: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"response": response}, f, ensure_ascii=False)
            os.replace(tmp, self._path(key))
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        self._evict()

    def _evict(self) -> None:
        """Держим размер под потолком: удаляем самые старые записи до 80% лимита."""
        try:
            files = [(p, p.stat()) for p in self.root.glob("*.json")]
        except OSError:
            return
        total = sum(st.st_size for _, st in files)
        if total <= self.max_bytes:
            return
        for p, st in sorted(files, key=lambda x: x[1].st_mtime):
            p.unlink(missing_ok=True)
            total -= st.st_size
            if total <= self.max_bytes * 0.8:
                break
