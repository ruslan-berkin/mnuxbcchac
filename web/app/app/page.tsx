import type { Metadata } from "next"
import Platform from "@/components/platform/Platform"

export const metadata: Metadata = { title: "Платформа — sau.ai" }

export default function Page() {
  return <Platform />
}
