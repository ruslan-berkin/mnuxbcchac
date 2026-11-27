import Link from "next/link"

const CARDS = [
  {
    title: "Находит противоречия",
    text: "Сравнивает требования с критериями приёмки, данными и API, а не только каждую фразу по отдельности.",
    icon: "M7 7h10M7 12h4m6 0l-4 4m0-4l4 4M7 17h2",
  },
  {
    title: "Задаёт вопросы",
    text: "Формулирует аналитику блокирующие вопросы и перепроверяет замечания с вашими ответами.",
    icon: "M9.5 9a2.5 2.5 0 114 2c-.9.6-1.5 1-1.5 2m0 3.2v.1M12 22a10 10 0 100-20 10 10 0 000 20z",
  },
  {
    title: "Не выдумывает цитаты",
    text: "Каждая цитата ищется в документе кодом. Замечание с выдуманной цитатой отбрасывается.",
    icon: "M5 12l4 4L19 6",
  },
]

export default function Partners() {
  return (
    <section id="bcc" className="mx-auto max-w-7xl px-5 py-20">
      <p className="flex flex-wrap items-center justify-center gap-4 text-4xl md:gap-8 md:text-6xl" data-rise>
        <span className="card-bcc grid h-28 w-40 place-items-center rounded-3xl md:h-40 md:w-60">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logos/bcc.png" alt="BCC" className="w-[44%]" />
        </span>
        <span className="text-muted">×</span>
        <span className="card-mnu grid h-28 w-40 place-items-center rounded-3xl md:h-40 md:w-60">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logos/mnu.png" alt="MNU" className="w-[82%]" />
        </span>
      </p>
      <ul id="how" className="mt-14 grid scroll-mt-24 gap-4 md:grid-cols-3">
        {CARDS.map((c) => (
          <li key={c.title} data-rise>
            <Link href="/app/?example=1" className="block h-full rounded-3xl border border-rule bg-page p-7 transition hover:-translate-y-1 hover:border-ink">
              <svg aria-hidden viewBox="0 0 24 24" className="size-10 fill-none stroke-accent" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d={c.icon} />
              </svg>
              <h3 className="mt-4 text-2xl font-semibold">{c.title}</h3>
              <p className="mt-2 text-muted">{c.text}</p>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
