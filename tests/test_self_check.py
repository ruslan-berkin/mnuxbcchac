import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def sc():
    spec = importlib.util.spec_from_file_location("sc", ROOT / "scripts" / "self_check.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_repo_check_passes_on_this_repo(sc):
    assert sc.check_repo() == []


def test_readme_checklist_reports_missing_items(sc, tmp_path, monkeypatch):
    (tmp_path / "README.md").write_text("# пусто\n", encoding="utf-8")
    monkeypatch.setattr(sc, "ROOT", tmp_path)
    errs = sc.check_readme()
    assert any("python -m reqcheck" in e for e in errs) and any("lint-only" in e for e in errs)


def _repo(tmp_path, monkeypatch, sc):
    run = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    run("init", "-q")
    run("config", "user.name", "A")
    run("config", "user.email", "a@a")
    monkeypatch.setattr(sc, "ROOT", tmp_path)
    return run


def test_history_detects_secret_env_and_trailers(sc, tmp_path, monkeypatch):
    run = _repo(tmp_path, monkeypatch, sc)
    (tmp_path / "a.txt").write_text("ok\n")
    run("add", "a.txt")
    run("commit", "-q", "-m", "feat: ok")
    assert sc.check_history() == []
    (tmp_path / ".env").write_text("X=1\n")
    (tmp_path / "b.txt").write_text("GEMINI_API_KEY=AIza" + "A" * 35 + "\n")
    run("add", "-f", ".env", "b.txt")
    run("commit", "-q", "-m", "feat: bad\n\nCo-Authored-By: Bot <b@b>")
    errs = " | ".join(sc.check_history())
    assert ".env" in errs and "секрет" in errs and "трейлеры" in errs


def test_history_detects_second_author(sc, tmp_path, monkeypatch):
    run = _repo(tmp_path, monkeypatch, sc)
    (tmp_path / "a.txt").write_text("1\n")
    run("add", "a.txt")
    run("commit", "-q", "-m", "a")
    (tmp_path / "a.txt").write_text("2\n")
    run("-c", "user.name=B", "commit", "-q", "-am", "b")
    assert any("больше одного автора" in e for e in sc.check_history())
