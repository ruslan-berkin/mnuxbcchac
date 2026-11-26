// Карточка-превью платформы: настоящие данные отчёта или живой прогресс прогона.
import type { ReportView, RunStatus } from "../api"
import { SEVERITY, SEVERITY_ORDER, VERDICT } from "../platform/meta"

const STEPS: [string, string[]][] = [
  ["Нарезка требований", ["ingest", "segment"]],
  ["Проверка требований", ["check_each"]],
  ["Проверка набора", ["check_set"]],
  ["Сверка цитат", ["ground"]],
  ["Верификация", ["verify"]],
  ["Отчёт", ["render"]],
]

type Props = { data: ReportView | null; run: RunStatus | null; compact?: boolean }

export default function Preview({ data, run, compact = false }: Props) {
  if (run && run.status !== "done") {
    return (
      <div role="status" className="space-y-3 rounded-3xl bg-page p-5 text-ink">
        <p className="font-semibold">
          {run.status === "queued" ? `Вы в очереди: ${run.position ?? 1}` : `Проверяю «${run.name}»…`}
        </p>
        <ol className="space-y-1 text-sm">
          {STEPS.map(([label, stages]) => {
            const now = run.stage !== null && stages.includes(run.stage)
            const done = stages.some((s) => run.stages_done.includes(s))
            return (
              <li key={label} className={`flex items-center gap-2 ${now ? "font-semibold" : done ? "" : "text-muted"}`}>
                <span aria-hidden className={`size-2.5 rounded-full ${now ? "animate-pulse bg-ink" : done ? "bg-accent" : "bg-rule"}`} />
                {label}
              </li>
            )
          })}
        </ol>
      </div>
    )
  }
  if (!data) return <div className="rounded-3xl bg-page p-5 text-muted">Загружаю пример…</div>
  const { report, view, document } = data
  const top = view.priorities.slice(0, compact ? 2 : 3).map((id) => report.findings.find((f) => f.id === id)).filter(Boolean)
  return (
    <div className="space-y-3 rounded-3xl bg-page p-4 text-ink md:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold">{document.title}</p>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${VERDICT[report.verdict.code].tone}`}>
          {VERDICT[report.verdict.code].short}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {SEVERITY_ORDER.map((s) => (
          <div key={s} className="rounded-xl border border-rule p-2">
            <span className={`block text-2xl font-semibold ${SEVERITY[s].text}`}>{view.by_severity[s]}</span>
            <span className="text-[11px] text-muted">{SEVERITY[s].label}</span>
          </div>
        ))}
      </div>
      <ul className="space-y-2">
        {top.map((f) => f && (
          <li key={f.id} className="rounded-xl border border-rule p-2 text-xs">
            <span className="font-semibold">{f.id}</span> <code>{f.criterion}</code>{" "}
            <span className={`font-semibold ${SEVERITY[f.severity].text}`}>{SEVERITY[f.severity].one}</span>
            <span className="mt-1 block rounded-md bg-accent-soft px-2 py-1">«{f.quotes[0].slice(0, 110)}{f.quotes[0].length > 110 ? "…" : ""}»</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
