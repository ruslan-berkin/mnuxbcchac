import Link from "next/link"
import ExampleStub from "@/components/ExampleStub"

export default function Platform() {
  return (
    <main className="mx-auto max-w-5xl space-y-6 px-6 py-10">
      <p>
        <Link href="/" className="font-semibold">sau.ai</Link>
      </p>
      <h1 className="text-4xl font-semibold">Пример: документ организаторов</h1>
      <ExampleStub />
    </main>
  )
}
