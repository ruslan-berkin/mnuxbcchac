"use client"

import { gsap } from "gsap"
import { ScrollTrigger } from "gsap/ScrollTrigger"
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react"
import { MAX_UPLOAD, createRun, fetchExample, fetchRun, type ReportView, type RunStatus } from "../api"
import { scrollBehavior } from "../platform/meta"
import Footer from "./Footer"
import Hero from "./Hero"
import Nav from "./Nav"
import Partners from "./Partners"
import PlatformBlock from "./PlatformBlock"
import Showcase from "./Showcase"
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
      // Волны: смещение textPath на ширину одной копии строки, бесконечно, в противоположные стороны.
      gsap.utils.toArray<SVGTextPathElement>("[data-wave]").forEach((el) => {
        const copy = el.getComputedTextLength() / 3
        if (!copy) return
        const reverse = el.dataset.wave === "reverse"
        gsap.fromTo(el, { attr: { startOffset: reverse ? -copy : 0 } },
          { attr: { startOffset: reverse ? 0 : -copy }, duration: copy / 60, ease: "none", repeat: -1 })
      })
      return () => safety.forEach((t) => window.clearTimeout(t))
    })
    // Ноутбук: на широком экране секция закреплена и скролл «открывает» его; на телефоне — только появление.
    mm.add("(min-width: 768px) and (prefers-reduced-motion: no-preference)", () => {
      const section = "[data-showcase]"
      const fill = () => {
        const laptop = root.current?.querySelector<HTMLElement>("[data-laptop]")
        if (!laptop) return 1
        return Math.min((window.innerWidth * 0.92) / laptop.offsetWidth, (window.innerHeight - 110) / laptop.offsetHeight)
      }
      const tl = gsap.timeline({
        defaults: { ease: "none" },
        scrollTrigger: { trigger: section, start: "top top+=56", end: "+=170%", pin: true, scrub: 0.8, invalidateOnRefresh: true },
      })
      tl.fromTo("[data-laptop]",
        { rotationX: -28, rotationY: -35, y: () => window.innerHeight * 0.12, scale: 0.55 },
        { rotationX: 0, rotationY: 0, y: 0, scale: 0.86, duration: 1, ease: "power1.inOut" }, 0)
      tl.fromTo("[data-lid]", { rotationX: -90, y: -10 }, { rotationX: 0, y: 0, duration: 0.85, ease: "power1.inOut" }, 0.2)
      tl.to("[data-laptop]", { scale: fill, duration: 0.55, ease: "power2.out" }, 1)
      tl.to("[data-wordmark]", { yPercent: -45, autoAlpha: 0.15, duration: 0.7 }, 0.85)
      tl.to({}, { duration: 0.25 }) // пауза: экран крупно перед тем, как секция отпустит скролл
    })
    mm.add("(max-width: 767px) and (prefers-reduced-motion: no-preference)", () => {
      gsap.from("[data-laptop]", { y: 60, autoAlpha: 0, duration: 0.9, ease: "power3.out",
        scrollTrigger: { trigger: "[data-showcase]", start: "top 75%", once: true } })
    })
    // Девушка выезжает с лёгким отскоком, когда блок платформы вошёл в экран (после анимации ноутбука).
    mm.add("(prefers-reduced-motion: no-preference)", () => {
      let timer = 0
      gsap.set("[data-girl]", { x: -90, autoAlpha: 0 })
      ScrollTrigger.create({
        trigger: "[data-platform]",
        start: "top 55%",
        once: true,
        onEnter: () => {
          const tween = gsap.to("[data-girl]", { x: 0, autoAlpha: 1, duration: 1, ease: "back.out(2.2)" })
          timer = window.setTimeout(() => tween.progress(1), 1600)
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
      <Nav />
      <main>
        <Hero busy={uploading || active} error={error} onUpload={upload} />
        <Wave id="wave-top" tone="ink" />
        <Showcase data={data} />
        <Wave id="wave-bottom" tone="accent" reverse />
        <PlatformBlock data={data} run={run} result={result} />
        <Partners />
      </main>
      <Footer />
    </div>
  )
}
