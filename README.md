# reqcheck

Агент статической проверки требований по ISO/IEC/IEEE 29148:2018 (п. 5.2.5, 5.2.6) и IEEE 830-1998 (п. 4.3).
Проект для BCC-HUB x MNU FinTech Hackathon. Архитектура и правила: [CLAUDE.md](CLAUDE.md), план работ: [PLAN.md](PLAN.md).

> Каркас (Фаза 1). Полный README с инструкцией по ключу и запуску появится в Фазе 4.

## Быстрый старт

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # ключ и ID модели из https://aistudio.google.com/
python -m reqcheck examples/input/requirements.pdf reports/report.md --lint-only
```

Рядом с отчётом создаются `report.json` и `report.log`. Без ключа агент работает в режиме `lint-only` (только правила без LLM).

## Тесты

```bash
python -m pytest
python scripts/self_check.py --repo
python scripts/self_check.py --report reports/report.md
```
