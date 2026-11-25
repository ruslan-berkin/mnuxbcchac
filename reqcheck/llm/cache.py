"""Дисковый кэш ответов LLM: .cache/llm/<sha256(provider+model+prompt)>.json."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path


class DiskCache:
    def __init__(self, root: str | Path = ".cache/llm") -> None:
        self.root = Path(root)

    @staticmethod
    def make_key(provider: str, model: str, system: str, prompt: str, schema_name: str = "") -> str:
        h = hashlib.sha256()
        for part in (provider, model, schema_name, system, prompt):
            h.update(part.encode("utf-8"))
            h.update(b"\x00")
        return h.hexdigest()

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> str | None:
        p = self._path(key)
        if not p.is_file():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))["response"]
        except (OSError, ValueError, KeyError):
            return None  # битый кэш = промах

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
