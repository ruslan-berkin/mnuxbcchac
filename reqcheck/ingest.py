"""ingest: PDF / DOCX / MD / TXT → Document с блоками и якорями."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

from reqcheck.errors import EmptyDocumentError, InputFileError
from reqcheck.models import Anchor, Block, Document

SUPPORTED = {".pdf", ".docx", ".md", ".markdown", ".txt"}
_MD_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_MD_FENCE = re.compile(r"^\s*(```|~~~)")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_document(path: str | Path) -> Document:
    p = Path(path)
    if not p.is_file():
        raise InputFileError(f"Файл не найден: {p}")
    ext = p.suffix.lower()
    if ext not in SUPPORTED:
        raise InputFileError(
            f"Формат {ext or '(без расширения)'} не поддерживается. Допустимы: PDF, DOCX, MD, TXT."
        )
    try:
        if ext == ".pdf":
            lines, blocks, title = _read_pdf(p)
        elif ext == ".docx":
            lines, blocks, title = _read_docx(p)
        else:
            lines, blocks, title = _read_text(p)
    except (InputFileError, EmptyDocumentError):
        raise
    except Exception as exc:  # повреждённый файл
        raise InputFileError(f"Не удалось прочитать {p.name}: {exc}") from exc

    if not any(line.strip() for line in lines):
        raise EmptyDocumentError(
            f"В файле {p.name} нет текста (возможно, это скан без текстового слоя). "
            "Распознайте документ (OCR) и повторите."
        )
    return Document(
        title=title or p.stem,
        path=str(p),
        sha256=sha256_file(p),
        format=ext.lstrip("."),
        lines=lines,
        blocks=blocks,
    )


# ---------------------------------------------------------------- MD / TXT


def _read_text(p: Path) -> tuple[list[str], list[Block], str]:
    raw = p.read_bytes().decode("utf-8-sig", errors="replace")
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


def _read_pdf(p: Path) -> tuple[list[str], list[Block], str]:
    import pymupdf

    lines: list[str] = []
    blocks: list[Block] = []
    section = ""
    with pymupdf.open(p) as pdf:
        meta_title = (pdf.metadata or {}).get("title", "") or ""
        pages = [pdf[i].get_text("dict", sort=True) for i in range(len(pdf))]

    sizes: Counter[float] = Counter()
    for data in pages:
        for blk in data.get("blocks", []):
            for ln in blk.get("lines", []):
                for sp in ln.get("spans", []):
                    sizes[round(sp["size"], 1)] += len(sp["text"].strip())
    # Базовый размер: наибольший среди размеров, на которые приходится ≥25% текста.
    # Мелкий шрифт таблиц не должен делать обычные абзацы «заголовками».
    total = sum(sizes.values()) or 1
    body = max((sz for sz, n in sizes.items() if n / total >= 0.25),
               default=sizes.most_common(1)[0][0] if sizes else 0.0)

    first_heading = ""
    for page_no, data in enumerate(pages, start=1):
        for blk in data.get("blocks", []):
            blk_lines: list[str] = []
            max_size = 0.0
            for ln in blk.get("lines", []):
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
    return lines, blocks, meta_title.strip() or first_heading


# ---------------------------------------------------------------- DOCX


def _read_docx(p: Path) -> tuple[list[str], list[Block], str]:
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
            for row in table.rows:
                cells: list[str] = []
                for cell in row.cells:
                    t = " ".join(cell.text.split())
                    if not cells or cells[-1] != t or t == "":  # склеенные ячейки не дублируем
                        cells.append(t)
                add("| " + " | ".join(cells) + " |")
    return lines, blocks, title
