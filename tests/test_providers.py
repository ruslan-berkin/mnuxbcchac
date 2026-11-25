from types import SimpleNamespace

import pytest

from reqcheck.errors import LLMUnavailableError
from reqcheck.llm import base
from reqcheck.llm.base import call_with_retries, inline_schema, structured_call
from reqcheck.llm.gemini import GeminiClient
from reqcheck.llm.gemini import classify as g_classify
from reqcheck.llm.openai_compat import OpenAICompatClient
from reqcheck.llm.openai_compat import classify as o_classify


class Err(Exception):
    def __init__(self, code, msg="x", headers=None):
        super().__init__(msg)
        self.code = code
        self.status_code = code
        self.response = SimpleNamespace(headers=headers or {})


def test_inline_schema_resolves_refs():
    from pydantic import BaseModel

    class In(BaseModel):
        a: int

    class Out(BaseModel):
        items: list[In]

    s = inline_schema(Out.model_json_schema())
    assert "$defs" not in s and "$ref" not in str(s)
    assert s["properties"]["items"]["items"]["properties"]["a"]["type"] == "integer"


def test_retries_on_429_with_retry_after_and_backoff():
    sleeps, calls = [], []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise Err(429, "RESOURCE_EXHAUSTED retryDelay: 7s")
        return "ok"

    assert call_with_retries(fn, g_classify, sleep=sleeps.append, base_delay=1) == "ok"
    assert len(calls) == 3
    assert sleeps[0] == 7.0 and sleeps[1] == 7.0  # retry-after больше экспоненты 1, 2


def test_backoff_grows_without_retry_after():
    sleeps = []
    with pytest.raises(LLMUnavailableError):
        call_with_retries(lambda: (_ for _ in ()).throw(Err(503)), g_classify, attempts=4,
                          sleep=sleeps.append, base_delay=2)
    assert sleeps == [2, 4, 8]


def test_non_retryable_fails_immediately():
    calls = []

    def fn():
        calls.append(1)
        raise Err(400, "bad request")

    with pytest.raises(LLMUnavailableError):
        call_with_retries(fn, g_classify, sleep=lambda s: None)
    assert len(calls) == 1


def test_classifiers():
    assert g_classify(Err(429))[0] and g_classify(Err(500))[0] and not g_classify(Err(401))[0]
    assert o_classify(Err(429, headers={"retry-after": "3"})) == (True, 3.0)
    assert not o_classify(Err(404))[0]
    assert g_classify(TimeoutError("t")) == (True, None)  # без кода: по имени класса


def test_gemini_client_uses_temperature_zero_and_schema():
    seen = {}

    class Models:
        def generate_content(self, model, contents, config):
            seen.update(model=model, contents=contents, config=config)
            return SimpleNamespace(text='{"n": 1}')

    from pydantic import BaseModel

    class Out(BaseModel):
        n: int

    c = GeminiClient("k", "model-x", client=SimpleNamespace(models=Models()))
    assert structured_call(c, "sys", "prompt", Out).n == 1
    assert seen["model"] == "model-x" and seen["config"].temperature == 0
    assert seen["config"].system_instruction == "sys"
    assert seen["config"].response_mime_type == "application/json"
    assert seen["config"].response_json_schema["properties"]["n"]["type"] == "integer"


def test_openai_compat_client_and_response_format_fallback():
    calls = []

    class Completions:
        def create(self, **kw):
            calls.append(kw)
            if "response_format" in kw:
                raise Err(400, "unknown parameter response_format")
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"n": 2}'))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    c = OpenAICompatClient("k", "m", client=client)
    out = c.complete("sys", "prompt", {"type": "object", "properties": {}})
    assert out == '{"n": 2}' and len(calls) == 2 and calls[0]["temperature"] == 0
    assert "response_format" not in calls[1] and "JSON" in calls[1]["messages"][1]["content"]


def test_build_client_factory(monkeypatch):
    from reqcheck.config import Settings
    from reqcheck.llm import build_client

    g = build_client(Settings("gemini", "m", "k"))
    assert g.provider == "gemini" and g.model == "m"
    o = build_client(Settings("openai_compat", "m", "k", "http://localhost:11434/v1"))
    assert o.provider == "openai_compat"
    with pytest.raises(LLMUnavailableError):
        build_client(Settings("gemini", None, None))
    assert base.LLMUnavailableError is LLMUnavailableError


def test_groq_preset(monkeypatch):
    from reqcheck.config import GROQ_BASE_URL, load_settings
    from reqcheck.llm import build_client

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GROQ_MODEL", "some-model")
    monkeypatch.delenv("GROQ_BASE_URL", raising=False)
    st = load_settings("groq")
    assert st.has_key and st.base_url == GROQ_BASE_URL
    c = build_client(st)
    assert c.provider == "groq" and c.model == "some-model"
    monkeypatch.setenv("GROQ_API_KEY", "your_groq_api_key_here")
    assert not load_settings("groq").has_key  # заглушка из .env.example не считается ключом
