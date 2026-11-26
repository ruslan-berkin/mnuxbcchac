import Link from "next/link"

// Заглушка лендинга (фаза A). Секции по эскизу появятся в фазах E и F.
export default function Landing() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col justify-center gap-6 px-6">
      <p className="text-lg font-semibold">sau.ai</p>
      <h1 className="text-5xl font-semibold leading-[1.02] md:text-7xl">
        ИИ-агент, который <span className="text-accent">проверяет ТЗ</span> до разработки
      </h1>
      <p className="max-w-2xl text-lg text-muted">
        Читает документ требований, проверяет каждое требование и весь набор по ISO/IEC/IEEE 29148 и IEEE 830,
        задаёт уточняющие вопросы и не выдумывает цитаты.
      </p>
      <p>
        <Link href="/app/?example=1" className="inline-block rounded-full bg-accent px-6 py-3 font-medium text-white">
          Пример на документе организаторов
        </Link>
      </p>
    </main>
  )
}
