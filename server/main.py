"""FastAPI: /api/* и раздача статического фронтенда web/out (один контейнер, один домен, без CORS)."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.gzip import GZipMiddleware

from reqcheck import __version__
from reqcheck.chat import ChatMessage, chat_reply
from reqcheck.config import Settings, load_env_file, load_settings
from reqcheck.errors import ReqcheckError
from reqcheck.ingest import SUPPORTED, load_document
from reqcheck.limits import Budget, BudgetedLLM, Limits
from reqcheck.llm import build_client
from reqcheck.models import Document, Report
from reqcheck.recheck import recheck
from server.jobs import JobManager, QueueFull
from server.ratelimit import LimitExceeded, RateLimiter, client_ip
from server.view import report_view

log = logging.getLogger("sau.server")

# Локальная разработка: подхватить .env, только если явно попросили. На сервере ключи в окружении.
if os.getenv("SITE_DOTENV") == "1":
    load_env_file()

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_REPORT = ROOT / "reports" / "report.json"
EXAMPLE_DOCUMENT = ROOT / "examples" / "input" / "requirements.pdf"
WEB_DIR = Path(os.getenv("SITE_WEB_DIR") or ROOT / "web" / "out")
RUN_ID = re.compile(r"^[0-9a-f]{32}$")
# Заголовок, который чужой сайт не может поставить без preflight: защита платных POST от межсайтовых форм.
CSRF_HEADER = "x-sau"

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Strict-Transport-Security": "max-age=31536000",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
QUOTED_SELF = "'self'"
INLINE_SCRIPT = re.compile(rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL)
# тело запроса к API: переписка и ответы укладываются в полмегабайта, файл проверяется отдельно
MAX_JSON_BYTES = 512 * 1024


@lru_cache(maxsize=4)
def _csp(web_dir: Path, built: int) -> str:
    """Next кладёт инлайн-скрипты гидратации в HTML: разрешаем ровно их по хешам, а не любые."""
    hashes = sorted({
        "'sha256-" + base64.b64encode(hashlib.sha256(code).digest()).decode() + "'"
        for page in web_dir.rglob("*.html") for code in INLINE_SCRIPT.findall(page.read_bytes()) if code
    })
    return (
        f"default-src 'self'; script-src {' '.join([QUOTED_SELF, *hashes])}; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )


def content_security_policy(web_dir: Path) -> str:
    index = web_dir / "index.html"
    # новая сборка меняет скрипты: ключ кэша — время сборки
    return _csp(web_dir, index.stat().st_mtime_ns if index.is_file() else 0)


def cache_control(path: str) -> str:
    if path.startswith("/api/"):
        return "no-store"
    if path.startswith("/_next/static/"):
        return "public, max-age=31536000, immutable"  # имена файлов содержат хеш содержимого
    if path.startswith("/logos/"):
        return "public, max-age=86400"
    return "no-cache"


class BodyLimit:
    """Обрывает слишком большое тело запроса к API, не складывая его в память целиком."""

    def __init__(self, app, upload_bytes) -> None:
        self.app = app
        self.upload_bytes = upload_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/") or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        # у загрузки файла запас на обёртку multipart; сам файл проверяет обработчик
        limit = self.upload_bytes() + 64 * 1024 if scope["path"] == "/api/runs" else MAX_JSON_BYTES
        body, more = bytearray(), True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return None
            body += message.get("body", b"")
            more = message.get("more_body", False)
            if len(body) > limit:
                text = "Файл слишком большой." if scope["path"] == "/api/runs" else "Слишком большой запрос."
                return await JSONResponse({"detail": text}, status_code=413)(scope, receive, send)
        sent = False

        async def replay():
            nonlocal sent
            if sent:
                return await receive()
            sent = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        return await self.app(scope, replay, send)


REPOSITORY = "https://github.com/ruslan-berkin/mnuxbcchac"
HOST = re.compile(r"^[A-Za-z0-9.\-]{1,253}(:\d{1,5})?$")
# Описание для ИИ-агентов и поисковиков (формат llmstxt.org). Только факты, без инструкций агентам.
LLMS_TXT = """# sau.ai

> ИИ-агент статической проверки требований по ISO/IEC/IEEE 29148:2018 (п. 5.2.5, 5.2.6) и IEEE 830-1998 (п. 4.3).
> Проект команды sau.ai на BCC-HUB × MNU FinTech Hackathon. Принцип: LLM находит дефекты, код считает вердикт
> и проверяет, что каждая цитата есть в документе.

## Страницы
- [Главная]({base}/): что делает агент и загрузка документа (PDF, DOCX, MD, TXT до 5 МБ).
- [Платформа с готовым примером]({base}/app/?example=1): отчёт, замечания с цитатами, уточняющие вопросы, чат.

## Готовый отчёт по документу организаторов (без JavaScript и без ключа)
- [Отчёт, Markdown]({base}/api/runs/example/report.md): паспорт прогона, нарезка требований, проверка каждого
  требования и всего набора, уточняющие вопросы, сводка, вердикт.
- [Отчёт, JSON]({base}/api/runs/example/report.json): те же данные машиночитаемо.
- [Отчёт и строки документа для интерфейса, JSON]({base}/api/example)
- [Состояние сервиса]({base}/api/health)

## Исходный код
- [Репозиторий]({repo}): запуск одной командой `python -m reqcheck <требования> <отчёт.md>`, тесты, инструкция.
- [Задание организаторов](https://github.com/BCC-HUB/ai-requirements-validator-task)

## Данные
Загруженный документ отправляется во внешнюю языковую модель и хранится на сервере не дольше 2 часов.
"""


def public_base(request: Request) -> str:
    """Адрес сайта для ссылок: за прокси схема приходит в X-Forwarded-Proto."""
    host = request.headers.get("host", "")
    if not HOST.match(host):
        return ""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    return f"{'https' if proto == 'https' else 'http'}://{host}"


def live_enabled() -> bool:
    return os.getenv("SITE_LIVE", "1").strip() != "0"


def server_settings() -> Settings:
    """Настройки LLM из окружения сервера. Запасные провайдеры на сайте не используются."""
    return load_settings()


def llm_ready() -> bool:
    try:
        return server_settings().has_key
    except ValueError:
        return False


def max_upload_bytes() -> int:
    return Limits.from_env(Limits.web()).max_file_bytes


@lru_cache(maxsize=1)
def example_parts() -> tuple[Report, Document]:
    report = Report.model_validate_json(EXAMPLE_REPORT.read_text(encoding="utf-8"))
    # Документ наш, доверенный: песочница не нужна. Нумерация строк та же, что при прогоне.
    # разбор как при генерации отчёта, чтобы номера строк совпали с якорями
    doc = load_document(EXAMPLE_DOCUMENT, limits=Limits(sandbox=False), display_name=EXAMPLE_DOCUMENT.name)
    if doc.sha256 != report.passport.document_sha256:
        log.warning("Пример: SHA-256 документа не совпадает с паспортом отчёта, подсветка может не совпасть")
    return report, doc


@lru_cache(maxsize=1)
def load_example() -> dict:
    """Готовый отчёт и строки документа. Без LLM."""
    report, doc = example_parts()
    return report_view(doc, report)


def _file(path: Path, kind: str, name: str) -> FileResponse:
    if not path.is_file():
        raise HTTPException(404, "Файл отчёта не найден.")
    media = "application/json" if kind == "json" else "text/markdown; charset=utf-8"
    return FileResponse(path, media_type=media, filename=f"{name}.{kind}")


class ChatRequest(BaseModel):
    run_id: str = Field(max_length=40)
    messages: list[ChatMessage] = Field(max_length=40)
    answers: dict[str, str] = Field(default_factory=dict, max_length=60)


class RecheckRequest(BaseModel):
    run_id: str = Field(max_length=40)
    answers: dict[str, str] = Field(max_length=60)


def create_app(web_dir: Path | None = None, jobs: JobManager | None = None, limiter: RateLimiter | None = None) -> FastAPI:
    app = FastAPI(title="sau.ai", docs_url=None, redoc_url=None, openapi_url=None)
    manager = jobs or JobManager(server_settings)
    limits = limiter or RateLimiter()
    app.state.jobs, app.state.limiter = manager, limits

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        response.headers.setdefault("Content-Security-Policy", content_security_policy(web_dir or WEB_DIR))
        response.headers.setdefault("Cache-Control", cache_control(request.url.path))
        return response

    app.add_middleware(BodyLimit, upload_bytes=max_upload_bytes)
    # поток чата (text/event-stream) сжатие пропускает, ответы не задерживаются
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    def require_same_site(request: Request) -> None:
        if request.headers.get(CSRF_HEADER) != "1":
            raise HTTPException(403, "Запрос отклонён.")

    def require_live() -> None:
        if not live_enabled():
            raise HTTPException(503, "Живые прогоны сейчас выключены. Откройте пример.")
        if not llm_ready():
            raise HTTPException(503, "На сервере не настроен ключ модели. Откройте пример.")

    def take(action: str, request: Request) -> str:
        ip = client_ip(request.headers.get("x-forwarded-for"), request.client.host if request.client else None)
        try:
            limits.take(action, ip)
        except LimitExceeded as exc:
            raise HTTPException(429, str(exc)) from exc
        return ip

    def parts(run_id: str) -> tuple[Report, Document]:
        if run_id == "example":
            return example_parts()
        job = manager.get(run_id) if RUN_ID.match(run_id) else None
        if job is None or job.status != "done" or job.report is None or job.document is None:
            raise HTTPException(404, "Результат прогона не найден или уже удалён (хранится 2 часа).")
        return job.report, job.document

    def chat_client():
        # чат и перепроверка тратят ключ: тот же бюджет, что и у веб-прогона
        return BudgetedLLM(build_client(server_settings(), attempts=2), Budget(Limits.from_env(Limits.web())))

    @app.get("/robots.txt")
    def robots(request: Request) -> PlainTextResponse:
        return PlainTextResponse(f"User-agent: *\nAllow: /\n\nSitemap: {public_base(request)}/sitemap.xml\n")

    @app.get("/sitemap.xml")
    def sitemap(request: Request) -> Response:
        base = public_base(request)
        urls = "".join(f"<url><loc>{base}{path}</loc></url>" for path in ("/", "/app/"))
        body = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
        return Response(body, media_type="application/xml")

    @app.get("/llms.txt")
    def llms(request: Request) -> PlainTextResponse:
        return PlainTextResponse(LLMS_TXT.format(base=public_base(request), repo=REPOSITORY))

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "live": live_enabled() and llm_ready(), "version": __version__}

    @app.get("/api/example")
    def example() -> dict:
        try:
            return load_example()
        except Exception as exc:  # без путей и трейсбэков в ответе
            log.exception("Не удалось загрузить пример")
            raise HTTPException(503, "Пример временно недоступен.") from exc

    @app.get("/api/runs/example/report.md")
    def example_md() -> FileResponse:
        return _file(EXAMPLE_REPORT.with_suffix(".md"), "md", "sau-example-report")

    @app.get("/api/runs/example/report.json")
    def example_json() -> FileResponse:
        return _file(EXAMPLE_REPORT, "json", "sau-example-report")

    @app.post("/api/runs", status_code=202)
    def create_run(request: Request, file: UploadFile) -> dict:
        require_same_site(request)
        require_live()
        name = file.filename or ""
        if Path(name).suffix.lower() not in SUPPORTED:
            raise HTTPException(415, "Поддерживаются PDF, DOCX, MD и TXT.")
        limit = max_upload_bytes()
        content = file.file.read(limit + 1)  # не доверяем Content-Length
        if len(content) > limit:
            raise HTTPException(413, f"Файл больше {limit // (1024 * 1024)} МБ.")
        if not content.strip():
            raise HTTPException(400, "Файл пустой.")
        ip = take("run", request)
        try:
            job = manager.submit(name, content)
        except QueueFull as exc:
            limits.refund("run", ip)
            raise HTTPException(429, "Очередь заполнена. Попробуйте через несколько минут или откройте пример.") from exc
        return {"run_id": job.id, "position": manager.position(job)}

    @app.get("/api/runs/{run_id}")
    def run_status(run_id: str) -> dict:
        job = manager.get(run_id) if RUN_ID.match(run_id) else None
        if job is None:
            raise HTTPException(404, "Прогон не найден или уже удалён (результаты хранятся 2 часа).")
        return manager.status(job)

    @app.get("/api/runs/{run_id}/report.{kind}")
    def run_file(run_id: str, kind: str) -> FileResponse:
        job = manager.get(run_id) if RUN_ID.match(run_id) else None
        if job is None or job.status != "done" or kind not in ("md", "json"):
            raise HTTPException(404, "Файл отчёта не найден.")
        return _file(job.directory / f"report.{kind}", kind, f"sau-report-{run_id[:8]}")

    @app.post("/api/chat")
    def chat(request: Request, body: ChatRequest) -> StreamingResponse:
        require_same_site(request)
        report, doc = parts(body.run_id)
        require_live()
        if not body.messages or body.messages[-1].role != "user" or not body.messages[-1].content.strip():
            raise HTTPException(400, "Напишите вопрос.")
        if len(body.messages[-1].content) > 2000:
            raise HTTPException(413, "Сообщение длиннее 2000 символов.")
        take("chat", request)
        max_tokens = int(os.getenv("SITE_MAX_CHAT_TOKENS") or 1500)

        def events() -> Iterator[str]:
            def event(data: dict) -> str:
                return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            try:
                for piece in chat_reply(report, doc, body.messages, chat_client(), body.answers, max_tokens):
                    yield event({"delta": piece})
                yield event({"done": True})
            except Exception as exc:  # noqa: BLE001 — поток уже начат: ошибку шлём событием без деталей
                log.warning("чат: %s", type(exc).__name__)
                yield event({"error": "Не удалось получить ответ модели. Попробуйте ещё раз."})

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/recheck")
    def recheck_answers(request: Request, body: RecheckRequest) -> dict:
        require_same_site(request)
        report, doc = parts(body.run_id)
        require_live()
        answers = {k: v for k, v in body.answers.items() if v.strip()}
        if not answers:
            raise HTTPException(400, "Сначала ответьте хотя бы на один вопрос.")
        ip = take("recheck", request)
        try:
            result = recheck(report, doc, answers, chat_client(), workers=2)
        except ReqcheckError as exc:
            limits.refund("recheck", ip)
            log.warning("перепроверка: %s", type(exc).__name__)
            raise HTTPException(502, "Модель недоступна. Попробуйте позже.") from exc
        return result.model_dump(mode="json")

    @app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def unknown_api(rest: str) -> None:
        raise HTTPException(404, "Нет такого метода API.")

    static = web_dir or WEB_DIR
    if static.is_dir():  # в разработке фронтенд может быть ещё не собран
        app.mount("/", StaticFiles(directory=static, html=True), name="web")
    return app


app = create_app()
