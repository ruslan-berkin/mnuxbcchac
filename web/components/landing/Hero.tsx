import Upload, { PRIVACY } from "./Upload"
import Words from "./Words"

type Props = { busy: boolean; error: string | null; onUpload: (file: File) => void }

export default function Hero({ busy, error, onUpload }: Props) {
  return (
    <section id="top" className="mx-auto flex max-w-5xl flex-col items-center px-5 pb-6 pt-12 text-center md:pt-16">
      <h1>
        <span className="font-display block text-[clamp(3.4rem,13vw,10.5rem)] font-bold leading-[1.05] tracking-[-0.045em]">
          <span className="mask"><span data-word className="wordmark inline-block px-1">sau.ai</span></span>
        </span>
        <span className="mt-2 block text-xl font-medium tracking-tight md:text-2xl">
          <Words text="Находит дыры в ТЗ раньше, чем они станут багами" />
        </span>
      </h1>
      <p className="mt-4 max-w-xl text-base text-muted">
        ИИ-агент проверяет каждое требование и весь набор по ISO/IEC/IEEE 29148 и IEEE 830, показывает цитату к
        каждому замечанию и задаёт вопросы аналитику.
      </p>
      <Upload busy={busy} onUpload={onUpload}
        className="shine mt-7 w-full rounded-full bg-accent px-10 py-5 text-lg font-semibold text-white shadow-[0_22px_44px_-18px_var(--accent)] transition hover:bg-accent-deep disabled:opacity-60 sm:w-auto" />
      <p className="mt-3 text-sm text-muted">PDF, DOCX, MD или TXT до 5 МБ</p>
      <p className="mt-1 max-w-md text-xs text-muted">{PRIVACY}</p>
      {error && <p role="alert" className="mt-2 text-sm text-critical">{error}</p>}
    </section>
  )
}
