// Живой фон лендинга: сетка с точками, мягкие пятна и всплывающие коды критериев проверки.
import type { CSSProperties } from "react"
import DotGrid from "./DotGrid"

const CODES = [
  ["VER", "проверяемость"], ["S-CON", "непротиворечивость"], ["UNA", "однозначность"], ["CMP", "полнота"],
  ["S-TRC", "трассируемость"], ["FEA", "выполнимость"], ["SNG", "единичность"], ["S-VAL", "валидируемость"],
]
const LEFT = [3, 88, 9, 82, 2, 91, 12, 79]

export default function Backdrop() {
  return (
    <div aria-hidden className="backdrop">
      <DotGrid />
      <div className="blob blob-a" />
      <div className="blob blob-b" />
      <div className="blob blob-c" />
      {CODES.map(([code, name], i) => (
        <span key={code} className="drift" style={{ left: `${LEFT[i]}%`, "--d": `${i * -4.5}s`, "--t": `${34 + (i % 3) * 7}s` } as CSSProperties}>
          <b>{code}</b> {name}
        </span>
      ))}
    </div>
  )
}
