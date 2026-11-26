// Типы ответа API и запрос данных. Всё производное (подсветка, сводка, приоритеты) считает сервер.
export type Severity = "critical" | "major" | "minor"

export type Anchor = { section: string; page: number | null; line_start: number; line_end: number }

export type Finding = {
  id: string
  scope: "requirement" | "set"
  requirement_ids: string[]
  criterion: string
  severity: Severity
  quotes: string[]
  anchors: Anchor[]
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
  anchor: Anchor
}

export type VerdictCode = "blocked" | "caveats" | "incomplete" | "ok"

export type Report = {
  passport: {
    document_title: string
    run_datetime: string
    model_provider: string
    model_id: string
    agent_version: string
    llm_mode: string
  }
  requirements: Requirement[]
  findings: Finding[]
  verdict: { code: VerdictCode; text: string }
  verifier_rejected: number
  dropped_count: number
  merged_count: number
  incomplete_reasons: string[]
}

export type Highlight = { finding_id: string; line: number; start: number; end: number }

export type ReportView = {
  report: Report
  document: { name: string; title: string; sha256: string; lines: string[] }
  view: {
    highlights: Highlight[]
    priorities: string[]
    by_severity: Record<Severity, number>
    by_criterion: Record<string, number>
    criteria: Record<string, { title: string; reference: string }>
  }
}

export async function fetchExample(signal?: AbortSignal): Promise<ReportView> {
  const res = await fetch("/api/example", { signal })
  if (!res.ok) throw new Error(`Сервер ответил ${res.status}`)
  return (await res.json()) as ReportView
}
