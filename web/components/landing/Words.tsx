// Слова поднимаются из масок (приём из референса). *звёздочки* выделяют акцент.
export default function Words({ text, className = "" }: { text: string; className?: string }) {
  let accent = false
  return (
    <span className={className}>
      {text.split(" ").map((raw, i) => {
        const opens = raw.startsWith("*")
        const closes = raw.endsWith("*") || raw.endsWith("*,")
        if (opens) accent = true
        const word = raw.replaceAll("*", "")
        const el = (
          <span key={i} className="mask mr-[0.25em] last:mr-0">
            <span data-word className={`inline-block ${accent ? "text-accent" : ""}`}>{word}</span>
          </span>
        )
        if (closes) accent = false
        return el
      })}
    </span>
  )
}
