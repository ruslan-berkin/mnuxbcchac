// Планшет выезжает под углом по скроллу (GSAP в Landing); за кнопкой загрузки приглушённый скриншот платформы.
// Без скрипта и при reduced motion планшет стоит фронтально.
import Upload from "./Upload"

type Props = { busy: boolean; error: string | null; onUpload: (file: File) => void }

export default function Tablet({ busy, error, onUpload }: Props) {
  return (
    <section aria-label="Загрузка документа на платформе" data-tablet-section className="overflow-hidden px-4 py-16 md:py-24">
      <div className="relative mx-auto w-full max-w-[960px]">
        {/* Девушка ладонью показывает на кнопку; на телефоне стоит над планшетом. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/girl.png" alt="" width={325} height={365} data-girl
          className="pointer-events-none relative z-20 -mb-3 ml-1 w-32 md:absolute md:left-[4%] md:top-[19%] md:mb-0 md:ml-0 md:w-[30%]" />
        <div className="stage">
          <div data-tablet className="tablet">
            <div className="tablet-screen">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/platform.jpg" alt="" loading="lazy" className="absolute inset-0 size-full object-cover object-top opacity-55 blur-[1px]" />
              <div className="relative flex h-full flex-col items-center justify-center gap-2 bg-[radial-gradient(closest-side,rgba(255,255,255,0.92),rgba(255,255,255,0))] text-center">
                <Upload busy={busy} onUpload={onUpload}
                  className="rounded-2xl bg-accent px-5 py-3 text-base font-semibold text-white shadow-[0_18px_40px_-14px_var(--accent)] transition hover:bg-accent-deep disabled:opacity-60 md:px-10 md:py-6 md:text-2xl" />
                <p className="rounded-full bg-page/90 px-3 py-1 text-xs text-muted md:text-sm">PDF, DOCX, MD или TXT до 5 МБ</p>
                {error && <p role="alert" className="rounded-lg bg-page px-3 py-1 text-sm text-critical">{error}</p>}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
