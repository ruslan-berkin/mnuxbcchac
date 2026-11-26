import type { Anchor, Severity, VerdictCode } from "../api"

export const SEVERITY_ORDER: Severity[] = ["critical", "major", "minor"]

export const SEVERITY: Record<Severity, { label: string; one: string; text: string; badge: string; mark: string }> = {
  critical: {
    label: "Критичные",
    one: "критичное",
    text: "text-critical",
    badge: "bg-critical text-white",
    mark: "bg-critical/15 decoration-critical",
  },
  major: {
    label: "Существенные",
    one: "существенное",
    text: "text-major",
    badge: "bg-major text-white",
    mark: "bg-major/15 decoration-major",
  },
  minor: {
    label: "Незначительные",
    one: "незначительное",
    text: "text-minor",
    badge: "bg-minor text-white",
    mark: "bg-minor/15 decoration-minor",
  },
}

export const VERDICT: Record<VerdictCode, { short: string; tone: string }> = {
  blocked: { short: "Нельзя начинать без исправлений", tone: "bg-critical text-white" },
  caveats: { short: "Можно начинать с оговорками", tone: "bg-major text-white" },
  incomplete: { short: "Проверка неполная", tone: "bg-minor text-white" },
  ok: { short: "Можно начинать разработку", tone: "bg-accent text-white" },
}

export function place(a: Anchor): string {
  const parts: string[] = []
  if (a.page !== null) parts.push(`стр. ${a.page}`)
  if (a.section) parts.push(`«${a.section}»`)
  parts.push(a.line_start === a.line_end ? `строка ${a.line_start}` : `строки ${a.line_start}–${a.line_end}`)
  return parts.join(", ")
}

export function scrollBehavior(): ScrollBehavior {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"
}
