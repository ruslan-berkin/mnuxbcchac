"""FastAPI: /api/* и раздача статического фронтенда web/out (один контейнер, один домен, без CORS).

Фаза A: health и готовый пример. Прогоны, чат и перепроверка появятся в фазе D.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from reqcheck import __version__
from reqcheck.ingest import load_document
from reqcheck.limits import Limits
from reqcheck.models import Report
from server.view import report_view

log = logging.getLogger("sau.server")

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_REPORT = ROOT / "reports" / "report.json"
EXAMPLE_DOCUMENT = ROOT / "examples" / "input" / "requirements.pdf"
WEB_DIR = Path(os.getenv("SITE_WEB_DIR") or ROOT / "web" / "out")

# Next кладёт инлайн-скрипты гидратации в статический HTML, поэтому 'unsafe-inline' для script-src.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
}


def live_enabled() -> bool:
    return os.getenv("SITE_LIVE", "1").strip() != "0"


@lru_cache(maxsize=1)
def load_example() -> dict:
    """Готовый отчёт и строки документа. Без LLM: читается один раз и кэшируется."""
    report = Report.model_validate_json(EXAMPLE_REPORT.read_text(encoding="utf-8"))
    # Документ наш, доверенный: песочница не нужна. Нумерация строк та же, что при прогоне.
    doc = load_document(EXAMPLE_DOCUMENT, limits=Limits(sandbox=False), display_name=EXAMPLE_DOCUMENT.name)
    if doc.sha256 != report.passport.document_sha256:
        log.warning("Пример: SHA-256 документа не совпадает с паспортом отчёта, подсветка может не совпасть")
    return report_view(doc, report)


def _example_file(kind: str) -> FileResponse:
    path = EXAMPLE_REPORT if kind == "json" else EXAMPLE_REPORT.with_suffix(".md")
    if not path.is_file():
        raise HTTPException(404, "Файл отчёта не найден.")
    media = "application/json" if kind == "json" else "text/markdown; charset=utf-8"
    return FileResponse(path, media_type=media, filename=f"sau-example-report.{kind}")


def create_app(web_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="sau.ai", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "live": live_enabled(), "version": __version__}

    @app.get("/api/example")
    def example() -> dict:
        try:
            return load_example()
        except Exception as exc:  # без путей и трейсбэков в ответе
            log.exception("Не удалось загрузить пример")
            raise HTTPException(503, "Пример временно недоступен.") from exc

    @app.get("/api/runs/example/report.md")
    def example_md() -> FileResponse:
        return _example_file("md")

    @app.get("/api/runs/example/report.json")
    def example_json() -> FileResponse:
        return _example_file("json")

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def unknown_api(rest: str) -> None:
        raise HTTPException(404, "Нет такого метода API.")

    static = web_dir or WEB_DIR
    if static.is_dir():  # в разработке фронтенд может быть ещё не собран
        app.mount("/", StaticFiles(directory=static, html=True), name="web")
    return app


app = create_app()
