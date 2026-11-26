"use client"

// Плывущая по синусоиде строка слов: SVG textPath, смещение анимирует GSAP из Landing.
const LINE = "MNU × BCC  ·  ".repeat(12)
const PATH = "M -200 60 C 0 0, 200 0, 400 60 S 800 120, 1000 60 S 1400 0, 1600 60 S 2000 120, 2200 60"

export default function Wave({ id, reverse = false, tone }: { id: string; reverse?: boolean; tone: "ink" | "accent" }) {
  return (
    <div aria-hidden className="relative w-full overflow-hidden py-2">
      {/* высота по пропорции viewBox с запасом под толщину ленты: изгибы не срезаются */}
      <svg viewBox="0 -16 1440 152" className="relative left-1/2 block h-auto w-[max(100%,1000px)] -translate-x-1/2">
        <path id={id} d={PATH} fill="none" stroke={tone === "ink" ? "var(--ink)" : "var(--accent)"} strokeWidth="46" strokeLinecap="round" />
        <text dy="8" className="font-display fill-white text-[17px] font-semibold">
          <textPath href={`#${id}`} startOffset="0" data-wave={reverse ? "reverse" : "forward"}>
            {LINE.repeat(3)}
          </textPath>
        </text>
      </svg>
    </div>
  )
}
