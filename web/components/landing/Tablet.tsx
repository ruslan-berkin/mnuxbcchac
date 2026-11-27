"use client"

// Планшет выезжает под углом по скроллу (GSAP в Landing), девушка слева от него пальцем показывает на загрузку.
// Без скрипта и при reduced motion всё стоит на местах.
import { useState } from "react"
import Girl from "./Girl"
import Upload, { PRIVACY } from "./Upload"

type Props = { busy: boolean; error: string | null; onUpload: (file: File) => void }

export default function Tablet({ busy, error, onUpload }: Props) {
  const [over, setOver] = useState(false)
  return (
    <section aria-label="Загрузка документа" data-tablet-section className="px-4 py-10 md:py-14">
      <div className="tablet-wrap">
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
                {/* Кнопка ровно в центре планшета (его края касается палец), подписи под ней вне потока. */}
                <div className="relative">
                  <Upload busy={busy} onUpload={onUpload}
                    className="tablet-button shine whitespace-nowrap rounded-full bg-accent font-semibold text-white shadow-[0_20px_44px_-16px_var(--accent)] transition hover:bg-accent-deep disabled:opacity-60" />
                  <div className="absolute left-1/2 top-full w-max -translate-x-1/2 pt-1.5 md:pt-4">
                    <p className="hidden text-base text-ink md:block">или перетащите файл сюда</p>
                    <p className="text-[10px] text-muted md:mt-2 md:text-sm">PDF, DOCX, MD или TXT до 5 МБ</p>
                    <p className="mx-auto mt-2 hidden max-w-xs whitespace-normal text-xs text-muted lg:block">{PRIVACY}</p>
                  </div>
                </div>
                {error && <p role="alert" className="absolute inset-x-2 top-2 rounded-lg bg-page px-3 py-1 text-xs text-critical md:text-sm">{error}</p>}
              </div>
            </div>
          </div>
        </div>
        <Girl />
      </div>
    </section>
  )
}
