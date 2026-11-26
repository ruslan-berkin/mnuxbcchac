"use client"

import Link from "next/link"
import { useRef } from "react"
import { ACCEPTED, type Report } from "../api"
import { VERDICT } from "./meta"

// Этапы прогона (названия сервера) → шаги в интерфейсе.
const STEPS: { label: string; stages: string[] }[] = [
  { label: "Нарезка", stages: ["ingest", "segment"] },
  { label: "Проверка требований", stages: ["check_each"] },
  { label: "Проверка набора", stages: ["check_set"] },
  { label: "Сверка цитат", stages: ["ground"] },
  { label: "Верификация", stages: ["verify"] },
  { label: "Отчёт", stages: ["render"] },
]

export type Progress = { stage: string | null; done: string[] }

type Props = {
  report: Report | null
  runId: string
  progress: Progress | null
  busy: boolean
  onUpload: (file: File) => void
  onExample: () => void
}

export default function TopBar({ report, runId, progress, busy, onUpload, onExample }: Props) {
  const input = useRef<HTMLInputElement>(null)
  const state = (stages: string[]) => {
    if (!progress) return report ? "done" : "todo"
    if (progress.stage && stages.includes(progress.stage)) return "now"
    return stages.some((s) => progress.done.includes(s)) ? "done" : "todo"
  }
  return (
    <header className="space-y-2 border-b border-rule px-4 py-3">
      <div className="flex flex-wrap items-center gap-3">
        <Link href="/" className="font-display text-base font-semibold">sau.ai</Link>
        <input ref={input} type="file" accept={ACCEPTED} className="sr-only" tabIndex={-1} aria-hidden
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) onUpload(file)
            e.target.value = ""
          }} />
        <button type="button" disabled={busy} onClick={() => input.current?.click()}
          className="rounded-full bg-accent px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40">
          Загрузить документ
        </button>
        <button type="button" onClick={onExample} className="rounded-full border border-rule px-4 py-1.5 text-sm hover:border-ink">
          Пример: документ организаторов
        </button>
        {report && (
          <span className="ml-auto flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${VERDICT[report.verdict.code].tone}`}>
              {VERDICT[report.verdict.code].short}
            </span>
            <a href={`/api/runs/${runId}/report.md`} className="text-sm underline underline-offset-4">Скачать .md</a>
            <a href={`/api/runs/${runId}/report.json`} className="text-sm underline underline-offset-4">.json</a>
          </span>
        )}
      </div>
      <ol aria-label="Этапы прогона" className="flex gap-x-4 gap-y-1 overflow-x-auto whitespace-nowrap text-xs text-muted">
        {STEPS.map((step) => {
          const s = state(step.stages)
          return (
            <li key={step.label} aria-current={s === "now" ? "step" : undefined}
              className={`flex items-center gap-1 ${s === "now" ? "font-semibold text-ink" : ""}`}>
              <span aria-hidden className={`inline-block size-2 rounded-full ${
                s === "done" ? "bg-accent" : s === "now" ? "animate-pulse bg-ink" : "bg-rule"}`} />
              {step.label}
            </li>
          )
        })}
      </ol>
    </header>
  )
}
