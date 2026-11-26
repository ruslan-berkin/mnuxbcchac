"use client"

// Шапка платформы: где я (документ и вердикт) слева, действия справа.
import Link from "next/link"
import { useRef } from "react"
import { ACCEPTED, type Report } from "../api"
import { VERDICT } from "./meta"

type Props = {
  report: Report | null
  title: string | null
  runId: string
  busy: boolean
  rechecked: boolean
  onUpload: (file: File) => void
  onExample: () => void
}

export default function TopBar({ report, title, runId, busy, rechecked, onUpload, onExample }: Props) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-rule bg-page px-4 py-3">
      <Link href="/" className="font-display text-base font-semibold" title="На главную">sau.ai</Link>
      {title && (
        <div className="order-last flex w-full min-w-0 items-center gap-3 md:order-none md:w-auto md:flex-1 md:border-l md:border-rule md:pl-4">
          <h1 className="truncate text-sm font-semibold" title={title}>{title}</h1>
          {report && (
            <span className={`hidden shrink-0 rounded-full px-3 py-1 text-xs font-semibold sm:inline ${VERDICT[report.verdict.code].tone}`}>
              {VERDICT[report.verdict.code].short}
              {rechecked && " · после ответов"}
            </span>
          )}
        </div>
      )}
      <div className="ml-auto flex items-center gap-2 text-sm">
        {report && (
          <span className="flex items-center gap-2">
            <a href={`/api/runs/${runId}/report.md`} className="rounded-full border border-rule px-3 py-1.5 hover:border-ink">
              {rechecked ? "Скачать исходный отчёт" : "Скачать отчёт"}
            </a>
            <a href={`/api/runs/${runId}/report.json`} className="hidden text-muted underline underline-offset-4 hover:text-ink lg:inline">
              JSON
            </a>
          </span>
        )}
        <button type="button" onClick={onExample} className="hidden rounded-full px-3 py-1.5 text-muted hover:text-ink lg:inline">
          Пример
        </button>
        <input ref={input} type="file" accept={ACCEPTED} className="sr-only" tabIndex={-1} aria-hidden
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) onUpload(file)
            e.target.value = ""
          }} />
        <button type="button" disabled={busy} onClick={() => input.current?.click()}
          className="rounded-full bg-accent px-4 py-1.5 font-medium text-white hover:bg-accent-deep disabled:opacity-40">
          Новый документ
        </button>
      </div>
    </header>
  )
}
