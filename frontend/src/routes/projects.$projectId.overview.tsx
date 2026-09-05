import { createFileRoute, Link } from '@tanstack/react-router'
import { useGetProjectSchedule } from '@/api/generated/endpoints'
import { OverviewTaskRow } from '@/components/OverviewTaskRow'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

export const Route = createFileRoute('/projects/$projectId/overview')({
  component: OverviewPage,
})

function OverviewPage() {
  const { projectId } = Route.useParams()
  const { data: schedule, isLoading } = useGetProjectSchedule(projectId)

  if (isLoading || !schedule) {
    return (
      <main className="mx-auto max-w-3xl p-8">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-4 h-64 w-full" />
      </main>
    )
  }

  const sortedTasks = [...schedule.tasks].sort(
    (a, b) =>
      new Date(a.earliest_start).getTime() -
      new Date(b.earliest_start).getTime(),
  )
  const maxDuration = Math.max(
    ...sortedTasks.map((t) => t.current_estimated_duration_hours),
    1,
  )

  return (
    <main className="mx-auto max-w-3xl p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">プロジェクト全体ビュー</h1>
        <Button variant="outline" size="sm" asChild>
          <Link to="/projects/$projectId" params={{ projectId }}>
            今日やるべきことに戻る
          </Link>
        </Button>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        完了予定:{' '}
        {new Date(schedule.projected_completion_at).toLocaleString('ja-JP')}
      </p>
      {sortedTasks.length === 0 ? (
        <p className="mt-6 text-sm text-muted-foreground">
          タスクがありません。
        </p>
      ) : (
        <div className="mt-6 flex flex-col gap-2">
          {sortedTasks.map((task) => (
            <OverviewTaskRow
              key={task.id}
              task={task}
              maxDurationHours={maxDuration}
            />
          ))}
        </div>
      )}
    </main>
  )
}
