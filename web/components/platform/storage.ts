import { useCallback, useEffect, useState } from "react"

// Ответы, переписка и перепроверка переживают перезагрузку и закрытие вкладки, но не дольше, чем сервер
// хранит сам прогон. Приватный режим и запрет хранилища не должны ломать страницу.
const TTL_MS = 2 * 60 * 60 * 1000

export function load<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return fallback
    const saved = JSON.parse(raw) as { at?: number; value?: T }
    if (!saved.at || Date.now() - saved.at > TTL_MS || saved.value === undefined) {
      window.localStorage.removeItem(key)
      return fallback
    }
    return saved.value
  } catch {
    return fallback
  }
}

export function save(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify({ at: Date.now(), value }))
  } catch {
    // хранилище недоступно: просто не сохраняем
  }
}

// Состояние, привязанное к прогону и переживающее перезагрузку. fallback должен быть постоянным значением.
export function useStored<T>(key: string, fallback: T): [T, (next: T | ((prev: T) => T)) => void] {
  const [state, setState] = useState<{ key: string; value: T }>({ key: "", value: fallback })
  useEffect(() => {
    setState({ key, value: load<T>(key, fallback) })
  }, [key, fallback])
  const set = useCallback(
    (next: T | ((prev: T) => T)) =>
      setState((s) => {
        const prev = s.key === key ? s.value : load<T>(key, fallback)
        const value = typeof next === "function" ? (next as (p: T) => T)(prev) : next
        save(key, value)
        return { key, value }
      }),
    [key, fallback],
  )
  return [state.key === key ? state.value : fallback, set]
}
