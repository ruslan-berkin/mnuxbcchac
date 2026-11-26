"""CLI: python -m reqcheck <требования> <отчёт.md> [опции]."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from reqcheck import __version__
from reqcheck.config import load_chain, load_env_file
from reqcheck.errors import MissingKeyError, ReqcheckError
from reqcheck.ingest import load_document
from reqcheck.limits import Budget, BudgetedLLM, Limits
from reqcheck.llm import FallbackLLM, build_client
from reqcheck.llm.cache import DiskCache
from reqcheck.parallel import default_workers
from reqcheck.pipeline import run, sidecar_paths, write_atomic
from reqcheck.recheck import parse_answers, recheck, render_recheck
from reqcheck.redact import redact

app = typer.Typer(add_completion=False, help="Статическая проверка требований по ISO/IEC/IEEE 29148 и IEEE 830.")


def _version(value: bool) -> None:
    if value:
        typer.echo(f"reqcheck {__version__}")
        raise typer.Exit()


@app.command()
def main(
    input_path: Annotated[Path, typer.Argument(metavar="ТРЕБОВАНИЯ", help="PDF, DOCX, MD или TXT с требованиями.")],
    output_path: Annotated[Path, typer.Argument(metavar="ОТЧЁТ", help="Куда записать отчёт (.md). Рядом лягут .json и .log.")],
    provider: Annotated[Optional[str], typer.Option(help="gemini | groq | openai_compat | fake (по умолчанию из LLM_PROVIDER).")] = None,
    model: Annotated[Optional[str], typer.Option(help="ID модели (по умолчанию из .env).")] = None,
    no_cache: Annotated[bool, typer.Option("--no-cache", help="Не использовать кэш ответов LLM.")] = False,
    require_llm: Annotated[bool, typer.Option("--require-llm", help="Ошибка (код 4), если нет ключа LLM.")] = False,
    lint_only: Annotated[bool, typer.Option("--lint-only", help="Только правила без LLM.")] = False,
    workers: Annotated[Optional[int], typer.Option("--workers", min=1, max=8, help="Параллельных вызовов LLM (по умолчанию 4 или REQCHECK_WORKERS).")] = None,
    no_fallback: Annotated[bool, typer.Option("--no-fallback", help="Не переключаться на запасной провайдер.")] = False,
    answers: Annotated[Optional[Path], typer.Option("--answers", help="Файл с ответами аналитика («D-013: ответ»): после проверки перепроверить эти замечания.")] = None,
    version: Annotated[bool, typer.Option("--version", callback=_version, is_eager=True, help="Показать версию.")] = False,
) -> None:
    load_env_file()
    try:
        settings, fallbacks, notes = load_chain(provider, model, fallback=not no_fallback)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if answers is not None and not answers.is_file():
        raise typer.BadParameter(f"Файл с ответами не найден: {answers.name}")
    try:
        report = run(input_path, output_path, settings, lint_only=lint_only,
                     require_llm=require_llm, use_cache=not no_cache,
                     fallbacks=fallbacks, notes=notes, workers=workers,
                     display_name=str(input_path))
    except ReqcheckError as exc:
        typer.secho(f"Ошибка: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(exc.exit_code) from exc
    except Exception as exc:  # noqa: BLE001 — непредвиденное: короткое сообщение и определённый код, без трейсбэка с секретами
        typer.secho(f"Внутренняя ошибка ({type(exc).__name__}): {redact(str(exc))[:300]}. "
                    "Подробности в .log рядом с отчётом.", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from exc

    for w in report.warnings:
        typer.secho(f"Предупреждение: {w}", fg=typer.colors.YELLOW, err=True)
    json_path, log_path = sidecar_paths(output_path)
    typer.echo(f"Отчёт: {output_path}\nJSON:  {json_path}\nЛог:   {log_path}")
    typer.echo(f"Требований: {len(report.requirements)}, замечаний: {len(report.findings)}. "
               f"{report.verdict.text}")
    if answers is not None:
        try:
            _recheck(input_path, output_path, report, answers, settings, fallbacks, use_cache=not no_cache)
        except ReqcheckError as exc:
            typer.secho(f"Ошибка перепроверки: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(exc.exit_code) from exc


def _recheck(input_path: Path, output_path: Path, report, answers_path: Path, settings, fallbacks, *, use_cache: bool) -> None:
    if report.passport.llm_mode != "full":
        raise MissingKeyError("Перепроверка с ответами требует LLM: отчёт получен в режиме lint-only.")
    parsed = parse_answers(answers_path.read_text(encoding="utf-8-sig"))
    if not parsed:
        typer.secho("В файле ответов нет строк вида «D-013: ответ».", fg=typer.colors.YELLOW, err=True)
        return
    limits = Limits.from_env()
    chain = [build_client(st) for st in (settings, *fallbacks)]
    client = BudgetedLLM(FallbackLLM(chain) if len(chain) > 1 else chain[0], Budget(limits))
    doc = load_document(input_path, limits=limits, display_name=str(input_path))
    result = recheck(report, doc, parsed, client, DiskCache() if use_cache else None, default_workers())
    base = output_path.with_suffix("")
    md, js = Path(f"{base}.recheck.md"), Path(f"{base}.recheck.json")
    write_atomic(js, result.model_dump_json(indent=2))
    write_atomic(md, render_recheck(result))
    counts = {s: sum(1 for i in result.items if i.status == s) for s in ("resolved", "partial", "open")}
    typer.echo(f"Перепроверка: закрыто {counts['resolved']}, частично {counts['partial']}, осталось {counts['open']}.")
    typer.echo(f"Было:  {result.verdict_before.text}\nСтало: {result.verdict_after.text}\nФайл:  {md}")
