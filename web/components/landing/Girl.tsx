// Нарисованная девушка слева от планшета: кепка MNU, футболка BCC, указательным пальцем показывает на кнопку.
// Координаты общие с обёрткой (1280×720): кончик пальца — левый край кнопки в центре планшета.
// Анимация в globals.css: дыхание, моргание, наклон головы, тычок пальцем.

const SKIN = "#f4c7a6"
const SKIN_SHADE = "#d99c78"
const HAIR = "#33211b"
const SHIRT = "#1f7a3e"
const SHIRT_SHADE = "#17602f"
const DEEP = "#11372c"

const skin = { fill: SKIN, stroke: SKIN_SHADE, strokeWidth: 1.8, strokeLinejoin: "round" as const }
// голова нарисована в своих координатах с центром (320, 100) и переносится на место
const HEAD = "translate(166 175) scale(0.95) translate(-320 -100)"

function Head() {
  return (
    <g className="girl-head">
      <circle cx="262" cy="116" r="11" fill={SKIN} />
      <circle cx="378" cy="116" r="11" fill={SKIN} />
      <circle cx="261" cy="132" r="5" fill="none" stroke="#e5ac3c" strokeWidth="3" />
      <circle cx="379" cy="132" r="5" fill="none" stroke="#e5ac3c" strokeWidth="3" />
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
            <ellipse cx={x} cy="118" rx="11" ry="11.5" fill="#fff" />
            <ellipse cx={x + 2} cy="119" rx="7.5" ry="9.5" fill="#4a2c1a" />
            <circle cx={x + 2} cy="120" r="4.2" fill="#1c100b" />
            <circle cx={x + 5} cy="115" r="2.8" fill="#fff" />
            <path d={`M${x - 12} 112Q${x} 102 ${x + 12} 112`} fill="none" stroke="#1c100b" strokeWidth="3.4" strokeLinecap="round" />
          </g>
        ))}
      </g>
      <path fill="none" stroke={SKIN_SHADE} strokeWidth="2.6" strokeLinecap="round" d="M322 128Q327 138 319 140" />
      <ellipse cx="282" cy="140" rx="12" ry="7" fill="#ee8f86" opacity="0.38" />
      <ellipse cx="358" cy="140" rx="12" ry="7" fill="#ee8f86" opacity="0.38" />
      <path fill="#8f2f3a" d="M302 148Q320 154 338 148Q334 167 320 167Q306 167 302 148Z" />
      <path fill="#fff" d="M305 149Q320 154 335 149L333 154Q320 158 307 154Z" />
      <path fill="#e98088" d="M310 162Q320 156 330 162Q320 170 310 162Z" />
      {/* кепка MNU */}
      <path fill="#fff" stroke="#cfdad4" strokeWidth="2" d="M257 88C250 8 390 8 383 88Q320 70 257 88Z" />
      <path fill="none" stroke="#dbe4df" strokeWidth="2" d="M320 28Q286 38 282 79M320 28Q354 38 358 79" />
      <circle cx="320" cy="27" r="6" fill={DEEP} />
      <text x="320" y="68" textAnchor="middle" className="girl-text" fill={DEEP} fontSize="27">MNU</text>
      <path fill={DEEP} d="M252 86Q320 62 388 86Q402 100 382 101Q320 80 258 101Q238 100 252 86Z" />
    </g>
  )
}

// Кисть смотрит вправо: указательный вытянут, три пальца согнуты, большой прижат поверх них.
function PointingHand() {
  return (
    <g {...skin} transform="translate(556 359) scale(0.8) translate(-556 -359)">
      <path d="M459 355C473 346 492 343 505 349C515 356 517 366 515 376L510 394C500 402 480 400 468 386Z" />
      <rect x="480" y="391" width="29" height="12" rx="6" transform="rotate(9 494 397)" />
      <rect x="486" y="380" width="33" height="13" rx="6.5" transform="rotate(5 502 386)" />
      <rect x="489" y="368" width="36" height="13.5" rx="6.75" transform="rotate(2 507 374)" />
      <path d="M494 350C510 348 534 351 551 352C562 353 563 368 551 369C534 370 516 369 500 370Z" />
      <path fill="#fde4d4" strokeWidth="1.2" d="M543 355C550 354.5 556 356 556 359.5C556 362.5 550 363 543 362Z" />
      <path fill="none" strokeWidth="1.4" d="M522 353Q525 361 522 368" />
      <path d="M470 357C481 357 494 364 505 373C513 380 508 391 499 387C491 382 484 379 473 378C465 376 463 361 470 357Z" />
    </g>
  )
}

export default function Girl() {
  return (
    <svg aria-hidden data-girl viewBox="0 0 1280 720" className="girl">
      <defs>
        <linearGradient id="girl-fade" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0.86" stopColor="#fff" />
          <stop offset="1" stopColor="#000" />
        </linearGradient>
        <mask id="girl-mask" maskUnits="userSpaceOnUse" x="0" y="0" width="1280" height="720">
          <rect width="1280" height="720" fill="url(#girl-fade)" />
        </mask>
      </defs>
      <g mask="url(#girl-mask)">
        {/* на широком экране кнопка уже, поэтому девушка стоит чуть правее: палец доходит до её края */}
        <g className="girl-place">
        {/* брюки с высокой талией */}
        <g transform="translate(50 0)">
        <path fill={DEEP} d="M138 386H194C197 420 212 440 212 474C212 540 204 640 198 720H176L167 520L156 720H134C128 640 120 540 120 474C120 440 135 420 138 386Z" />
        </g>
        <g className="girl-breathe">
          <g transform="translate(50 0)">
          <g transform={HEAD}>
            <g className="girl-hair">
              <path fill={HAIR} d="M252 112C236 36 404 32 390 112C398 166 440 214 424 290C412 330 374 316 366 270L272 270C264 320 222 334 214 290C200 230 250 174 252 112Z" />
            </g>
          </g>
          {/* опущенная рука вдоль тела */}
          <path {...skin} d="M130 282C114 292 106 330 100 392C97 430 95 462 97 494L109 495C112 464 117 430 118 398C122 362 128 332 140 308Z" />
          <path {...skin} d="M97 492C92 506 91 522 95 532C98 540 103 537 103 528L105 541C107 548 112 546 112 537V522C116 529 121 527 118 516L109 494Z" />
          <path fill={SKIN} d="M156 232V262Q166 276 176 262V232Z" />
          <path fill={SKIN_SHADE} d="M156 240Q166 258 176 240V248Q166 266 156 248Z" />
          {/* приталенная футболка, заправлена в брюки */}
          <path fill={SHIRT} d="M153 258C138 262 120 268 114 284C112 300 124 316 126 332C129 356 138 372 138 396H194C194 372 203 356 206 332C208 316 220 300 218 284C212 268 194 262 179 258Q166 276 153 258Z" />
          <path fill={SHIRT_SHADE} d="M126 332C129 356 138 372 138 396H147C147 372 137 352 126 332ZM206 332C203 356 194 372 194 396H185C185 372 195 352 206 332Z" />
          <path fill="none" stroke={SHIRT_SHADE} strokeWidth="4" strokeLinecap="round" d="M153 258Q166 276 179 258" />
          {/* левый рукав */}
          <path fill={SHIRT} d="M138 264C117 270 106 292 100 324L123 330C126 312 130 300 140 290Z" />
          <path fill="none" stroke={SHIRT_SHADE} strokeWidth="4" strokeLinecap="round" d="M100 324L123 330" />
          <g transform="translate(144 316) scale(0.7)" fill="none" stroke="#fff" strokeLinejoin="round">
            <path strokeWidth="5" d="M0 -14L17 15H-17Z" />
            <path strokeWidth="3" d="M1 -2L7 8H-5Z" />
          </g>
          <text x="159" y="324" className="girl-text" fill="#fff" fontSize="16">BCC</text>
          <g transform={HEAD}>
            <Head />
          </g>
          </g>
          {/* указывающая рука */}
          <circle className="girl-tap" cx="570" cy="360" r="13" />
          <g className="girl-point">
            <path {...skin} d="M252 276C276 288 312 336 346 372C390 368 440 361 480 357L481 376C444 381 400 392 358 398C342 400 330 395 320 386C292 358 266 324 246 306Z" />
            <PointingHand />
            <path fill={SHIRT} d="M232 261C260 266 288 290 310 315L287 339C274 324 260 312 242 306Z" />
            <path fill="none" stroke={SHIRT_SHADE} strokeWidth="4" strokeLinecap="round" d="M310 315L287 339" />
          </g>
        </g>
        <path fill="none" stroke="#0a251d" strokeWidth="8" d="M138 392H194" transform="translate(50 0)" />
        </g>
      </g>
    </svg>
  )
}
