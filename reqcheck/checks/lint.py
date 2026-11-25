"""lint: правила без LLM. Работают всегда, в том числе без ключа.

Правила общие, не привязаны к конкретному документу. Каждое правило — отдельная
функция `rule_*`, зарегистрированная в RULES.
"""

from __future__ import annotations

import bisect
import hashlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass

from reqcheck.models import Anchor, Block, Document, Finding, Requirement, Severity

log = logging.getLogger("reqcheck.lint")
Rule = Callable[[Document, list[Requirement]], list[Finding]]


@dataclass(frozen=True)
class _Pattern:
    regex: re.Pattern[str]
    severity: Severity


def _words(*words: str) -> re.Pattern[str]:
    alt = "|".join(words)
    return re.compile(rf"(?<![\w-])(?:{alt})(?![\w])", re.IGNORECASE)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+")


def _is_code_or_heading(block: Block) -> bool:
    t = block.text.lstrip()
    return t.startswith(("```", "~~~", "#"))


def _sentence_at(line: str, pos: int) -> str:
    """Предложение строки, содержащее позицию pos (подстрока строки документа)."""
    offset = 0
    for part in _SENTENCE_SPLIT.split(line):
        idx = line.find(part, offset)
        if idx <= pos < idx + len(part):
            return part.strip()
        offset = idx + len(part)
    return line.strip()


def _owner(requirements: list[Requirement], line_no: int) -> Requirement | None:
    for r in requirements:
        if r.anchor.line_start <= line_no <= r.anchor.line_end:
            return r
    return None


def _iter_hits(doc: Document, patterns: list[_Pattern]):
    """Для каждого совпадения: (блок, номер строки, строка, match, severity)."""
    for block in doc.blocks:
        if _is_code_or_heading(block):
            continue
        for offset, line in enumerate(block.text.split("\n")):
            for p in patterns:
                for m in p.regex.finditer(line):
                    yield block, block.anchor.line_start + offset, line, m, p.severity


def _fingerprint(rule: str, lines: list[int], text: str) -> str:
    return hashlib.sha1(f"{rule}|{sorted(set(lines))}|{text}".encode("utf-8")).hexdigest()[:16]


def _make(
    *, rule: str, req_code: str, set_code: str, severity: Severity, block: Block, line_no: int,
    line: str, m: re.Match[str], requirements: list[Requirement],
    problem: str, fix: str, question: str,
) -> Finding:
    term = m.group(0)
    owner = _owner(requirements, line_no)
    fmt = {"term": term}
    return Finding(
        id="",
        scope="requirement" if owner else "set",
        requirement_ids=[owner.id] if owner else [],
        criterion=req_code if owner else set_code,  # type: ignore[arg-type]
        severity=severity,
        quotes=[_sentence_at(line, m.start())],
        anchors=[Anchor(section=block.anchor.section, page=block.anchor.page,
                        line_start=line_no, line_end=line_no)],
        problem=problem.format(**fmt),
        fix=fix.format(**fmt),
        question=question.format(**fmt),
        source="lint",
        rule=rule,
        fingerprint=_fingerprint(rule, [line_no], term + problem.format(**fmt)),
    )


# ------------------------------------------------------------------ правила

_VAGUE = [_Pattern(_words(
    "быстро", "быстрый", "быстрая", "быстрое", "удобно", "удобный", "удобная", "оптимально",
    "оптимальный", "достаточно", "достаточный", "как правило", "красиво", "надёжно", "надежно",
    "максимально", "минимально возможн\\w+", "user-friendly", "fast", "quickly", "easy",
), "major")]


def rule_vague_words(doc: Document, requirements: list[Requirement]) -> list[Finding]:
    out = []
    for block, line_no, line, m, sev in _iter_hits(doc, _VAGUE):
        out.append(_make(
            rule="vague_words", req_code="UNA", set_code="S-CMH", severity=sev, block=block,
            line_no=line_no, line=line, m=m, requirements=requirements,
            problem="Оценочное слово «{term}» без измеримого критерия: его можно понять по-разному, "
                    "и по нему нельзя написать однозначный тест.",
            fix="Заменить «{term}» измеримым значением: число, единица, граница и способ измерения.",
            question="Какое измеримое значение скрывается за словом «{term}» "
                     "(число, единица, граница, способ измерения)?",
        ))
    return out


_OPEN_LIST = [_Pattern(_words(r"и т\.\s?п\.", r"и т\.\s?д\.", r"и др\.", "и прочее", "и так далее",
                              "etc\\.?", "и тому подобн\\w+"), "minor")]


def rule_open_lists(doc: Document, requirements: list[Requirement]) -> list[Finding]:
    out = []
    for block, line_no, line, m, sev in _iter_hits(doc, _OPEN_LIST):
        out.append(_make(
            rule="open_lists", req_code="UNA", set_code="S-CMP", severity=sev, block=block,
            line_no=line_no, line=line, m=m, requirements=requirements,
            problem="Открытый перечень («{term}»): состав не определён, объём работ и приёмка "
                    "остаются на усмотрение исполнителя.",
            fix="Перечислить все элементы явно или указать, что список закрытый.",
            question="Какие именно элементы входят в перечень вместо «{term}»? Список закрытый?",
        ))
    return out


_CONDITIONAL = [_Pattern(_words("при необходимости", "по возможности", "при желании",
                                "в случае необходимости", "если потребуется", "где возможно"), "major")]


def rule_conditional_phrases(doc: Document, requirements: list[Requirement]) -> list[Finding]:
    out = []
    for block, line_no, line, m, sev in _iter_hits(doc, _CONDITIONAL):
        out.append(_make(
            rule="conditional_phrases", req_code="VER", set_code="S-VAL", severity=sev, block=block,
            line_no=line_no, line=line, m=m, requirements=requirements,
            problem="Оборот «{term}» делает исполнение необязательным и не задаёт условие: "
                    "нельзя проверить, выполнено требование или нет.",
            fix="Указать точное условие, при котором действие обязательно, или убрать оборот.",
            question="При каком конкретном условии срабатывает «{term}» и кто это решает?",
        ))
    return out


_PLACEHOLDER = [_Pattern(re.compile(
    r"(?<![\w-])(?:TBD|TODO|TBC|заполня(?:ются|ется|ть)(?:\s+\w+)?|не заполнен\w*|будет определен\w+|"
    r"уточня(?:ется|ются)\s+позже)(?![\w])", re.IGNORECASE), "major")]


def rule_placeholders(doc: Document, requirements: list[Requirement]) -> list[Finding]:
    out = []
    for block, line_no, line, m, sev in _iter_hits(doc, _PLACEHOLDER):
        out.append(_make(
            rule="placeholders", req_code="CMP", set_code="S-CMP", severity=sev, block=block,
            line_no=line_no, line=line, m=m, requirements=requirements,
            problem="Раздел не заполнен или содержит заглушку («{term}»): содержимого для "
                    "реализации и проверки нет.",
            fix="Заполнить раздел или убрать его, если он не нужен. Указать ответственного и срок.",
            question="Кто и к какому сроку заполнит этот раздел? Что в нём должно быть до начала разработки?",
        ))
    return out



# ============================================================ правила по структуре и HTTP
#
# Общие правила: ни одно не опирается на формулировки конкретного документа.


def _line_sections(doc: Document) -> dict[int, str]:
    out: dict[int, str] = {}
    for b in doc.blocks:
        for n in range(b.anchor.line_start, b.anchor.line_end + 1):
            out[n] = b.anchor.section
    return out


def _anchor(doc: Document, line_no: int) -> Anchor:
    for b in doc.blocks:
        a = b.anchor
        if a.line_start <= line_no <= a.line_end:
            return Anchor(section=a.section, page=a.page, line_start=line_no, line_end=line_no)
    return Anchor(line_start=line_no, line_end=line_no)


def _line(doc: Document, n: int) -> str:
    return doc.lines[n - 1].strip()


def _build(
    doc: Document, reqs: list[Requirement], *, rule: str, req_code: str, set_code: str,
    severity: Severity, lines: list[int], quotes: list[str] | None = None,
    problem: str, fix: str, question: str,
) -> Finding:
    owners = list(dict.fromkeys(r.id for n in lines if (r := _owner(reqs, n))))
    # Правило смотрит на несколько мест сразу (противоречие, сравнение) — это замечание к набору.
    as_set = len(set(lines)) > 1 or not owners
    return Finding(
        id="",
        scope="set" if as_set else "requirement",
        requirement_ids=owners,
        criterion=set_code if as_set else req_code,  # type: ignore[arg-type]
        severity=severity,
        quotes=quotes if quotes is not None else [_line(doc, n) for n in lines],
        anchors=[_anchor(doc, n) for n in lines],
        problem=problem, fix=fix, question=question, source="lint", rule=rule,
        fingerprint=_fingerprint(rule, lines, problem),
    )


_SEP_CELL = re.compile(r"^:?-{3,}:?$")


def _cells(line: str) -> list[str]:
    s = line.strip()
    if not s.startswith("|"):
        return []
    s = s[1:-1] if s.endswith("|") else s[1:]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def _is_sep(cells: list[str]) -> bool:
    return bool(cells) and all(_SEP_CELL.match(c) or c == "" for c in cells) and any(cells)


def _tables(doc: Document) -> list[list[tuple[int, list[str]]]]:
    """Таблицы: списки (номер строки, ячейки). Строки-разделители пропускаются."""
    out: list[list[tuple[int, list[str]]]] = []
    cur: list[tuple[int, list[str]]] = []
    for i, line in enumerate(doc.lines, start=1):
        cells = _cells(line)
        if cells:
            if not _is_sep(cells):
                cur.append((i, cells))
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _plain(cell: str) -> str:
    return re.sub(r"[*_`]", "", cell).strip()


# --- «в течение» без точки отсчёта

_WITHIN = re.compile(
    r"в\s+течение\s+(?:[\w\-]+\s+){0,2}?(?:секунд\w*|сек\.?|минут\w*|мин\.?|час\w*|дн\w*|суток|"
    r"недел\w*|месяц\w*|мс|миллисекунд\w*)(?![\w])", re.IGNORECASE)
_REFERENCE = re.compile(
    r"после|с\s+момента|со\s+дня|с\s+даты|от\s+(?:момента|получения|даты)|начиная|по\s+истечении|"
    r"с\s+(?:получения|поступления|начала)|с\s+того\s+как|в\s+случае|при\s+получении|within\s+\d.*\bof\b|after|since",
    re.IGNORECASE)


def rule_time_without_reference(doc: Document, reqs: list[Requirement]) -> list[Finding]:
    out = []
    for block in doc.blocks:
        if _is_code_or_heading(block):
            continue
        for off, line in enumerate(block.text.split("\n")):
            for m in _WITHIN.finditer(line):
                sentence = _sentence_at(line, m.start())
                if _REFERENCE.search(sentence):
                    continue
                n = block.anchor.line_start + off
                out.append(_build(
                    doc, reqs, rule="time_without_reference", req_code="UNA", set_code="S-CMH",
                    severity="major", lines=[n], quotes=[sentence],
                    problem=f"Срок «{m.group(0)}» задан без точки отсчёта: неясно, с какого события "
                            "он считается, поэтому его нельзя измерить и проверить.",
                    fix="Указать событие, от которого идёт отсчёт, и способ измерения "
                        "(например, перцентиль и точки замера).",
                    question=f"От какого именно события отсчитывается «{m.group(0)}» и как это измеряется?",
                ))
    return out


# --- прочерк вместо значения

_DASHES_ONLY = {"—", "–", "-", "−"}
_INLINE_DASH = re.compile(r"[:：]\s*[—–−]\s*(?=[.;,)]|\s*$)")


def rule_dash_fields(doc: Document, reqs: list[Requirement]) -> list[Finding]:
    out = []
    seen: set[int] = set()
    for table in _tables(doc):
        header = [_plain(h).lower() for h in table[0][1]]
        for n, cells in table[1:]:
            label = _plain(cells[0]) if cells else ""
            for k, c in enumerate(cells[1:], start=1):
                # В колонке «DB field» прочерк означает «поля в БД нет», это не пропуск.
                if k < len(header) and re.search(r"\bdb\b|бд|баз[аы]", header[k]):
                    continue
                if _plain(c) in _DASHES_ONLY:
                    seen.add(n)
                    out.append(_build(
                        doc, reqs, rule="dash_fields", req_code="CMP", set_code="S-CMP",
                        severity="major", lines=[n],
                        problem=f"Поле «{label}» содержит прочерк вместо значения: сведений для "
                                "реализации или проверки нет.",
                        fix="Заполнить поле или явно указать, что оно не применимо, и почему.",
                        question=f"Какое значение должно быть у поля «{label}», или оно не требуется?",
                    ))
                    break
    for block in doc.blocks:
        if _is_code_or_heading(block):
            continue
        for off, line in enumerate(block.text.split("\n")):
            n = block.anchor.line_start + off
            if n in seen or line.lstrip().startswith("|"):
                continue
            for m in _INLINE_DASH.finditer(line):
                head = re.split(r"[.;]\s", line[:m.start()])[-1].strip(" *`")
                label = head.split()[-1] if head.split() else "значение"
                out.append(_build(
                    doc, reqs, rule="dash_fields", req_code="CMP", set_code="S-CMP",
                    severity="major", lines=[n], quotes=[_sentence_at(line, m.start())],
                    problem=f"Значение «{label}» заменено прочерком: сведений для реализации нет.",
                    fix="Заполнить значение или явно указать, что оно не применимо.",
                    question=f"Какое значение должно быть у «{label}», или оно не требуется?",
                ))
    return out


# --- «Да / Нет» без отметки и пустые строки таблиц

_UNCHECKED = re.compile(r"^да\s*/\s*нет(?:\s*/\s*не\s+требуется)?$", re.IGNORECASE)


def rule_unchecked_options(doc: Document, reqs: list[Requirement]) -> list[Finding]:
    out = []
    for table in _tables(doc):
        hits = [n for n, cells in table[1:] if any(_UNCHECKED.match(_plain(c)) for c in cells)]
        if hits:
            out.append(_build(
                doc, reqs, rule="unchecked_options", req_code="CNF", set_code="S-VAL",
                severity="minor", lines=[hits[0]],
                problem=f"В таблице {len(hits)} строк(и) с невыбранным вариантом «Да / Нет»: "
                        "отметки не проставлены, проверка по чек-листу не выполнена.",
                fix="Проставить отметки или убрать неприменимые строки; указать, кто и когда проверил.",
                question="Кто и до какой даты проставит отметки в чек-листе ревью?",
            ))
    return out


def rule_empty_table_rows(doc: Document, reqs: list[Requirement]) -> list[Finding]:
    out = []
    for table in _tables(doc):
        header_n, header = table[0]
        empty = [n for n, cells in table[1:] if cells and all(c == "" for c in cells)]
        if empty and any(c for c in header):
            out.append(_build(
                doc, reqs, rule="empty_table_rows", req_code="CMP", set_code="S-CMP",
                severity="major", lines=[header_n],
                problem=f"В таблице «{' | '.join(c for c in header if c)}» есть пустые строки "
                        f"({len(empty)}): данные не внесены.",
                fix="Заполнить строки (например, ответственных и подписи) или удалить пустые.",
                question="Кто должен быть указан в этой таблице и когда будет заполнено?",
            ))
    return out


# --- версия и дата документа

_VERSION = re.compile(r"(?:верси\w*|version|редакци\w*|ред\.)\s*[:№]?\s*v?\d+(?:\.\d+)*|\bv\d+(?:\.\d+)+\b",
                      re.IGNORECASE)
_DATE = re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b|"
                   r"\b\d{1,2}\s+(?:январ|феврал|март|апрел|ма[яй]|июн|июл|август|сентябр|октябр|ноябр|декабр)\w*\s+\d{4}",
                   re.IGNORECASE)


def rule_missing_version(doc: Document, reqs: list[Requirement]) -> list[Finding]:
    text = doc.full_text
    missing = []
    if not _VERSION.search(text):
        missing.append("версия")
    if not _DATE.search(text):
        missing.append("дата")
    if not missing:
        return []
    first = next((i for i, ln in enumerate(doc.lines, start=1) if ln.strip()), 1)
    return [_build(
        doc, reqs, rule="missing_version", req_code="CNF", set_code="S-MOD", severity="minor",
        lines=[first],
        problem=f"В документе не указаны: {', '.join(missing)}. Без них нельзя понять, какая "
                "редакция требований согласована, и отследить изменения.",
        fix="Указать версию и дату документа и вести историю изменений.",
        question="Какая версия и дата у этого документа и где ведётся история изменений?",
    )]


# --- смешение единиц одной величины

_UNIT_FAMILIES: list[tuple[str, re.Pattern[str], str, re.Pattern[str]]] = [
    ("тиын", re.compile(r"тиын\w*", re.I), "тенге", re.compile(r"тенге|₸", re.I)),
    ("копейки", re.compile(r"копе(?:йк|ек)\w*", re.I), "рубли", re.compile(r"руб(?:л\w*|\.)|₽", re.I)),
    ("миллисекунды", re.compile(r"(?<!\w)(?:мс|мсек\.?|миллисекунд\w*)(?!\w)", re.I), "секунды",
     re.compile(r"(?<!\w)(?:сек\.?|секунд\w*)(?!\w)", re.I)),
]
_UNIT_WINDOW = 15


def _near_pair(xs: list[int], ys: list[int], window: int) -> tuple[int, int] | None:
    """Первая пара (x, y), где |x - y| <= window; xs и ys отсортированы. O((A+B) log B) вместо O(A·B)."""
    for x in xs:
        k = bisect.bisect_left(ys, x - window)
        if k < len(ys) and ys[k] <= x + window:
            return x, ys[k]
    return None


def rule_mixed_units(doc: Document, reqs: list[Requirement]) -> list[Finding]:
    out = []
    for name_a, pat_a, name_b, pat_b in _UNIT_FAMILIES:
        hits_a = [i for i, ln in enumerate(doc.lines, start=1) if pat_a.search(ln)]
        hits_b = [i for i, ln in enumerate(doc.lines, start=1) if pat_b.search(ln)]
        pair = _near_pair(hits_a, hits_b, _UNIT_WINDOW)
        if not pair:
            continue
        a, b = pair
        lines = sorted({a, b})
        out.append(_build(
            doc, reqs, rule="mixed_units", req_code="COR", set_code="S-CON", severity="major",
            lines=lines,
            problem=f"Рядом используются разные единицы одной величины: {name_a} и {name_b}. "
                    "Без явного правила пересчёта легко получить расхождение на порядки при реализации и сравнении.",
            fix=f"Привести к одной единице или явно описать пересчёт между «{name_a}» и «{name_b}» "
                "и место, где он выполняется.",
            question=f"В каких единицах ({name_a} или {name_b}) хранится, передаётся и сравнивается "
                     "каждая из этих величин и где выполняется пересчёт?",
        ))
    return out


# --- HTTP

_METHOD_LINE = re.compile(r"REST\s*type\W+(GET|POST|PUT|PATCH|DELETE)\b|^\W*(GET|POST|PUT|PATCH|DELETE)\s+/",
                          re.IGNORECASE)
_WRITE_VERB = re.compile(
    r"(?<![\w])(?:сохран\w*|созда\w*|измен\w*|удал\w*|обнов\w*|записа\w*|добав\w*|"
    r"save|create|update|delete|remove|insert)", re.IGNORECASE)
_URL_WRITE = re.compile(r"/[\w/\-]*(?:save|create|update|delete|remove|set|add)\w*", re.IGNORECASE)
_READ_VERB = re.compile(r"(?<![\w])(?:чтен\w*|чита\w*|прочит\w*|получ\w*|read|fetch)", re.IGNORECASE)


def rule_http_method_verb(doc: Document, reqs: list[Requirement]) -> list[Finding]:
    secs = _line_sections(doc)
    out = []
    for i, line in enumerate(doc.lines, start=1):
        m = _METHOD_LINE.search(line)
        method = (m.group(1) or m.group(2)).upper() if m else ""
        if method != "GET":
            continue
        same = [n for n in range(max(1, i - 25), min(len(doc.lines), i + 25) + 1)
                if secs.get(n) == secs.get(i) and n != i]
        hit = next((n for n in same
                    if _WRITE_VERB.search(doc.lines[n - 1]) or _URL_WRITE.search(doc.lines[n - 1])), None)
        if hit is None:
            continue
        out.append(_build(
            doc, reqs, rule="http_method_verb", req_code="COR", set_code="S-CON", severity="major",
            lines=[i, hit],
            problem="Операция изменяет данные (сохранить/создать/изменить/удалить), но описана методом GET. "
                    "GET по определению безопасный метод и не должен менять состояние (RFC 9110, п. 9.2.1).",
            fix="Использовать POST, PUT, PATCH или DELETE в зависимости от семантики операции "
                "и описать тело запроса.",
            question="Какой HTTP-метод должен использоваться для этой операции и почему выбран GET?",
        ))
    return out


def rule_mixed_operation(doc: Document, reqs: list[Requirement]) -> list[Finding]:
    out = []
    for i, line in enumerate(doc.lines, start=1):
        cells = _cells(line)
        if len(cells) < 2 or not re.fullmatch(r"(?:description|описание)", _plain(cells[0]), re.I):
            continue
        desc = " ".join(cells[1:])
        if _WRITE_VERB.search(desc) and _READ_VERB.search(desc):
            out.append(_build(
                doc, reqs, rule="mixed_operation", req_code="SNG", set_code="S-CON", severity="major",
                lines=[i],
                problem="Описание метода объединяет запись и чтение: из него неясно, что делает один вызов.",
                fix="Разделить на два метода или описать один вызов, указав, что он принимает и что возвращает.",
                question="Это один метод или два? Что делает вызов: сохраняет, читает или оба действия сразу?",
            ))
    return out


_STATUS_DESCRIBED = re.compile(r"^[\s#*|•\-–]*([1-5]\d\d)\**\s*(?:[.:]|[—–-]\s)")
_STATUS_CONTEXT = re.compile(r"статус|код\w*|возвращ\w*|результат|http|status|ответ", re.IGNORECASE)
_STATUS_MENTION = re.compile(
    r"(?<![\d.,/\-:])(?<!\d )(?<!\d\xa0)([1-5]\d\d)(?!\d)(?![.,]\d)(?!\s*(?:руб|₸|тенге|тиын|сек|мс|%|шт|симв|байт|"
    r"кб|мб|дн|мин|час|₽|\d))", re.IGNORECASE)


def rule_status_codes(doc: Document, reqs: list[Requirement]) -> list[Finding]:
    described: set[str] = set()
    for line in doc.lines:
        m = _STATUS_DESCRIBED.match(line)
        if m:
            described.add(m.group(1))
    if not described:
        return []  # в документе нет списка статусов — это не описание API
    out = []
    reported: set[str] = set()
    for i, line in enumerate(doc.lines, start=1):
        own = _STATUS_DESCRIBED.match(line)
        if not _STATUS_CONTEXT.search(line):
            continue
        for m in _STATUS_MENTION.finditer(line):
            code = m.group(1)
            if (own and own.group(1) == code) or code in described or code in reported:
                continue
            reported.add(code)
            out.append(_build(
                doc, reqs, rule="status_codes", req_code="CMP", set_code="S-CMP", severity="major",
                lines=[i], quotes=[_sentence_at(line, m.start())],
                problem=f"Код статуса {code} упоминается в тексте, но не описан в списке статусов: "
                        "неизвестно, при каких условиях он возвращается и каким будет тело ответа.",
                fix=f"Добавить статус {code} в список с условием возврата и примером ответа "
                    "или убрать упоминание.",
                question=f"Возвращается ли статус {code}? При каких условиях и с каким телом ответа?",
            ))
    return out


_NO_BODY = re.compile(r"тело\s+(?:запроса\s+)?не\s+использу\w+|без\s+тела|нет\s+тела|"
                      r"body\s+(?:is\s+)?not\s+(?:used|required)|no\s+(?:request\s+)?body", re.IGNORECASE)


def rule_content_type_without_body(doc: Document, reqs: list[Requirement]) -> list[Finding]:
    secs = _line_sections(doc)
    out = []
    for i, line in enumerate(doc.lines, start=1):
        if not re.search(r"content-type", line, re.IGNORECASE):
            continue
        hit = next((n for n in range(max(1, i - 10), min(len(doc.lines), i + 10) + 1)
                    if n != i and secs.get(n) == secs.get(i) and _NO_BODY.search(doc.lines[n - 1])), None)
        if hit is None:
            continue
        out.append(_build(
            doc, reqs, rule="content_type_without_body", req_code="COR", set_code="S-CON",
            severity="minor", lines=[i, hit],
            problem="Указан заголовок Content-Type, хотя тело запроса не используется: "
                    "заголовок не несёт смысла и сбивает реализатора.",
            fix="Убрать Content-Type или описать тело запроса.",
            question="Используется ли тело запроса? Если нет, зачем указан Content-Type?",
        ))
    return out


_TYPE_ALIASES = {"int": "integer", "int32": "integer", "int64": "integer", "long": "integer",
                 "number": "integer", "str": "string", "text": "string", "bool": "boolean"}
_REQ_SECTION = re.compile(r"запрос|request|query|path|body|тело", re.IGNORECASE)
_RESP_SECTION = re.compile(r"ответ|response", re.IGNORECASE)


def _ptype(value: str) -> str:
    v = re.sub(r"[`*_]", "", value).strip().lower()
    return _TYPE_ALIASES.get(v, v)


def rule_field_type_mismatch(doc: Document, reqs: list[Requirement]) -> list[Finding]:
    side_fields: dict[str, dict[str, tuple[str, int]]] = {"req": {}, "resp": {}}
    secs = _line_sections(doc)
    for table in _tables(doc):
        header = [_plain(c).lower() for c in table[0][1]]
        name_i = next((k for k, h in enumerate(header)
                       if re.fullmatch(r"parameter|param|name|field|параметр|поле|имя", h)), None)
        type_i = next((k for k, h in enumerate(header)
                       if re.fullmatch(r"format|type|формат|тип", h)), None)
        if name_i is None or type_i is None:
            continue
        section = secs.get(table[0][0], "")
        side = "resp" if _RESP_SECTION.search(section) else "req" if _REQ_SECTION.search(section) else None
        if side is None:
            continue
        for n, cells in table[1:]:
            if max(name_i, type_i) < len(cells):
                name = _plain(cells[name_i])
                if name:
                    side_fields[side].setdefault(name, (_ptype(cells[type_i]), n))
    out = []
    for name, (t_req, n_req) in side_fields["req"].items():
        if name in side_fields["resp"]:
            t_resp, n_resp = side_fields["resp"][name]
            if t_req != t_resp:
                out.append(_build(
                    doc, reqs, rule="field_type_mismatch", req_code="COR", set_code="S-CON",
                    severity="major", lines=[n_req, n_resp],
                    problem=f"Поле «{name}» имеет тип «{t_req}» в запросе и «{t_resp}» в ответе: "
                            "клиент и сервер по-разному разбирают одно и то же значение.",
                    fix="Привести типы к одному или явно описать преобразование.",
                    question=f"Какой тип должен быть у поля «{name}» в запросе и в ответе и почему они различаются?",
                ))
    return out


# --- ссылки на несуществующие разделы и документы

_REF_NUM = re.compile(r"(?<![\w.])(?:разделе?|разделу|раздела|пункт\w*|п\.|section|§)\s*(\d+(?:\.\d+)*)", re.IGNORECASE)
_REF_NAMED = re.compile(r"(?:раздел\w*|section|приложени\w*|документ\w*|спецификаци\w*)\s*[«\"]([^»\"]{4,120})[»\"]",
                        re.IGNORECASE)
_STANDARD_CONTEXT = re.compile(r"ISO|IEC|IEEE|ГОСТ|RFC|СТ РК|стандарт", re.IGNORECASE)


def _heading_names(doc: Document) -> list[str]:
    from reqcheck.ground import normalize
    names = {normalize(b.anchor.section) for b in doc.blocks if b.anchor.section}
    return [n for n in names if n]


_NUM_PREFIX = re.compile(r"^[\s|*#•\-]*(\d+(?:\.\d+)*)(?=[.\s)]|$)")


def _known_numbers(doc: Document, headings: list[str]) -> set[str]:
    """Номера разделов, начинающие строку или заголовок, вместе со всеми «родительскими» префиксами (1.2.3 → 1, 1.2)."""
    out: set[str] = set()
    for text in list(doc.lines) + headings:
        m = _NUM_PREFIX.match(text)
        if m:
            parts = m.group(1).split(".")
            out.update(".".join(parts[:k]) for k in range(1, len(parts) + 1))
    return out


def rule_dangling_references(doc: Document, reqs: list[Requirement]) -> list[Finding]:
    from reqcheck.ground import normalize

    headings = _heading_names(doc)
    norm_lines = [normalize(ln) for ln in doc.lines]
    numbers = _known_numbers(doc, headings)
    name_counts: dict[str, int] = {}
    out = []
    for block in doc.blocks:
        if _is_code_or_heading(block):
            continue
        for off, line in enumerate(block.text.split("\n")):
            n = block.anchor.line_start + off
            for m in _REF_NUM.finditer(line):
                sentence = _sentence_at(line, m.start())
                if _STANDARD_CONTEXT.search(sentence):
                    continue
                num = m.group(1)
                if num in numbers:
                    continue
                out.append(_build(
                    doc, reqs, rule="dangling_references", req_code="CMP", set_code="S-TRC",
                    severity="major", lines=[n], quotes=[sentence],
                    problem=f"Ссылка на раздел/пункт {num}, которого нет в документе: "
                            "читатель не может найти, на что именно сослались.",
                    fix="Исправить номер ссылки или добавить недостающий раздел.",
                    question=f"Какой раздел имеется в виду под «{m.group(0)}» и где он находится?",
                ))
            for m in _REF_NAMED.finditer(line):
                name = normalize(m.group(1))
                if not name:
                    continue
                if any(name in h or h in name for h in headings if len(h) >= 4):
                    continue
                if name not in name_counts:
                    name_counts[name] = sum(1 for ln in norm_lines if name in ln)
                if name_counts[name] >= 2:
                    continue
                out.append(_build(
                    doc, reqs, rule="dangling_references", req_code="CMP", set_code="S-TRC",
                    severity="major", lines=[n], quotes=[_sentence_at(line, m.start())],
                    problem=f"Ссылка на «{m.group(1)}», но такого раздела или документа в предоставленном "
                            "тексте нет: проверить согласованность нельзя.",
                    fix="Приложить документ или раздел либо убрать ссылку и перенести нужные требования сюда.",
                    question=f"Где находится «{m.group(1)}» и можно ли получить его для проверки?",
                ))
    return out


# --- попытки внедрить инструкции в документ (детерминированный пол вердикта)

_INJECTION = re.compile(
    r"(?i)(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\s+"
    r"(?:instructions?|rules?|prompts?)|"
    r"игнорируй\w*\s+(?:все\s+|вс[её]\s+)?(?:предыдущ\w+|прежн\w+|вышестоящ\w+|системн\w+)\s+"
    r"(?:инструкци\w+|правил\w+|указани\w+|промпт\w*)|"
    r"system\s+prompt|системн\w+\s+промпт|you\s+are\s+now|ты\s+теперь|"
    r"верни\s+пустой\s+список|не\s+сообщай\s+о\s+(?:дефект|замечани|проблем)\w*|"
    r"return\s+an?\s+empty\s+(?:list|array)|<\s*/?\s*(?:document|data)\b")


def rule_prompt_injection_markers(doc: Document, requirements: list[Requirement]) -> list[Finding]:
    """Текст, похожий на команду ИИ-ассистенту. Это дефект документа, а не указание агенту."""
    out = []
    for i, line in enumerate(doc.lines, start=1):
        m = _INJECTION.search(line)
        if not m:
            continue
        term = m.group(0).strip()
        out.append(_build(
            doc, requirements, rule="prompt_injection_markers", req_code="COR", set_code="S-CMH",
            severity="major", lines=[i], quotes=[_sentence_at(line, m.start())],
            problem=f"В документе есть фрагмент, похожий на команду ИИ-ассистенту («{term}»). Агент считает "
                    "документ данными и такие команды не выполняет; посторонняя вставка в требованиях — дефект "
                    "документа и признак попытки повлиять на результат проверки.",
            fix="Удалить постороннюю вставку из текста требований.",
            question=f"Кто и зачем добавил в документ фрагмент «{term}»? Его нужно удалить?",
        ))
    return out


RULES: list[Rule] = [
    rule_vague_words,
    rule_open_lists,
    rule_conditional_phrases,
    rule_placeholders,
    rule_time_without_reference,
    rule_dash_fields,
    rule_unchecked_options,
    rule_empty_table_rows,
    rule_missing_version,
    rule_mixed_units,
    rule_http_method_verb,
    rule_mixed_operation,
    rule_status_codes,
    rule_content_type_without_body,
    rule_field_type_mismatch,
    rule_dangling_references,
    rule_prompt_injection_markers,
]


def run_lint_safe(
    doc: Document, requirements: list[Requirement], per_rule_cap: int = 10**9
) -> tuple[list[Finding], list[str], list[str]]:
    """Каждое правило изолировано: сбой одного не роняет прогон.

    Возвращает (замечания, упавшие правила, правила, обрезанные по лимиту замечаний).
    """
    findings: list[Finding] = []
    failed: list[str] = []
    truncated: list[str] = []
    for rule in RULES:
        try:
            found = rule(doc, requirements)
        except Exception:  # noqa: BLE001 — правило не должно ронять оплаченный прогон
            log.exception("lint: правило %s упало", rule.__name__)
            failed.append(rule.__name__)
            continue
        if len(found) > per_rule_cap:
            truncated.append(rule.__name__)
            found = found[:per_rule_cap]
        findings.extend(found)
    return findings, failed, truncated


def run_lint(doc: Document, requirements: list[Requirement]) -> list[Finding]:
    return run_lint_safe(doc, requirements)[0]
