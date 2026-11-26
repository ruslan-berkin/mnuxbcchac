"use client"

import { memo, useMemo } from "react"
import type { Finding, Highlight } from "../api"
import { SEVERITY, SEVERITY_ORDER } from "./meta"

type Segment = { text: string; ids: string[] }

// Режет строку по границам всех подсветок: на пересечениях у отрезка несколько замечаний.
function segments(line: string, marks: Highlight[]): Segment[] {
  if (!marks.length) return [{ text: line, ids: [] }]
  const cuts = new Set([0, line.length])
  for (const m of marks) {
    cuts.add(Math.max(0, Math.min(line.length, m.start)))
    cuts.add(Math.max(0, Math.min(line.length, m.end)))
  }
  const points = [...cuts].sort((a, b) => a - b)
  return points.slice(0, -1).map((from, i) => {
    const to = points[i + 1]
    const ids = [...new Set(marks.filter((m) => m.start <= from && m.end >= to).map((m) => m.finding_id))]
    return { text: line.slice(from, to), ids }
  })
}

type Props = {
  lines: string[]
  highlights: Highlight[]
  findings: Map<string, Finding>
  selected: string | null
  flashLines: { from: number; to: number; n: number } | null
  onPick: (id: string) => void
}

function DocumentPane({ lines, highlights, findings, selected, flashLines, onPick }: Props) {
  const byLine = useMemo(() => {
    const map = new Map<number, Highlight[]>()
    for (const h of highlights) {
      const list = map.get(h.line) ?? []
      list.push(h)
      map.set(h.line, list)
    }
    return map
  }, [highlights])

  const rank = (id: string) => SEVERITY_ORDER.indexOf(findings.get(id)?.severity ?? "minor")

  // Повторный клик по тому же месту перебирает все замечания на нём.
  const pick = (ids: string[]) => {
    const ordered = [...ids].sort((a, b) => rank(a) - rank(b))
    const at = selected ? ordered.indexOf(selected) : -1
    onPick(ordered[(at + 1) % ordered.length])
  }

  return (
    <ol className="py-3 text-[13px] leading-6">
      {lines.map((line, i) => {
        const no = i + 1
        const flash = flashLines && no >= flashLines.from && no <= flashLines.to
        return (
          <li
            key={flash ? `${no}-${flashLines.n}` : no}
            id={`line-${no}`}
            className={`grid grid-cols-[3rem_1fr] gap-2 pr-3 ${flash ? "flash" : ""}`}
          >
            <span aria-hidden className="select-none text-right tabular-nums text-muted/60">{no}</span>
            <span className={`whitespace-pre-wrap break-words ${line.startsWith("|") ? "text-[12px] text-ink/80" : ""}`}>
              {segments(line, byLine.get(no) ?? []).map((s, k) => {
                if (!s.ids.length) return <span key={k}>{s.text}</span>
                const top = [...s.ids].sort((a, b) => rank(a) - rank(b))[0]
                const severity = findings.get(top)?.severity ?? "minor"
                const active = selected !== null && s.ids.includes(selected)
                return (
                  <mark
                    key={k}
                    data-finding={s.ids.join(" ")}
                    role="button"
                    tabIndex={0}
                    aria-label={`Замечания ${s.ids.join(", ")}: ${s.text}`}
                    title={s.ids.join(", ")}
                    onClick={() => pick(s.ids)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault()
                        pick(s.ids)
                      }
                    }}
                    className={`cursor-pointer rounded-sm text-ink underline decoration-2 underline-offset-4 ${SEVERITY[severity].mark} ${
                      active ? "flash outline outline-2 outline-ink" : ""
                    }`}
                  >
                    {s.text}
                  </mark>
                )
              })}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

export default memo(DocumentPane)
