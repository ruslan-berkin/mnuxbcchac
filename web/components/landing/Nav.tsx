import Link from "next/link"

export default function Nav() {
  return (
    <header className="sticky top-0 z-30 border-b border-rule/70 bg-page/75 backdrop-blur-md">
      <nav aria-label="Главное меню" className="mx-auto flex max-w-7xl items-center gap-6 px-5 py-3">
        <a href="#top" className="text-xl font-semibold tracking-tight">sau.ai</a>
        <ul className="ml-4 hidden gap-6 text-sm text-muted md:flex">
          <li><a href="#how" className="hover:text-ink">Как работает</a></li>
          <li><a href="#platform" className="hover:text-ink">Платформа</a></li>
          <li><a href="#bcc" className="hover:text-ink">BCC × MNU</a></li>
        </ul>
        <Link href="/app/" className="ml-auto rounded-full bg-ink px-5 py-2 text-sm font-medium text-page hover:bg-accent-deep">
          Открыть платформу
        </Link>
      </nav>
      <div aria-hidden className="h-0.5 w-full origin-left scale-x-0 bg-accent" data-progress />
    </header>
  )
}
