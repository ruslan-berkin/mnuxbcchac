import type { Finding, RecheckStatus } from "../api"
import { RECHECK, SEVERITY, place } from "./meta"

type Props = {
  finding: Finding
  title: string
  reference: string
  selected: boolean
  onSelect: (id: string) => void
  onRequirement: (id: string) => void
  checked?: RecheckStatus
}

export default function FindingCard({ finding: f, title, reference, selected, onSelect, onRequirement, checked }: Props) {
  return (
    <article
      id={`card-${f.id}`}
      className={`space-y-2 rounded-2xl border p-4 ${selected ? "border-ink bg-accent-soft/40" : "border-rule"} ${checked === "resolved" ? "opacity-60" : ""}`}
    >
      <header className="flex flex-wrap items-center gap-2 text-sm">
        <button type="button" onClick={() => onSelect(f.id)} className="font-semibold underline-offset-4 hover:underline">
          {f.id}
        </button>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY[f.severity].badge}`}>
          {SEVERITY[f.severity].one}
        </span>
        {checked && <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${RECHECK[checked].tone}`}>{RECHECK[checked].label}</span>}
        <span title={reference} className="text-muted">
          <code className="font-semibold text-ink">{f.criterion}</code> {title}
        </span>
      </header>

      {f.quotes.map((q, i) => (
        <button
          key={i}
          type="button"
          onClick={() => onSelect(f.id)}
          className="block w-full rounded-xl bg-accent-soft px-3 py-2 text-left text-sm hover:brightness-95"
        >
          «{q}»<span className="mt-1 block text-xs text-muted">{place(f.anchors[i] ?? f.anchors[0])}</span>
        </button>
      ))}

      <p className="text-sm"><span className="font-semibold">Проблема. </span>{f.problem}</p>
      <p className="text-sm"><span className="font-semibold">Как исправить. </span>{f.fix}</p>
      {f.question && (
        <p className="border-l-4 border-accent pl-3 text-sm">
          <span className="font-semibold">Вопрос аналитику. </span>{f.question}
        </p>
      )}
      {f.requirement_ids.length > 0 && (
        <p className="flex flex-wrap gap-1 text-xs">
          {f.requirement_ids.map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => onRequirement(id)}
              className="rounded-full border border-rule px-2 py-0.5 hover:border-ink"
            >
              {id}
            </button>
          ))}
        </p>
      )}
    </article>
  )
}
