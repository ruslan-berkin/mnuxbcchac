import type { Metadata } from "next"
import Platform from "@/components/platform/Platform"

export const metadata: Metadata = { title: "Платформа — sau.ai" }

export default function Page() {
  return (
    <>
      <noscript>
        <main style={{ padding: "1.5rem" }}>
          <h1>Платформа sau.ai</h1>
          <p>
            Интерфейсу нужен JavaScript. Готовый отчёт по документу организаторов доступен без него:{" "}
            <a href="/api/runs/example/report.md">Markdown</a> или <a href="/api/runs/example/report.json">JSON</a>.
          </p>
        </main>
      </noscript>
      <Platform />
    </>
  )
}
