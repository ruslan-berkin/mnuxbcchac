# sau.ai: проверка требований до разработки

[![CI](https://github.com/ruslan-berkin/mnuxbcchac/actions/workflows/ci.yml/badge.svg)](https://github.com/ruslan-berkin/mnuxbcchac/actions/workflows/ci.yml)

## 👉 Оценить без установки: **<https://sau-ai.onrender.com>**

**Ничего подключать не нужно.** API модели (`gpt-6.2-sol`, OpenAI) уже подключён на сервере: без регистрации,
без своего ключа и без установки. Свой ключ нужен только для запуска у себя.

Сервер бесплатный: после простоя первый ответ может идти около минуты.

1. [**Открыть готовый пример**](https://sau-ai.onrender.com/app/?example=1): отчёт по документу организаторов,
   замечания с подсветкой цитат, вопросы аналитику, чат с агентом. Загружать ничего не нужно.
2. Ответить на вопросы агента и нажать «Перепроверить»: видно, как меняется вердикт («было → стало»).
3. Загрузить свой документ на [главной](https://sau-ai.onrender.com) (PDF, DOCX, MD, TXT до 5 МБ). Текст уходит
   в OpenAI, конфиденциальные документы не загружайте. Лимит: 5 загрузок в день с одного адреса
   и 20 на весь сайт; пример открывается без ограничений.

| Что сдаётся | Где |
|---|---|
| Отчёт, сформированный агентом | [reports/report.md](reports/report.md) · [JSON](reports/report.json) · [журнал прогона](reports/report.log) |
| Документ организаторов (вход агента, не результат) | [requirements.md](examples/input/requirements.md) · [PDF](examples/input/requirements.pdf) |
| Задание хакатона | [BCC-HUB x MNU FinTech Hackathon](https://github.com/BCC-HUB/ai-requirements-validator-task) |

Итог по документу организаторов: 55 требований, 72 замечания, из них **6 критичных**, поэтому начинать
разработку без исправлений нельзя.

## Что делает агент

Читает ТЗ, выделяет отдельные требования, проверяет каждое и весь набор по **ISO/IEC/IEEE 29148:2018**
(п. 5.2.5, 5.2.6) и **IEEE Std 830-1998** (п. 4.3) и записывает отчёт на русском: паспорт прогона, нарезка,
замечания с цитатами, **уточняющие вопросы аналитику**, сводка и вердикт.

**LLM думает, код контролирует.** Модель находит дефекты и формулирует вопросы. Вердикт, счётчики, паспорт и
проверку того, что каждая цитата есть в документе, делает обычный код.

## Запуск у себя

Нужен Python 3.11 или новее.

```bash
git clone https://github.com/ruslan-berkin/mnuxbcchac.git && cd mnuxbcchac
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -c constraints.txt
cp .env.example .env
```

Впишите в `.env` ключ и точный ID модели (в коде они не зашиты), провайдера задаёт `LLM_PROVIDER`:

| `LLM_PROVIDER` | Где взять ключ | Переменные |
|---|---|---|
| `gemini` (есть бесплатный тариф) | <https://aistudio.google.com/> → *Get API key* | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| `groq` | <https://console.groq.com/keys> | `GROQ_API_KEY`, `GROQ_MODEL` |
| `openai_compat` (OpenAI, OpenRouter, Ollama, vLLM) | у провайдера | `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL` |

Проверка одной командой:

```bash
python -m reqcheck examples/input/requirements.pdf reports/report.md
```

Общий вид: `python -m reqcheck <требования> <отчёт.md>`. Отчёт ляжет по указанному пути (здесь в `reports/`),
рядом появятся `.json` и `.log`. Прогон документа организаторов занимает несколько минут, повтор из кэша — секунды.

**Какая модель использована:** отчёт в `reports/` получен моделью **`gpt-6.2-sol`** (`openai_compat`), версия
агента `v1.3`; модель, дата, SHA-256 документа и версия записаны в паспорт отчёта. Агент проверен также на
Gemini (`gemini-3.1-flash-lite`) и Groq (`openai/gpt-oss-120b`).

**Без ключа** агент не падает, а работает в режиме `lint-only` (только правила) и пишет это в паспорте:

```bash
python -m reqcheck examples/input/requirements.pdf reports/report_lint.md --lint-only
```

<details>
<summary>Опции командной строки и коды выхода</summary>

| Опция | Назначение |
|---|---|
| `--provider`, `--model` | провайдер и ID модели (иначе из `.env`) |
| `--lint-only` | только правила без LLM |
| `--require-llm` | ошибка, если нет ключа |
| `--no-cache` | не использовать кэш ответов (`.cache/llm/`) |
| `--workers N` | параллельных вызовов LLM (по умолчанию 4) |
| `--no-fallback` | не переключаться на запасной провайдер (порядок задаёт `LLM_FALLBACK`) |
| `--answers FILE` | перепроверить замечания с ответами аналитика (строки `D-013: ответ`) |

Коды выхода: `0` ок; `1` внутренняя ошибка; `2` файл не найден, не поддерживается или слишком большой; `3` в
документе нет текста (скан); `4` нет ключа при `--require-llm`; `5` LLM недоступна; `6` исчерпан бюджет прогона.
</details>

## Как устроен агент

```
ingest → segment → check_each ─┐
                   check_set  ─┼→ ground → consolidate → verify → questions → render
                   lint (без LLM)┘
```

| Этап | Кто | Суть |
|---|---|---|
| ingest | код | PDF, DOCX, MD, TXT → блоки с якорями (страница, раздел, строка) |
| segment | код + LLM | явные ID регулярками, остальные требования выделяет модель; у каждого дословная цитата |
| check_each, check_set | LLM | каждое требование и весь набор по закрытому списку критериев |
| lint | код | правила без LLM: размытые слова, пустые поля, единицы, ошибки HTTP |
| ground | код | цитата ищется в тексте; выдуманная — замечание отбрасывается и попадает в лог |
| consolidate, verify, questions | LLM + код | склейка дублей, независимая перепроверка критичных, вопросы |
| render | код | отчёт по шаблону; вердикт: есть критичные → «нельзя», только существенные → «с оговорками» |

<details>
<summary>Надёжность и безопасность</summary>

- Ответ модели проверяется по схеме; при ошибке один повторный запрос, затем «не проверено» в отчёте.
- Ретраи на 429/5xx/таймаут, запасной провайдер, `temperature=0`, если модель допускает.
- Документ подаётся как данные: инструкции внутри него не выполняются (есть тесты с prompt injection).
- Лимиты на размер, страницы, вызовы и время (`REQCHECK_*`), разбор PDF и DOCX в отдельном процессе без ключей.
- Секреты вырезаются из логов; если часть проверки не выполнена, вердикт «проверка неполная».
- Использование из кода: `reqcheck.pipeline.run(...)` с `Limits.web()` и `cache_namespace` на пользователя.
- Под выданный документ ничего не зашито, тесты идут и на других документах.
</details>

## Сайт

Next.js (статический экспорт, `web/`) и FastAPI (`server/`) в одном контейнере.

```bash
docker build -t sau-site . && docker run -p 8000:8000 -e LLM_PROVIDER=openai_compat -e OPENAI_API_KEY=... -e OPENAI_MODEL=... sau-site
```

<details>
<summary>Деплой на Render и лимиты</summary>

1. Render → **New → Blueprint** → этот репозиторий (`render.yaml`).
2. Вписать `OPENAI_API_KEY` и `OPENAI_MODEL`; в кабинете OpenAI поставить жёсткий лимит расходов.

Лимиты платного ключа: `SITE_LIVE`, `SITE_DAILY_RUNS`, `SITE_RUNS_PER_IP`, `SITE_CHAT_PER_IP`,
`SITE_RECHECK_PER_IP`, `SITE_DAILY_CHAT`, `SITE_DAILY_RECHECK`, `SITE_MAX_CHAT_TOKENS` (значения в `render.yaml`).
Без ключа работают лендинг и пример. Локально без Docker: `SITE_DOTENV=1 uvicorn server.main:app`.
</details>

## Тесты

```bash
python -m pytest                                          # без ключа, на фейковой модели
python scripts/self_check.py --repo                       # проверка репозитория
python scripts/self_check.py --report reports/report.md   # отчёт на соответствие заданию
```

## Ограничения

- Это ревью формулировок до разработки, а не тестирование программы.
- Качество замечаний зависит от модели; часть «существенных» может быть спорной, решает аналитик.
- PDF должен иметь текстовый слой: сканы отклоняются.
- На сайте результаты хранятся не дольше 2 часов и пропадают при перезапуске сервера.

Дизайн сайта вдохновлён шаблоном «Teal Treasury Landing» (MIT, Kedhareswer Naidu).
