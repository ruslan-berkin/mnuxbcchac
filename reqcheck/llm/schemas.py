"""Схемы ответов LLM по этапам.

Строгие: обязательные поля без значений по умолчанию и запрет лишних ключей. Пустой или
чужой по форме JSON (`{}`, `{"issues": []}`) не проходит как «замечаний нет», а идёт в ремонтный
запрос и, если не помог, в «не проверено». Лимиты длины защищают от раздутых ответов.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from reqcheck.criteria import CriterionCode
from reqcheck.models import RequirementKind, Severity

Short = Annotated[str, Field(max_length=800)]
Quote = Annotated[str, Field(max_length=1500)]
Text = Annotated[str, Field(max_length=2500)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SegItem(_Strict):
    source_id: Annotated[str, Field(max_length=60)] | None = None
    kind: RequirementKind = "other"
    quote: Quote
    summary: Short


class SegOut(_Strict):
    requirements: Annotated[list[SegItem], Field(max_length=500)]


class LLMFinding(_Strict):
    requirement_ids: Annotated[list[str], Field(max_length=40)] = Field(default_factory=list)
    criterion: CriterionCode
    severity: Severity
    quotes: Annotated[list[Quote], Field(min_length=1, max_length=6)]
    problem: Text
    fix: Text
    question: Short | None = None


class EachOut(_Strict):
    findings: Annotated[list[LLMFinding], Field(max_length=60)]


class SetConclusion(_Strict):
    code: CriterionCode
    conclusion: Text


class SetOut(_Strict):
    conclusions: Annotated[list[SetConclusion], Field(max_length=20)]
    findings: Annotated[list[LLMFinding], Field(max_length=80)]


class QItem(_Strict):
    finding_id: Annotated[str, Field(max_length=20)]
    question: Short


class QOut(_Strict):
    questions: Annotated[list[QItem], Field(max_length=100)]


class VerifyOut(_Strict):
    verdict: Literal["confirmed", "rejected"]
    # None: проверяющий серьёзность не назвал — остаётся исходная (не понижаем молча)
    severity: Severity | None = None
    reason: Text = ""


class DupGroup(_Strict):
    ids: Annotated[list[str], Field(max_length=40)]
    primary: Annotated[str, Field(max_length=20)]


class ConsolidateOut(_Strict):
    groups: Annotated[list[DupGroup], Field(max_length=100)]
