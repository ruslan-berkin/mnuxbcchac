"""ingest: PDF / DOCX / MD / TXT → Document с блоками и якорями."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

import logging
import zipfile

from reqcheck.errors import EmptyDocumentError, InputFileError, InputTooLargeError
from reqcheck.limits import Limits
from reqcheck.redact import redact
from reqcheck.models import Anchor, Block, Document

log = logging.getLogger("reqcheck.ingest")
SUPPORTED = {".pdf", ".docx", ".md", ".markdown", ".txt"}
_MD_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_MD_FENCE = re.compile(r"^\s*(```|~~~)")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_display_name(name: str, limit: int = 120) -> str:
    """Имя файла для паспорта: без каталогов, управляющих символов и с ограничением длины."""
    base = re.split(r"[\\/]", str(name))[-1]
    base = "".join(ch for ch in base if ch.isprintable() and ch not in "\u202e\u202d\u200b\ufeff")
    return base.strip()[:limit] or "document"


def load_document(
    path: str | Path, limits: Limits | None = None, display_name: str | None = None,
) -> Document:
    limits = limits or Limits()
    p = Path(path)
    if not p.is_file():
        raise InputFileError(f"Файл не найден: {p.name}")
    ext = p.suffix.lower()
    if ext not in SUPPORTED:
        raise InputFileError(
            f"Формат {ext or '(без расширения)'} не поддерживается. Допустимы: PDF, DOCX, MD, TXT."
        )
    size = p.stat().st_size
    if size > limits.max_file_bytes:
        raise InputTooLargeError(
            f"Файл {size / 1e6:.1f} МБ больше лимита {limits.max_file_bytes / 1e6:.0f} МБ.")
    _check_signature(p, ext, limits)
    warnings: list[str] = []
    incomplete: list[str] = []
    try:
        if ext == ".pdf":
            lines, blocks, title = _read_pdf(p, limits, warnings, incomplete)
        elif ext == ".docx":
            lines, blocks, title = _read_docx(p, limits)
        else:
            lines, blocks, title = _read_text(p, warnings)
    except (InputFileError, EmptyDocumentError):
        raise
    except Exception as exc:  # повреждённый файл; текст исключения парсера пользователю не показываем
        log.warning("ingest: не удалось прочитать %s: %s", p.name, redact(exc))
        raise InputFileError(f"Не удалось прочитать {p.name}: файл повреждён или имеет неподдерживаемую структуру "
                             f"({type(exc).__name__}).") from exc

    if not any(line.strip() for line in lines):
        raise EmptyDocumentError(
            f"В файле {p.name} нет текста (возможно, это скан без текстового слоя). "
            "Распознайте документ (OCR) и повторите."
        )
    chars = sum(len(x) + 1 for x in lines)
    if chars > limits.max_chars or len(lines) > limits.max_lines:
        raise InputTooLargeError(
            f"Документ слишком большой: {chars} символов и {len(lines)} строк при лимите "
            f"{limits.max_chars} символов и {limits.max_lines} строк.")
    shown = safe_display_name(display_name if display_name is not None else p.name)
    return Document(
        title=title or p.stem,
        path=shown,
        sha256=sha256_file(p),
        format=ext.lstrip("."),
        lines=lines,
        blocks=blocks,
        warnings=warnings,
        incomplete=incomplete,
    )


def _check_signature(p: Path, ext: str, limits: Limits) -> None:
    """Содержимое должно соответствовать расширению; DOCX проверяем на zip-бомбу до разбора."""
    with p.open("rb") as f:
        head = f.read(1024)
    if ext == ".pdf" and b"%PDF-" not in head:
        raise InputFileError(f"Файл {p.name} не похож на PDF (нет сигнатуры %PDF).")
    if ext == ".docx":
        if not zipfile.is_zipfile(p):
            raise InputFileError(f"Файл {p.name} не похож на DOCX (это не zip-архив).")
        with zipfile.ZipFile(p) as z:
            infos = z.infolist()
            if len(infos) > limits.max_zip_entries or sum(i.file_size for i in infos) > limits.max_uncompressed_bytes:
                raise InputTooLargeError(f"DOCX {p.name} после распаковки превышает лимиты (возможна zip-бомба).")
    if ext in (".txt", ".md", ".markdown") and b"\x00" in head and not head.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise InputFileError(f"Файл {p.name} выглядит бинарным, а не текстовым.")


# ---------------------------------------------------------------- MD / TXT


def _decode(raw: bytes, warnings: list[str]) -> str:
    """Строго: UTF-16 по BOM, UTF-8, затем windows-1251. Мусор «�» в LLM и цитаты не пропускаем."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        text = raw.decode("cp1251")
    except UnicodeDecodeError as exc:
        raise InputFileError("Не удалось определить кодировку текста (ожидались UTF-8, UTF-16 или windows-1251).") from exc
    warnings.append("Кодировка файла не UTF-8: прочитан как windows-1251. Проверьте, что текст в отчёте не искажён.")
    return text


def _read_text(p: Path, warnings: list[str]) -> tuple[list[str], list[Block], str]:
    raw = _decode(p.read_bytes(), warnings)
    lines = raw.splitlines()
    is_md = p.suffix.lower() in {".md", ".markdown"}
    blocks: list[Block] = []
    title = ""
    section = ""
    cur: list[int] = []  # индексы строк текущего абзаца (0-based)
    in_fence = False

    def flush() -> None:
        if cur:
            text = "\n".join(lines[i] for i in cur)
            blocks.append(Block(text=text, anchor=Anchor(
                section=section, page=None, line_start=cur[0] + 1, line_end=cur[-1] + 1)))
            cur.clear()

    for i, line in enumerate(lines):
        if is_md and _MD_FENCE.match(line):
            if not in_fence:
                flush()
            cur.append(i)
            if in_fence:
                flush()
            in_fence = not in_fence
            continue
        if in_fence:
            cur.append(i)
            continue
        m = _MD_HEADING.match(line) if is_md else None
        if m:
            flush()
            section = m.group(2).strip()
            if not title and len(m.group(1)) == 1:
                title = section
            blocks.append(Block(text=line, anchor=Anchor(
                section=section, page=None, line_start=i + 1, line_end=i + 1)))
        elif not line.strip() or line.strip() == "---":
            flush()
        else:
            cur.append(i)
    flush()
    if not title:
        title = next((ln.strip() for ln in lines if ln.strip()), "")[:120]
    return lines, blocks, title


# ---------------------------------------------------------------- PDF


def _pdf_tables(page, max_rows: int) -> tuple[list[tuple[object, list[str]]], bool]:
    """Таблицы страницы как (rect, строки «| a | b |»). Второй результат: разбор таблиц упал."""
    import pymupdf

    out = []
    try:
        found = page.find_tables().tables
    except Exception as exc:  # find_tables капризен на экзотических PDF; тогда остаётся обычный текст
        log.warning("ingest: find_tables упал на стр. %s: %s", page.number + 1, redact(exc))
        return out, True
    for t in found:
        rows = []
        for r in t.rows[:max_rows]:
            cells = [" ".join(page.get_text("text", clip=pymupdf.Rect(c)).split()) if c else ""
                     for c in r.cells]
            rows.append("| " + " | ".join(cells) + " |")
        if rows:
            out.append((pymupdf.Rect(t.bbox), rows))
    return out, False


def _read_pdf(
    p: Path, limits: Limits, warnings: list[str], incomplete: list[str]
) -> tuple[list[str], list[Block], str]:
    import pymupdf

    pages = []
    table_fail: list[int] = []
    with pymupdf.open(p) as pdf:
        if pdf.page_count > limits.max_pages:
            raise InputTooLargeError(f"В PDF {pdf.page_count} страниц при лимите {limits.max_pages}.")
        meta_title = (pdf.metadata or {}).get("title", "") or ""
        for i in range(len(pdf)):
            page = pdf[i]
            tables, failed = _pdf_tables(page, limits.max_table_rows)
            if failed:
                table_fail.append(i + 1)
            pages.append((page.get_text("dict", sort=True), tables))
    if table_fail:
        warnings.append("Таблицы не разобраны на страницах: " + ", ".join(map(str, table_fail[:20]))
                        + ". Их текст прочитан как обычный, правила по таблицам там не работали.")

    sizes: Counter[float] = Counter()
    for data, tables in pages:
        for blk in data.get("blocks", []):
            if _in_tables(blk, tables):
                continue
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    sizes[round(sp["size"], 1)] += len(sp["text"].strip())
    # Базовый размер: наибольший среди размеров, на которые приходится ≥25% текста.
    # Мелкий шрифт таблиц не должен делать обычные абзацы «заголовками».
    total = sum(sizes.values()) or 1
    body = max((sz for sz, n in sizes.items() if n / total >= 0.25),
               default=sizes.most_common(1)[0][0] if sizes else 0.0)

    lines: list[str] = []
    blocks: list[Block] = []
    section = ""
    first_heading = ""
    for page_no, (data, tables) in enumerate(pages, start=1):
        items: list[tuple[float, str, object]] = []
        for blk in data.get("blocks", []):
            if blk.get("lines") and not _in_tables(blk, tables):
                items.append((blk["bbox"][1], "text", blk))
        for rect, rows in tables:
            items.append((rect.y0, "table", rows))
        items.sort(key=lambda it: it[0])
        for _, kind, payload in items:
            if kind == "table":
                start = len(lines) + 1
                lines.extend(payload)  # type: ignore[arg-type]
                blocks.append(Block(text="\n".join(payload), anchor=Anchor(  # type: ignore[arg-type]
                    section=section, page=page_no, line_start=start, line_end=len(lines))))
                continue
            blk_lines: list[str] = []
            max_size = 0.0
            for ln in payload["lines"]:  # type: ignore[index]
                text = "".join(sp["text"] for sp in ln.get("spans", [])).strip()
                if not text:
                    continue
                blk_lines.append(text)
                max_size = max([max_size] + [sp["size"] for sp in ln["spans"] if sp["text"].strip()])
            if not blk_lines:
                continue
            start = len(lines) + 1
            lines.extend(blk_lines)
            joined = " ".join(blk_lines)
            if body and max_size > body * 1.05 and len(joined) <= 150:
                section = joined
                first_heading = first_heading or joined
            blocks.append(Block(text="\n".join(blk_lines), anchor=Anchor(
                section=section, page=page_no, line_start=start, line_end=len(lines))))
    empty_pages = [n for n, (data, tables) in enumerate(pages, start=1)
                   if not tables and not any(b.get("lines") for b in data.get("blocks", []))]
    if empty_pages and len(empty_pages) < len(pages):
        shown = ", ".join(map(str, empty_pages[:20]))
        warnings.append(f"Страницы без текстового слоя: {shown} (возможно, сканы или схемы).")
        incomplete.append(f"часть страниц без текста ({len(empty_pages)}): требования на них не проверены")
    return lines, blocks, meta_title.strip() or first_heading


def _in_tables(blk: dict, tables: list) -> bool:
    x0, y0, x1, y1 = blk["bbox"]
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return any(r.x0 <= cx <= r.x1 and r.y0 <= cy <= r.y1 for r, _ in tables)


# ---------------------------------------------------------------- DOCX


def _read_docx(p: Path, limits: Limits) -> tuple[list[str], list[Block], str]:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(str(p))
    lines: list[str] = []
    blocks: list[Block] = []
    section = ""
    title = (d.core_properties.title or "").strip()

    def add(text: str) -> None:
        start = len(lines) + 1
        lines.extend(text.split("\n"))
        blocks.append(Block(text=text, anchor=Anchor(
            section=section, page=None, line_start=start, line_end=len(lines))))

    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, d)
            text = para.text.strip()
            if not text:
                continue
            style = (para.style.name if para.style is not None else "") or ""
            if style.startswith(("Heading", "Заголовок", "Title")):
                section = text
                title = title or text
            add(text)
        elif tag == "tbl":
            table = Table(child, d)
            for row in table.rows[:limits.max_table_rows]:
                cells: list[str] = []
                for cell in row.cells:
                    t = " ".join(cell.text.split())
                    if not cells or cells[-1] != t or t == "":  # склеенные ячейки не дублируем
                        cells.append(t)
                add("| " + " | ".join(cells) + " |")
    return lines, blocks, title
