"""render: сборка отчёта из данных через Jinja2-шаблон (структуру задаёт код, не модель)."""

from __future__ import annotations

from jinja2 import Environment, PackageLoader

from reqcheck.criteria import CRITERIA, REQUIREMENT_CODES, SET_CODES
from reqcheck.models import Anchor, Finding, Report, Requirement
from reqcheck.summary import SEVERITY_RU, build_summary, top_priorities

SECTION_TITLES = [
    "Паспорт прогона",
    "Как агент нарезал требования",
    "Проверка каждого требования",
    "Проверка всего набора требований",
    "Уточняющие вопросы к аналитику",
    "Сводка",
    "Итог",
    "Приложение. Методика и коды критериев",
]
REPORT_TITLE = "Отчёт о проверке требований"


def cell(text: object) -> str:
    """Безопасное значение для ячейки таблицы Markdown."""
    return " ".join(str(text).split()).replace("|", "\\|")


def inline(text: object) -> str:
    return " ".join(str(text).split())


def place(a: Anchor) -> str:
    parts = []
    if a.page is not None:
        parts.append(f"стр. {a.page}")
    if a.section:
        parts.append(f"раздел «{inline(a.section)}»")
    parts.append(f"строка {a.line_start}" if a.line_start == a.line_end
                 else f"строки {a.line_start}–{a.line_end}")
    return ", ".join(parts)


def places(f: Finding) -> str:
    return "; ".join(place(a) for a in f.anchors)


def quotes(f: Finding) -> str:
    return "; ".join(f"«{inline(q)}»" for q in f.quotes)


def _env() -> Environment:
    env = Environment(
        loader=PackageLoader("reqcheck", "templates"),
        trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True, autoescape=False,
    )
    env.filters.update(cell=cell, inline=inline, place=place)
    env.globals.update(places=places, quotes=quotes)
    return env


def requirement_status(report: Report, req: Requirement) -> tuple[str, list[Finding]]:
    items = [f for f in report.findings if f.scope == "requirement" and req.id in f.requirement_ids]
    if req.id in report.unchecked:
        return "⏳ не проверено", items
    if any(f.severity == "critical" for f in items):
        return "❌ есть критичные замечания", items
    if items:
        return "⚠️ есть замечания", items
    if report.passport.llm_mode == "lint-only":
        return "➖ LLM не проверяла, правила замечаний не нашли", items
    return "✅ без замечаний", items


def render_report(report: Report) -> str:
    summary = build_summary(report)
    set_findings = [f for f in report.findings if f.scope == "set"]
    set_groups = []
    for code in list(SET_CODES) + sorted({f.criterion for f in set_findings} - set(SET_CODES)):
        items = [f for f in set_findings if f.criterion == code]
        crit = CRITERIA[code]
        if report.set_conclusions.get(code):
            conclusion = report.set_conclusions[code]
        elif items:
            conclusion = f"Найдено замечаний: {len(items)}."
        elif report.passport.llm_mode == "lint-only":
            conclusion = "Не оценивалось: для этого критерия нужна LLM (режим lint-only)."
        else:
            conclusion = "Замечаний нет."
        set_groups.append({"code": code, "title": crit.title, "conclusion": conclusion, "findings": items})

    req_blocks = []
    for r in report.requirements:
        status, items = requirement_status(report, r)
        req_blocks.append({"req": r, "status": status, "findings": items,
                           "reason": report.unchecked.get(r.id)})

    # Вопросы: по требованиям, затем по набору в целом.
    by_req: dict[str, list[Finding]] = {}
    general: list[Finding] = []
    for f in report.findings:
        if not f.question:
            continue
        if f.requirement_ids:
            by_req.setdefault(f.requirement_ids[0], []).append(f)
        else:
            general.append(f)
    order = {r.id: i for i, r in enumerate(report.requirements)}
    question_groups = [
        {"req": next(r for r in report.requirements if r.id == rid), "findings": by_req[rid]}
        for rid in sorted(by_req, key=lambda x: order.get(x, 10**6)) if rid in order
    ]

    return _env().get_template("report.md.j2").render(
        report=report, passport=report.passport, titles=SECTION_TITLES, report_title=REPORT_TITLE,
        req_blocks=req_blocks, set_groups=set_groups, summary=summary,
        question_groups=question_groups, general_questions=general,
        priorities=top_priorities(report.findings), sev_ru=SEVERITY_RU,
        criteria=CRITERIA, requirement_codes=REQUIREMENT_CODES, set_codes=SET_CODES,
        reqs_by_id={r.id: r for r in report.requirements},
    )
