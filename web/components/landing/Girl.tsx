// Нарисованная девушка: кепка MNU, футболка BCC, пальцем показывает на кнопку загрузки.
// Два слоя в одних координатах: back стоит за планшетом, front (рука и пальцы) лежит поверх него.
// Анимация в globals.css: дыхание, моргание, наклон головы, тычок пальцем.

const SKIN = "#f3c4a2"
const SKIN_SHADE = "#dfa380"
const HAIR = "#35201a"
const SHIRT = "#14955d"
const SHIRT_SHADE = "#0e7a4b"
const MNU = "#8a0b19"

function Back() {
  return (
    <g className="girl-breathe">
      <g className="girl-hair">
        <path fill={HAIR} d="M252 118C236 40 404 36 390 118C396 168 436 214 416 276C404 312 370 296 366 262L272 262C268 300 228 318 218 276C204 226 250 178 252 118Z" />
      </g>
      <path fill={SHIRT} d="M214 340C216 250 244 206 296 190L344 190C396 206 424 250 428 340Z" />
      <path fill={SHIRT_SHADE} d="M376 206C406 232 424 276 428 340L392 340C394 290 390 246 376 206Z" />
      <path fill={SKIN} d="M302 146V190Q320 214 338 190V146Z" />
      <path fill={SKIN_SHADE} d="M302 156Q320 180 338 156V170Q320 190 302 170Z" />
      <path fill="none" stroke={SHIRT_SHADE} strokeWidth="6" strokeLinecap="round" d="M297 191Q320 222 343 191" />
      {/* знак BCC: вложенные треугольники */}
      <g transform="translate(264 238)" fill="none" stroke="#fff" strokeLinejoin="round">
        <path strokeWidth="5" d="M0 -14L17 15H-17Z" />
        <path strokeWidth="3" d="M1 -2L7 8H-5Z" />
      </g>
      <text x="288" y="252" className="girl-text" fill="#fff" fontSize="24">BCC</text>

      <g className="girl-head">
        <circle cx="262" cy="116" r="11" fill={SKIN} />
        <circle cx="378" cy="116" r="11" fill={SKIN} />
        <circle className="girl-earring" cx="261" cy="132" r="5" fill="none" stroke="#e5ac3c" strokeWidth="3" />
        <circle className="girl-earring" cx="379" cy="132" r="5" fill="none" stroke="#e5ac3c" strokeWidth="3" />
        <path fill={SKIN} d="M263 98C263 56 377 56 377 98C378 142 350 176 320 176C290 176 262 142 263 98Z" />
        <path fill={HAIR} d="M262 82C246 128 258 164 240 210C272 192 270 148 280 108C284 94 292 86 304 82Z" />
        <path fill={HAIR} d="M378 82C394 128 382 164 400 210C368 192 370 148 360 108C356 94 348 86 336 82Z" />
        <g fill="none" stroke={HAIR} strokeWidth="4" strokeLinecap="round">
          <path d="M282 101Q295 93 309 100" />
          <path d="M331 100Q345 93 358 101" />
        </g>
        <g className="girl-eyes">
          {[296, 344].map((x) => (
            <g key={x}>
              <ellipse cx={x} cy="118" rx="11" ry="12" fill="#fff" />
              <ellipse cx={x + 1} cy="119" rx="8" ry="10" fill="#4a2a18" />
              <circle cx={x + 1} cy="120" r="4.5" fill="#1c0f0a" />
              <circle cx={x + 4} cy="115" r="3" fill="#fff" />
              <path d={`M${x - 12} 112Q${x} 101 ${x + 12} 112`} fill="none" stroke="#1c0f0a" strokeWidth="3.5" strokeLinecap="round" />
            </g>
          ))}
        </g>
        <path fill="none" stroke={SKIN_SHADE} strokeWidth="3" strokeLinecap="round" d="M321 128Q327 138 318 140" />
        <ellipse cx="282" cy="140" rx="12" ry="7" fill="#f08a80" opacity="0.4" />
        <ellipse cx="358" cy="140" rx="12" ry="7" fill="#f08a80" opacity="0.4" />
        <path fill="#8d2433" d="M300 148Q320 154 340 148Q336 169 320 169Q304 169 300 148Z" />
        <path fill="#fff" d="M303 149Q320 154 337 149L335 154Q320 159 305 154Z" />
        <path fill="#ef7d86" d="M309 163Q320 156 331 163Q320 172 309 163Z" />
        {/* кепка MNU */}
        <path fill="#fbfbfa" stroke="#d9dedb" strokeWidth="2" d="M257 88C250 8 390 8 383 88Q320 70 257 88Z" />
        <path fill="none" stroke="#d9dedb" strokeWidth="2" d="M320 28Q286 38 282 79M320 28Q354 38 358 79" />
        <circle cx="320" cy="27" r="6" fill={MNU} />
        <text x="320" y="68" textAnchor="middle" className="girl-text" fill={MNU} fontSize="27">MNU</text>
        <path fill={MNU} d="M252 86Q320 62 388 86Q402 100 382 101Q320 80 258 101Q238 100 252 86Z" />
      </g>
    </g>
  )
}

function Front() {
  return (
    <>
      {/* пальцы другой руки держатся за верхний край планшета */}
      <g fill={SKIN} stroke={SKIN_SHADE} strokeWidth="2">
        {[232, 248, 264, 280].map((x, i) => (
          <rect key={x} x={x} y={266 + (i === 0 || i === 3 ? 4 : 0)} width="15" height="36" rx="7.5" />
        ))}
      </g>
      <circle className="girl-tap" cx="494" cy="562" r="12" />
      <g className="girl-point">
        <path fill="none" stroke={SKIN} strokeWidth="34" strokeLinecap="round" d="M390 232C436 262 452 296 450 340C448 394 454 440 466 478" />
        <path fill="none" stroke={SHIRT} strokeWidth="52" strokeLinecap="round" d="M386 230C410 242 428 260 440 284" />
        <path fill="none" stroke={SHIRT_SHADE} strokeWidth="5" strokeLinecap="round" d="M418 304Q442 304 464 284" />
        {/* кисть: указательный палец вытянут к кнопке, остальные согнуты */}
        <g stroke={SKIN_SHADE} strokeWidth="2" fill={SKIN}>
          <path d="M448 470C446 492 452 508 470 512C488 514 494 498 490 482L480 466Z" />
          <rect x="474" y="494" width="17" height="62" rx="8.5" transform="rotate(-15 482 500)" />
          <rect x="455" y="498" width="16" height="28" rx="8" transform="rotate(4 463 506)" />
          <rect x="441" y="490" width="16" height="27" rx="8" transform="rotate(22 449 498)" />
          <path d="M480 470C496 470 504 484 502 498C500 508 489 508 488 497C487 488 482 484 474 482Z" />
        </g>
      </g>
    </>
  )
}

export default function Girl({ layer }: { layer: "back" | "front" }) {
  return (
    <svg aria-hidden data-girl viewBox="0 0 1000 965" className={`girl girl-${layer}`}>
      {layer === "back" ? <Back /> : <Front />}
    </svg>
  )
}
