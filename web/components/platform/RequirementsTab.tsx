import type { ReportView } from "../api"

type Props = { data: ReportView; onRequirement: (id: string) => void }

export default function RequirementsTab({ data, onRequirement }: Props) {
  const { report } = data
  const count = (id: string) => report.findings.filter((f) => f.requirement_ids.includes(id)).length
  return (
    <table className="w-full text-left text-sm">
      <thead className="text-xs text-muted">
        <tr>
          <th className="py-2 pr-2 font-medium">В отчёте</th>
          <th className="py-2 pr-2 font-medium">В документе</th>
          <th className="py-2 pr-2 font-medium">Формулировка</th>
          <th className="py-2 text-right font-medium">Замеч.</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-rule align-top">
        {report.requirements.map((r) => (
          <tr key={r.id}>
            <td className="py-2 pr-2">
              <button type="button" onClick={() => onRequirement(r.id)} className="font-semibold underline underline-offset-4">
                {r.id}
              </button>
            </td>
            <td className="py-2 pr-2">{r.source_id ?? <span className="text-muted">без номера</span>}</td>
            <td className="py-2 pr-2">{r.summary}</td>
            <td className="py-2 text-right tabular-nums">{count(r.id)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
