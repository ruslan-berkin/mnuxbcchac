from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def repo_root() -> Path:
    return REPO


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    p = tmp_path / "doc.md"
    p.write_text(
        "# ТЗ тестовое\n\nВведение.\n\n## Функциональные требования\n\n"
        "* **Ф-1.** Система быстро отвечает на запрос.\n"
        "* **Ф-2.** Система хранит данные и т.д.\n\n"
        "```text\nкод\n\nещё код\n```\n\n"
        "## Тестирование\n\nзаполняются тестировщиками\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def sample_txt(tmp_path: Path) -> Path:
    p = tmp_path / "doc.txt"
    p.write_text("Первая строка\nвторая строка\n\nАбзац два\n", encoding="utf-8")
    return p


@pytest.fixture
def sample_docx(tmp_path: Path) -> Path:
    import docx

    d = docx.Document()
    d.add_heading("Документ DOCX", level=1)
    d.add_heading("Функциональные требования", level=2)
    d.add_paragraph("Ф-1. Система должна работать быстро.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "Поле"
    t.cell(0, 1).text = "Значение"
    t.cell(1, 0).text = "Версия"
    t.cell(1, 1).text = "1.0"
    p = tmp_path / "doc.docx"
    d.save(str(p))
    return p


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Heading line", fontsize=20)
    page.insert_text((72, 110), "FR-1. The system shall respond quickly.", fontsize=11)
    page.insert_text((72, 130), "FR-2. The system stores data.", fontsize=11)
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Second page text line.", fontsize=11)
    p = tmp_path / "doc.pdf"
    doc.save(str(p))
    return p


@pytest.fixture
def empty_pdf(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    doc.new_page()
    p = tmp_path / "empty.pdf"
    doc.save(str(p))
    return p
