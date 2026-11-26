// Кольцо из восьми стеклянных карточек, само вращается на фоне сплошного SAU.AI.
// Всё на CSS: вращение останавливает общий блок prefers-reduced-motion в globals.css.
import type { CSSProperties, ReactNode } from "react"

// Официальных файлов логотипов в репозитории нет, поэтому названия набраны шрифтом.
const CARDS: [string, ReactNode][] = [
  ["bcc", (
    <>
      <span className="rounded-[0.18em] bg-accent-deep px-[0.28em] py-[0.08em] text-[length:calc(var(--card-w)*0.27)] font-extrabold tracking-tighter text-white">BCC</span>
      <span className="ring-caption">Bank CenterCredit</span>
    </>
  )],
  ["mnu", (
    <>
      <span className="text-[length:calc(var(--card-w)*0.31)] font-extrabold tracking-tighter text-accent">MNU</span>
      <span className="ring-caption">Maqsut Narikbayev University</span>
    </>
  )],
  ["sau", (
    <>
      <span className="text-[length:calc(var(--card-w)*0.25)] font-extrabold tracking-tighter">sau<b className="text-accent">.</b>ai</span>
      <span className="ring-caption">наша команда</span>
    </>
  )],
  ["platform", (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/platform.jpg" alt="" className="aspect-[4/5] w-[84%] rounded-lg border border-rule object-cover object-left-top" />
      <span className="ring-caption">платформа</span>
    </>
  )],
]
const ITEMS = [...CARDS, ...CARDS]

export default function Ring() {
  return (
    <section aria-label="BCC, MNU и sau.ai" className="relative overflow-hidden py-6">
      <p aria-hidden className="ring-wordmark">SAU.AI</p>
      <div aria-hidden className="ring-stage">
        <div className="ring-tilt">
          <div className="ring">
            {ITEMS.map(([key, content], i) => (
              <div key={`${key}-${i}`} className="ring-item" style={{ "--i": i } as CSSProperties}>
                <div className="glass">{content}</div>
                <div className="glass glass-back">{content}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
