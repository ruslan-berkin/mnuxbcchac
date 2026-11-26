// Кольцо из восьми стеклянных карточек, само вращается на фоне сплошного SAU.AI.
// Всё на CSS: вращение останавливает общий блок prefers-reduced-motion в globals.css.
import type { CSSProperties, ReactNode } from "react"

type Card = { tone: string; content: ReactNode }

const BCC: Card = {
  tone: "card-bcc",
  content: (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/logos/bcc.png" alt="" className="h-[52%]" />
      <span className="ring-caption">Bank CenterCredit</span>
    </>
  ),
}
const MNU: Card = {
  tone: "card-mnu",
  // eslint-disable-next-line @next/next/no-img-element
  content: <img src="/logos/mnu.png" alt="" className="w-[78%]" />,
}
const SAU: Card = {
  tone: "card-sau",
  content: (
    <>
      <span className="font-display text-[length:calc(var(--card-w)*0.17)] font-bold tracking-tight">
        sau<b className="text-accent">.</b>ai
      </span>
      <span className="ring-caption">наша команда</span>
    </>
  ),
}
const ITEMS = [BCC, MNU, SAU, MNU, BCC, MNU, SAU, MNU]

export default function Ring() {
  return (
    <section aria-label="BCC, MNU и sau.ai" className="relative overflow-hidden py-4">
      <svg aria-hidden viewBox="0 0 1000 240" className="ring-wordmark">
        <text x="500" y="195" textAnchor="middle" textLength="975" lengthAdjust="spacingAndGlyphs">SAU.AI</text>
      </svg>
      <div aria-hidden className="ring-stage">
        <div className="ring-tilt">
          <div className="ring-spin">
            {ITEMS.map(({ tone, content }, i) => (
              <div key={i} className="ring-item" style={{ "--i": i } as CSSProperties}>
                <div className={`glass ${tone}`}>{content}</div>
                <div className={`glass glass-back ${tone}`}>{content}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
