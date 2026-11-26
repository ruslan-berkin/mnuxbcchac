import type { NextConfig } from "next"

// Статический экспорт: FastAPI раздаёт web/out как статику (один контейнер, один домен, без CORS).
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
}

export default nextConfig
