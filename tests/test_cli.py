import json

from typer.testing import CliRunner

from reqcheck.cli import app

runner = CliRunner()


def run(*args, env=None):
    return runner.invoke(app, [str(a) for a in args], env=env)


def test_lint_only_run_writes_report_json_log(sample_md, tmp_path):
    out = tmp_path / "rep" / "report.md"
    r = run(sample_md, out, "--lint-only")
    assert r.exit_code == 0, r.output
    assert out.is_file() and out.with_suffix(".json").is_file() and out.with_suffix(".log").is_file()
    data = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert data["passport"]["llm_mode"] == "lint-only"
    assert len(data["passport"]["document_sha256"]) == 64
    assert [r["source_id"] for r in data["requirements"]] == ["Ф-1", "Ф-2"]
    assert not list(out.parent.glob("*.tmp")) and not list(out.parent.glob(".*.tmp"))


def test_no_key_falls_back_with_warning(sample_md, tmp_path, monkeypatch):
    for k in ("GEMINI_API_KEY", "GEMINI_MODEL", "LLM_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)  # чтобы не подхватить .env
    out = tmp_path / "r.md"
    r = run(sample_md, out)
    assert r.exit_code == 0
    assert "lint-only" in r.output
    assert json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))["passport"]["llm_mode"] == "lint-only"


def test_require_llm_without_key_exits_4(sample_md, tmp_path, monkeypatch):
    for k in ("GEMINI_API_KEY", "GEMINI_MODEL", "LLM_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.chdir(tmp_path)
    r = run(sample_md, tmp_path / "r.md", "--require-llm")
    assert r.exit_code == 4
    assert not (tmp_path / "r.md").exists()


def test_missing_file_exits_2(tmp_path):
    assert run(tmp_path / "no.pdf", tmp_path / "r.md", "--lint-only").exit_code == 2


def test_unsupported_format_exits_2(tmp_path):
    p = tmp_path / "a.xlsx"
    p.write_text("x")
    assert run(p, tmp_path / "r.md", "--lint-only").exit_code == 2


def test_empty_pdf_exits_3_without_report(empty_pdf, tmp_path):
    out = tmp_path / "r.md"
    assert run(empty_pdf, out, "--lint-only").exit_code == 3
    assert not out.exists()


def test_fake_provider_runs_in_full_mode(sample_md, tmp_path):
    out = tmp_path / "r.md"
    r = run(sample_md, out, "--provider", "fake")
    assert r.exit_code == 0, r.output
    data = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert data["passport"]["llm_mode"] == "full" and data["passport"]["model_provider"] == "fake"


def test_llm_unavailable_exits_5_without_report(sample_md, tmp_path, monkeypatch):
    from reqcheck.errors import LLMUnavailableError

    def boom(settings):
        raise LLMUnavailableError("сервис недоступен")

    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("GEMINI_MODEL", "m")
    monkeypatch.setattr("reqcheck.pipeline.build_client", boom)  # без сетевых вызовов
    r = run(sample_md, tmp_path / "r.md", "--provider", "gemini")
    assert r.exit_code == 5
    assert not (tmp_path / "r.md").exists()


def test_unknown_provider_is_usage_error(sample_md, tmp_path):
    assert run(sample_md, tmp_path / "r.md", "--provider", "zzz").exit_code == 2


def test_pdf_end_to_end_passes_self_check(repo_root, tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("self_check", repo_root / "scripts" / "self_check.py")
    sc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sc)
    pdf = repo_root / "examples" / "input" / "requirements.pdf"
    out = tmp_path / "report.md"
    assert run(pdf, out, "--lint-only").exit_code == 0
    assert sc.check_report(out) == []
