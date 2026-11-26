"""Очередь живых прогонов: один рабочий поток, статусы по этапам, временные папки и TTL."""

from __future__ import annotations

import logging
import queue
import shutil
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from reqcheck.config import Settings
from reqcheck.errors import ReqcheckError
from reqcheck.ingest import load_document, safe_display_name
from reqcheck.limits import Limits
from reqcheck.models import Document, Report
from reqcheck.pipeline import run
from server.view import report_view

log = logging.getLogger("sau.jobs")

STAGES = ("ingest", "segment", "check_each", "check_set", "ground", "verify", "render")


@dataclass
class Job:
    id: str
    name: str
    directory: Path
    created: float = field(default_factory=time.time)
    status: str = "queued"  # queued | running | done | error
    stage: str | None = None
    stages_done: list[str] = field(default_factory=list)
    error: str | None = None
    report: Report | None = None
    document: Document | None = None
    view: dict | None = None


class QueueFull(Exception):
    pass


class JobManager:
    def __init__(
        self,
        settings_factory: Callable[[], Settings],
        base_dir: Path | None = None,
        ttl_s: float = 2 * 3600,
        max_queue: int = 5,
    ) -> None:
        self.settings_factory = settings_factory
        self.base = Path(base_dir or tempfile.mkdtemp(prefix="sau-runs-"))
        self.ttl_s = ttl_s
        self.max_queue = max_queue
        self.jobs: dict[str, Job] = {}
        self._queue: queue.Queue[tuple[str, Path]] = queue.Queue()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

    # ---- постановка

    def pending(self) -> int:
        with self._lock:
            return sum(j.status in ("queued", "running") for j in self.jobs.values())

    def submit(self, filename: str, content: bytes) -> Job:
        self.cleanup()
        if self.pending() >= self.max_queue:
            raise QueueFull
        name = safe_display_name(filename)
        job_id = uuid.uuid4().hex
        directory = self.base / job_id
        directory.mkdir(parents=True)
        # на диске имя своё: имя пользователя идёт только в паспорт
        upload = directory / ("upload" + Path(name).suffix.lower())
        upload.write_bytes(content)
        job = Job(id=job_id, name=name, directory=directory)
        with self._lock:
            self.jobs[job_id] = job
        self._queue.put((job_id, upload))
        self._ensure_worker()
        return job

    # ---- чтение

    def get(self, job_id: str) -> Job | None:
        self.cleanup()
        with self._lock:
            return self.jobs.get(job_id)

    def position(self, job: Job) -> int:
        """Место в очереди: 1 — следующий (или уже выполняется)."""
        with self._lock:
            ahead = [j for j in self.jobs.values() if j.status in ("queued", "running") and j.created < job.created]
        return len(ahead) + 1

    def status(self, job: Job) -> dict:
        body = {"run_id": job.id, "name": job.name, "status": job.status, "stage": job.stage,
                "stages_done": list(job.stages_done), "error": job.error}
        if job.status == "queued":
            body["position"] = self.position(job)
        if job.status == "done" and job.view is not None:
            body.update(job.view)
        return body

    # ---- выполнение

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._loop, name="sau-worker", daemon=True)
                self._worker.start()

    def _loop(self) -> None:
        while True:
            job_id, upload = self._queue.get()
            with self._lock:
                job = self.jobs.get(job_id)
            if job is not None:
                self._execute(job, upload)
            self._queue.task_done()

    def _execute(self, job: Job, upload: Path) -> None:
        job.status = "running"

        def on_stage(name: str) -> None:
            if job.stage and job.stage not in job.stages_done:
                job.stages_done.append(job.stage)
            job.stage = name

        limits = Limits.from_env(Limits.web())
        try:
            report = run(
                upload, job.directory / "report.md", self.settings_factory(),
                require_llm=True, limits=limits, display_name=job.name, cache_namespace=job.id,
                on_stage=on_stage,
            )
            # тот же разбор, что в прогоне: номера строк совпадают с якорями
            job.document = load_document(upload, limits=limits, display_name=job.name)
            job.report = report
            job.view = report_view(job.document, report)
            job.stages_done = list(dict.fromkeys([*job.stages_done, job.stage or "render"]))
            job.stage = None
            job.status = "done"
        except ReqcheckError as exc:  # сообщения ядра без секретов и серверных путей
            log.warning("прогон %s: %s", job.id, type(exc).__name__)
            # в сообщении ядра фигурирует наше имя файла на диске: показываем имя пользователя
            job.error, job.status = str(exc).replace(upload.name, job.name), "error"
        except Exception:  # noqa: BLE001
            log.exception("прогон %s упал", job.id)
            job.error, job.status = "Внутренняя ошибка при проверке. Попробуйте позже или откройте пример.", "error"
        finally:
            upload.unlink(missing_ok=True)  # загруженный файл не храним

    def cleanup(self) -> None:
        now = time.time()
        with self._lock:
            expired = [j for j in self.jobs.values()
                       if j.status in ("done", "error") and now - j.created > self.ttl_s]
            for job in expired:
                del self.jobs[job.id]
        for job in expired:
            shutil.rmtree(job.directory, ignore_errors=True)
