"""Сборка промптов: тексты лежат в prompts/*.md, документ всегда обёрнут как данные."""

from __future__ import annotations

from reqcheck.criteria import criteria_for_prompt
from reqcheck.llm.base import load_prompt


def system_prompt(stage: str, scope: str | None = None) -> str:
    text = load_prompt(stage).replace("<<common>>", load_prompt("common").strip())
    if scope:
        text = text.replace("<<criteria>>", criteria_for_prompt(scope))  # type: ignore[arg-type]
    return text


def document_block(text: str) -> str:
    """Документ — данные. Закрывающий тег внутри текста обезвреживается."""
    safe = text.replace("</document", "< /document").replace("<document", "< document")
    return f"<document>\n{safe}\n</document>"
