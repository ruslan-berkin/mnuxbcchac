// Типы ответа API (подмножество reports/report.json) и запрос примера.
export type Severity = "critical" | "major" | "minor"

export type Finding = {
  id: string
  scope: "requirement" | "set"
  requirement_ids: string[]
  criterion: string
  severity: Severity
  quotes: string[]
  anchors: { section: string; page: number | null; line_start: number; line_end: number }[]
  problem: string
  fix: string
  question: string | null
  source: "llm" | "lint"
}

export type Requirement = {
  id: string
  source_id: string | null
  kind: string
  quote: string
  summary: string
  anchor: Finding["anchors"][number]
}

export type Report = {
  passport: Record<string, string>
  requirements: Requirement[]
  findings: Finding[]
  verdict: { code: "blocked" | "caveats" | "incomplete" | "ok"; text: string }
  verifier_rejected: number
  dropped_count: number
  merged_count: number
}

export type Example = {
  report: Report
  document: { name: string; title: string; sha256: string; lines: string[] }
}

export async function fetchExample(signal?: AbortSignal): Promise<Example> {
  const res = await fetch("/api/example", { signal })
  if (!res.ok) throw new Error(`Сервер ответил ${res.status}`)
  return (await res.json()) as Example
}
