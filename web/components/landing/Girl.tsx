"use client"

// Нарисованная девушка слева от планшета: кепка MNU, футболка BCC, указательным пальцем касается края кнопки.
// Фигура собрана по суставам в координатах обёртки (1280×720): голова 133, плечи 160, талия 96, бёдра 144.
// Анимация в globals.css: дыхание, моргание, наклон головы и тычок — сгибаются плечо и локоть, а не вся рука.
import { useEffect, useRef, useState } from "react"

const SKIN = "#f1c3a1"
const SKIN_SHADE = "#cf9271"
const HAIR = "#33211b"
const SHIRT = "#1f7a3e"
const SHIRT_SHADE = "#17602f"
const DEEP = "#11372c"

type Point = [number, number]

const SHOULDER: Point = [240, 262]
const ELBOW: Point = [347, 360]
const WRIST: Point = [469, 367]
const TIP_X = 550 // кончик указательного при вытянутой руке
const GAP = 3 // палец останавливается на границе кнопки

const FAR_SHOULDER: Point = [138, 262]
const FAR_ELBOW: Point = [109, 398]
const FAR_WRIST: Point = [106, 512]

// сужающаяся часть конечности между двумя суставами: касательные к двум окружностям
function limb([x0, y0]: Point, r0: number, [x1, y1]: Point, r1: number): string {
  const angle = Math.atan2(y1 - y0, x1 - x0)
  const spread = Math.acos((r0 - r1) / Math.hypot(x1 - x0, y1 - y0))
  const at = (x: number, y: number, r: number, a: number) => `${(x + r * Math.cos(a)).toFixed(1)} ${(y + r * Math.sin(a)).toFixed(1)}`
  const [plus, minus] = [angle + spread, angle - spread]
  return `M${at(x0, y0, r0, plus)}L${at(x1, y1, r1, plus)}A${r1} ${r1} 0 0 0 ${at(x1, y1, r1, minus)}L${at(x0, y0, r0, minus)}A${r0} ${r0} 0 1 0 ${at(x0, y0, r0, plus)}Z`
}

// короткий рукав: начинается в плечевом суставе и кончается ровной манжетой поперёк плеча
function sleeve(shoulder: Point, elbow: Point): { body: string; cuff: string } {
  const [x0, y0] = shoulder
  const angle = Math.atan2(elbow[1] - y0, elbow[0] - x0)
  const length = Math.hypot(elbow[0] - x0, elbow[1] - y0) * 0.46
  const point = (along: number, across: number) =>
    `${(x0 + along * Math.cos(angle) - across * Math.sin(angle)).toFixed(1)} ${(y0 + along * Math.sin(angle) + across * Math.cos(angle)).toFixed(1)}`
  return {
    body: `M${point(0, 20)}L${point(length, 18)}L${point(length, -18)}L${point(0, -20)}A20 20 0 0 0 ${point(0, 20)}Z`,
    cuff: `M${point(length, 18)}L${point(length, -18)}`,
  }
}

const outline = { fill: "none", stroke: SKIN_SHADE, strokeWidth: 3.4, strokeLinejoin: "round" as const }
const handSkin = { fill: SKIN, stroke: SKIN_SHADE, strokeWidth: 1.6, strokeLinejoin: "round" as const }

// Кисть в своих координатах: запястье в (0,0), указательный вытянут вправо до x=81.
const CURLED = [
  { x: 28, y: -2, w: 26, h: 9.5 },
  { x: 26, y: 6.5, w: 23, h: 9 },
  { x: 23, y: 14, w: 19, h: 8 },
]

function PointingHand() {
  return (
    <g transform={`translate(${WRIST[0]} ${WRIST[1]})`}>
      <path {...handSkin} d="M-2 -10C10 -16 26 -19 38 -16C45 -12 48 -4 46 4L40 17C32 23 22 20 12 15L-2 10Z" />
      {CURLED.map((f) => (
        <rect key={f.y} {...handSkin} x={f.x} y={f.y} width={f.w} height={f.h} rx={f.h / 2} />
      ))}
      <path {...handSkin} d="M32 -15C48 -17 64 -13 76 -12C82 -10 83 -3 76 -2.5C62 -2 48 -2 34 -2Z" />
      <path fill="#fbdfce" d="M72 -10.5C78 -10 81 -8.5 81 -7C80 -5.5 76 -5 72 -5.5Z" />
      <path {...handSkin} d="M8 -9C20 -7 33 -1 41 5C45 11 39 16 33 12C26 7 18 5 8 4Z" />
    </g>
  )
}

function RelaxedHand() {
  return (
    <g transform={`translate(${FAR_WRIST[0]} ${FAR_WRIST[1]}) rotate(92)`}>
      <path {...handSkin} d="M-2 -9C14 -13 30 -13 42 -10C54 -9 66 -5 68 0C69 5 62 6 52 3C58 7 60 13 54 13C47 13 40 9 31 9C20 13 8 10 -2 9Z" />
      <path {...handSkin} d="M10 -9C20 -16 32 -18 36 -14C37 -10 28 -9 18 -6Z" />
      <path fill="none" stroke={SKIN_SHADE} strokeWidth="1.3" strokeLinecap="round" d="M40 -2L58 1M38 4L52 8" />
    </g>
  )
}

// голова нарисована в своих координатах (подбородок в 320,176) и переносится на шею
const HEAD = "translate(190 206) scale(0.86) translate(-320 -176)"

function HairBack() {
  return (
    <g transform={HEAD}>
      <g className="girl-hair">
        <path fill={HAIR} d="M254 108C240 34 400 32 386 108C394 168 424 214 410 286C396 330 366 316 360 262L280 262C274 316 244 330 230 286C216 214 246 168 254 108Z" />
      </g>
    </g>
  )
}

function Head() {
  return (
    <g transform={HEAD}>
      <g className="girl-head">
        <circle cx="263" cy="116" r="10" fill={SKIN} />
        <circle cx="377" cy="116" r="10" fill={SKIN} />
        <circle cx="262" cy="131" r="4.5" fill="none" stroke="#d9a23f" strokeWidth="3" />
        <circle cx="378" cy="131" r="4.5" fill="none" stroke="#d9a23f" strokeWidth="3" />
        <path fill={SKIN} d="M264 98C264 58 376 58 376 98C377 140 348 176 320 176C292 176 263 140 264 98Z" />
        <path fill={HAIR} d="M263 82C250 122 256 154 246 196C268 176 270 138 278 106C283 92 292 86 304 82Z" />
        <path fill={HAIR} d="M377 82C390 122 384 154 394 196C372 176 370 138 362 106C357 92 348 86 336 82Z" />
        <g fill="none" stroke={HAIR} strokeWidth="3.4" strokeLinecap="round">
          <path d="M283 102Q296 95 309 101" />
          <path d="M331 101Q344 95 357 102" />
        </g>
        <g className="girl-eyes">
          {[297, 343].map((x) => (
            <g key={x}>
              <path fill="#fff" d={`M${x - 11} 118Q${x} 105 ${x + 11} 118Q${x} 128 ${x - 11} 118Z`} />
              <circle cx={x + 1} cy="117.5" r="6.4" fill="#4a2c1a" />
              <circle cx={x + 1} cy="117.5" r="3" fill="#1c100b" />
              <circle cx={x + 3.5} cy="115" r="1.8" fill="#fff" />
              <path d={`M${x - 12} 117Q${x} 104 ${x + 12} 117`} fill="none" stroke="#1c100b" strokeWidth="2.8" strokeLinecap="round" />
            </g>
          ))}
        </g>
        <path fill="none" stroke={SKIN_SHADE} strokeWidth="2.4" strokeLinecap="round" d="M321 126Q325 138 318 140" />
        <ellipse cx="284" cy="139" rx="11" ry="6" fill="#e8897d" opacity="0.28" />
        <ellipse cx="356" cy="139" rx="11" ry="6" fill="#e8897d" opacity="0.28" />
        <path fill="#c25b64" d="M303 151Q312 147 320 150Q328 147 337 151Q328 163 320 163Q312 163 303 151Z" />
        <path fill="none" stroke="#8f3640" strokeWidth="1.8" strokeLinecap="round" d="M304 152Q320 157 336 152" />
        {/* кепка MNU */}
        <path fill="#fff" stroke="#c9d5cf" strokeWidth="2" d="M257 88C250 8 390 8 383 88Q320 70 257 88Z" />
        <path fill="none" stroke="#dbe4df" strokeWidth="2" d="M320 28Q286 38 282 79M320 28Q354 38 358 79" />
        <circle cx="320" cy="27" r="6" fill={DEEP} />
        <text x="320" y="68" textAnchor="middle" className="girl-text" fill={DEEP} fontSize="27">MNU</text>
        <path fill={DEEP} d="M254 86Q320 64 386 86Q398 99 380 99Q320 80 260 99Q242 99 254 86Z" />
      </g>
    </g>
  )
}

export default function Girl() {
  const ref = useRef<SVGSVGElement>(null)
  const [shift, setShift] = useState(0)

  // Ширина кнопки зависит от экрана, поэтому девушка подходит ровно настолько, чтобы палец упёрся в её край.
  // offsetLeft не учитывает 3D-поворот планшета во время скролла.
  useEffect(() => {
    const wrap = ref.current?.parentElement
    const button = wrap?.querySelector<HTMLElement>("[data-tablet] button")
    if (!wrap || !button) return
    const place = () => {
      let left = 0
      for (let el: HTMLElement | null = button; el && el !== wrap; el = el.offsetParent as HTMLElement | null) {
        left += el.offsetLeft + ((el.offsetParent as HTMLElement | null)?.clientLeft ?? 0)
      }
      if (wrap.clientWidth) setShift((left * 1280) / wrap.clientWidth - GAP - TIP_X)
    }
    const observer = new ResizeObserver(place)
    observer.observe(wrap)
    observer.observe(button)
    document.fonts.ready.then(place)
    return () => observer.disconnect()
  }, [])

  const far = sleeve(FAR_SHOULDER, FAR_ELBOW)
  const near = sleeve(SHOULDER, ELBOW)
  const upper = limb(SHOULDER, 18, ELBOW, 12.5)
  const fore = limb(ELBOW, 13.5, WRIST, 9.5)
  const farUpper = limb(FAR_SHOULDER, 18, FAR_ELBOW, 12.5)
  const farFore = limb(FAR_ELBOW, 13, FAR_WRIST, 9)

  return (
    <svg ref={ref} aria-hidden data-girl viewBox="0 0 1280 720" className="girl">
      <defs>
        <linearGradient id="girl-fade" gradientUnits="userSpaceOnUse" x1="0" y1="650" x2="0" y2="720">
          <stop offset="0" stopColor="#fff" />
          <stop offset="1" stopColor="#000" />
        </linearGradient>
        <mask id="girl-mask" maskUnits="userSpaceOnUse" x="-400" y="0" width="1680" height="720">
          <rect x="-400" width="1680" height="720" fill="url(#girl-fade)" />
        </mask>
      </defs>
      <g mask="url(#girl-mask)">
        <g transform={`translate(${shift.toFixed(1)} 0)`}>
          {/* брюки с высокой талией */}
          <path fill={DEEP} d="M142 388H238C243 418 262 436 262 464C260 540 250 630 244 724H204L193 532Q190 522 187 532L176 724H136C130 630 120 540 118 464C118 436 137 418 142 388Z" />
          <path fill="none" stroke="#0a251d" strokeWidth="2" d="M190 402V526" />
          <g className="girl-breathe">
            <HairBack />
            {/* дальняя рука свободно опущена */}
            <path {...outline} d={farUpper} />
            <path {...outline} d={farFore} />
            <path fill={SKIN} d={farUpper} />
            <path fill={SKIN} d={farFore} />
            <RelaxedHand />
            <path fill={SHIRT} d={far.body} />
            <path fill="none" stroke={SHIRT_SHADE} strokeWidth="4" d={far.cuff} />
            {/* указывающая рука: сначала контур, затем заливка, чтобы в локте не было шва */}
            <g className="girl-upper">
              <path {...outline} d={upper} />
              <g className="girl-fore">
                <path {...outline} d={fore} />
              </g>
            </g>
            <g className="girl-upper">
              <path fill={SKIN} d={upper} />
              <g className="girl-fore">
                <path fill={SKIN} d={fore} />
                <PointingHand />
              </g>
              <path fill={SHIRT} d={near.body} />
              <path fill="none" stroke={SHIRT_SHADE} strokeWidth="4" d={near.cuff} />
            </g>
            {/* шея и футболка: торс лежит поверх начала рукавов, поэтому ничего не торчит */}
            <path fill={SKIN} d="M172 186H208V232Q190 250 172 232Z" />
            <path fill={SKIN_SHADE} opacity="0.55" d="M172 196Q190 220 208 196V211Q190 231 172 211Z" />
            <path fill={SHIRT} d="M172 222C158 230 138 232 124 246C122 266 130 282 134 300C132 330 142 356 142 384L141 398H239L238 384C238 356 248 330 246 300C250 284 260 266 256 246C242 232 222 230 208 222Q190 246 172 222Z" />
            <path fill="none" stroke={SHIRT_SHADE} strokeWidth="4" strokeLinecap="round" d="M172 222Q190 246 208 222" />
            <g transform="translate(163 291) scale(0.78)" fill="none" stroke="#fff" strokeLinejoin="round">
              <path strokeWidth="5" d="M0 -14L17 15H-17Z" />
              <path strokeWidth="3" d="M1 -2L7 8H-5Z" />
            </g>
            <text x="179" y="299" className="girl-text" fill="#fff" fontSize="18">BCC</text>
            <Head />
          </g>
          <path fill="none" stroke="#0a251d" strokeWidth="8" d="M141 394H239" />
        </g>
      </g>
    </svg>
  )
}
