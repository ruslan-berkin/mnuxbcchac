export default function Footer() {
  return (
    <footer className="overflow-hidden border-t border-rule px-5 pt-14">
      <div className="mx-auto flex max-w-7xl flex-wrap justify-between gap-4 text-sm text-muted">
        <p>BCC-HUB × MNU FinTech Hackathon 2026</p>
        <p><a className="underline underline-offset-4 hover:text-ink" href="https://github.com/ruslan-berkin/mnuxbcchac">Репозиторий на GitHub</a></p>
        <p>Дизайн по мотивам шаблона «Teal Treasury Landing» (MIT, Kedhareswer Naidu).</p>
      </div>
      <p aria-label="sau.ai" data-bigmark className="mt-8 flex justify-center text-[26vw] font-bold leading-[0.85] tracking-tighter">
        {"sau.ai".split("").map((ch, i) => (
          <span key={i} aria-hidden className="inline-block overflow-hidden pb-[0.12em] pt-[0.12em]">
            <span data-letter className={`inline-block ${ch === "." ? "text-accent" : ""}`}>{ch}</span>
          </span>
        ))}
      </p>
    </footer>
  )
}
