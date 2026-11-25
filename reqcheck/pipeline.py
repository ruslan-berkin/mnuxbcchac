"""pipeline: ingest → segment → check_each → check_set (+ lint) → ground → render."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from reqcheck import __version__
from reqcheck.checks.lint import run_lint_safe
from reqcheck.config import Settings
from reqcheck.errors import InputFileError, LLMUnavailableError, MissingKeyError
from reqcheck.ingest import load_document
from reqcheck.llm import FallbackLLM, build_client
from reqcheck.llm.base import LLMClient
from reqcheck.models import LLMMode, Report, RunPassport
from reqcheck.render import render_report
from reqcheck.checks.each import check_each
from reqcheck.consolidate import consolidate
from reqcheck.criteria import SET_CODES
from reqcheck.checks.set import check_set
from reqcheck.ground import ground_findings_detailed, ground_requirements
from reqcheck.llm.cache import DiskCache
from reqcheck.models import Finding
from reqcheck.limits import Budget, BudgetedLLM, Limits
from reqcheck.parallel import clamp_workers, default_workers
from reqcheck.redact import redact
from reqcheck.runlog import run_log
from reqcheck.questions import ensure_questions
from reqcheck.verify import verify_critical
from reqcheck.segment import segment
from reqcheck.summary import compute_verdict, finalize_findings

log = logging.getLogger("reqcheck.pipeline")


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
        os.chmod(tmp, 0o644)  # mkstemp создаёт 0600: читать отчёт должен и веб-процесс
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _validate_output(out: Path) -> tuple[Path, Path]:
    """Три файла отчёта должны быть разными: .json или .log в роли отчёта затёрли бы сопутствующие файлы."""
    json_path, log_path = sidecar_paths(out)
    if out.suffix.lower() in (".json", ".log") or len({out, json_path, log_path}) != 3:
        raise InputFileError(
            f"Путь отчёта «{out.name}» совпадёт с сопутствующим файлом (.json или .log). Укажите имя вида report.md.")
    return json_path, log_path


def _cap_findings(findings: list[Finding], limit: int) -> tuple[list[Finding], int]:
    if len(findings) <= limit:
        return findings, 0
    order = {"critical": 0, "major": 1, "minor": 2}
    keep = sorted(findings, key=lambda f: (order[f.severity], f.id))[:limit]
    ids = {f.id for f in keep}
    return [f for f in findings if f.id in ids], len(findings) - limit


def run(
    input_path: str | Path,
    output_path: str | Path,
    settings: Settings,
    *,
    lint_only: bool = False,
    require_llm: bool = False,
    use_cache: bool = True,
    client: LLMClient | None = None,
    fallbacks: Sequence[Settings] = (),
    notes: Sequence[str] = (),
    workers: int | None = None,
    limits: Limits | None = None,
    display_name: str | None = None,
    cache_dir: str | Path | None = None,
    cache_namespace: str = "",
) -> Report:
    """Один прогон. Для сервера: `limits=Limits.web()`, `display_name` (имя файла пользователя),
    `cache_namespace` (арендатор) или `use_cache=False`, отдельный `output_path` на запрос."""
    out = Path(output_path)
    json_path, log_path = _validate_output(out)
    limits = limits or Limits.from_env()
    budget = Budget(limits)

    doc = load_document(input_path, limits=limits, display_name=display_name)  # ошибки ввода: коды 2 и 3

    mode: LLMMode = "lint-only"
    warnings: list[str] = list(notes) + list(doc.warnings)
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
        if fallbacks:  # у основного меньше попыток, чтобы быстрее перейти к запасному
            chain = [settings, *fallbacks]
            client = FallbackLLM([build_client(st, attempts=3 if i < len(chain) - 1 else 4)
                                  for i, st in enumerate(chain)])
        else:
            client = build_client(settings)  # LLMUnavailableError → код 5
    llm: LLMClient | None = BudgetedLLM(client, budget) if (mode == "full" and client is not None) else None

    # Версию агента считаем ДО того, как трогаем файлы отчёта: если отчёт закоммичен в репозитории,
    # его удаление и перезапись не должны делать паспорт «dirty».
    version = agent_version()
    out.parent.mkdir(parents=True, exist_ok=True)
    # Файлы прошлого прогона удаляем до начала работы: при сбое нового прогона они не должны
    # выглядеть актуальными. Отчёт (.md) пишется последним и служит признаком успешного завершения.
    out.unlink(missing_ok=True)
    json_path.unlink(missing_ok=True)
    with run_log(log_path):
        log.info("Документ: %s (%s, %d строк, %d блоков)", doc.path, doc.format, len(doc.lines), len(doc.blocks))
        log.info("Режим: %s", mode)

        nworkers = clamp_workers(workers if workers is not None else default_workers())
        cache = (DiskCache(cache_dir, namespace=cache_namespace) if (use_cache and mode == "full") else None)
        if mode == "full":
            log.info("LLM: %s / %s, кэш %s, потоков %d", client.provider, client.model,  # type: ignore[union-attr]
                     "вкл" if cache else "выкл", nworkers)

        incomplete: list[str] = list(doc.incomplete)
        breakdown: dict[str, int] = {}

        requirements, dropped_reqs, seg_warnings = segment(doc, llm, cache, nworkers, limits)
        warnings.extend(seg_warnings)
        if seg_warnings:
            incomplete.append("сегментация LLM выполнена не полностью")
        log.info("segment: требований %d", len(requirements))
        if not requirements:
            warnings.append("Требования не выделены: нет явных ID" +
                            ("." if mode == "full" else " и режим lint-only (требования без номеров выделяет LLM)."))
            if mode == "full":
                incomplete.append("требования не выделены, проверка отдельных требований и набора не выполнялась")

        findings: list[Finding] = []
        unchecked: dict[str, str] = {}
        conclusions: dict[str, str] = {}
        llm_total = 0
        if mode == "full" and requirements:
            each_findings, unchecked, discarded, each_notes = check_each(doc, requirements, llm, cache, nworkers)  # type: ignore[arg-type]
            for n in each_notes:
                warnings.append(f"Контекст раздела обрезан для проверки: {n}.")
            log.info("check_each: замечаний %d, не проверено %d, отброшено по ID/критерию %d",
                     len(each_findings), len(unchecked), discarded)
            if discarded:
                breakdown["ответ модели: ID вне пачки или критерий вне списка"] = discarded
            set_findings, conclusions, set_warnings = check_set(doc, requirements, llm, cache, nworkers)  # type: ignore[arg-type]
            log.info("check_set: замечаний %d", len(set_findings))
            warnings.extend(set_warnings)
            incomplete.extend(w.split(":")[0] + " (не выполнено)" if w.startswith("Проход") else w for w in set_warnings)
            findings += each_findings + set_findings
            llm_total = len(findings)
            if unchecked:
                incomplete.append(f"не проверено LLM требований: {len(unchecked)}")
        elif mode == "full":
            conclusions = {c: "Не проверено: требования не выделены." for c in SET_CODES}

        lint_findings, failed_rules, truncated = run_lint_safe(doc, requirements, limits.max_lint_per_rule)
        log.info("lint: замечаний %d, упало правил %d, обрезано правил %d", len(lint_findings), len(failed_rules), len(truncated))
        if failed_rules:
            warnings.append("Правила линтера не выполнены: " + ", ".join(failed_rules) + ".")
            incomplete.append("правила линтера не выполнены: " + ", ".join(failed_rules))
        if truncated:
            warnings.append("Правила линтера дали слишком много замечаний, показаны первые "
                            f"{limits.max_lint_per_rule} от каждого: " + ", ".join(truncated) + ".")
        findings += lint_findings

        findings, dropped_findings = ground_findings_detailed(
            doc, findings, {r.id: r.anchor.line_start for r in requirements})
        dropped = len(dropped_findings) + dropped_reqs
        by_req: dict[str, int] = {}
        for f in dropped_findings:
            for rid in f.requirement_ids:
                by_req[rid] = by_req.get(rid, 0) + 1
        log.info("ground: отброшено %d (замечаний %d, требований %d)", dropped, len(dropped_findings), dropped_reqs)
        llm_dropped = sum(1 for f in dropped_findings if f.source == "llm")
        if llm_total >= 5 and llm_dropped / llm_total > 0.3:
            incomplete.append(f"проверкой цитат отброшено {llm_dropped} из {llm_total} замечаний LLM")
        if dropped_findings:
            breakdown["замечания: цитата не найдена в документе"] = len(dropped_findings)
        if dropped_reqs:
            breakdown["сегментация: цитата требования не найдена в документе"] = dropped_reqs

        dedupe_stats: dict[str, int] = {}
        findings = finalize_findings(findings, dedupe_stats)
        if dedupe_stats.get("deduped"):
            breakdown["автоматически склеены дубли (тот же критерий и цитата)"] = dedupe_stats["deduped"]
        findings, cut = _cap_findings(findings, limits.max_findings)
        if cut:
            warnings.append(f"Замечаний больше лимита ({limits.max_findings}): показаны самые серьёзные, скрыто {cut}.")
            findings = finalize_findings(findings)

        rejected_notes: list[dict[str, str]] = []
        merged = 0
        if mode == "full":
            try:
                findings, merged, w = consolidate(findings, llm, cache)  # type: ignore[arg-type]
                warnings.extend(w)
            except LLMUnavailableError as exc:
                _skipped(warnings, "объединение дублей", exc)
            findings = finalize_findings(findings)
            try:
                findings, rejected_notes, w = verify_critical(  # type: ignore[arg-type]
                    doc, findings, llm, cache, nworkers, limits.max_verified)
                warnings.extend(w)
            except LLMUnavailableError as exc:
                _skipped(warnings, "перепроверка критичных замечаний", exc)
            findings = finalize_findings(findings)  # перенумерация после снятых
            try:
                findings, w = ensure_questions(findings, llm, cache, nworkers)  # type: ignore[arg-type]
                warnings.extend(w)
            except LLMUnavailableError as exc:
                _skipped(warnings, "уточняющие вопросы", exc)
        if unchecked:
            warnings.append(f"Не проверено LLM: {', '.join(sorted(unchecked))} (см. раздел 3).")

        provider_name = client.provider if client else "не используется"
        model_name = client.model if client else "—"
        if isinstance(client, FallbackLLM):
            used = client.used or [(client.provider, client.model)]
            provider_name = " → ".join(dict.fromkeys(pv for pv, _ in used))
            model_name = ", ".join(dict.fromkeys(m for _, m in used))
            if client.switches:
                warnings.append("Основной провайдер был недоступен, часть вызовов выполнил запасной: "
                                + "; ".join(client.switches) + ".")

        passport = RunPassport(
            document_title=doc.title,
            document_path=doc.path,
            document_sha256=doc.sha256,
            run_datetime=_now(),
            model_provider=provider_name,
            model_id=model_name,
            agent_version=version,
            llm_mode=mode,
        )
        report = Report(
            passport=passport,
            requirements=requirements,
            findings=findings,
            dropped_count=dropped,
            merged_count=merged,
            verifier_rejected=sum(1 for n in rejected_notes if n["action"] == "снято"),
            verifier_notes=rejected_notes,
            drop_breakdown=breakdown,
            dropped_by_requirement=by_req,
            incomplete_reasons=incomplete if mode == "full" else [],
            unchecked=unchecked,
            set_conclusions=conclusions,
            verdict=compute_verdict(findings, mode, incomplete if mode == "full" else ()),
            warnings=warnings,
        )
        write_atomic(json_path, report.model_dump_json(indent=2))
        write_atomic(out, render_report(report))  # последним: наличие .md значит, что прогон завершён
        log.info("Отчёт записан: %s", out)
        return report


def _skipped(warnings: list[str], name: str, exc: Exception) -> None:
    """Необязательный этап не выполнен: оплаченные проверки не выбрасываем, а помечаем пропуск."""
    log.error("%s: LLM недоступна: %s", name, redact(exc))
    warnings.append(f"Этап «{name}» не выполнен: LLM недоступна. Отчёт построен без него.")


__all__ = ["run", "InputFileError", "sidecar_paths", "write_atomic"]
