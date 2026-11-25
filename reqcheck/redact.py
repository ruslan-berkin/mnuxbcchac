"""Вырезание секретов из текстов, которые попадают в лог, отчёт и сообщения об ошибках."""

from __future__ import annotations

import re

_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-*]{6,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{10,}"),
    re.compile(r"gsk_[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)(api[_-]?key[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9_\-*.]{6,}"),
    re.compile(r"org-[A-Za-z0-9]{6,}"),
]


def redact(text: object) -> str:
    out = str(text)
    for pat in _PATTERNS:
        if pat.groups:
            out = pat.sub(lambda m: m.group(1) + "[скрыто]", out)
        else:
            out = pat.sub("[скрыто]", out)
    return out
