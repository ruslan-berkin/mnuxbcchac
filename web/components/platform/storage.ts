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
