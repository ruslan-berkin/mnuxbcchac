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

export type TopQuestion = {
  finding_id: string
  question: string
  severity: Severity
  requirement_ids: string[]
  options: string[]
}

export type ReportView = {
  report: Report
  document: { name: string; title: string; sha256: string; lines: string[] }
  view: {
    highlights: Highlight[]
    priorities: string[]
    by_severity: Record<Severity, number>
    by_criterion: Record<string, number>
    top_questions: TopQuestion[]
    criteria: Record<string, { title: string; reference: string }>
  }
}

export async function fetchExample(signal?: AbortSignal): Promise<ReportView> {
  const res = await fetch("/api/example", { signal })
  if (!res.ok) throw new Error(`Сервер ответил ${res.status}`)
  return (await res.json()) as ReportView
}

export type RunStatus = Partial<ReportView> & {
  run_id: string
  name: string
  status: "queued" | "running" | "done" | "error"
  stage: string | null
  stages_done: string[]
  position?: number
  error: string | null
}

export type RecheckStatus = "resolved" | "partial" | "open"

export type RecheckResult = {
  items: { finding_id: string; status: RecheckStatus; reason: string }[]
  verdict_before: { code: VerdictCode; text: string }
  verdict_after: { code: VerdictCode; text: string }
  skipped: string[]
}

export type ChatMessage = { role: "user" | "assistant"; content: string }

// Заголовок, который чужая страница не может поставить без preflight (защита платных POST).
const SITE_HEADER = { "x-sau": "1" }

export const ACCEPTED = ".pdf,.docx,.md,.markdown,.txt"
export const MAX_UPLOAD = 5 * 1024 * 1024

async function failure(res: Response): Promise<Error> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    if (typeof body.detail === "string") return new Error(body.detail)
  } catch {
    // ответ без JSON
  }
  // Наш сервер всегда объясняет отказ в JSON. 403 без него — фильтр хостинга перед сервером.
  if (res.status === 403) {
    return new Error(
      "Запрос отклонила защита хостинга: так бывает, когда в тексте есть примеры команд (например, curl). " +
        "Загрузите этот документ в PDF или DOCX.",
    )
  }
  return new Error(`Сервер ответил ${res.status}`)
}

export async function createRun(file: File): Promise<{ run_id: string; position: number }> {
  const form = new FormData()
  form.append("file", file)
  const res = await fetch("/api/runs", { method: "POST", body: form, headers: SITE_HEADER })
  if (!res.ok) throw await failure(res)
  return res.json()
}

export async function fetchRun(id: string, signal?: AbortSignal): Promise<RunStatus> {
  const res = await fetch(`/api/runs/${encodeURIComponent(id)}`, { signal })
  if (!res.ok) throw await failure(res)
  return res.json()
}

export async function recheck(runId: string, answers: Record<string, string>): Promise<RecheckResult> {
  const res = await fetch("/api/recheck", {
    method: "POST",
    headers: { ...SITE_HEADER, "content-type": "application/json" },
    body: JSON.stringify({ run_id: runId, answers }),
  })
  if (!res.ok) throw await failure(res)
  return res.json()
}

// SSE поверх POST: читаем поток и разбираем строки «data: {...}».
export async function streamChat(
  body: { run_id: string; messages: ChatMessage[]; answers: Record<string, string> },
  onDelta: (text: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { ...SITE_HEADER, "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok || !res.body) throw await failure(res)
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  for (;;) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const events = buffer.split("\n\n")
    buffer = events.pop() ?? ""
    for (const raw of events) {
      if (!raw.startsWith("data: ")) continue
      const event = JSON.parse(raw.slice(6)) as { delta?: string; error?: string }
      if (event.error) throw new Error(event.error)
      if (event.delta) onDelta(event.delta)
    }
    if (done) return
  }
}
