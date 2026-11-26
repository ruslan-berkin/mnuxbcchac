// Чат с агентом подключается в фазе D (SSE, перепроверка с ответами).
export default function ChatPane({ questions }: { questions: number }) {
  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <h2 className="text-lg font-semibold">Чат с агентом</h2>
      <div className="rounded-2xl bg-accent-soft p-4 text-sm">
        Я проверил документ. Вопросов аналитику: <b>{questions}</b>. Скоро здесь можно будет отвечать на них и
        перепроверять замечания.
      </div>
    </div>
  )
}
