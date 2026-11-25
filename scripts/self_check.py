"""Самопроверка: отчёт и репозиторий на соответствие ТЗ.

  python scripts/self_check.py --report reports/report.md
  python scripts/self_check.py --repo

Код выхода 0, если ошибок нет; 1, если есть.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reqcheck.render import SECTION_TITLES  # noqa: E402

PASSPORT_FIELDS = [
    "Название документа", "Путь к документу", "SHA-256 документа", "Дата и время прогона",
    "Провайдер LLM", "Модель", "Версия агента", "Режим",
]
TABLE_HEADER = "| ID в отчёте | ID в документе | Тип | Краткая формулировка | Цитата | Место |"
FINDING_START = re.compile(r"^- \*\*(D-\d+)\*\*")
FINDING_FIELDS = ["Цитата", "Место", "Проблема", "Как исправить"]


def _sections(text: str) -> dict[int, str]:
    """Номер раздела верхнего уровня → его текст."""
    parts = re.split(r"(?m)^## (\d+)\. .*$", text)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def check_report(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"Отчёт не найден: {path}"]
    text = path.read_text(encoding="utf-8")

    # 1. Разделы: наличие и порядок.
    found = re.findall(r"(?m)^## (\d+)\. (.*?)\s*$", text)
    expected = [(str(i), t) for i, t in enumerate(SECTION_TITLES, start=1)]
    if found != expected:
        errors.append(f"Разделы отчёта не совпадают с ТЗ. Ожидалось: {expected}. Найдено: {found}.")
    secs = _sections(text)

    # 2. Паспорт заполнен.
    for field in PASSPORT_FIELDS:
        m = re.search(rf"(?m)^\| {re.escape(field)} \| (.*?) \|\s*$", text)
        if not m or not m.group(1).strip().strip("`"):
            errors.append(f"Паспорт: поле «{field}» отсутствует или пусто.")
    sha = re.search(r"(?m)^\| SHA-256 документа \| `?([0-9a-f]+)`? \|", text)
    if not sha or len(sha.group(1)) != 64:
        errors.append("Паспорт: SHA-256 должен быть 64 hex-символа.")

    # 3. Таблица нарезки.
    s2 = secs.get(2, "")
    if TABLE_HEADER not in s2:
        errors.append("Раздел 2: нет таблицы нарезки с нужными колонками.")
    rows = [ln for ln in s2.splitlines() if re.match(r"^\| R-\d+ \|", ln)]
    if not rows:
        errors.append("Раздел 2: в таблице нарезки нет ни одного требования.")
    for ln in rows:
        cells = re.split(r"(?<!\\)\|", ln.strip().strip("|"))
        if len(cells) != 6 or any(not c.strip() for c in cells):
            errors.append(f"Раздел 2: неполная строка таблицы: {ln[:80]}")
    req_ids = {re.match(r"^\| (R-\d+) ", ln).group(1) for ln in rows}  # type: ignore[union-attr]

    # 4. Раздел 3: каждое R-xx описано; раздел 4: все S-коды.
    for rid in sorted(req_ids):
        if not re.search(rf"(?m)^### {rid}\b", secs.get(3, "")):
            errors.append(f"Раздел 3: нет блока для {rid}.")
    for code in ("S-CMP", "S-CON", "S-FEA", "S-CMH", "S-VAL", "S-RNK", "S-MOD", "S-TRC"):
        if not re.search(rf"(?m)^### {code}\b", secs.get(4, "")):
            errors.append(f"Раздел 4: нет критерия {code}.")

    # 5. У каждого замечания есть цитата, место, проблема, исправление.
    finding_ids: list[str] = []
    for num in (3, 4):
        lines = secs.get(num, "").splitlines()
        i = 0
        while i < len(lines):
            m = FINDING_START.match(lines[i])
            if not m:
                i += 1
                continue
            fid = m.group(1)
            finding_ids.append(fid)
            body = []
            i += 1
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                body.append(lines[i])
                i += 1
            for field in FINDING_FIELDS:
                fm = next((b for b in body if b.strip().startswith(f"- {field}:")), None)
                value = fm.split(":", 1)[1].strip() if fm else ""
                if not value:
                    errors.append(f"{fid}: нет поля «{field}».")
            quote = next((b for b in body if b.strip().startswith("- Цитата:")), "")
            if "«" not in quote:
                errors.append(f"{fid}: цитата должна быть в кавычках « ».")
    if len(finding_ids) != len(set(finding_ids)):
        errors.append("Есть повторяющиеся ID замечаний.")

    # 6. Вопросы ссылаются на R-xx / D-xxx.
    s5 = secs.get(5, "")
    for block in re.split(r"(?m)^(?=\d+\. )", s5)[1:]:
        if not re.search(r"Связано с: .*\b(?:R-\d+|D-\d+)\b", block):
            errors.append(f"Раздел 5: у вопроса нет ссылки на R-xx/D-xxx: {block.strip()[:60]}")
        if "Почему нужен ответ" not in block:
            errors.append(f"Раздел 5: у вопроса нет пояснения: {block.strip()[:60]}")

    # 7. Сводка и итог.
    if not re.search(r"Требований: \d+", secs.get(6, "")):
        errors.append("Раздел 6: нет числа требований.")
    if "Отброшено при проверке цитат" not in secs.get(6, ""):
        errors.append("Раздел 6: нет счётчика отброшенных цитат.")
    if "Вердикт:" not in secs.get(7, ""):
        errors.append("Раздел 7: нет вердикта.")
    if "Что исправить в первую очередь" not in secs.get(7, ""):
        errors.append("Раздел 7: нет списка «Что исправить в первую очередь».")

    # 8. Согласованность с JSON-файлом рядом.
    js = path.with_suffix(".json")
    if js.is_file():
        data = json.loads(js.read_text(encoding="utf-8"))
        if len(data["requirements"]) != len(rows):
            errors.append("JSON и отчёт расходятся по числу требований.")
        if len(data["findings"]) != len(finding_ids):
            errors.append("JSON и отчёт расходятся по числу замечаний.")
    else:
        errors.append(f"Рядом с отчётом нет {js.name}.")
    if not path.with_suffix(".log").is_file():
        errors.append(f"Рядом с отчётом нет {path.with_suffix('.log').name}.")
    return errors


SECRET_PATTERNS = [r"AIza[0-9A-Za-z_\-]{30,}", r"sk-[A-Za-z0-9]{20,}", r"(?i)api[_-]?key\s*=\s*['\"]?(?!your_)[A-Za-z0-9_\-]{20,}"]


def check_repo() -> list[str]:
    errors: list[str] = []
    for name in ("README.md", "PLAN.md", "CLAUDE.md", ".env.example", ".gitignore",
                 "requirements.txt", "constraints.txt", "pyproject.toml", ".github/workflows/ci.yml",
                 "reqcheck/templates/report.md.j2", "scripts/self_check.py"):
        if not (ROOT / name).is_file():
            errors.append(f"Нет файла {name}.")
    for prompt in ("common", "segment", "check_each", "check_set", "questions", "repair"):
        if not (ROOT / "reqcheck" / "prompts" / f"{prompt}.md").is_file():
            errors.append(f"Нет промпта reqcheck/prompts/{prompt}.md.")
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8") if (ROOT / ".gitignore").is_file() else ""
    for entry in (".env", ".cache/"):
        if not re.search(rf"(?m)^{re.escape(entry)}\s*$", gi):
            errors.append(f".gitignore не содержит {entry}")
    if (ROOT / ".git").exists():
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        if ".env" in tracked:
            errors.append(".env попал в git.")
        for f in tracked:
            p = ROOT / f
            if not p.is_file() or p.suffix in {".pdf", ".png", ".ico"} or f == "scripts/self_check.py":
                continue
            try:
                content = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for pat in SECRET_PATTERNS:
                if re.search(pat, content):
                    errors.append(f"Похоже на секрет в {f} (шаблон {pat}).")
    errors += check_readme()
    if (ROOT / ".git").exists():
        errors += check_history()
    env = ROOT / ".env.example"
    if env.is_file() and re.search(r"AIza|sk-[A-Za-z0-9]{10,}", env.read_text(encoding="utf-8")):
        errors.append(".env.example содержит реальный ключ.")
    return errors


README_MUST_MENTION = [
    ("pip install", "установка зависимостей"),
    (".env", "куда положить ключ"),
    (".env.example", "пример конфига без ключа"),
    ("python -m reqcheck", "команда запуска"),
    ("reports/", "куда ляжет отчёт"),
    ("aistudio.google.com", "как получить ключ LLM"),
    ("модел", "какая модель использована"),
    ("lint-only", "режим без ключа"),
    ("Как устроен агент", "схема архитектуры"),
    ("Ограничения", "ограничения"),
]


def check_readme() -> list[str]:
    path = ROOT / "README.md"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8").lower()
    return [f"README: нет упоминания «{needle}» ({why})." for needle, why in README_MUST_MENTION
            if needle.lower() not in text]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def check_history() -> list[str]:
    """История git: нет секретов, .env, трейлеров ассистента; автор один."""
    errors: list[str] = []
    if _git("log", "--all", "--name-only", "--format=", "--", ".env").strip():
        errors.append("История: файл .env когда-то попадал в коммит.")
    patch = _git("log", "-p", "--all")
    for pat in SECRET_PATTERNS:
        m = re.search(pat, patch)
        if m:
            errors.append(f"История: похоже на секрет (шаблон {pat}): {m.group(0)[:12]}…")
    msgs = _git("log", "--all", "--format=%B")
    if re.search(r"(?im)^co-authored-by:|generated with|claude\.ai/code", msgs):
        errors.append("История: в сообщениях коммитов есть трейлеры или упоминания ассистента.")
    names = {n for n in _git("log", "--all", "--format=%an").splitlines() if n.strip()}
    if len(names) > 1:
        errors.append(f"История: больше одного автора коммитов: {sorted(names)}.")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", type=Path, help="проверить отчёт")
    ap.add_argument("--repo", action="store_true", help="проверить репозиторий")
    args = ap.parse_args()
    if not args.report and not args.repo:
        ap.error("укажите --report <файл> и/или --repo")
    errors: list[str] = []
    if args.report:
        errors += [f"[отчёт] {e}" for e in check_report(args.report)]
    if args.repo:
        errors += [f"[репозиторий] {e}" for e in check_repo()]
    for e in errors:
        print(f"ОШИБКА: {e}")
    print("self_check: OK" if not errors else f"self_check: найдено ошибок: {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
