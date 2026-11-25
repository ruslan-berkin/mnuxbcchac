"""pipeline: ingest → segment → check_each → check_set (+ lint) → ground → render.

Фаза 1: работают ingest, segment (явные ID), lint и render. LLM-этапы подключаются в Фазе 2.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from reqcheck import __version__
from reqcheck.checks.lint import run_lint
from reqcheck.config import Settings
from reqcheck.errors import InputFileError, MissingKeyError
from reqcheck.ingest import load_document
from reqcheck.llm import build_client
from reqcheck.llm.base import LLMClient
from reqcheck.models import LLMMode, Report, RunPassport
from reqcheck.render import render_report
from reqcheck.segment import segment_explicit
from reqcheck.summary import compute_verdict, finalize_findings

log = logging.getLogger("reqcheck")


def sidecar_paths(output: Path) -> tuple[Path, Path]:
    return output.with_suffix(".json"), output.with_suffix(".log")


def agent_version() -> str:
    root = Path(__file__).resolve().parent.parent
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--dirty", "--always"],
            cwd=root, capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        if out:
            return out
    except (OSError, subprocess.SubprocessError):
        pass
    return f"{__version__}+nogit"


def _now() -> str:
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Asia/Almaty")
    except Exception:  # нет базы часовых поясов
        tz = timezone.utc
    return datetime.now(tz).replace(microsecond=0).isoformat()


def write_atomic(path: Path, text: str) -> None:
    """Сначала временный файл рядом, затем атомарное переименование."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def run(
    input_path: str | Path,
    output_path: str | Path,
    settings: Settings,
    *,
    lint_only: bool = False,
    require_llm: bool = False,
    use_cache: bool = True,
    client: LLMClient | None = None,
) -> Report:
    out = Path(output_path)
    json_path, log_path = sidecar_paths(out)

    doc = load_document(input_path)  # ошибки ввода: коды 2 и 3

    mode: LLMMode = "lint-only"
    warnings: list[str] = []
    if not lint_only:
        if client is not None or settings.has_key:
            mode = "full"
        elif require_llm:
            raise MissingKeyError(
                "Нет ключа или ID модели для LLM (см. .env.example), а указан --require-llm."
            )
        else:
            warnings.append(
                "Ключ LLM не найден: прогон выполнен в режиме lint-only, только по правилам без LLM."
            )
    if mode == "full" and client is None:
        client = build_client(settings)  # LLMUnavailableError → код 5

    out.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        log.info("Документ: %s (%s, %d строк, %d блоков)", doc.path, doc.format,
                 len(doc.lines), len(doc.blocks))
        log.info("Режим: %s", mode)

        requirements = segment_explicit(doc)
        log.info("segment: найдено требований с явными ID: %d", len(requirements))
        if not requirements:
            warnings.append("Явные ID требований не найдены; требования без номеров "
                            "выделяет LLM (появится в Фазе 2).")

        if mode == "full":
            warnings.append("LLM-этапы check_each и check_set ещё не подключены в этой версии каркаса.")

        findings = finalize_findings(run_lint(doc, requirements))
        log.info("lint: замечаний %d", len(findings))

        passport = RunPassport(
            document_title=doc.title,
            document_path=doc.path,
            document_sha256=doc.sha256,
            run_datetime=_now(),
            model_provider=client.provider if client else "не используется",
            model_id=client.model if client else "—",
            agent_version=agent_version(),
            llm_mode=mode,
        )
        report = Report(
            passport=passport,
            requirements=requirements,
            findings=findings,
            dropped_count=0,
            verdict=compute_verdict(findings, mode),
            warnings=warnings,
        )
        write_atomic(out, render_report(report))
        write_atomic(json_path, report.model_dump_json(indent=2))
        log.info("Отчёт записан: %s", out)
        return report
    finally:
        log.removeHandler(handler)
        handler.close()


__all__ = ["run", "InputFileError", "sidecar_paths", "write_atomic"]
