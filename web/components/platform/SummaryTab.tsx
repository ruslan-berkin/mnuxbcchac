// Отчёт аналитики: сверху ответ на главный вопрос «можно ли начинать», дальше — что делать.
import type { Finding, ReportView, Severity } from "../api"
import { SEVERITY, SEVERITY_ORDER, VERDICT } from "./meta"

type Props = {
  data: ReportView
  findings: Map<string, Finding>
  onSelect: (id: string) => void
  onFilter: (filter: { severity?: Severity; criterion?: string }) => void
  onQuestions: () => void
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

export default function SummaryTab({ data, findings, onSelect, onFilter, onQuestions }: Props) {
  const { report, view } = data
  const most = Math.max(1, ...Object.values(view.by_criterion))
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
          <button type="button" onClick={onQuestions} className="rounded-full border border-ink px-4 py-2 font-medium hover:bg-accent-soft">
            Ответить на вопросы агента
          </button>
        </div>
        <p className="text-xs text-muted">
          Проверено требований: {report.requirements.length} · {report.passport.model_id} · {report.passport.run_datetime.slice(0, 10)}
        </p>
      </section>

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

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Какие критерии нарушены</h2>
        <ul className="rounded-2xl border border-rule bg-page p-2">
          {Object.entries(view.by_criterion).map(([code, n]) => (
            <li key={code}>
              <button type="button" onClick={() => onFilter({ criterion: code })}
                className="grid w-full grid-cols-[minmax(0,1fr)_minmax(0,1fr)_2.5rem] items-center gap-3 rounded-xl px-3 py-2 text-left text-sm hover:bg-accent-soft">
                <span className="truncate">{view.criteria[code]?.title} <code className="text-xs text-muted">{code}</code></span>
                <span aria-hidden className="h-2 rounded-full bg-rule">
                  <span className="block h-full rounded-full bg-accent" style={{ width: `${(n / most) * 100}%` }} />
                </span>
                <span className="text-right font-semibold tabular-nums">{n}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="text-xs text-muted">
          Объединено дублей: {report.merged_count} · снято перепроверкой: {report.verifier_rejected} · отброшено цитат:{" "}
          {report.dropped_count}
        </p>
      </section>
    </div>
  )
}
