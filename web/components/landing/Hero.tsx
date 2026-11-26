import Link from "next/link"
import Upload from "./Upload"
import Words from "./Words"

type Props = { busy: boolean; error: string | null; onUpload: (file: File) => void }

export default function Hero({ busy, error, onUpload }: Props) {
  return (
    <section id="top" className="mx-auto grid max-w-7xl gap-8 px-5 pb-10 pt-10 md:pt-16 lg:grid-cols-[1.3fr_1fr] lg:items-center">
      <h1>
        <span className="block text-[clamp(5rem,17vw,13rem)] font-extrabold leading-[0.95] tracking-[-0.06em]">
          <Words text="*sau.ai*" />
        </span>
        <span className="mt-3 block text-xl font-medium tracking-tight md:text-2xl">
          <Words text="ИИ-агент, который проверяет ТЗ до разработки" />
        </span>
      </h1>
      <div className="max-w-md space-y-5 lg:justify-self-end">
        <p className="text-base text-muted">
          Читает документ требований, проверяет каждое требование и весь набор по ISO/IEC/IEEE 29148 и IEEE 830,
          задаёт уточняющие вопросы и не выдумывает цитаты.
        </p>
        <div>
          <Upload busy={busy} onUpload={onUpload}
            className="w-full rounded-2xl bg-accent px-8 py-5 text-xl font-semibold text-white shadow-[0_18px_40px_-18px_var(--accent)] transition hover:bg-accent-deep disabled:opacity-60 sm:w-auto" />
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
