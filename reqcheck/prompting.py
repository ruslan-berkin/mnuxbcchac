"""Сборка промптов: тексты лежат в prompts/*.md, всё из документа и ответов модели идёт как данные.

Данные обёрнуты тегами `<document-XXXX>` / `<data-XXXX>`, где XXXX — хеш самого текста. Документ не может
содержать корректный закрывающий тег: его суффикс зависит от всего текста, включая этот тег. Кроме того,
любые варианты тегов в тексте (регистр, пробелы) обезвреживаются.
"""

from __future__ import annotations

import hashlib
import re

from reqcheck.criteria import criteria_for_prompt
from reqcheck.llm.base import load_prompt

_TAG_LIKE = re.compile(r"(?i)<(\s*/?\s*(?:document|data)\b)")
# управляющие, bidi- и невидимые символы: в служебных списках не нужны и маскируют инъекции
_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]")


def system_prompt(stage: str, scope: str | None = None) -> str:
    text = load_prompt(stage).replace("<<common>>", load_prompt("common").strip())
    if scope:
        text = text.replace("<<criteria>>", criteria_for_prompt(scope))  # type: ignore[arg-type]
    return text


def neutralize(text: str) -> str:
    """Любой текст, похожий на наш тег (в любом регистре и с пробелами), перестаёт быть тегом."""
    return _TAG_LIKE.sub(r"< \1", text)


def _wrap(tag: str, safe: str) -> str:
    n = hashlib.sha256(safe.encode("utf-8")).hexdigest()[:10]
    return f"<{tag}-{n}>\n{safe}\n</{tag}-{n}>"


def document_block(text: str) -> str:
    """Документ — данные: текст не меняется, кроме обезвреживания тегов."""
    return _wrap("document", neutralize(text))


def data_block(text: str, limit: int | None = None) -> str:
    """Служебные списки, собранные из документа или ответов LLM (требования, цитаты, заголовки)."""
    clean = _CTRL.sub("", text)
    if limit is not None:
        clean = clean[:limit]
    return _wrap("data", neutralize(clean))
