import type { Metadata, Viewport } from "next"
import type { ReactNode } from "react"
import "@fontsource-variable/onest"
import "@fontsource-variable/unbounded"
import "./globals.css"

const title = "sau.ai — проверка ТЗ до разработки"
const description =
  "ИИ-агент статической проверки требований по ISO/IEC/IEEE 29148:2018 и IEEE 830-1998. BCC-HUB × MNU FinTech Hackathon."

export const metadata: Metadata = {
  title,
  description,
  openGraph: { title, description, siteName: "sau.ai", locale: "ru_RU", type: "website" },
  twitter: { card: "summary", title, description },
}

export const viewport: Viewport = { themeColor: "#ffffff" }

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  )
}
