// Номера R-xx и D-xxx в тексте превращаются в ссылки на требование или замечание.
const REF = /\b([RD]-\d{2,3})\b/g

export default function Refs({ text, onRef }: { text: string; onRef: (id: string) => void }) {
  return (
    <>
      {text.split(REF).map((part, i) =>
        i % 2 ? (
          <button key={i} type="button" onClick={() => onRef(part)} className="font-semibold text-accent underline underline-offset-2">
            {part}
          </button>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  )
}
