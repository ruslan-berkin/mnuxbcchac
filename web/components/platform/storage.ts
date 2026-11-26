import { useCallback, useEffect, useState } from "react"

// История чата переживает перезагрузку страницы; приватный режим и запрет хранилища не должны ломать страницу.
export function load<T>(key: string, fallback: T): T {
  try {
    const raw = window.sessionStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

export function save(key: string, value: unknown): void {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value))
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
