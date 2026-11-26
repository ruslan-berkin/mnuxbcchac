"use client"

// Планшет выезжает под углом по скроллу (GSAP в Landing), девушка выглядывает из-за него и пальцем показывает на загрузку.
// Без скрипта и при reduced motion всё стоит на местах.
import { useState } from "react"
import Girl from "./Girl"
import Upload from "./Upload"

type Props = { busy: boolean; error: string | null; onUpload: (file: File) => void }

export default function Tablet({ busy, error, onUpload }: Props) {
  const [over, setOver] = useState(false)
  return (
    <section aria-label="Загрузка документа" data-tablet-section className="px-4 py-10 md:py-14">
      <div className="tablet-wrap">
        <Girl layer="back" />
        <div className="stage tablet-slot">
          <div data-tablet className="tablet">
            <div className="tablet-screen">
              <div className={`dropzone ${over ? "dropzone-over" : ""}`}
                onDragOver={(e) => { e.preventDefault(); setOver(true) }}
                onDragLeave={() => setOver(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setOver(false)
                  const file = e.dataTransfer.files[0]
                  if (file && !busy) onUpload(file)
                }}>
                <Upload busy={busy} onUpload={onUpload}
                  className="shine rounded-full bg-[#4be094] px-6 py-3.5 text-base font-semibold text-ink shadow-[0_20px_50px_-12px_rgba(75,224,148,0.6)] transition hover:bg-white disabled:opacity-60 md:px-11 md:py-6 md:text-2xl" />
                <p className="text-sm text-white/85 md:text-base">или перетащите файл сюда</p>
                <p className="text-xs text-white/55 md:text-sm">PDF, DOCX, MD или TXT до 5 МБ</p>
                {error && <p role="alert" className="rounded-lg bg-page px-3 py-1 text-sm text-critical">{error}</p>}
              </div>
            </div>
          </div>
        </div>
        <Girl layer="front" />
      </div>
    </section>
  )
}
