"""Собрать PDF из Markdown (вход для агента; кириллица, таблицы).

Использование: python scripts/make_pdf.py examples/input/requirements.md examples/input/requirements.pdf
Нужны пакеты pymupdf и markdown (requirements.txt).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import markdown
import pymupdf

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
CSS = """
body { font-family: UF; font-size: 10pt; }
h1 { font-size: 20pt; } h2 { font-size: 15pt; } h3 { font-size: 12.5pt; } h4 { font-size: 11.5pt; }
table { border-collapse: collapse; width: 100%; }
td, th { border: 1px solid #888; padding: 3px; font-size: 8.5pt; }
code, pre { font-size: 8.5pt; }
"""


def main(src: str, dst: str) -> None:
    font = next((p for p in FONT_CANDIDATES if Path(p).is_file()), None)
    if font is None:
        sys.exit("Не найден шрифт с кириллицей; укажите путь в FONT_CANDIDATES.")
    html = markdown.markdown(Path(src).read_text(encoding="utf-8"),
                             extensions=["tables", "fenced_code", "sane_lists"])
    tmp = Path(tempfile.mkdtemp())
    shutil.copy(font, tmp / "font.ttf")  # имя без пробелов для CSS
    css = "@font-face { font-family: UF; src: url(font.ttf); }\n" + CSS
    archive = pymupdf.Archive(str(tmp))
    story = pymupdf.Story(html=html, user_css=css, archive=archive)
    writer = pymupdf.DocumentWriter(dst)
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (50, 50, -50, -50)
    more = True
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
