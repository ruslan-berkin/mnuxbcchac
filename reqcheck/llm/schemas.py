"""Схемы ответов LLM по этапам (валидируются pydantic)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from reqcheck.criteria import CriterionCode
from reqcheck.models import RequirementKind, Severity


class SegItem(BaseModel):
    source_id: str | None = None
    kind: RequirementKind = "other"
    quote: str
    summary: str


class SegOut(BaseModel):
    requirements: list[SegItem] = Field(default_factory=list)


class LLMFinding(BaseModel):
    requirement_ids: list[str] = Field(default_factory=list)
    criterion: CriterionCode
    severity: Severity
    quotes: list[str] = Field(default_factory=list)
    problem: str
    fix: str
    question: str | None = None


class EachOut(BaseModel):
    findings: list[LLMFinding] = Field(default_factory=list)


class SetConclusion(BaseModel):
    code: CriterionCode
    conclusion: str


class SetOut(BaseModel):
    conclusions: list[SetConclusion] = Field(default_factory=list)
    findings: list[LLMFinding] = Field(default_factory=list)


class QItem(BaseModel):
    finding_id: str
    question: str


class QOut(BaseModel):
    questions: list[QItem] = Field(default_factory=list)
