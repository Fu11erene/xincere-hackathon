import { useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import {
  getGetProjectScheduleQueryKey,
  useGetProjectSchedule,
  useRecordTaskEvent,
} from '@/api/generated/endpoints'
import { TaskCard } from '@/components/TaskCard'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'

export const Route = createFileRoute('/projects/$projectId')({
  component: DashboardPage,
})

function DashboardPage() {
  const { projectId } = Route.useParams()
  const queryClient = useQueryClient()
  const { data: schedule, isLoading } = useGetProjectSchedule(projectId)
  const eventMutation = useRecordTaskEvent()

  const handleEvent = (taskId: string, eventType: 'complete' | 'skip') => {
    eventMutation.mutate(
      { taskId, data: { event_type: eventType } },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({
            queryKey: getGetProjectScheduleQueryKey(projectId),
          })
        },
      },
    )
  }

  if (isLoading || !schedule) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-4 h-32 w-full" />
      </main>
    )
  }

  const now = new Date()
  const endOfToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
    23,
    59,
    59,
  )
  const todayTasks = schedule.tasks
    .filter((task) => task.status === 'todo' || task.status === 'in_progress')
    .filter((task) => new Date(task.earliest_start) <= endOfToday)
    .sort((a, b) => {
      if (a.is_critical !== b.is_critical) return a.is_critical ? -1 : 1
      return (
        new Date(a.earliest_start).getTime() -
        new Date(b.earliest_start).getTime()
      )
    })

  return (
    <main className="mx-auto max-w-2xl p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">今日やるべきこと</h1>
        <Button variant="outline" size="sm" asChild>
          <Link to="/projects/$projectId/overview" params={{ projectId }}>
            全体を見る
          </Link>
        </Button>
      </div>
      {todayTasks.length === 0 ? (
        <p className="mt-6 text-sm text-muted-foreground">
          今日着手すべきタスクはありません。お疲れさまです。
        </p>
      ) : (
        <div className="mt-6 flex flex-col gap-3">
          {todayTasks.map((task) => (
            <TaskCard key={task.id} task={task} onEvent={handleEvent} />
          ))}
        </div>
      )}
    </main>
  )
}
