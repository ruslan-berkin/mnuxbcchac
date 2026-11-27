import Link from "next/link"
import type { ReportView } from "../api"
import Preview from "./Preview"

type Props = { data: ReportView | null }

export default function PlatformBlock({ data }: Props) {
  const stats = data
    ? [
        [data.report.requirements.length, "требований выделено"],
        [data.report.findings.length, "замечаний с цитатами"],
        [data.report.verifier_rejected, "ложных замечаний снял верификатор"],
      ]
    : []
  return (
    <section id="platform" data-platform className="relative px-3 py-10 md:px-5">
      <div className="relative mx-auto max-w-7xl rounded-[2.5rem] bg-ink px-5 py-12 text-page md:px-12 md:py-16">
        {/* Весь блок — ссылка на платформу. */}
        <Link href="/app/?example=1" aria-label="Открыть платформу" className="absolute inset-0 z-10 rounded-[2.5rem]" />
        <div className="grid items-center gap-10 lg:grid-cols-[1fr_1.35fr_0.7fr]">
          <div className="space-y-5" data-rise>
            <h2 className="font-display text-3xl font-semibold leading-[1.15] md:text-4xl">
              Проверка ТЗ — <span className="text-[#7fd49b]">за минуты</span>
            </h2>
            <span className="inline-block rounded-full bg-page px-5 py-3 font-medium text-ink">
              Открыть платформу →
            </span>
          </div>
          <div data-rise>
            <Preview data={data} run={null} />
          </div>
          <div data-rise>
            <dl className="grid grid-cols-3 gap-4 lg:grid-cols-1">
              {stats.map(([value, label]) => (
                <div key={label as string} className="flex flex-col">
                  <dt className="order-2 text-sm opacity-70">{label}</dt>
                  <dd className="order-1 text-4xl font-semibold md:text-6xl">{value}</dd>
                </div>
              ))}
            </dl>
            {data && <p className="mt-4 text-xs opacity-50">Из настоящего отчёта по документу организаторов.</p>}
          </div>
        </div>
      </div>
    </section>
  )
}
