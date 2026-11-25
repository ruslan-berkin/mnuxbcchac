import pytest

from reqcheck.errors import EmptyDocumentError, InputFileError
from reqcheck.ingest import load_document


def test_markdown_blocks_sections_lines(sample_md):
    doc = load_document(sample_md)
    assert doc.format == "md"
    assert doc.title == "ТЗ тестовое"
    assert len(doc.sha256) == 64
    bullets = [b for b in doc.blocks if "Ф-1" in b.text]
    assert bullets and bullets[0].anchor.section == "Функциональные требования"
    a = bullets[0].anchor
    assert doc.lines[a.line_start - 1].startswith("* **Ф-1.**")
    # блок кода с пустой строкой внутри не разрывается
    code = next(b for b in doc.blocks if b.text.startswith("```"))
    assert "ещё код" in code.text


def test_txt(sample_txt):
    doc = load_document(sample_txt)
    assert doc.format == "txt"
    assert [b.text for b in doc.blocks] == ["Первая строка\nвторая строка", "Абзац два"]
    assert doc.blocks[0].anchor.line_start == 1 and doc.blocks[0].anchor.line_end == 2


def test_docx(sample_docx):
    doc = load_document(sample_docx)
    assert doc.format == "docx"
    assert doc.title == "Документ DOCX"
    texts = [b.text for b in doc.blocks]
    assert "Ф-1. Система должна работать быстро." in texts
    assert "| Версия | 1.0 |" in texts
    para = next(b for b in doc.blocks if b.text.startswith("Ф-1"))
    assert para.anchor.section == "Функциональные требования"


def test_pdf(sample_pdf):
    doc = load_document(sample_pdf)
    assert doc.format == "pdf"
    assert doc.title == "Heading line"
    fr1 = next(b for b in doc.blocks if "FR-1" in b.text)
    assert fr1.anchor.page == 1 and fr1.anchor.section == "Heading line"
    last = next(b for b in doc.blocks if "Second page" in b.text)
    assert last.anchor.page == 2
    assert doc.lines[last.anchor.line_start - 1] == "Second page text line."


def test_empty_pdf_is_error(empty_pdf):
    with pytest.raises(EmptyDocumentError) as e:
        load_document(empty_pdf)
    assert e.value.exit_code == 3


def test_empty_text_file(tmp_path):
    p = tmp_path / "e.txt"
    p.write_text("  \n\n", encoding="utf-8")
    with pytest.raises(EmptyDocumentError):
        load_document(p)


def test_missing_and_unsupported(tmp_path):
    with pytest.raises(InputFileError):
        load_document(tmp_path / "nope.pdf")
    bad = tmp_path / "a.xlsx"
    bad.write_text("x")
    with pytest.raises(InputFileError) as e:
        load_document(bad)
    assert e.value.exit_code == 2


def test_corrupt_pdf_is_input_error(tmp_path):
    p = tmp_path / "broken.pdf"
    p.write_bytes(b"not a pdf")
    with pytest.raises(InputFileError):
        load_document(p)
