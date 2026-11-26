"use client"

import { gsap } from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react"
import { MAX_UPLOAD, createRun, fetchExample, fetchRun, type ReportView, type RunStatus } from "../api"
import { scrollBehavior } from "../platform/meta"
import Backdrop from "./Backdrop"
import Footer from "./Footer"
import Hero from "./Hero"
import Nav from "./Nav"
import Partners from "./Partners"
import PlatformBlock from "./PlatformBlock"
import Ring from "./Ring"
import Tablet from "./Tablet"
import Wave from "./Wave"

const useIso = typeof window !== "undefined" ? useLayoutEffect : useEffect

export default function Landing() {
  const root = useRef<HTMLDivElement>(null)
  const [data, setData] = useState<ReportView | null>(null)
  const [run, setRun] = useState<RunStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    const ctrl = new AbortController()
    fetchExample(ctrl.signal).then(setData).catch(() => {}) // без сервера цифры просто не показываем
    return () => ctrl.abort()
  }, [])

  const active = run !== null && run.status !== "done" && run.status !== "error"

  useEffect(() => {
    if (!active || !run) return
    const timer = window.setTimeout(() => {
      fetchRun(run.run_id)
        .then(setRun)
        .catch((e: Error) => setRun({ ...run, status: "error", error: e.message }))
    }, 1500)
    return () => window.clearTimeout(timer)
  }, [run, active])

  const upload = useCallback(async (file: File) => {
    setError(null)
    if (file.size > MAX_UPLOAD) {
      setError("Файл больше 5 МБ.")
      return
    }
    setUploading(true)
    try {
      const { run_id, position } = await createRun(file)
      setRun({ run_id, name: file.name, status: "queued", stage: null, stages_done: [], position, error: null })
      document.querySelector("[data-platform]")?.scrollIntoView({ behavior: scrollBehavior(), block: "center" })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setUploading(false)
    }
  }, [])

  // Вся анимация в одном месте, с областью видимости корня; при prefers-reduced-motion ничего не двигается.
  useIso(() => {
    gsap.registerPlugin(ScrollTrigger)
    const mm = gsap.matchMedia(root.current ?? undefined)
    mm.add("(prefers-reduced-motion: no-preference)", () => {
      // Если браузер урезает кадры (вкладка не в фокусе), текст не должен оставаться невидимым.
      const safety: number[] = []
      const finish = (tween: gsap.core.Tween, ms: number) => safety.push(window.setTimeout(() => tween.progress(1), ms))
      finish(gsap.from("[data-word]", { yPercent: 118, rotate: 3, duration: 1.1, ease: "power4.out", stagger: 0.055 }), 2200)
      gsap.to("[data-progress]", {
        scaleX: 1, ease: "none",
        scrollTrigger: { start: 0, end: "max", scrub: true },
      })
      ScrollTrigger.batch("[data-rise]", {
        start: "top 90%",
        once: true,
        onEnter: (els) => finish(gsap.fromTo(els, { y: 36, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.9, ease: "power3.out", stagger: 0.1 }), 1500),
      })
      gsap.from("[data-letter]", {
        yPercent: 105, ease: "none", stagger: 0.05,
        scrollTrigger: { trigger: "[data-bigmark]", start: "top bottom", end: "bottom bottom", scrub: 0.6 },
      })
      // Волны: смещение textPath на ширину одной копии строки. Длину меряем после загрузки шрифта, иначе виден шов.
      const waves: gsap.core.Tween[] = []
      let alive = true
      document.fonts.ready.then(() => {
        if (!alive) return
        gsap.utils.toArray<SVGTextPathElement>("[data-wave]").forEach((el) => {
          const copy = el.getComputedTextLength() / 3
          if (!copy) return
          const reverse = el.dataset.wave === "reverse"
          waves.push(gsap.fromTo(el, { attr: { startOffset: reverse ? -copy : 0 } },
            { attr: { startOffset: reverse ? 0 : -copy }, duration: copy / 60, ease: "none", repeat: -1 }))
        })
      })
      return () => {
        alive = false
        waves.forEach((t) => t.kill())
        safety.forEach((t) => window.clearTimeout(t))
      }
    })
    // Планшет выезжает под углом и по мере скролла разворачивается к зрителю.
    mm.add("(prefers-reduced-motion: no-preference)", () => {
      gsap.fromTo("[data-tablet]",
        { rotationX: 46, rotationY: -30, rotationZ: 9, y: 120, scale: 0.72 },
        { rotationX: 0, rotationY: 0, rotationZ: 0, y: 0, scale: 1, ease: "none",
          scrollTrigger: { trigger: "[data-tablet-section]", start: "top 90%", end: "top 8%", scrub: 0.6 } })
      // Когда планшет почти развернулся, сверху выпрыгивает девушка и прорисовывается стрелка к загрузке.
      let timer = 0
      gsap.set("[data-girl]", { y: 90, autoAlpha: 0 })
      gsap.set("[data-arrow]", { autoAlpha: 0 })
      gsap.set("[data-stroke]", { strokeDashoffset: 1 })
      ScrollTrigger.create({
        trigger: "[data-tablet-section]",
        start: "top 35%",
        once: true,
        onEnter: () => {
          const tl = gsap.timeline()
            .to("[data-girl]", { y: 0, autoAlpha: 1, duration: 0.8, ease: "back.out(1.8)" })
            .set("[data-arrow]", { autoAlpha: 1 })
            .to("[data-stroke]", { strokeDashoffset: 0, duration: 0.45, ease: "power2.out", stagger: 0.35 })
          timer = window.setTimeout(() => tl.progress(1), 2400)
        },
      })
      return () => window.clearTimeout(timer)
    })
    // высота страницы меняется, когда приходят данные примера: пересчитать позиции триггеров
    const refresh = window.setTimeout(() => ScrollTrigger.refresh(), 600)
    return () => {
      window.clearTimeout(refresh)
      mm.revert()
    }
  }, [])

  useEffect(() => {
    if (data) ScrollTrigger.refresh()
  }, [data])

  const result = run?.status === "done" ? (run as unknown as ReportView) : null

  return (
    <div ref={root}>
      <Backdrop />
      <Nav />
      <main>
        <Hero busy={uploading || active} error={error} onUpload={upload} />
        <Wave id="wave-top" tone="ink" />
        <Ring />
        <Wave id="wave-bottom" tone="accent" reverse />
        <Tablet busy={uploading || active} error={error} onUpload={upload} />
        <PlatformBlock data={data} run={run} result={result} />
        <Partners />
      </main>
      <Footer />
    </div>
  )
}
