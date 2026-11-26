import Link from "next/link"
import type { Report } from "../api"
import { VERDICT } from "./meta"

const STAGES = ["Нарезка", "Проверка требований", "Проверка набора", "Сверка цитат", "Верификация", "Отчёт"]

type Props = { report: Report | null; onExample: () => void }

export default function TopBar({ report, onExample }: Props) {
  return (
    <header className="space-y-2 border-b border-rule px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <Link href="/" className="text-lg font-semibold">sau.ai</Link>
        {/* Загрузка своего файла появится вместе с API прогонов (фаза D). */}
        <button type="button" disabled title="Живые прогоны подключаются на следующем этапе"
          className="rounded-full bg-accent px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40">
          Загрузить документ
        </button>
        <button type="button" onClick={onExample} className="rounded-full border border-rule px-4 py-1.5 text-sm hover:border-ink">
          Пример: документ организаторов
        </button>
        <span className="ml-auto flex flex-wrap items-center gap-2">
          {report && (
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${VERDICT[report.verdict.code].tone}`}>
              {VERDICT[report.verdict.code].short}
            </span>
          )}
          {report && (
            <>
              <a href="/api/runs/example/report.md" className="text-sm underline underline-offset-4">Скачать .md</a>
              <a href="/api/runs/example/report.json" className="text-sm underline underline-offset-4">.json</a>
            </>
          )}
        </span>
      </div>
      <ol aria-label="Этапы прогона" className="flex gap-x-4 gap-y-1 overflow-x-auto whitespace-nowrap text-xs text-muted">
        {STAGES.map((s) => (
          <li key={s} className="flex items-center gap-1">
            <span aria-hidden className={`inline-block size-2 rounded-full ${report ? "bg-accent" : "bg-rule"}`} />
            {s}
          </li>
        ))}
      </ol>
    </header>
  )
}
