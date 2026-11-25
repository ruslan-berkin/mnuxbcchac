import json

import pytest
from pydantic import BaseModel

from reqcheck.llm import DiskCache, FakeLLM, LLMValidationError, structured_call


class Out(BaseModel):
    n: int


def test_structured_ok_and_cache(tmp_path):
    llm = FakeLLM(['{"n": 1}'])
    cache = DiskCache(tmp_path)
    assert structured_call(llm, "s", "p", Out, cache).n == 1
    # второй вызов берётся из кэша, модель не вызывается
    assert structured_call(llm, "s", "p", Out, cache).n == 1
    assert len(llm.calls) == 1
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_repair_retry_once(tmp_path):
    llm = FakeLLM(["not json", '```json\n{"n": 2}\n```'])
    assert structured_call(llm, "s", "p", Out).n == 2
    assert len(llm.calls) == 2
    assert "Ошибка валидации" in llm.calls[1][1]


def test_failure_after_repair(tmp_path):
    llm = FakeLLM(["bad", '{"n": "x"}'])
    cache = DiskCache(tmp_path)
    with pytest.raises(LLMValidationError):
        structured_call(llm, "s", "p", Out, cache)
    assert len(llm.calls) == 2
    assert not list(tmp_path.glob("*.json"))  # невалидное в кэш не попадает


def test_cache_key_depends_on_provider_model_prompt():
    k = DiskCache.make_key
    assert k("a", "m", "s", "p") != k("b", "m", "s", "p")
    assert k("a", "m", "s", "p") != k("a", "m2", "s", "p")
    assert k("a", "m", "s", "p") != k("a", "m", "s", "p2")


def test_corrupt_cache_is_miss(tmp_path):
    cache = DiskCache(tmp_path)
    key = DiskCache.make_key("a", "m", "s", "p")
    (tmp_path / f"{key}.json").write_text("{broken")
    assert cache.get(key) is None
    cache.put(key, json.dumps({"n": 1}))
    assert cache.get(key)
