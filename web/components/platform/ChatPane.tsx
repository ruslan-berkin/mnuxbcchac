"use client"

import { useEffect, useRef, useState } from "react"
import { recheck, streamChat, type ChatMessage, type RecheckResult, type ReportView } from "../api"
import AgentReport from "./AgentReport"
import { SEVERITY, scrollBehavior } from "./meta"
import RecheckCard from "./RecheckCard"
import Refs from "./Refs"
import { load, save } from "./storage"

type Props = {
  runId: string
  data: ReportView
  totalQuestions: number
  result: RecheckResult | null
  onResult: (r: RecheckResult | null) => void
  onRef: (id: string) => void
}

type Saved = { messages: ChatMessage[]; answers: Record<string, string> }

export default function ChatPane({ runId, data, totalQuestions, result, onResult, onRef }: Props) {
  const questions = data.view.top_questions
  const key = `sau-chat:${runId}`
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const loaded = useRef<string | null>(null)
  const end = useRef<HTMLDivElement>(null)
  const abort = useRef<AbortController | null>(null)

  useEffect(() => {
    const saved = load<Saved>(key, { messages: [], answers: {} })
    setMessages(saved.messages)
    setAnswers(saved.answers)
    setDrafts({})
    setError(null)
    loaded.current = key
    return () => abort.current?.abort()
  }, [key])

  useEffect(() => {
    if (loaded.current === key && !busy) save(key, { messages, answers })
  }, [key, messages, answers, busy])

  const answered = Object.keys(answers).length

  const answer = (id: string, text: string) => {
    const value = text.trim().slice(0, 1000)
    setAnswers((a) => {
      const next = { ...a }
      if (value) next[id] = value
      else delete next[id]
      return next
    })
    onResult(null)
  }

  const send = async () => {
    const text = input.trim()
    if (!text || busy) return
    setError(null)
    setInput("")
    const history: ChatMessage[] = [...messages, { role: "user", content: text.slice(0, 2000) }]
    setMessages([...history, { role: "assistant", content: "" }])
    setBusy(true)
    abort.current = new AbortController()
    let reply = ""
    try {
      await streamChat(
        { run_id: runId, messages: history.slice(-12), answers },
        (delta) => {
          reply += delta
          setMessages([...history, { role: "assistant", content: reply }])
          end.current?.scrollIntoView({ block: "end" })
        },
        abort.current.signal,
      )
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message)
      if (!reply) setMessages(history)
    } finally {
      setBusy(false)
    }
  }

  const runRecheck = async () => {
    setError(null)
    setChecking(true)
    try {
      onResult(await recheck(runId, answers))
      requestAnimationFrame(() => end.current?.scrollIntoView({ block: "end", behavior: scrollBehavior() }))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <h2 className="border-b border-rule px-4 py-2 text-base font-semibold">Чат с агентом</h2>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4 text-sm">
        <AgentReport data={data} runId={runId} onRef={onRef} />
        <p className="rounded-2xl bg-accent-soft p-3">
          Чтобы документ можно было отдавать в разработку, мне нужны ответы на вопросы (всего <b>{totalQuestions}</b>).
          Начните с блокирующих:
        </p>
        <ol className="space-y-3">
          {questions.map((q, i) => (
            <li key={q.finding_id} className="space-y-2 rounded-2xl border border-rule p-3">
              <p>
                <span className="font-semibold">{i + 1}. </span>
                {q.question} <span className={`text-xs font-semibold ${SEVERITY[q.severity].text}`}>{SEVERITY[q.severity].one}</span>{" "}
                <Refs text={q.finding_id} onRef={onRef} />
              </p>
              {answers[q.finding_id] ? (
                <p className="rounded-xl bg-accent-soft px-3 py-2">
                  Ваш ответ: {answers[q.finding_id]}{" "}
                  <button type="button" onClick={() => { setDrafts((d) => ({ ...d, [q.finding_id]: answers[q.finding_id] })); answer(q.finding_id, "") }}
                    className="underline underline-offset-2">изменить</button>
                </p>
              ) : (
                <>
                  {q.options.length > 0 && (
                    <p className="flex flex-wrap gap-2">
                      {q.options.map((o) => (
                        <button key={o} type="button" onClick={() => answer(q.finding_id, o)}
                          className="rounded-full border border-accent px-3 py-1 hover:bg-accent hover:text-white">{o}</button>
                      ))}
                    </p>
                  )}
                  <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); answer(q.finding_id, drafts[q.finding_id] ?? "") }}>
                    <input aria-label={`Ответ на вопрос ${q.finding_id}`} value={drafts[q.finding_id] ?? ""} maxLength={1000}
                      onChange={(e) => setDrafts((d) => ({ ...d, [q.finding_id]: e.target.value }))}
                      placeholder="Свой ответ" className="min-w-0 flex-1 rounded-lg border border-rule px-2 py-1" />
                    <button type="submit" className="rounded-lg border border-rule px-2 py-1 hover:border-ink">Ответить</button>
                  </form>
                </>
              )}
            </li>
          ))}
        </ol>
        <button type="button" disabled={!answered || checking} onClick={runRecheck}
          className="w-full rounded-full bg-ink px-4 py-2 font-medium text-page disabled:opacity-40">
          {checking ? "Перепроверяю…" : `Перепроверить с ответами (${answered})`}
        </button>
        {result && <RecheckCard result={result} onRef={onRef} />}

        {messages.map((m, i) => (
          <p key={i} className={`whitespace-pre-wrap rounded-2xl p-3 ${m.role === "user" ? "ml-8 bg-ink text-page" : "mr-4 bg-accent-soft"}`}>
            {m.role === "assistant" ? (m.content ? <Refs text={m.content.replaceAll("**", "")} onRef={onRef} /> : "…") : m.content}
          </p>
        ))}
        {error && <p role="alert" className="rounded-xl border border-critical p-3 text-critical">{error}</p>}
        <div ref={end} />
      </div>
      <form className="flex gap-2 border-t border-rule p-3" onSubmit={(e) => { e.preventDefault(); send() }}>
        <textarea aria-label="Вопрос агенту" value={input} onChange={(e) => setInput(e.target.value)} rows={2} maxLength={2000}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder="Почему это критично? Перепиши Ф-3…" className="min-w-0 flex-1 resize-none rounded-xl border border-rule px-3 py-2 text-sm" />
        <button type="submit" disabled={busy || !input.trim()} className="rounded-xl bg-accent px-3 text-sm font-medium text-white disabled:opacity-40">
          {busy ? "…" : "Спросить"}
        </button>
      </form>
    </div>
  )
}
