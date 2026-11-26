"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { MAX_UPLOAD, createRun, fetchExample, fetchRun, type Finding, type RecheckResult, type ReportView, type RunStatus, type Severity } from "../api"
import ChatPane from "./ChatPane"
import DocumentPane from "./DocumentPane"
import FindingCard from "./FindingCard"
import RequirementsTab from "./RequirementsTab"
import RecheckCard from "./RecheckCard"
import SummaryTab from "./SummaryTab"
import TopBar, { type Progress } from "./TopBar"
import { SEVERITY, SEVERITY_ORDER, scrollBehavior } from "./meta"

type Tab = "summary" | "findings" | "requirements"
type Pane = "doc" | "findings" | "chat"
type Filters = { severity: Severity | ""; criterion: string; requirement: string }
type Source = { kind: "example" } | { kind: "run"; id: string }
type Jump = { kind: "doc"; id: string; n: number } | { kind: "card"; id: string; n: number }

const NO_FILTERS: Filters = { severity: "", criterion: "", requirement: "" }

export default function Platform() {
  const [data, setData] = useState<ReportView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>("summary")
  const [pane, setPane] = useState<Pane>("findings")
  const [filters, setFilters] = useState<Filters>(NO_FILTERS)
  const [jump, setJump] = useState<Jump | null>(null)
  const [flashLines, setFlashLines] = useState<{ from: number; to: number; n: number } | null>(null)
  const counter = useRef(0)

  const [source, setSource] = useState<Source | null>(null)
  const [status, setStatus] = useState<RunStatus | null>(null)
  const [progress, setProgress] = useState<Progress | null>(null)
  const [result, setResult] = useState<RecheckResult | null>(null)
  const [uploading, setUploading] = useState(false)
  const [reload, setReload] = useState(0)

  const open = useCallback((next: Source) => {
    setData(null)
    setStatus(null)
    setProgress(null)
    setResult(null)
    setError(null)
    setSelected(null)
    setFlashLines(null)
    setFilters(NO_FILTERS)
    setTab("summary")
    setSource(next)
    setReload((n) => n + 1)
    window.history.replaceState(null, "", next.kind === "run" ? `?run=${next.id}` : "?example=1")
  }, [])

  // Что открыть по адресу: ?run=<id> или пример.
  useEffect(() => {
    const run = new URLSearchParams(window.location.search).get("run")
    setSource(run && /^[0-9a-f]{32}$/.test(run) ? { kind: "run", id: run } : { kind: "example" })
  }, [])

  // Пример грузится сразу; живой прогон опрашивается, пока не завершится.
  useEffect(() => {
    if (!source) return
    const ctrl = new AbortController()
    let timer: number | undefined
    const fail = (e: Error) => {
      if (e.name !== "AbortError") setError(e.message)
    }
    if (source.kind === "example") {
      fetchExample(ctrl.signal).then(setData).catch(fail)
    } else {
      const poll = () =>
        fetchRun(source.id, ctrl.signal)
          .then((s) => {
            setStatus(s)
            if (s.status === "done") {
              setProgress(null)
              setData(s as unknown as ReportView)
            } else if (s.status === "error") {
              setProgress(null)
              setError(s.error ?? "Проверка не удалась.")
            } else {
              setProgress({ stage: s.stage, done: s.stages_done })
              timer = window.setTimeout(poll, 1500)
            }
          })
          .catch(fail)
      poll()
    }
    return () => {
      ctrl.abort()
      window.clearTimeout(timer)
    }
  }, [source, reload])

  const upload = useCallback(
    async (file: File) => {
      if (file.size > MAX_UPLOAD) {
        setError("Файл больше 5 МБ.")
        return
      }
      setUploading(true)
      setError(null)
      try {
        const { run_id } = await createRun(file)
        open({ kind: "run", id: run_id })
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setUploading(false)
      }
    },
    [open],
  )

  const findings = useMemo(
    () => new Map<string, Finding>((data?.report.findings ?? []).map((f) => [f.id, f])),
    [data],
  )

  // Клик по замечанию: подсветить и прокрутить документ к цитате.
  const selectFromList = useCallback((id: string) => {
    setSelected(id)
    setFlashLines(null)
    setPane("doc")
    setJump({ kind: "doc", id, n: ++counter.current })
  }, [])

  // Клик по подсветке: открыть карточку замечания.
  const selectFromDoc = useCallback((id: string) => {
    setSelected(id)
    setFlashLines(null)
    setFilters(NO_FILTERS)
    setTab("findings")
    setPane("findings")
    setJump({ kind: "card", id, n: ++counter.current })
  }, [])

  const showRequirement = useCallback(
    (id: string) => {
      const r = data?.report.requirements.find((x) => x.id === id)
      if (!r) return
      setSelected(null)
      setFilters({ ...NO_FILTERS, requirement: id })
      setPane("doc")
      setFlashLines({ from: r.anchor.line_start, to: r.anchor.line_end, n: ++counter.current })
    },
    [data],
  )

  const openRef = useCallback(
    (id: string) => (id.startsWith("R-") ? showRequirement(id) : selectFromDoc(id)),
    [showRequirement, selectFromDoc],
  )

  const applyFilter = (f: { severity?: Severity; criterion?: string }) => {
    setFilters({ ...NO_FILTERS, ...f })
    setTab("findings")
  }

  useEffect(() => {
    if (!jump) return
    const target =
      jump.kind === "doc"
        ? document.querySelector(`mark[data-finding~="${jump.id}"]`)
        : document.getElementById(`card-${jump.id}`)
    target?.scrollIntoView({ block: "center", behavior: scrollBehavior() })
  }, [jump])

  useEffect(() => {
    if (flashLines) {
      document.getElementById(`line-${flashLines.from}`)?.scrollIntoView({ block: "center", behavior: scrollBehavior() })
    }
  }, [flashLines])

  const visible = useMemo(
    () =>
      (data?.report.findings ?? []).filter(
        (f) =>
          (!filters.severity || f.severity === filters.severity) &&
          (!filters.criterion || f.criterion === filters.criterion) &&
          (!filters.requirement || f.requirement_ids.includes(filters.requirement)),
      ),
    [data, filters],
  )

  const totalQuestions = data?.report.findings.filter((f) => f.question).length ?? 0
  const runId = source?.kind === "run" ? source.id : "example"
  const running = source?.kind === "run" && !data && !error
  const paneClass = (name: Pane) => `${pane === name ? "block" : "hidden"} min-h-0 overflow-y-auto lg:block`

  return (
    <div className="flex h-dvh flex-col">
      <TopBar report={data?.report ?? null} runId={runId} progress={progress} busy={uploading || running}
        onUpload={upload} onExample={() => open({ kind: "example" })} />

      <nav aria-label="Разделы" className="grid grid-cols-3 border-b border-rule text-sm lg:hidden">
        {([["doc", "Документ"], ["findings", "Замечания"], ["chat", "Чат"]] as [Pane, string][]).map(([key, label]) => (
          <button key={key} type="button" aria-pressed={pane === key} onClick={() => setPane(key)}
            className={`py-2 ${pane === key ? "border-b-2 border-ink font-semibold" : "text-muted"}`}>
            {label}
          </button>
        ))}
      </nav>

      {error && (
        <p role="alert" className="p-4 text-critical">
          {error}{" "}
          <button type="button" onClick={() => open({ kind: "example" })} className="underline">Открыть пример</button>
        </p>
      )}
      {running && (
        <div role="status" className="m-4 rounded-2xl bg-accent-soft p-4">
          <p className="font-semibold">{status?.name ? `Проверяю «${status.name}»…` : "Загружаю…"}</p>
          <p className="text-sm text-muted">
            {status?.status === "queued"
              ? `Вы в очереди: ${status.position ?? 1}.`
              : "Обычно это занимает несколько минут. Этапы видны сверху, страницу можно не держать открытой."}
          </p>
        </div>
      )}
      {!data && !error && !running && <p className="p-4 text-muted">Загружаю пример…</p>}

      {data && (
        <main className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(0,5fr)_minmax(0,4.4fr)_minmax(0,2.6fr)]">
          <section aria-label="Документ" className={`${paneClass("doc")} lg:border-r lg:border-rule`}>
            <h1 className="sticky top-0 z-10 border-b border-rule bg-page px-4 py-2 text-base font-semibold">
              {data.document.title}
            </h1>
            <DocumentPane
              lines={data.document.lines}
              highlights={data.view.highlights}
              findings={findings}
              selected={selected}
              flashLines={flashLines}
              onPick={selectFromDoc}
            />
          </section>

          <section aria-label="Замечания и аналитика" className={`${paneClass("findings")} lg:border-r lg:border-rule`}>
            <div role="tablist" className="sticky top-0 z-10 flex gap-4 border-b border-rule bg-page px-4 text-sm">
              {([["summary", "Сводка"], ["findings", `Замечания (${data.report.findings.length})`], ["requirements", "Требования"]] as [Tab, string][]).map(
                ([key, label]) => (
                  <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
                    className={`py-2 ${tab === key ? "border-b-2 border-ink font-semibold" : "text-muted"}`}>
                    {label}
                  </button>
                ),
              )}
            </div>
            <div className="space-y-3 p-4">
              {tab === "summary" && (
                <>
                  {result && <RecheckCard result={result} onRef={openRef} />}
                  <SummaryTab data={data} findings={findings} onSelect={selectFromDoc} onFilter={applyFilter} />
                </>
              )}
              {tab === "requirements" && <RequirementsTab data={data} onRequirement={showRequirement} />}
              {tab === "findings" && (
                <>
                  <div className="flex flex-wrap gap-2 text-sm">
                    <select aria-label="Серьёзность" value={filters.severity}
                      onChange={(e) => setFilters({ ...filters, severity: e.target.value as Severity | "" })}
                      className="rounded-lg border border-rule bg-page px-2 py-1">
                      <option value="">Любая серьёзность</option>
                      {SEVERITY_ORDER.map((s) => <option key={s} value={s}>{SEVERITY[s].label}</option>)}
                    </select>
                    <select aria-label="Критерий" value={filters.criterion}
                      onChange={(e) => setFilters({ ...filters, criterion: e.target.value })}
                      className="rounded-lg border border-rule bg-page px-2 py-1">
                      <option value="">Все критерии</option>
                      {Object.keys(data.view.by_criterion).map((c) => <option key={c} value={c}>{c} — {data.view.criteria[c]?.title}</option>)}
                    </select>
                    <select aria-label="Требование" value={filters.requirement}
                      onChange={(e) => setFilters({ ...filters, requirement: e.target.value })}
                      className="rounded-lg border border-rule bg-page px-2 py-1">
                      <option value="">Все требования</option>
                      {data.report.requirements.map((r) => <option key={r.id} value={r.id}>{r.id}{r.source_id ? ` (${r.source_id})` : ""}</option>)}
                    </select>
                    <button type="button" onClick={() => setFilters(NO_FILTERS)} className="underline underline-offset-4">Сбросить</button>
                    <span className="ml-auto self-center text-muted">Показано: {visible.length}</span>
                  </div>
                  {visible.map((f) => (
                    <FindingCard key={f.id} finding={f} title={data.view.criteria[f.criterion]?.title ?? ""}
                      reference={data.view.criteria[f.criterion]?.reference ?? ""} selected={selected === f.id}
                      onSelect={selectFromList} onRequirement={showRequirement} />
                  ))}
                  {!visible.length && <p className="text-muted">Под эти фильтры замечаний нет.</p>}
                </>
              )}
            </div>
          </section>

          <aside aria-label="Чат с агентом" className={`${pane === "chat" ? "flex" : "hidden"} min-h-0 flex-col lg:flex`}>
            <ChatPane key={runId} runId={runId} questions={data.view.top_questions} totalQuestions={totalQuestions}
              result={result} onResult={setResult} onRef={openRef} />
          </aside>
        </main>
      )}
    </div>
  )
}
