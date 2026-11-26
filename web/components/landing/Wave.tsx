"use client"

// Плывущая по синусоиде строка слов: SVG textPath, смещение анимирует GSAP из Landing.
const WORDS = [
  "BCC × MNU", "FinTech Hackathon", "ISO/IEC/IEEE 29148", "IEEE 830", "противоречия", "проверяемость", "полнота",
  "однозначность", "уточняющие вопросы", "трассируемость", "сверка цитат", "sau.ai",
]
const LINE = WORDS.join("  ·  ") + "  ·  "
const PATH = "M -200 60 C 0 0, 200 0, 400 60 S 800 120, 1000 60 S 1400 0, 1600 60 S 2000 120, 2200 60"

export default function Wave({ id, reverse = false, tone }: { id: string; reverse?: boolean; tone: "ink" | "accent" }) {
  return (
    <div aria-hidden className="relative w-full overflow-hidden py-2">
      <svg viewBox="0 0 1440 120" preserveAspectRatio="xMidYMid slice" className="h-20 w-full md:h-28">
        <path id={id} d={PATH} fill="none" stroke={tone === "ink" ? "var(--ink)" : "var(--accent)"} strokeWidth="46" strokeLinecap="round" />
        <text dy="8" className="fill-white text-[22px] font-semibold tracking-wide">
          <textPath href={`#${id}`} startOffset="0" data-wave={reverse ? "reverse" : "forward"}>
            {LINE.repeat(3)}
          </textPath>
        </text>
      </svg>
    </div>
  )
}
