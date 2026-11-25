from reqcheck.ground import GroundIndex, ground_findings, ground_requirements, normalize
from reqcheck.ingest import load_document
from reqcheck.models import Anchor, Finding, Requirement


def mkdoc(tmp_path, text):
    p = tmp_path / "d.md"
    p.write_text(text, encoding="utf-8")
    return load_document(p)


def finding(*quotes):
    return Finding(id="", scope="set", criterion="S-CON", severity="major", quotes=list(quotes),
                   anchors=[Anchor(line_start=1, line_end=1)] * len(quotes), problem="p", fix="f",
                   source="llm")


def test_normalize_case_yo_quotes_dashes_spaces_markup():
    assert normalize("«Всё  Ёлка» — **ТАК** да") == normalize('"все елка" - так да')


def test_exact_match_with_markdown_and_case(tmp_path):
    doc = mkdoc(tmp_path, "## Раздел\n\n* **Ф-1.** Система ВСЕГДА отвечает за 2 секунды.\n")
    m = GroundIndex(doc).find("система всегда отвечает за 2 секунды")
    assert m and m.method == "exact" and m.line_start == 3
    assert m.text == "Система ВСЕГДА отвечает за 2 секунды"


def test_quote_spanning_lines_and_yo(tmp_path):
    doc = mkdoc(tmp_path, "Объём берётся\nиз карты клиента.\n")
    m = GroundIndex(doc).find("Объем берется из карты клиента")
    assert m and (m.line_start, m.line_end) == (1, 2)
    assert m.text == "Объём берётся из карты клиента"


def test_fuzzy_match_small_typo(tmp_path):
    doc = mkdoc(tmp_path, "Сервис передаёт push на отправку в течение минуты после получения события.\n")
    m = GroundIndex(doc).find("Сервис передает push на отправку в течении минуты после получения события")
    assert m and m.method == "fuzzy" and m.score >= 90


def test_invented_quote_is_dropped_and_counted(tmp_path, caplog):
    doc = mkdoc(tmp_path, "## Р\n\nСистема отправляет письмо клиенту сразу после оплаты заказа.\n")
    good = finding("Система отправляет письмо клиенту сразу после оплаты заказа.")
    bad = finding("Система удаляет аккаунт клиента через 30 дней без предупреждения.")
    mixed = finding("Система отправляет письмо клиенту", "Совсем выдуманная цитата про блокчейн и ИИ")
    with caplog.at_level("WARNING"):
        kept, dropped = ground_findings(doc, [good, bad, mixed])
    assert dropped == 2 and len(kept) == 1
    assert kept[0].anchors[0].section == "Р" and kept[0].anchors[0].line_start == 3
    assert "цитата не найдена" in caplog.text


def test_finding_without_quotes_is_dropped(tmp_path):
    doc = mkdoc(tmp_path, "Текст документа.\n")
    kept, dropped = ground_findings(doc, [finding()])
    assert kept == [] and dropped == 1


def test_short_quote_needs_exact(tmp_path):
    doc = mkdoc(tmp_path, "быстро и надёжно работает\n")
    assert GroundIndex(doc).find("быстро")
    assert GroundIndex(doc).find("быстра") is None  # слишком коротко для fuzzy


def test_requirements_grounded_and_replaced(tmp_path):
    doc = mkdoc(tmp_path, "## Р\n\nПароль хранится в хэшированном виде.\n")
    r = Requirement(id="R-01", kind="other", quote="пароль хранится в хэшированном виде",
                    summary="s", anchor=Anchor(line_start=1, line_end=1))
    fake = r.model_copy(update={"id": "R-02", "quote": "нет такого текста вообще нигде тут"})
    kept, dropped = ground_requirements(doc, [r, fake])
    assert dropped == 1 and kept[0].quote == "Пароль хранится в хэшированном виде"
    assert kept[0].anchor.line_start == 3 and kept[0].anchor.section == "Р"


def test_works_on_pdf_table_rows(repo_root):
    doc = load_document(repo_root / "examples" / "input" / "requirements.pdf")
    m = GroundIndex(doc).find("Покупка 31 января в 23:58 на 4 000 ₸")
    assert m and doc.lines[m.line_start - 1].startswith("| Покупка 31 января")
