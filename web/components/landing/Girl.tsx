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
const HEAD = "translate(165 165) scale(1.15) translate(-320 -100)"

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
    <g {...skin}>
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
        {/* брюки */}
        <path fill={DEEP} d="M101 496H233C250 560 248 640 240 720H182L168 580L154 720H96C86 640 84 560 101 496Z" />
        <g className="girl-breathe">
          <g transform={HEAD}>
            <g className="girl-hair">
              <path fill={HAIR} d="M252 112C236 36 404 32 390 112C398 166 436 208 420 272C408 310 372 296 366 262L272 262C266 298 228 314 218 274C204 224 250 174 252 112Z" />
            </g>
          </g>
          {/* опущенная рука: ладонь на поясе */}
          <path {...skin} d="M106 300C84 320 62 372 50 404C46 418 52 428 62 436L106 484L124 464L86 414C98 386 112 356 126 336Z" />
          <g {...skin}>
            <path d="M104 462C116 456 128 462 132 474L134 492C128 500 116 498 110 490L100 476Z" />
            <rect x="117" y="478" width="11" height="30" rx="5.5" transform="rotate(-14 122 492)" />
            <rect x="128" y="474" width="11" height="28" rx="5.5" transform="rotate(-22 133 488)" />
          </g>
          <path fill={SHIRT} d="M118 262Q166 250 214 262C244 272 258 300 252 340L232 372C226 420 228 460 236 500H98C106 460 108 420 100 372L76 336C72 298 88 272 118 262Z" />
          <path fill={SHIRT_SHADE} d="M100 372C108 420 106 460 98 500H122C128 452 122 404 100 372Z" />
          <path fill={SKIN} d="M147 228V264Q166 286 185 264V228Z" />
          <path fill={SKIN_SHADE} d="M147 238Q166 262 185 238V250Q166 272 147 250Z" />
          <path fill="none" stroke={SHIRT_SHADE} strokeWidth="6" strokeLinecap="round" d="M142 262Q166 298 190 262" />
          <g transform="translate(127 336)" fill="none" stroke="#fff" strokeLinejoin="round">
            <path strokeWidth="5" d="M0 -14L17 15H-17Z" />
            <path strokeWidth="3" d="M1 -2L7 8H-5Z" />
          </g>
          <text x="148" y="350" className="girl-text" fill="#fff" fontSize="23">BCC</text>
          <path fill="none" stroke={DEEP} strokeWidth="10" d="M99 496H235" />
          <g transform={HEAD}>
            <Head />
          </g>
          {/* указывающая рука */}
          <circle className="girl-tap" cx="570" cy="360" r="13" />
          <g className="girl-point">
            <path {...skin} d="M226 302C268 306 300 354 344 390C380 382 424 364 461 354L470 386C436 400 394 428 356 440C338 446 322 438 308 424C282 400 252 374 218 362Z" />
            <PointingHand />
            <path fill={SHIRT} d="M214 276C262 284 298 330 322 366L284 408C264 388 242 372 208 362Z" />
            <path fill="none" stroke={SHIRT_SHADE} strokeWidth="7" strokeLinecap="round" d="M322 366L284 408" />
          </g>
        </g>
        </g>
      </g>
    </svg>
  )
}
