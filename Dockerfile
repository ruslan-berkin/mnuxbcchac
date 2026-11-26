# --- 1. Статическая сборка фронтенда
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY web/ ./
RUN npm run build

# --- 2. Python: ядро reqcheck + FastAPI, раздающий web/out
FROM python:3.12-slim AS runtime
# Памяти на Render free 512 МБ: без анализа макета разбор PDF занимает ~85 МБ вместо ~355 МБ.
# PARSE_MEMORY_MB ограничивает адресное пространство (не резидентную память): меньше ~700 МБ pymupdf не стартует.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    REQCHECK_PARSE_MEMORY_MB=1024 REQCHECK_PDF_LAYOUT=0
WORKDIR /app
COPY requirements.txt constraints.txt ./
COPY server/requirements.txt server/requirements.txt
RUN pip install --disable-pip-version-check -r server/requirements.txt -c constraints.txt
COPY reqcheck reqcheck
COPY server server
COPY reports/report.json reports/report.md reports/
COPY examples/input/requirements.pdf examples/input/requirements.pdf
COPY --from=web /web/out web/out
# Права файлов с машины сборки могут быть 0600: сервер работает не от root и должен их читать.
RUN chmod -R a+rX /app && useradd --system --no-create-home sau
USER sau
EXPOSE 8000
# Render передаёт порт в $PORT
CMD ["sh", "-c", "exec uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
