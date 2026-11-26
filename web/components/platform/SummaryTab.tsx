import type { Finding, ReportView, Severity } from "../api"
import { SEVERITY, SEVERITY_ORDER, VERDICT } from "./meta"

type Props = {
  data: ReportView
  findings: Map<string, Finding>
  onSelect: (id: string) => void
  onFilter: (filter: { severity?: Severity; criterion?: string }) => void
}

export default function SummaryTab({ data, findings, onSelect, onFilter }: Props) {
  const { report, view } = data
  return (
    <div className="space-y-6">
      <section className="space-y-2 rounded-2xl bg-ink p-4 text-page">
        <p className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${VERDICT[report.verdict.code].tone}`}>
          {VERDICT[report.verdict.code].short}
        </p>
        <p className="text-sm">{report.verdict.text}</p>
        <p className="text-xs opacity-70">
          {report.passport.model_id} · {report.passport.agent_version} · {report.passport.run_datetime.slice(0, 10)}
        </p>
      </section>

      <section aria-label="Счётчики по серьёзности" className="grid grid-cols-3 gap-2">
        {SEVERITY_ORDER.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onFilter({ severity: s })}
            className="rounded-2xl border border-rule p-3 text-left hover:border-ink"
          >
            <span className={`block text-3xl font-semibold ${SEVERITY[s].text}`}>{view.by_severity[s]}</span>
            <span className="text-xs text-muted">{SEVERITY[s].label}</span>
          </button>
        ))}
      </section>
      <p className="text-xs text-muted">
        Требований: {report.requirements.length} · объединено дублей: {report.merged_count} · снято перепроверкой:{" "}
        {report.verifier_rejected} · отброшено цитат: {report.dropped_count}
      </p>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Что исправить первым</h2>
        <ol className="space-y-2">
          {view.priorities.map((id, i) => {
            const f = findings.get(id)
            if (!f) return null
            return (
              <li key={id}>
                <button
                  type="button"
                  onClick={() => onSelect(id)}
                  className="w-full rounded-xl border border-rule p-3 text-left text-sm hover:border-ink"
                >
                  <span className="font-semibold">{i + 1}. {id}</span>{" "}
                  <span className={`text-xs font-semibold ${SEVERITY[f.severity].text}`}>{SEVERITY[f.severity].one}</span>
                  <span className="mt-1 block text-muted">{f.fix}</span>
                </button>
              </li>
            )
          })}
        </ol>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">По критериям</h2>
        <ul className="divide-y divide-rule rounded-2xl border border-rule">
          {Object.entries(view.by_criterion).map(([code, n]) => (
            <li key={code}>
              <button
                type="button"
                onClick={() => onFilter({ criterion: code })}
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-accent-soft"
              >
                <span><code className="font-semibold">{code}</code> {view.criteria[code]?.title}</span>
                <span className="tabular-nums">{n}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
