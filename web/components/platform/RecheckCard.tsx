import type { RecheckResult, RecheckStatus } from "../api"
import { VERDICT } from "./meta"
import Refs from "./Refs"

const STATUS: Record<RecheckStatus, { label: string; tone: string }> = {
  resolved: { label: "закрыто", tone: "bg-accent text-white" },
  partial: { label: "частично", tone: "bg-major text-white" },
  open: { label: "осталось", tone: "bg-minor text-white" },
}

export default function RecheckCard({ result, onRef }: { result: RecheckResult; onRef: (id: string) => void }) {
  return (
    <section aria-label="Результат перепроверки" className="space-y-3 rounded-2xl bg-ink p-4 text-page">
      <p className="text-xs uppercase tracking-wide opacity-70">Вердикт: было → стало</p>
      <p className="flex flex-wrap items-center gap-2 text-sm font-semibold">
        <span className={`rounded-full px-3 py-1 ${VERDICT[result.verdict_before.code].tone}`}>{VERDICT[result.verdict_before.code].short}</span>
        <span aria-hidden>→</span>
        <span className={`rounded-full px-3 py-1 ${VERDICT[result.verdict_after.code].tone}`}>{VERDICT[result.verdict_after.code].short}</span>
      </p>
      <p className="text-sm">{result.verdict_after.text}</p>
      <ul className="space-y-2 text-sm">
        {result.items.map((i) => (
          <li key={i.finding_id} className="rounded-xl bg-page p-2 text-ink">
            <Refs text={i.finding_id} onRef={onRef} />{" "}
            <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS[i.status].tone}`}>{STATUS[i.status].label}</span>
            <span className="mt-1 block text-muted">{i.reason}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
