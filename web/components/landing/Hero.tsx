"use client"

import Link from "next/link"
import { useRef } from "react"
import { ACCEPTED } from "../api"
import Words from "./Words"

type Props = { busy: boolean; error: string | null; onUpload: (file: File) => void }

export default function Hero({ busy, error, onUpload }: Props) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <section id="top" className="mx-auto grid max-w-7xl gap-10 px-5 pb-16 pt-14 md:pt-24 lg:grid-cols-[1.45fr_1fr] lg:items-end">
      <h1 className="text-5xl font-semibold leading-[1.02] md:text-7xl xl:text-[5.4rem]">
        <Words text="sau.ai — ИИ-агент, который *проверяет ТЗ* до разработки" />
      </h1>
      <div className="space-y-6">
        <p className="text-lg text-muted">
          Читает документ требований, проверяет каждое требование и весь набор по ISO/IEC/IEEE 29148 и IEEE 830,
          задаёт уточняющие вопросы и не выдумывает цитаты.
        </p>
        <div>
          <input ref={input} type="file" accept={ACCEPTED} className="sr-only" tabIndex={-1} aria-hidden
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) onUpload(file)
              e.target.value = ""
            }} />
          <button type="button" disabled={busy} onClick={() => input.current?.click()}
            className="w-full rounded-2xl bg-accent px-8 py-5 text-xl font-semibold text-white shadow-[0_18px_40px_-18px_var(--accent)] transition hover:bg-accent-deep disabled:opacity-60 sm:w-auto">
            {busy ? "Проверяю…" : "Загрузить документ"}
          </button>
          <p className="mt-2 text-sm text-muted">PDF, DOCX, MD или TXT до 5 МБ</p>
          {error && <p role="alert" className="mt-2 text-sm text-critical">{error}</p>}
          <p className="mt-3 text-sm">
            <Link href="/app/?example=1" className="underline underline-offset-4 hover:text-accent">
              или посмотрите пример на документе организаторов
            </Link>
          </p>
        </div>
      </div>
    </section>
  )
}
