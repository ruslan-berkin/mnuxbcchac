"""Тесты правил линтера §6. Тексты — не из выданного документа (правила общие)."""

import pytest

from reqcheck.checks import lint
from reqcheck.ingest import load_document
from reqcheck.segment import segment_explicit


def run(tmp_path, text, rule):
    p = tmp_path / "t.md"
    p.write_text(text, encoding="utf-8")
    d = load_document(p)
    findings = getattr(lint, rule)(d, segment_explicit(d))
    for f in findings:  # каждая цитата дословно присутствует в документе
        for q in f.quotes:
            assert " ".join(q.split()) in " ".join(d.full_text.split()), q
        assert f.anchors and f.question and f.source == "lint" and f.rule
    return findings


def test_time_without_reference(tmp_path):
    f = run(tmp_path, "## Т\n\nОтчёт формируется в течение 5 минут.\n\nПисьмо уходит в течение часа после оплаты.\n",
            "rule_time_without_reference")
    assert len(f) == 1 and "5 минут" in f[0].problem and f[0].criterion == "S-CMH"


def test_dash_fields_table_and_inline_and_db_column(tmp_path):
    f = run(tmp_path, (
        "## Метод\n\n| Поле | Значение |\n| :--- | :--- |\n| Swagger | — |\n| Автор | Иванов |\n\n"
        "Dev: `/a/b`. Prod: —\n\n"
        "| Parameter | Format | DB field |\n| :--- | :--- | :--- |\n| `x` | string | — |\n"), "rule_dash_fields")
    assert len(f) == 2
    assert any("Swagger" in x.problem for x in f)
    assert not any("«x»" in x.problem for x in f)  # прочерк в колонке DB field допустим


def test_unchecked_options_aggregated_per_table(tmp_path):
    f = run(tmp_path, "## Ч\n\n| Проверка | Готово |\n| :--- | :--- |\n| А | Да / Нет |\n| Б | Да / Нет / Не требуется |\n"
                      "| В | Да |\n", "rule_unchecked_options")
    assert len(f) == 1 and "2 строк" in f[0].problem and f[0].severity == "minor"


def test_empty_table_rows(tmp_path):
    f = run(tmp_path, "## С\n\n| Отдел | ФИО | Подпись |\n| :--- | :--- | :--- |\n| | | |\n| | | |\n",
            "rule_empty_table_rows")
    assert len(f) == 1 and "(2)" in f[0].problem


def test_empty_table_rows_not_triggered_for_filled(tmp_path):
    assert run(tmp_path, "## С\n\n| Отдел | ФИО |\n| :--- | :--- |\n| ИТ | Иванов |\n", "rule_empty_table_rows") == []


@pytest.mark.parametrize("text,expected", [
    ("# Док\n\nТекст без метаданных.\n", 1),
    ("# Док\n\nВерсия 1.2 от 03.05.2026.\n", 0),
    ("# Док\n\nВерсия 2.0.\n", 1),  # нет даты
    ("# Doc\n\nv1.4, 2026-05-03\n", 0),
])
def test_missing_version(tmp_path, text, expected):
    assert len(run(tmp_path, text, "rule_missing_version")) == expected


def test_mixed_units_nearby_only(tmp_path):
    near = run(tmp_path, "## Д\n\nСумма хранится в копейках.\n\nЛимит задаётся в рублях.\n", "rule_mixed_units")
    assert len(near) == 1 and near[0].scope == "set" and near[0].criterion == "S-CON"
    far = run(tmp_path, "Сумма в копейках.\n\n" + "\n\n".join(f"Строка {i}." for i in range(30)) +
              "\n\nЛимит в рублях.\n", "rule_mixed_units")
    assert far == []
    ms = run(tmp_path, "Таймаут 500 мс.\n\nОтвет за 2 секунды.\n", "rule_mixed_units")
    assert len(ms) == 1


def test_http_get_with_write_verb(tmp_path):
    f = run(tmp_path, "## Общие\n\n| Поле | Значение |\n| :--- | :--- |\n| Description | Создание заказа |\n"
                      "| REST type | GET |\n| URL | `/orders/create` |\n\n## Другой\n\nУдаление не тут.\n",
            "rule_http_method_verb")
    assert len(f) == 1 and f[0].scope == "set" and len(f[0].quotes) == 2


def test_http_post_is_fine(tmp_path):
    assert run(tmp_path, "## Общие\n\n| Description | Создание заказа |\n| REST type | POST |\n", "rule_http_method_verb") == []


def test_mixed_operation(tmp_path):
    f = run(tmp_path, "## О\n\n| Поле | Значение |\n| :-- | :-- |\n| Description | Сохранение профиля и чтение профиля |\n",
            "rule_mixed_operation")
    assert len(f) == 1 and f[0].criterion == "S-CON" or f[0].criterion == "SNG"
    assert run(tmp_path, "| Description | Чтение профиля |\n", "rule_mixed_operation") == []


STATUS_DOC = """## Ответ

Если результат 200 или 201 — успешный. Если вернулся 409, повторить позже.

## Статусы

**200.** Успех.
**400.** Неверный запрос.
"""


def test_status_codes_mentioned_not_described(tmp_path):
    f = run(tmp_path, STATUS_DOC, "rule_status_codes")
    codes = sorted(x.problem.split()[2] for x in f)
    assert codes == ["201", "409"]


def test_status_codes_ignores_amounts_and_docs_without_status_list(tmp_path):
    assert run(tmp_path, "Комиссия возвращается клиентом 500 руб. в течение дня.\n", "rule_status_codes") == []
    assert run(tmp_path, "## Ответ\n\nСервис возвращает ответ 404 при ошибке.\n", "rule_status_codes") == []


def test_content_type_without_body(tmp_path):
    f = run(tmp_path, "## Request body\n\n* Content-Type: application/json\n* Тело запроса не используется.\n",
            "rule_content_type_without_body")
    assert len(f) == 1
    assert run(tmp_path, "## Request body\n\n* Content-Type: application/json\n* Тело содержит JSON.\n",
               "rule_content_type_without_body") == []


def test_field_type_mismatch(tmp_path):
    doc = ("## Параметры запроса\n\n| Parameter | Format | Description |\n| :-- | :-- | :-- |\n"
           "| `id` | integer | Ид |\n| `name` | string | Имя |\n\n"
           "## Ответ\n\n| Parameter | Format | Description |\n| :-- | :-- | :-- |\n"
           "| `id` | string | Ид |\n| `name` | String | Имя |\n")
    f = run(tmp_path, doc, "rule_field_type_mismatch")
    assert len(f) == 1 and "«id»" in f[0].problem and len(f[0].quotes) == 2


def test_dangling_references(tmp_path):
    f = run(tmp_path, (
        "# Док\n\n## 1. Введение\n\nПодробности см. в разделе 7.2.\n\n"
        "Порядок описан в разделе 1.\n\n"
        "Требования ISO/IEC/IEEE 29148, п. 5.2.5 соблюдаются.\n\n"
        "Интеграция описана в документе «Спецификация обмена с биллингом».\n"), "rule_dangling_references")
    texts = " ".join(x.problem for x in f)
    assert "7.2" in texts and "Спецификация обмена" in texts
    assert len(f) == 2


def test_dangling_reference_to_existing_document_not_flagged(tmp_path):
    assert run(tmp_path, ("# Док\n\nСмотри раздел «Интеграция».\n\n## Интеграция\n\nТекст.\n"),
               "rule_dangling_references") == []


def test_run_lint_covers_all_rules_and_is_deterministic(fixtures):
    d = load_document(fixtures / "loyalty.md")
    a = lint.run_lint(d, segment_explicit(d))
    b = lint.run_lint(d, segment_explicit(d))
    assert [x.model_dump() for x in a] == [x.model_dump() for x in b]
    assert len(lint.RULES) >= 15
