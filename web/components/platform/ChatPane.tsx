"use client"

// Только разговор с агентом: отчёт и вопросы живут в своих вкладках.
import { useEffect, useRef, useState } from "react"
import { streamChat, type ChatMessage, type ReportView } from "../api"
import { AnswerForm } from "./QuestionsTab"
import Refs from "./Refs"
import { load, save } from "./storage"

type Props = {
  runId: string
  data: ReportView
  answers: Record<string, string>
  totalQuestions: number
  onAnswer: (id: string, text: string) => void
  onQuestions: () => void
  onRef: (id: string) => void
}

export default function ChatPane({ runId, data, answers, totalQuestions, onAnswer, onQuestions, onRef }: Props) {
  const key = `sau-chat:${runId}`
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const loaded = useRef<string | null>(null)
  const end = useRef<HTMLDivElement>(null)
  const abort = useRef<AbortController | null>(null)

  useEffect(() => {
    const saved = load<{ messages?: ChatMessage[] }>(key, {})
    setMessages(saved.messages ?? [])
    setError(null)
    loaded.current = key
    return () => abort.current?.abort()
  }, [key])

  useEffect(() => {
    if (loaded.current === key && !busy) save(key, { messages })
  }, [key, messages, busy])

  const send = async (value: string) => {
    const text = value.trim()
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
          end.current?.scrollIntoView({ block: "nearest" })
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

  const questions = data.view.top_questions
  const pending = questions.filter((q) => !answers[q.finding_id])
  const next = pending[0]
  const done = questions.length - pending.length
  const first = data.view.priorities[0]
  const suggestions = ["Почему такой вердикт?", "Что исправить в первую очередь?", ...(first ? [`Как исправить ${first}?`] : [])]

  return (
    <div className="flex h-full min-h-0 flex-col bg-page">
      <header className="flex items-center gap-3 border-b border-rule px-4 py-3">
        <span aria-hidden className="grid size-9 place-items-center rounded-full bg-accent text-sm font-bold text-white">s</span>
        <div>
          <h2 className="text-sm font-semibold leading-tight">Агент sau.ai</h2>
          <p className="text-xs text-muted">Отвечает по этому документу</p>
        </div>
      </header>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4 text-sm">
        <p className="mr-6 rounded-2xl rounded-tl-md bg-accent-soft p-3">
          Я проверил документ: замечаний {data.report.findings.length}, критичных {data.view.by_severity.critical}.
          {next ? " Чтобы довести его до разработки, мне нужны ваши ответы." : " Спросите меня о любом из них."}
        </p>
        {questions.length > 0 && (
          <div className="space-y-3 rounded-2xl rounded-tl-md border-2 border-accent bg-page p-3">
            {next ? (
              <>
                <p className="text-xs font-semibold text-accent">Мой вопрос {done + 1} из {questions.length}</p>
                <p className="font-medium">{next.question}</p>
                <AnswerForm key={next.finding_id} question={next} onAnswer={onAnswer} />
              </>
            ) : (
              <p className="font-medium">Спасибо, на главные вопросы вы ответили.</p>
            )}
            <p className="flex flex-wrap gap-3 text-xs">
              {done > 0 && (
                <button type="button" onClick={onQuestions} className="rounded-full bg-ink px-3 py-1.5 font-medium text-page">
                  Перепроверить ({done})
                </button>
              )}
              <button type="button" onClick={onQuestions} className="font-semibold text-accent underline underline-offset-4">
                Все вопросы ({totalQuestions})
              </button>
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <p key={i} className={`whitespace-pre-wrap rounded-2xl p-3 ${m.role === "user" ? "ml-8 rounded-tr-md bg-ink text-page" : "mr-6 rounded-tl-md bg-accent-soft"}`}>
            {m.role === "assistant" ? (m.content ? <Refs text={m.content.replaceAll("**", "")} onRef={onRef} /> : "…") : m.content}
          </p>
        ))}
        {error && <p role="alert" className="rounded-xl border border-critical p-3 text-critical">{error}</p>}
        <div ref={end} />
      </div>

      <div className="space-y-2 border-t border-rule p-3">
        {!messages.length && (
          <p className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button key={s} type="button" disabled={busy} onClick={() => send(s)}
                className="rounded-full border border-rule px-3 py-1.5 text-xs hover:border-accent hover:text-accent">{s}</button>
            ))}
          </p>
        )}
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); send(input) }}>
          <textarea aria-label="Вопрос агенту" value={input} onChange={(e) => setInput(e.target.value)} rows={2} maxLength={2000}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input) } }}
            placeholder="Напишите вопрос агенту" className="min-w-0 flex-1 resize-none rounded-xl border border-rule px-3 py-2 text-sm" />
          <button type="submit" disabled={busy || !input.trim()} className="rounded-xl bg-accent px-3 text-sm font-medium text-white disabled:opacity-40">
            {busy ? "…" : "Спросить"}
          </button>
        </form>
      </div>
    </div>
  )
}
