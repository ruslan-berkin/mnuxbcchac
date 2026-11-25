"""Рабочий процесс разбора PDF/DOCX. Запускается из ingest в отдельном процессе с лимитами.

Печатает один JSON в stdout: {"ok": true, lines, blocks, title, warnings, incomplete}
или {"ok": false, "kind": "too_large" | "input" | "error", "message": ...}.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from reqcheck.errors import EmptyDocumentError, InputFileError, InputTooLargeError
from reqcheck.limits import Limits


def main() -> int:
    path, ext, limits_json = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    limits = Limits(**json.loads(limits_json))
    from reqcheck import ingest

    warnings: list[str] = []
    incomplete: list[str] = []
    try:
        if ext == ".pdf":
            lines, blocks, title = ingest._read_pdf(path, limits, warnings, incomplete)
        else:
            lines, blocks, title = ingest._read_docx(path, limits, warnings, incomplete)
        result = {"ok": True, "lines": lines, "blocks": [b.model_dump() for b in blocks], "title": title,
                  "warnings": warnings, "incomplete": incomplete}
    except InputTooLargeError as exc:
        result = {"ok": False, "kind": "too_large", "message": str(exc)}
    except EmptyDocumentError as exc:
        result = {"ok": False, "kind": "empty", "message": str(exc)}
    except InputFileError as exc:
        result = {"ok": False, "kind": "input", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001 — текст исключения парсера наружу не отдаём
        result = {"ok": False, "kind": "error",
                  "message": f"Не удалось прочитать {path.name}: файл повреждён или имеет неподдерживаемую структуру ({type(exc).__name__})."}
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
