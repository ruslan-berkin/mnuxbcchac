"""Модель данных."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from reqcheck.criteria import CriterionCode

Severity = Literal["critical", "major", "minor"]
RequirementKind = Literal[
    "functional", "nonfunctional", "data", "integration", "acceptance", "api", "ui", "other"
]
VerdictCode = Literal["blocked", "caveats", "incomplete", "ok"]
LLMMode = Literal["full", "lint-only"]


class Anchor(BaseModel):
    section: str = ""
    page: int | None = None
    line_start: int
    line_end: int


class Block(BaseModel):
    """Фрагмент документа: абзац, строка таблицы, элемент списка."""

    text: str
    anchor: Anchor


class Document(BaseModel):
    warnings: list[str] = Field(default_factory=list)  # проблемы разбора: сканы, кодировка, таблицы
    incomplete: list[str] = Field(default_factory=list)  # проблемы разбора, из-за которых проверка неполная
    title: str
    path: str
    sha256: str
    format: str
    lines: list[str]
    blocks: list[Block]

    @property
    def full_text(self) -> str:
        return "\n".join(self.lines)


class Requirement(BaseModel):
    id: str  # R-01
    source_id: str | None = None  # "Ф-1" или None
    kind: RequirementKind = "other"
    quote: str  # дословно из документа
    summary: str
    anchor: Anchor


class Finding(BaseModel):
    id: str  # D-001
    scope: Literal["requirement", "set"]
    requirement_ids: list[str] = Field(default_factory=list)
    criterion: CriterionCode
    severity: Severity
    quotes: list[str]  # каждая проходит ground
    anchors: list[Anchor]
    problem: str
    fix: str
    question: str | None = None
    source: Literal["llm", "lint"]
    rule: str | None = None  # имя правила линтера
    fingerprint: str | None = None  # у замечаний линтера: правило + строка + суть; равные отпечатки — настоящий дубль


class RunPassport(BaseModel):
    document_title: str
    document_path: str
    document_sha256: str
    run_datetime: str
    model_provider: str
    model_id: str
    agent_version: str
    llm_mode: LLMMode


class Verdict(BaseModel):
    code: VerdictCode
    text: str


class Report(BaseModel):
    passport: RunPassport
    requirements: list[Requirement]
    findings: list[Finding]
    dropped_count: int = 0
    merged_count: int = 0  # замечания, слитые как дубли
    verifier_rejected: int = 0  # критичные замечания, снятые перепроверкой
    # что именно снято/понижено перепроверкой: criterion, quote, reason, action
    verifier_notes: list[dict[str, str]] = Field(default_factory=list)
    # причины отбрасывания → число (цитата не найдена, ID/критерий вне батча, сегментация)
    drop_breakdown: dict[str, int] = Field(default_factory=dict)
    # R-xx → сколько замечаний к нему отброшено проверкой цитат
    dropped_by_requirement: dict[str, int] = Field(default_factory=dict)
    # почему проверка неполная (пусто — полная)
    incomplete_reasons: list[str] = Field(default_factory=list)
    verdict: Verdict
    # R-xx -> причина, по которой LLM-проверка не удалась («не проверено»)
    unchecked: dict[str, str] = Field(default_factory=dict)
    # код S-* -> вывод по критерию набора
    set_conclusions: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
