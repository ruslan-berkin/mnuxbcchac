"use client"

// Блокирующие вопросы агента и перепроверка с ответами — отдельная вкладка, а не часть переписки.
import { useState } from "react"
import { recheck, type RecheckResult, type TopQuestion } from "../api"
import { RECHECK, SEVERITY } from "./meta"
import RecheckCard from "./RecheckCard"
import Refs from "./Refs"

type Props = {
  runId: string
  questions: TopQuestion[]
  total: number
  answers: Record<string, string>
  onAnswer: (id: string, text: string) => void
  result: RecheckResult | null
  onResult: (r: RecheckResult) => void
  onRef: (id: string) => void
}

type FormProps = { question: TopQuestion; initial?: string; onAnswer: (id: string, text: string) => void }

export function AnswerForm({ question: q, initial = "", onAnswer }: FormProps) {
  const [draft, setDraft] = useState(initial)
  return (
    <div className="space-y-2 text-sm">
      {q.options.length > 0 && (
        <p className="flex flex-wrap gap-2">
          {q.options.map((o) => (
            <button key={o} type="button" onClick={() => onAnswer(q.finding_id, o)}
              className="rounded-full border border-accent bg-page px-3 py-1.5 hover:bg-accent hover:text-white">{o}</button>
          ))}
        </p>
      )}
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); onAnswer(q.finding_id, draft) }}>
        <input aria-label={`Ответ на вопрос ${q.finding_id}`} value={draft} maxLength={1000} onChange={(e) => setDraft(e.target.value)}
          placeholder="Ваш ответ" className="min-w-0 flex-1 rounded-xl border border-rule bg-page px-3 py-2" />
        <button type="submit" disabled={!draft.trim()}
          className="rounded-xl bg-accent px-4 py-2 font-medium text-white hover:bg-accent-deep disabled:opacity-40">Ответить</button>
      </form>
    </div>
  )
}

export default function QuestionsTab({ runId, questions, total, answers, onAnswer, result, onResult, onRef }: Props) {
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const answered = Object.keys(answers).length
  const shown = questions.filter((q) => answers[q.finding_id]).length

  const run = async () => {
    setError(null)
    setChecking(true)
    try {
      onResult(await recheck(runId, answers))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-3 p-4 md:p-6">
          <header className="space-y-2">
            <h2 className="text-xl font-semibold">Ответьте на вопросы — агент перепроверит замечания</h2>
            <p className="text-sm text-muted">
              Здесь {questions.length} самых блокирующих из {total}, остальные есть в полном отчёте. Отвечено: {shown} из{" "}
              {questions.length}.
            </p>
            <div aria-hidden className="h-1.5 overflow-hidden rounded-full bg-rule">
              <div className="h-full bg-accent transition-all" style={{ width: `${questions.length ? (shown / questions.length) * 100 : 0}%` }} />
            </div>
          </header>

          {result && <RecheckCard result={result} onRef={onRef} />}
          {!questions.length && <p className="rounded-2xl border border-rule bg-page p-4">Вопросов к документу нет.</p>}

          <ol className="space-y-3">
            {questions.map((q, i) => (
              <li key={q.finding_id} className="grid grid-cols-[2rem_1fr] gap-3 rounded-2xl border border-rule bg-page p-4">
                <span aria-hidden className={`grid size-8 place-items-center rounded-full text-sm font-semibold ${
                  answers[q.finding_id] ? "bg-accent text-white" : "bg-accent-soft text-accent-deep"}`}>
                  {answers[q.finding_id] ? "✓" : i + 1}
                </span>
                <div className="space-y-3">
                  <p className="font-medium">{q.question}</p>
                  <p className="text-xs text-muted">
                    <span className={`font-semibold ${SEVERITY[q.severity].text}`}>{SEVERITY[q.severity].one}</span> · замечание{" "}
                    <Refs text={q.finding_id} onRef={onRef} />
                    {result?.items.filter((i) => i.finding_id === q.finding_id).map((i) => (
                      <span key={i.finding_id} className={`ml-2 rounded-full px-2 py-0.5 font-medium ${RECHECK[i.status].tone}`}>
                        {RECHECK[i.status].label}
                      </span>
                    ))}
                  </p>
                  {answers[q.finding_id] ? (
                    <p className="rounded-xl bg-accent-soft px-3 py-2 text-sm">
                      Ваш ответ: {answers[q.finding_id]}{" "}
                      <button type="button" className="underline underline-offset-2"
                        onClick={() => { setDrafts((d) => ({ ...d, [q.finding_id]: answers[q.finding_id] })); onAnswer(q.finding_id, "") }}>
                        изменить
                      </button>
                    </p>
                  ) : (
                    <AnswerForm question={q} initial={drafts[q.finding_id]} onAnswer={onAnswer} />
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <div className="border-t border-rule bg-page p-3">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-3">
          <p className="mr-auto text-sm text-muted">
            {error ? <span role="alert" className="text-critical">{error}</span> : "Агент проверит, снимают ли ответы замечания."}
          </p>
          <button type="button" disabled={!answered || checking} onClick={run}
            className="rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-white hover:bg-accent-deep disabled:opacity-40">
            {checking ? "Перепроверяю…" : `Перепроверить с ответами (${answered})`}
          </button>
        </div>
      </div>
    </div>
  )
}
