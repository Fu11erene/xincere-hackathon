import { createFileRoute } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'

export const Route = createFileRoute('/')({
  component: TodayDashboard,
})

function TodayDashboard() {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-semibold">今日やるべきこと</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        TODO: /projects/:id/schedule を取得して表示する
      </p>
      <Button className="mt-4">完了</Button>
    </main>
  )
}
