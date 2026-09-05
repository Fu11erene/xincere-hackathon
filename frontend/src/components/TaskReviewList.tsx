import type { TaskPreview } from '@/api/generated/model'
import { TaskEditRow } from '@/components/TaskEditRow'
import { Button } from '@/components/ui/button'

interface TaskReviewListProps {
  tasks: TaskPreview[]
  onChange: (tasks: TaskPreview[]) => void
  onConfirm: () => void
  isSubmitting: boolean
}

export function TaskReviewList({
  tasks,
  onChange,
  onConfirm,
  isSubmitting,
}: TaskReviewListProps) {
  const updateTask = (index: number, updated: TaskPreview) => {
    const next = [...tasks]
    next[index] = updated
    onChange(next)
  }

  const removeTask = (index: number) => {
    const removedId = tasks[index].temp_id
    const next = tasks
      .filter((_, i) => i !== index)
      .map((task) => ({
        ...task,
        depends_on: task.depends_on?.filter((id) => id !== removedId),
      }))
    onChange(next)
  }

  return (
    <div className="mt-6 flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        {tasks.map((task, index) => (
          <TaskEditRow
            key={task.temp_id}
            task={task}
            onChange={(updated) => updateTask(index, updated)}
            onRemove={() => removeTask(index)}
          />
        ))}
      </div>
      <Button onClick={onConfirm} disabled={isSubmitting || tasks.length === 0}>
        {isSubmitting ? '保存中...' : 'この内容で確定する'}
      </Button>
    </div>
  )
}
