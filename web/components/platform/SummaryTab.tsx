// Отчёт аналитики: сверху ответ на главный вопрос «можно ли начинать», дальше — что делать.
import type { ReactNode } from "react"
import type { Finding, ReportView, Severity } from "../api"
import { SEVERITY, SEVERITY_ORDER, VERDICT } from "./meta"

type Props = {
  data: ReportView
  findings: Map<string, Finding>
  onSelect: (id: string) => void
  onFilter: (filter: { severity?: Severity; criterion?: string }) => void
  ask: ReactNode
}

const MEANING: Record<Severity, string> = {
  critical: "без исправления нельзя писать код и тесты",
  major: "несколько трактовок или нет границы",
  minor: "стиль и оформление",
}
const EDGE: Record<string, string> = {
  blocked: "border-critical",
  caveats: "border-major",
  incomplete: "border-minor",
  ok: "border-accent",
}

// цвета проверены на различимость (порядок фиксирован), «остальные» — нейтральный серый
const SLICES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
const REST = "#b7beba"

type Slice = { code: string | null; title: string; n: number; color: string }

function sector(from: number, to: number): string {
  const point = (share: number) => {
    const a = share * 2 * Math.PI - Math.PI / 2
    return `${(100 + 96 * Math.cos(a)).toFixed(2)} ${(100 + 96 * Math.sin(a)).toFixed(2)}`
  }
  return `M100 100L${point(from)}A96 96 0 ${to - from > 0.5 ? 1 : 0} 1 ${point(to)}Z`
}

function CriteriaPie({ data, onFilter }: { data: ReportView; onFilter: (f: { criterion?: string }) => void }) {
  const { view } = data
  const all = Object.entries(view.by_criterion).sort((a, b) => b[1] - a[1])
  const total = all.reduce((sum, [, n]) => sum + n, 0)
  if (!total) return null
  const top: Slice[] = all.slice(0, 5).map(([code, n], i) => ({ code, title: view.criteria[code]?.title ?? code, n, color: SLICES[i] }))
  const rest = all.slice(5)
  const slices = rest.length
    ? [...top, { code: null, title: "Остальные", n: rest.reduce((sum, [, n]) => sum + n, 0), color: REST }]
    : top
  let start = 0
  return (
    <section className="space-y-3 rounded-2xl border border-rule bg-page p-5">
      <h2 className="text-lg font-semibold">Какие критерии нарушены</h2>
      <div className="grid items-center gap-5 sm:grid-cols-[13rem_1fr]">
        <svg viewBox="0 0 200 200" role="img" aria-label="Доли замечаний по критериям" className="mx-auto w-52">
          {slices.map((s) => {
            const from = start
            start += s.n / total
            const label = `${s.title}: ${s.n} из ${total}`
            const props = {
              fill: s.color,
              stroke: "#fff",
              strokeWidth: 2,
              className: s.code ? "cursor-pointer transition-opacity hover:opacity-75" : "",
              onClick: () => s.code && onFilter({ criterion: s.code }),
            }
            return slices.length === 1 ? (
              <circle key={s.title} cx="100" cy="100" r="96" {...props}><title>{label}</title></circle>
            ) : (
              <path key={s.title} d={sector(from, start)} {...props}><title>{label}</title></path>
            )
          })}
        </svg>
        <ul className="text-sm">
          {slices.map((s) => (
            <li key={s.title}>
              <button type="button" disabled={!s.code} onClick={() => s.code && onFilter({ criterion: s.code })}
                className="grid w-full grid-cols-[0.75rem_minmax(0,1fr)_auto_3rem] items-center gap-2 rounded-lg px-2 py-1.5 text-left enabled:hover:bg-accent-soft">
                <span aria-hidden className="size-3 rounded-sm" style={{ background: s.color }} />
                <span className="truncate">{s.title} {s.code && <code className="text-xs text-muted">{s.code}</code>}</span>
                <span className="font-semibold tabular-nums">{s.n}</span>
                <span className="text-right text-muted tabular-nums">{Math.round((s.n / total) * 100)}%</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
      {rest.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer text-muted hover:text-ink">Что входит в «остальные»</summary>
          <p className="mt-2 flex flex-wrap gap-2">
            {rest.map(([code, n]) => (
              <button key={code} type="button" onClick={() => onFilter({ criterion: code })}
                className="rounded-full border border-rule px-3 py-1 hover:border-ink">
                {view.criteria[code]?.title} <code className="text-xs text-muted">{code}</code> <b>{n}</b>
              </button>
            ))}
          </p>
        </details>
      )}
    </section>
  )
}

export default function SummaryTab({ data, findings, onSelect, onFilter, ask }: Props) {
  const { report, view } = data
  return (
    <div className="mx-auto max-w-3xl space-y-8 p-4 md:p-6">
      <section aria-label="Вердикт" className={`space-y-3 rounded-2xl border border-rule border-l-8 bg-page p-5 ${EDGE[report.verdict.code]}`}>
        <p className="text-sm text-muted">Отчёт аналитики</p>
        <h2 className="text-2xl font-semibold leading-tight">{VERDICT[report.verdict.code].short}</h2>
        <p className="text-sm">{report.verdict.text}</p>
        {report.incomplete_reasons.length > 0 && (
          <ul className="list-disc pl-5 text-sm text-muted">
            {report.incomplete_reasons.map((r) => <li key={r}>{r}</li>)}
          </ul>
        )}
        <div className="flex flex-wrap gap-2 pt-1 text-sm">
          <button type="button" onClick={() => onFilter({})} className="rounded-full bg-ink px-4 py-2 font-medium text-page">
            Смотреть замечания ({report.findings.length})
          </button>
        </div>
        <p className="text-xs text-muted">
          Проверено требований: {report.requirements.length} · {report.passport.model_id} · {report.passport.run_datetime.slice(0, 10)}
        </p>
      </section>

      {ask}

      <section aria-label="Замечания по серьёзности" className="grid gap-3 sm:grid-cols-3">
        {SEVERITY_ORDER.map((s) => (
          <button key={s} type="button" onClick={() => onFilter({ severity: s })}
            className="rounded-2xl border border-rule bg-page p-4 text-left hover:border-ink">
            <span className={`block text-4xl font-semibold tabular-nums ${SEVERITY[s].text}`}>{view.by_severity[s]}</span>
            <span className="block font-semibold">{SEVERITY[s].label}</span>
            <span className="text-xs text-muted">{MEANING[s]}</span>
          </button>
        ))}
      </section>

      <CriteriaPie data={data} onFilter={onFilter} />

      {view.priorities.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Что исправить первым</h2>
          <ol className="space-y-3">
            {view.priorities.map((id, i) => {
              const f = findings.get(id)
              if (!f) return null
              return (
                <li key={id}>
                  <button type="button" onClick={() => onSelect(id)}
                    className="grid w-full grid-cols-[2rem_1fr] gap-3 rounded-2xl border border-rule bg-page p-4 text-left hover:border-ink">
                    <span aria-hidden className="grid size-8 place-items-center rounded-full bg-accent-soft text-sm font-semibold text-accent-deep">
                      {i + 1}
                    </span>
                    <span className="space-y-2 text-sm">
                      <span className="block font-medium">{f.problem}</span>
                      <span className="block rounded-xl bg-accent-soft px-3 py-2"><b>Как исправить: </b>{f.fix}</span>
                      <span className="flex flex-wrap items-center gap-2 text-xs text-muted">
                        <span className={`rounded-full px-2 py-0.5 font-medium ${SEVERITY[f.severity].badge}`}>{SEVERITY[f.severity].one}</span>
                        <span>{view.criteria[f.criterion]?.title} · {id}</span>
                        <span className="ml-auto font-semibold text-accent">Показать в документе</span>
                      </span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ol>
        </section>
      )}

      <p className="text-xs text-muted">
        Объединено дублей: {report.merged_count} · снято перепроверкой: {report.verifier_rejected} · отброшено цитат:{" "}
        {report.dropped_count}
      </p>
    </div>
  )
}
