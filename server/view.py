"""Данные отчёта для интерфейса: всё считает код (подсветка, сводка, приоритеты, названия критериев)."""

from __future__ import annotations

from reqcheck.criteria import CRITERIA
from reqcheck.ground import GroundIndex
from reqcheck.models import Document, Report
from reqcheck.questions import top_questions
from reqcheck.summary import build_summary, top_priorities


def _utf16(line: str, col: int) -> int:
    """Позиция в строке в единицах UTF-16 (так считает JavaScript)."""
    return len(line[:col].encode("utf-16-le")) // 2


def highlights(doc: Document, report: Report) -> list[dict]:
    """Отрезки строк документа для каждой цитаты каждого замечания."""
    index = GroundIndex(doc)
    out: list[dict] = []
    for f in report.findings:
        for quote, anchor in zip(f.quotes, f.anchors):
            spans = index.locate(quote, anchor.line_start)
            if not spans:  # нечёткое совпадение: подсвечиваем строки якоря целиком
                spans = [(n, 0, len(doc.lines[n - 1]))
                         for n in range(anchor.line_start, anchor.line_end + 1)]
            for line, start, end in spans:
                text = doc.lines[line - 1]
                out.append({"finding_id": f.id, "line": line, "start": _utf16(text, start), "end": _utf16(text, end)})
    return out


def report_view(doc: Document, report: Report) -> dict:
    """Ответ API для платформы: отчёт, строки документа и производные данные."""
    summary = build_summary(report)
    return {
        "report": report.model_dump(mode="json"),
        "document": {"name": doc.path, "title": doc.title, "sha256": doc.sha256, "lines": doc.lines},
        "view": {
            "highlights": highlights(doc, report),
            "priorities": [f.id for f in top_priorities(report.findings)],
            "top_questions": [q.model_dump() for q in top_questions(report.findings)],
            "by_severity": summary.by_severity,
            "by_criterion": summary.by_criterion,
            "criteria": {c.code: {"title": c.title, "reference": c.reference} for c in CRITERIA.values()},
        },
    }
