"use client"

// Сетка с точкой в центре каждой клетки. На первом экране под курсором она выпучивается линзой и идёт за ним.
import { useEffect, useRef } from "react"

const STEP = 48
const RADIUS = 190
const BULGE = 0.9

export default function DotGrid() {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas?.getContext("2d")
    if (!canvas || !ctx) return
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const target = { x: -999, y: -999, s: 0 }
    const lens = { x: -999, y: -999, s: 0 }
    let w = 0
    let h = 0
    let frame = 0

    // 1 на самом верху страницы, 0 после первого экрана
    const first = () => Math.max(0, Math.min(1, 1 - window.scrollY / (window.innerHeight * 0.6)))

    const warp = (x: number, y: number, s: number): [number, number, number] => {
      const dx = x - lens.x
      const dy = y - lens.y
      const d = Math.hypot(dx, dy)
      if (s < 0.001 || d >= RADIUS) return [x, y, 0]
      const t = 1 - d / RADIUS
      const m = 1 + BULGE * s * t * t
      return [lens.x + dx * m, lens.y + dy * m, t * s]
    }

    const line = (x0: number, y0: number, x1: number, y1: number, s: number) => {
      const n = Math.ceil(Math.hypot(x1 - x0, y1 - y0) / 12)
      for (let i = 0; i <= n; i++) {
        const [x, y] = warp(x0 + ((x1 - x0) * i) / n, y0 + ((y1 - y0) * i) / n, s)
        if (i) ctx.lineTo(x, y)
        else ctx.moveTo(x, y)
      }
    }

    const glow = (x: number, y: number, r: number, color: string) => {
      const g = ctx.createRadialGradient(x, y, 0, x, y, r)
      g.addColorStop(0, color)
      g.addColorStop(1, "rgba(255,255,255,0)")
      ctx.fillStyle = g
      ctx.fillRect(x - r, y - r, r * 2, r * 2)
    }

    const draw = () => {
      const fade = first()
      const s = lens.s * fade
      ctx.clearRect(0, 0, w, h)
      if (s > 0.01) {
        // тень снизу и блик сверху делают выпуклость объёмной
        glow(lens.x + 14, lens.y + 30, RADIUS * 1.05, `rgba(17,90,55,${0.17 * s})`)
        glow(lens.x - 22, lens.y - 28, RADIUS * 0.8, `rgba(255,255,255,${0.95 * s})`)
      }
      const left = (w / 2) % STEP
      ctx.beginPath()
      for (let x = left; x <= w; x += STEP) line(x, 0, x, h, s)
      for (let y = 0; y <= h; y += STEP) line(0, y, w, y, s)
      ctx.strokeStyle = "rgba(17,55,44,0.075)"
      ctx.lineWidth = 1
      ctx.stroke()
      if (fade <= 0) return
      for (let x = left - STEP / 2; x <= w + STEP; x += STEP) {
        for (let y = STEP / 2; y <= h + STEP; y += STEP) {
          const [px, py, f] = warp(x, y, s)
          ctx.beginPath()
          ctx.arc(px, py, 1.7 + 3.6 * f, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(31,122,62,${(0.34 + 0.66 * f) * fade})`
          ctx.fill()
        }
      }
    }

    const tick = () => {
      lens.x += (target.x - lens.x) * 0.18
      lens.y += (target.y - lens.y) * 0.18
      lens.s += (target.s - lens.s) * 0.1
      draw()
      const moving = Math.abs(target.x - lens.x) + Math.abs(target.y - lens.y) > 0.3 || Math.abs(target.s - lens.s) > 0.005
      frame = moving ? requestAnimationFrame(tick) : 0
    }
    const wake = () => {
      if (!frame) frame = requestAnimationFrame(tick)
    }
    const move = (e: PointerEvent) => {
      if (target.s === 0 && lens.s < 0.05) {
        lens.x = e.clientX
        lens.y = e.clientY
      }
      target.x = e.clientX
      target.y = e.clientY
      target.s = 1
      wake()
    }
    const leave = () => {
      target.s = 0
      wake()
    }
    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      w = window.innerWidth
      h = window.innerHeight
      canvas.width = w * dpr
      canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      draw()
    }

    resize()
    window.addEventListener("resize", resize)
    window.addEventListener("scroll", draw, { passive: true })
    if (!still) {
      window.addEventListener("pointermove", move, { passive: true })
      document.documentElement.addEventListener("pointerleave", leave)
    }
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener("resize", resize)
      window.removeEventListener("scroll", draw)
      window.removeEventListener("pointermove", move)
      document.documentElement.removeEventListener("pointerleave", leave)
    }
  }, [])

  return <canvas ref={ref} className="dot-grid" />
}
