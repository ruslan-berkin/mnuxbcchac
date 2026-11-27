"use client"

// Кнопка выбора файла: одна на первый экран и на планшет.
import { useRef } from "react"
import { ACCEPTED } from "../api"

export const PRIVACY =
  "Текст документа отправляется во внешнюю модель (OpenAI) и хранится на сервере до 2 часов. Не загружайте конфиденциальные документы."

type Props = { busy: boolean; className: string; onUpload: (file: File) => void }

export default function Upload({ busy, className, onUpload }: Props) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <>
      <input ref={input} type="file" accept={ACCEPTED} className="sr-only" tabIndex={-1} aria-hidden
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onUpload(file)
          e.target.value = ""
        }} />
      <button type="button" disabled={busy} onClick={() => input.current?.click()} className={className}>
        {busy ? "Проверяю…" : "Загрузить документ"}
      </button>
    </>
  )
}
