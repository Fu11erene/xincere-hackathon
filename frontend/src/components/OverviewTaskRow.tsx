import type { ScheduledTask } from '@/api/generated/model'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface OverviewTaskRowProps {
  task: ScheduledTask
  maxDurationHours: number
}

export function OverviewTaskRow({
  task,
  maxDurationHours,
}: OverviewTaskRowProps) {
  const slackDays = task.slack_hours / 24
  const slackLabel = task.is_critical
    ? 'スラックなし'
    : `余裕: ${slackDays.toFixed(1)}日`
  const barWidthPercent = Math.max(
    (task.current_estimated_duration_hours / maxDurationHours) * 100,
    4,
  )

  return (
    <div
      className={cn(
        'rounded-md border-l-4 bg-card p-3',
        task.is_critical ? 'border-l-destructive' : 'border-l-border',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{task.name}</span>
        {task.is_critical && (
          <Badge variant="destructive">クリティカルパス</Badge>
        )}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{slackLabel}</p>
      <div className="mt-2 h-2 rounded-full bg-muted">
        <div
          className="h-2 rounded-full bg-primary"
          style={{ width: `${barWidthPercent}%` }}
        />
      </div>
    </div>
  )
}
