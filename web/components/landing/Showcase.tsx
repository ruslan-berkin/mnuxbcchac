// Синяя зона эскиза: ноутбук на CSS 3D на фоне гигантского SAU.AI.
// Без скрипта и при reduced motion ноутбук открыт и стоит фронтально; анимацию задаёт Landing (GSAP).
import type { ReportView } from "../api"
import Preview from "./Preview"

export default function Showcase({ data }: { data: ReportView | null }) {
  return (
    <section aria-label="Платформа на ноутбуке" data-showcase
      className="relative flex min-h-[calc(100dvh-3.5rem)] items-center justify-center overflow-hidden px-4 py-16">
      <p aria-hidden data-wordmark
        className="pointer-events-none absolute inset-x-0 top-[8%] select-none text-center text-[22vw] font-bold leading-none tracking-tighter text-transparent [-webkit-text-stroke:2px_var(--rule)]">
        SAU.AI
      </p>
      <div className="stage w-[min(760px,92vw)]">
        <div data-laptop className="laptop">
          <div data-lid className="lid">
            <div className="lid-front">
              <div className="screen">
                <div className="screen-inner">
                  <Preview data={data} run={null} />
                </div>
              </div>
            </div>
            <div aria-hidden className="lid-back">
              <span>sau<b>.</b>ai</span>
            </div>
          </div>
          <div aria-hidden className="base">
            <div className="keys" />
            <div className="trackpad" />
          </div>
          <div aria-hidden className="lip" />
        </div>
      </div>
    </section>
  )
}
