import type { Metadata, Viewport } from "next"
import type { ReactNode } from "react"
import "@fontsource-variable/inter-tight"
import "./globals.css"

export const metadata: Metadata = {
  title: "sau.ai — проверка ТЗ до разработки",
  description:
    "ИИ-агент статической проверки требований по ISO/IEC/IEEE 29148:2018 и IEEE 830-1998. BCC-HUB × MNU FinTech Hackathon.",
}

export const viewport: Viewport = { themeColor: "#ffffff" }

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  )
}
