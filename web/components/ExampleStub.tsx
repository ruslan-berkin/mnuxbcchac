"use client"

import { useEffect, useState } from "react"
import { fetchExample, type Example, type Severity } from "./api"

const SEVERITY: { key: Severity; label: string; color: string }[] = [
  { key: "critical", label: "Критичные", color: "text-critical" },
  { key: "major", label: "Существенные", color: "text-major" },
  { key: "minor", label: "Незначительные", color: "text-minor" },
]

// Заглушка платформы (фаза A): подтверждает, что пример приходит из API. Платформа целиком — фаза B.
export default function ExampleStub() {
  const [data, setData] = useState<Example | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const ctrl = new AbortController()
    fetchExample(ctrl.signal)
      .then(setData)
      .catch((e: Error) => {
        if (e.name !== "AbortError") setError(e.message)
      })
    return () => ctrl.abort()
  }, [])

  if (error) return <p role="alert" className="text-critical">Не удалось загрузить пример: {error}</p>
  if (!data) return <p className="text-muted">Загружаю пример…</p>

  const { report, document } = data
  return (
    <section className="space-y-4">
      <p className="text-muted">
        {document.title} · строк: {document.lines.length} · требований: {report.requirements.length} · замечаний:{" "}
        {report.findings.length}
      </p>
      <p className="rounded-xl bg-accent-soft p-4 font-medium">{report.verdict.text}</p>
      <ul className="flex flex-wrap gap-3">
        {SEVERITY.map((s) => (
          <li key={s.key} className="rounded-xl border border-rule px-4 py-3">
            <span className={`text-3xl font-semibold ${s.color}`}>
              {report.findings.filter((f) => f.severity === s.key).length}
            </span>
            <span className="ml-2 text-muted">{s.label}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
