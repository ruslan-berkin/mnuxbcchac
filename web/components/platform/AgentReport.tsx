// Отчёт аналитики первым сообщением чата. Всё считает код из результата прогона: модель здесь не вызывается.
import type { ReportView } from "../api"
import { SEVERITY, SEVERITY_ORDER, VERDICT } from "./meta"
import Refs from "./Refs"

type Props = { data: ReportView; runId: string; onRef: (id: string) => void }

export default function AgentReport({ data, runId, onRef }: Props) {
  const { report, view, document } = data
  const top = view.priorities.slice(0, 3).map((id) => report.findings.find((f) => f.id === id)).filter((f) => f !== undefined)
  return (
    <section aria-label="Отчёт аналитики" className="space-y-3 rounded-2xl border border-rule p-3">
      <h3 className="text-base font-semibold">Отчёт аналитики</h3>
      <p className="text-muted">{document.title}</p>
      <p className={`inline-block rounded-xl px-3 py-1.5 font-semibold ${VERDICT[report.verdict.code].tone}`}>
        {report.verdict.text}
      </p>
      <p>
        Требований: <b>{report.requirements.length}</b>. Замечаний: <b>{report.findings.length}</b>
      </p>
      <ul className="flex flex-wrap gap-x-4 gap-y-1">
        {SEVERITY_ORDER.map((s) => (
          <li key={s}>
            <b className={SEVERITY[s].text}>{view.by_severity[s]}</b> {SEVERITY[s].label.toLowerCase()}
          </li>
        ))}
      </ul>
      {top.length > 0 && (
        <div>
          <p className="font-semibold">Что исправить первым</p>
          <ol className="mt-1 list-decimal space-y-2 pl-5">
            {top.map((f) => (
              <li key={f.id}>
                <Refs text={f.id} onRef={onRef} /> {view.criteria[f.criterion]?.title}: {f.problem}
              </li>
            ))}
          </ol>
        </div>
      )}
      <p>
        <a href={`/api/runs/${runId}/report.md`} className="font-medium text-accent underline underline-offset-4">
          Скачать полный отчёт
        </a>
      </p>
    </section>
  )
}
