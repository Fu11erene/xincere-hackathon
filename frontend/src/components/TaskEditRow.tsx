import type { TaskPreview } from '@/api/generated/model'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface TaskEditRowProps {
  task: TaskPreview
  onChange: (task: TaskPreview) => void
  onRemove: () => void
}

export function TaskEditRow({ task, onChange, onRemove }: TaskEditRowProps) {
  return (
    <div className="flex items-center gap-2 rounded-md border p-3">
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
        onChange={(event) =>
          onChange({
            ...task,
            estimated_duration_hours: Number(event.target.value),
          })
        }
        className="w-24"
      />
      <span className="text-xs text-muted-foreground">時間</span>
      <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
        削除
      </Button>
    </div>
  )
}
