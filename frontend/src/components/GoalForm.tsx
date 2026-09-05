import type { FormEvent } from 'react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

interface GoalFormProps {
  onSubmit: (goalText: string, deadline: string | undefined) => void
  isSubmitting: boolean
}

export function GoalForm({ onSubmit, isSubmitting }: GoalFormProps) {
  const [goalText, setGoalText] = useState('')
  const [deadline, setDeadline] = useState('')

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!goalText.trim()) return
    onSubmit(goalText.trim(), deadline || undefined)
  }

  return (
    <form className="mt-6 flex flex-col gap-4" onSubmit={handleSubmit}>
      <div className="flex flex-col gap-2">
        <Label htmlFor="goal-text">ゴール</Label>
        <Textarea
          id="goal-text"
          value={goalText}
          onChange={(event) => setGoalText(event.target.value)}
          placeholder="例: 2日間のハッカソンでCEOを超えるプロダクトを完成させる"
          rows={4}
          required
        />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="deadline">締切（任意）</Label>
        <Input
          id="deadline"
          type="date"
          value={deadline}
          onChange={(event) => setDeadline(event.target.value)}
        />
      </div>
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'タスクに分解中...' : 'タスクに分解する'}
      </Button>
    </form>
  )
}
