import type { ScheduledTask } from '@/api/generated/model'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface TaskCardProps {
  task: ScheduledTask
  onEvent: (taskId: string, eventType: 'complete' | 'skip') => void
}

export function TaskCard({ task, onEvent }: TaskCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="text-base">{task.name}</CardTitle>
        {task.is_critical && (
          <Badge variant="destructive">クリティカルパス</Badge>
        )}
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          残り見積もり: 約{task.current_estimated_duration_hours.toFixed(1)}時間
        </p>
        <div className="mt-3 flex gap-2">
          <Button size="sm" onClick={() => onEvent(task.id, 'complete')}>
            完了
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onEvent(task.id, 'skip')}
          >
            後回し
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
