import type { TaskPreview } from '@/api/generated/model'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface TaskEditRowProps {
  task: TaskPreview
  dependencyNames: string[]
  onChange: (task: TaskPreview) => void
  onRemove: () => void
}

export function TaskEditRow({
  task,
  dependencyNames,
  onChange,
  onRemove,
}: TaskEditRowProps) {
  return (
    <div className="flex flex-col gap-2 rounded-md border p-3">
      <div className="flex items-center gap-2">
        <Input
          value={task.name}
          onChange={(event) => onChange({ ...task, name: event.target.value })}
          className="flex-1"
        />
        <Input
          type="number"
          min={0.5}
          step={0.5}
          value={task.estimated_duration_hours}
          onChange={(event) => {
            const value = Number(event.target.value)
            if (Number.isNaN(value)) return
            onChange({ ...task, estimated_duration_hours: value })
          }}
          className="w-24"
        />
        <span className="text-xs text-muted-foreground">時間</span>
        <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
          削除
        </Button>
      </div>
      {dependencyNames.length > 0 && (
        <p className="text-xs text-muted-foreground">
          先行タスク: {dependencyNames.join('、')}
        </p>
      )}
    </div>
  )
}
