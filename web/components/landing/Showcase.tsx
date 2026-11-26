// Синяя зона эскиза: ноутбук на фоне гигантского SAU.AI. CSS-анимация 3D появится в фазе F.
import type { ReportView } from "../api"
import Preview from "./Preview"

export default function Showcase({ data }: { data: ReportView | null }) {
  return (
    <section aria-label="Платформа на ноутбуке" data-showcase className="relative overflow-hidden px-5 py-20 md:py-28">
      <p aria-hidden data-wordmark
        className="pointer-events-none absolute inset-x-0 top-6 select-none text-center text-[22vw] font-bold leading-none tracking-tighter text-transparent [-webkit-text-stroke:2px_var(--rule)] md:top-2">
        SAU.AI
      </p>
      <div data-laptop className="relative mx-auto w-full max-w-4xl">
        <div className="rounded-t-3xl border-[10px] border-ink bg-ink">
          <div className="max-h-[60vh] overflow-hidden rounded-xl bg-page p-2">
            <Preview data={data} run={null} />
          </div>
        </div>
        <div aria-hidden className="mx-[-3%] h-4 rounded-b-2xl bg-gradient-to-b from-[#c9cfcc] to-[#9aa39f]" />
      </div>
    </section>
  )
}
