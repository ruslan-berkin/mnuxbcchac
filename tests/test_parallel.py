import json
import threading
import time

import pytest

from reqcheck.errors import LLMUnavailableError
from reqcheck.llm import FakeLLM, FallbackLLM
from reqcheck.parallel import default_workers, pmap
from reqcheck.pipeline import run
from tests.test_pipeline_llm import SETTINGS, SEG, finding, make_doc, stage


def test_pmap_keeps_input_order_even_if_finish_order_differs():
    def slow_first(x):
        time.sleep(0.15 if x == 0 else 0.0)
        return x * 10

    assert pmap(slow_first, list(range(6)), workers=4) == [0, 10, 20, 30, 40, 50]


def test_pmap_actually_runs_concurrently():
    t = time.monotonic()
    pmap(lambda x: time.sleep(0.2), list(range(4)), workers=4)
    assert time.monotonic() - t < 0.6  # последовательно было бы 0.8


def test_pmap_sequential_when_one_worker_and_propagates_error():
    order = []
    assert pmap(lambda x: order.append(x) or x, [1, 2, 3], workers=1) == [1, 2, 3] and order == [1, 2, 3]

    def boom(x):
        if x == 2:
            raise LLMUnavailableError("down")
        return x

    with pytest.raises(LLMUnavailableError):
        pmap(boom, [1, 2, 3, 4], workers=4)


def test_default_workers_from_env(monkeypatch):
    monkeypatch.setenv("REQCHECK_WORKERS", "7")
    assert default_workers() == 7
    monkeypatch.setenv("REQCHECK_WORKERS", "мусор")
    assert default_workers() == 4
    monkeypatch.setenv("REQCHECK_WORKERS", "0")
    assert default_workers() == 1


def _llm(delay=0.0):
    each = lambda prompt: {"findings": [finding([rid], "UNA", "major", [q]) for rid, q in
                                        __import__("re").findall(r"(R-\d+) \[[^\]]*\] \([a-z]+\): (.+)", prompt)[:1]]}
    state = {"max": 0, "now": 0}
    lock = threading.Lock()

    def handler(system, prompt):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(delay)
        with lock:
            state["now"] -= 1
        s = stage(system)
        data = {"segment": SEG, "each": each(prompt) if s == "each" else None,
                "set": {"findings": [], "conclusions": []},
                "verify": {"verdict": "confirmed", "severity": "major", "reason": "ок"},
                "questions": {"questions": []}, "consolidate": {"groups": []}}[s]
        return json.dumps(data, ensure_ascii=False)

    return FakeLLM(handler=handler), state


def test_report_is_identical_with_1_and_4_workers_and_calls_overlap(tmp_path):
    reports = {}
    for w in (1, 4):
        llm, state = _llm(delay=0.05)
        out = tmp_path / f"r{w}.md"
        rep = run(make_doc(tmp_path), out, SETTINGS, client=llm, use_cache=False, workers=w)
        reports[w] = (rep.model_dump(exclude={"passport"}), state["max"])
    assert reports[1][0] == reports[4][0]  # детерминированный результат
    assert reports[1][1] == 1 and reports[4][1] > 1  # при 4 потоках вызовы реально пересекаются


def test_fallback_is_thread_safe():
    class Down(FakeLLM):
        provider = "a"

        def complete(self, system, prompt, schema):
            err = LLMUnavailableError("лимит")
            err.transient = True
            raise err

    class Up(FakeLLM):
        provider = "b"

    llm = FallbackLLM([Down(), Up(["{}"] * 200)])
    results = pmap(lambda i: llm.complete("s", f"p{i}", {}), list(range(40)), workers=8)
    assert results == ["{}"] * 40
    assert len(llm.switches) == 1 and llm.used == [("b", "fake-model")]
