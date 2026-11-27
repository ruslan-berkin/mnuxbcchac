import Link from "next/link"

export default function NotFound() {
  return (
    <main className="grid min-h-dvh place-items-center px-5 text-center">
      <div className="space-y-4">
        <p className="font-display text-2xl font-semibold">sau.ai</p>
        <h1 className="text-3xl font-semibold">Такой страницы нет</h1>
        <p className="text-muted">Проверьте адрес или вернитесь на главную.</p>
        <p className="flex flex-wrap justify-center gap-3">
          <Link href="/" className="rounded-full bg-accent px-5 py-2.5 font-medium text-white hover:bg-accent-deep">
            На главную
          </Link>
          <Link href="/app/?example=1" className="rounded-full border border-ink px-5 py-2.5 font-medium">
            Открыть пример
          </Link>
        </p>
      </div>
    </main>
  )
}
