"""lint: правила без LLM. Работают всегда, в том числе без ключа.

Правила общие, не привязаны к конкретному документу. Каждое правило — отдельная
функция `rule_*`, зарегистрированная в RULES.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from reqcheck.models import Anchor, Block, Document, Finding, Requirement, Severity

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


RULES: list[Rule] = [
    rule_vague_words,
    rule_open_lists,
    rule_conditional_phrases,
    rule_placeholders,
]


def run_lint(doc: Document, requirements: list[Requirement]) -> list[Finding]:
    findings: list[Finding] = []
    for rule in RULES:
        findings.extend(rule(doc, requirements))
    return findings
