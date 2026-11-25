import json

import pytest
from pydantic import BaseModel

from reqcheck.config import Settings, load_chain
from reqcheck.errors import LLMUnavailableError
from reqcheck.llm import DiskCache, FakeLLM, FallbackLLM, structured_call
from reqcheck.pipeline import run


class Out(BaseModel):
    n: int


class Down(FakeLLM):
    def __init__(self, provider, transient=True, model="m"):
        super().__init__(model=model)
        self.provider = provider
        self.transient = transient

    def complete(self, system, prompt, schema):
        self.calls.append((system, prompt))
        err = LLMUnavailableError(f"{self.provider} лимит исчерпан")
        err.transient = self.transient
        raise err


class Up(FakeLLM):
    def __init__(self, provider, answer='{"n": 7}', model="m2"):
        super().__init__([answer] * 50, model=model)
        self.provider = provider


def test_switches_to_fallback_and_marks_transient_dead():
    a, b = Down("gemini"), Up("groq")
    llm = FallbackLLM([a, b])
    assert llm.complete("s", "p", {}) == '{"n": 7}'
    assert llm.complete("s", "p2", {}) == '{"n": 7}'
    assert len(a.calls) == 1  # после transient-сбоя основной больше не дёргается
    assert llm.provider == "groq" and llm.used == [("groq", "m2")]
    assert llm.switches and "gemini" in llm.switches[0] and "groq" in llm.switches[0]


def test_non_transient_error_retries_primary_next_call():
    a, b = Down("gemini", transient=False), Up("groq")
    llm = FallbackLLM([a, b])
    llm.complete("s", "p", {})
    llm.complete("s", "p2", {})
    assert len(a.calls) == 2  # например, 413 на большом запросе: на малом основной ещё может ответить


def test_all_down_raises_exit_5():
    llm = FallbackLLM([Down("gemini"), Down("groq")])
    with pytest.raises(LLMUnavailableError) as e:
        llm.complete("s", "p", {})
    assert e.value.exit_code == 5 and "gemini" in str(e.value) and "groq" in str(e.value)


def test_cache_is_found_under_any_chain_identity(tmp_path):
    cache = DiskCache(tmp_path)
    # прошлый прогон: ответил запасной
    first = FallbackLLM([Down("gemini"), Up("groq")])
    assert structured_call(first, "s", "p", Out, cache).n == 7
    assert len(list(tmp_path.glob("*.json"))) == 1
    # новый прогон: основной снова жив, но ответ берётся из кэша без вызовов
    primary, secondary = Up("gemini", '{"n": 1}', model="m"), Up("groq")
    second = FallbackLLM([primary, secondary])
    assert structured_call(second, "s", "p", Out, cache).n == 7
    assert primary.calls == [] and secondary.calls == []


def test_pipeline_reports_providers_used(tmp_path):
    doc = tmp_path / "d.md"
    doc.write_text("# Док\n\nВерсия 1.0 от 01.01.2026.\n\n* **FR-1.** Система работает.\n", encoding="utf-8")
    llm = FallbackLLM([Down("gemini"), Up("groq", '{"requirements": [], "findings": [], "conclusions": []}')])
    rep = run(doc, tmp_path / "r.md", Settings("fake", "x", "x"), client=llm, use_cache=False)
    assert rep.passport.model_provider == "groq"
    assert any("запасной" in w for w in rep.warnings)


def clear_env(monkeypatch):
    for k in ("LLM_PROVIDER", "LLM_FALLBACK", "GEMINI_API_KEY", "GEMINI_MODEL", "GROQ_API_KEY",
              "GROQ_MODEL", "OPENAI_API_KEY", "OPENAI_MODEL"):
        monkeypatch.delenv(k, raising=False)


def test_load_chain_auto_uses_other_providers_with_keys(monkeypatch):
    clear_env(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("GEMINI_MODEL", "gm")
    monkeypatch.setenv("GROQ_API_KEY", "q")
    monkeypatch.setenv("GROQ_MODEL", "qm")
    primary, fb, notes = load_chain("gemini")
    assert primary.provider == "gemini" and [f.provider for f in fb] == ["groq"] and notes == []
    primary, fb, _ = load_chain("groq")
    assert primary.provider == "groq" and [f.provider for f in fb] == ["gemini"]
    assert load_chain("gemini", fallback=False)[1] == []
    monkeypatch.setenv("LLM_FALLBACK", "none")
    assert load_chain("gemini")[1] == []


def test_load_chain_promotes_fallback_when_primary_has_no_key(monkeypatch):
    clear_env(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "q")
    monkeypatch.setenv("GROQ_MODEL", "qm")
    primary, fb, notes = load_chain("gemini")
    assert primary.provider == "groq" and fb == [] and "нет ключа" in notes[0]


def test_load_chain_skips_providers_without_keys(monkeypatch):
    clear_env(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    monkeypatch.setenv("GEMINI_MODEL", "gm")
    monkeypatch.setenv("GROQ_API_KEY", "your_groq_api_key_here")
    primary, fb, _ = load_chain("gemini")
    assert fb == []
