"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { MAX_UPLOAD, createRun, fetchExample, fetchRun, type Finding, type RecheckResult, type ReportView, type RunStatus, type Severity } from "../api"
import ChatPane from "./ChatPane"
import Preview from "../landing/Preview"
import DocumentPane from "./DocumentPane"
import FindingCard from "./FindingCard"
import RequirementsTab from "./RequirementsTab"
import QuestionsTab from "./QuestionsTab"
import RecheckCard from "./RecheckCard"
import SummaryTab from "./SummaryTab"
import TopBar from "./TopBar"
import { SEVERITY, SEVERITY_ORDER, scrollBehavior } from "./meta"
import { load, save } from "./storage"

type Tab = "report" | "findings" | "questions" | "requirements"
type Filters = { severity: Severity | ""; criterion: string; requirement: string }
type Source = { kind: "example" } | { kind: "run"; id: string }
type Jump = { kind: "doc"; id: string; n: number } | { kind: "card"; id: string; n: number }

const NO_FILTERS: Filters = { severity: "", criterion: "", requirement: "" }

export default function Platform() {
  const [data, setData] = useState<ReportView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [tab, setTab] = useState<Tab>("report")
  // только для узкого экрана: чат вместо отчёта и документ вместо списка замечаний
  const [chatOpen, setChatOpen] = useState(false)
  const [docOpen, setDocOpen] = useState(false)
  const [filters, setFilters] = useState<Filters>(NO_FILTERS)
  const [jump, setJump] = useState<Jump | null>(null)
  const [flashLines, setFlashLines] = useState<{ from: number; to: number; n: number } | null>(null)
  const counter = useRef(0)

  const [source, setSource] = useState<Source | null>(null)
  const [status, setStatus] = useState<RunStatus | null>(null)
  const [result, setResult] = useState<RecheckResult | null>(null)
  const [uploading, setUploading] = useState(false)
  const [reload, setReload] = useState(0)

  const open = useCallback((next: Source) => {
    setData(null)
    setStatus(null)
    setResult(null)
    setError(null)
    setSelected(null)
    setFlashLines(null)
    setFilters(NO_FILTERS)
    setTab("report")
    setChatOpen(false)
    setDocOpen(false)
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
              setData(s as unknown as ReportView)
            } else if (s.status === "error") {
              setError(s.error ?? "Проверка не удалась.")
            } else {
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

  const runId = source?.kind === "run" ? source.id : "example"
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const answersFor = useRef<string | null>(null)

  // Ответы аналитика общие для вкладки вопросов и чата и переживают перезагрузку.
  useEffect(() => {
    setAnswers(load<Record<string, string>>(`sau-answers:${runId}`, {}))
    answersFor.current = null
  }, [runId])
  useEffect(() => {
    if (answersFor.current === runId) save(`sau-answers:${runId}`, answers)
    else answersFor.current = runId
  }, [runId, answers])

  const answer = useCallback((id: string, text: string) => {
    const value = text.trim().slice(0, 1000)
    setAnswers((a) => {
      const next = { ...a }
      if (value) next[id] = value
      else delete next[id]
      return next
    })
    setResult(null)
  }, [])

  const showFindings = useCallback((document: boolean) => {
    setTab("findings")
    setChatOpen(false)
    setDocOpen(document)
  }, [])

  // Клик по карточке замечания: подсветить и прокрутить документ к цитате.
  const selectFromList = useCallback(
    (id: string) => {
      setSelected(id)
      setFlashLines(null)
      showFindings(true)
      setJump({ kind: "doc", id, n: ++counter.current })
    },
    [showFindings],
  )

  // Клик по подсветке или ссылке D-xxx: открыть карточку замечания.
  const selectFromDoc = useCallback(
    (id: string) => {
      setSelected(id)
      setFlashLines(null)
      setFilters(NO_FILTERS)
      showFindings(false)
      setJump({ kind: "card", id, n: ++counter.current })
    },
    [showFindings],
  )

  const showRequirement = useCallback(
    (id: string) => {
      const r = data?.report.requirements.find((x) => x.id === id)
      if (!r) return
      setSelected(null)
      setFilters({ ...NO_FILTERS, requirement: id })
      showFindings(true)
      setFlashLines({ from: r.anchor.line_start, to: r.anchor.line_end, n: ++counter.current })
    },
    [data, showFindings],
  )

  const openRef = useCallback(
    (id: string) => (id.startsWith("R-") ? showRequirement(id) : selectFromDoc(id)),
    [showRequirement, selectFromDoc],
  )

  const applyFilter = (f: { severity?: Severity; criterion?: string }) => {
    setFilters({ ...NO_FILTERS, ...f })
    showFindings(false)
  }

  // Из отчёта: сразу и карточка замечания, и его цитата в документе.
  const focusFinding = (id: string) => {
    selectFromDoc(id)
    window.setTimeout(() => {
      document.querySelector(`mark[data-finding~="${id}"]`)?.scrollIntoView({ block: "center", behavior: scrollBehavior() })
    }, 450)
  }

  const showQuestions = () => {
    setTab("questions")
    setChatOpen(false)
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
  const running = source?.kind === "run" && !data && !error
  const tabs: [Tab, string, number | null][] = [
    ["report", "Отчёт", null],
    ["findings", "Замечания", data?.report.findings.length ?? 0],
    ["questions", "Вопросы агента", totalQuestions],
    ["requirements", "Требования", data?.report.requirements.length ?? 0],
  ]
  const select = "rounded-lg border border-rule bg-page px-2 py-1.5"

  return (
    <div className="flex h-dvh flex-col bg-[#f4f7f5]">
      <TopBar report={data?.report ?? null} title={data?.document.title ?? status?.name ?? null} runId={runId}
        busy={uploading || running} onUpload={upload} onExample={() => open({ kind: "example" })} />

      {error && (
        <p role="alert" className="p-4 text-critical">
          {error}{" "}
          <button type="button" onClick={() => open({ kind: "example" })} className="underline">Открыть пример</button>
        </p>
      )}
      {running && (
        <div className="mx-auto w-full max-w-xl space-y-3 p-4 pt-10">
          <div className="rounded-3xl border border-rule bg-page p-3">
            {status ? <Preview data={null} run={status} /> : <p role="status" className="p-3">Загружаю…</p>}
          </div>
          <p className="text-center text-sm text-muted">
            Обычно это занимает несколько минут. Отчёт аналитики и чат с агентом откроются здесь сами.
          </p>
        </div>
      )}
      {!data && !error && !running && <p className="p-4 text-muted">Загружаю пример…</p>}

      {data && (
        <>
          <div role="group" aria-label="Что показывать" className="grid grid-cols-2 gap-1 border-b border-rule bg-page p-2 text-sm lg:hidden">
            {([[false, "Результаты проверки"], [true, "Чат с агентом"]] as [boolean, string][]).map(([chat, label]) => (
              <button key={label} type="button" aria-pressed={chatOpen === chat} onClick={() => setChatOpen(chat)}
                className={`rounded-full py-2 font-medium ${chatOpen === chat ? "bg-ink text-page" : "text-muted"}`}>
                {label}
              </button>
            ))}
          </div>

          <div className="grid min-h-0 flex-1 grid-cols-1 grid-rows-1 lg:grid-cols-[minmax(0,1fr)_360px]">
            <main className={`${chatOpen ? "hidden" : "flex"} min-h-0 min-w-0 flex-col lg:flex`}>
              <div role="tablist" aria-label="Разделы отчёта" className="flex gap-1 overflow-x-auto border-b border-rule bg-page px-3 pt-2 text-sm">
                {tabs.map(([key, label, n]) => (
                  <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
                    className={`flex items-center gap-2 whitespace-nowrap rounded-t-xl border-b-[3px] px-4 py-2.5 ${
                      tab === key ? "border-accent bg-accent-soft font-semibold" : "border-transparent text-muted hover:text-ink"}`}>
                    {label}
                    {n !== null && (
                      <span className={`rounded-full px-2 text-xs tabular-nums ${tab === key ? "bg-accent text-white" : "bg-rule text-ink"}`}>{n}</span>
                    )}
                  </button>
                ))}
              </div>

              <div className="min-h-0 flex-1">
                {tab === "report" && (
                  <div className="h-full overflow-y-auto">
                    {result && <div className="mx-auto max-w-3xl px-4 pt-4 md:px-6"><RecheckCard result={result} onRef={openRef} /></div>}
                    <SummaryTab data={data} findings={findings} onSelect={focusFinding} onFilter={applyFilter} onQuestions={showQuestions} />
                  </div>
                )}

                {tab === "questions" && (
                  <QuestionsTab key={runId} runId={runId} questions={data.view.top_questions} total={totalQuestions}
                    answers={answers} onAnswer={answer} result={result} onResult={setResult} onRef={openRef} />
                )}

                {tab === "requirements" && (
                  <div className="h-full overflow-y-auto p-4 md:p-6">
                    <div className="mx-auto max-w-4xl space-y-3">
                      <p className="text-sm text-muted">Так агент нарезал документ. Нажмите на номер, чтобы увидеть требование в тексте.</p>
                      <div className="overflow-x-auto rounded-2xl border border-rule bg-page px-4 py-2">
                        <RequirementsTab data={data} onRequirement={showRequirement} />
                      </div>
                    </div>
                  </div>
                )}

                {tab === "findings" && (
                  <div className="grid h-full min-h-0 grid-rows-1 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
                    <section aria-label="Список замечаний" className={`${docOpen ? "hidden" : "flex"} min-h-0 flex-col xl:flex xl:border-r xl:border-rule`}>
                      <div className="space-y-2 border-b border-rule bg-page p-3 text-sm">
                        <div className="flex flex-wrap gap-2">
                          <select aria-label="Серьёзность" value={filters.severity}
                            onChange={(e) => setFilters({ ...filters, severity: e.target.value as Severity | "" })} className={select}>
                            <option value="">Любая серьёзность</option>
                            {SEVERITY_ORDER.map((s) => <option key={s} value={s}>{SEVERITY[s].label}</option>)}
                          </select>
                          <select aria-label="Критерий" value={filters.criterion}
                            onChange={(e) => setFilters({ ...filters, criterion: e.target.value })} className={`${select} max-w-48`}>
                            <option value="">Все критерии</option>
                            {Object.keys(data.view.by_criterion).map((c) => <option key={c} value={c}>{c} — {data.view.criteria[c]?.title}</option>)}
                          </select>
                          <select aria-label="Требование" value={filters.requirement}
                            onChange={(e) => setFilters({ ...filters, requirement: e.target.value })} className={select}>
                            <option value="">Все требования</option>
                            {data.report.requirements.map((r) => <option key={r.id} value={r.id}>{r.id}{r.source_id ? ` (${r.source_id})` : ""}</option>)}
                          </select>
                        </div>
                        <p className="flex flex-wrap items-center justify-between gap-x-3 text-muted">
                          <span>Показано {visible.length} из {data.report.findings.length}</span>
                          <span className="flex gap-3">
                            <button type="button" onClick={() => setFilters(NO_FILTERS)} className="underline underline-offset-4 hover:text-ink">Сбросить</button>
                            <button type="button" onClick={() => setDocOpen(true)} className="font-semibold text-accent xl:hidden">Открыть документ</button>
                          </span>
                        </p>
                      </div>
                      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
                        {visible.map((f) => (
                          <div key={f.id} className="rounded-2xl bg-page">
                            <FindingCard finding={f} title={data.view.criteria[f.criterion]?.title ?? ""}
                              reference={data.view.criteria[f.criterion]?.reference ?? ""} selected={selected === f.id}
                              onSelect={selectFromList} onRequirement={showRequirement} />
                          </div>
                        ))}
                        {!visible.length && <p className="text-muted">Под эти фильтры замечаний нет.</p>}
                      </div>
                    </section>

                    <section aria-label="Документ" className={`${docOpen ? "flex" : "hidden"} min-h-0 flex-col bg-page xl:flex`}>
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-rule px-4 py-3 text-xs text-muted">
                        <button type="button" onClick={() => setDocOpen(false)} className="text-sm font-semibold text-accent xl:hidden">
                          ← К замечаниям
                        </button>
                        <h2 className="text-sm font-semibold text-ink">Текст документа</h2>
                        {SEVERITY_ORDER.map((s) => (
                          <span key={s} className="flex items-center gap-1">
                            <span aria-hidden className={`inline-block h-3 w-5 rounded-sm underline ${SEVERITY[s].mark}`} />
                            {SEVERITY[s].label.toLowerCase()}
                          </span>
                        ))}
                      </div>
                      <div className="min-h-0 flex-1 overflow-y-auto">
                        <DocumentPane lines={data.document.lines} highlights={data.view.highlights} findings={findings}
                          selected={selected} flashLines={flashLines} onPick={selectFromDoc} />
                      </div>
                    </section>
                  </div>
                )}
              </div>
            </main>

            <aside aria-label="Чат с агентом" className={`${chatOpen ? "flex" : "hidden"} min-h-0 flex-col border-rule lg:flex lg:border-l`}>
              <ChatPane key={runId} runId={runId} data={data} answers={answers} totalQuestions={totalQuestions}
                onQuestions={showQuestions} onRef={openRef} />
            </aside>
          </div>
        </>
      )}
    </div>
  )
}
