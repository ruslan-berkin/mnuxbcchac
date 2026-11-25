"""CLI: python -m reqcheck <требования> <отчёт.md> [опции]."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from reqcheck import __version__
from reqcheck.config import load_chain, load_env_file
from reqcheck.errors import ReqcheckError
from reqcheck.pipeline import run, sidecar_paths

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
    version: Annotated[bool, typer.Option("--version", callback=_version, is_eager=True, help="Показать версию.")] = False,
) -> None:
    load_env_file()
    try:
        settings, fallbacks, notes = load_chain(provider, model, fallback=not no_fallback)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    try:
        report = run(input_path, output_path, settings, lint_only=lint_only,
                     require_llm=require_llm, use_cache=not no_cache,
                     fallbacks=fallbacks, notes=notes, workers=workers,
                     display_name=str(input_path))
    except ReqcheckError as exc:
        typer.secho(f"Ошибка: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(exc.exit_code) from exc

    for w in report.warnings:
        typer.secho(f"Предупреждение: {w}", fg=typer.colors.YELLOW, err=True)
    json_path, log_path = sidecar_paths(output_path)
    typer.echo(f"Отчёт: {output_path}\nJSON:  {json_path}\nЛог:   {log_path}")
    typer.echo(f"Требований: {len(report.requirements)}, замечаний: {len(report.findings)}. "
               f"{report.verdict.text}")
