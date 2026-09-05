import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { useCreateProject, usePreviewProject } from '@/api/generated/endpoints'
import type { TaskPreview } from '@/api/generated/model'
import { GoalForm } from '@/components/GoalForm'
import { TaskReviewList } from '@/components/TaskReviewList'
import { Alert, AlertDescription } from '@/components/ui/alert'

export const Route = createFileRoute('/new')({
  component: NewProjectPage,
})

function NewProjectPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState<'goal' | 'review'>('goal')
  const [goalText, setGoalText] = useState('')
  const [deadline, setDeadline] = useState<string | undefined>(undefined)
  const [tasks, setTasks] = useState<TaskPreview[]>([])

  const previewMutation = usePreviewProject()
  const createMutation = useCreateProject()

  const handlePreview = (goal: string, dl: string | undefined) => {
    setGoalText(goal)
    setDeadline(dl)
    previewMutation.mutate(
      { data: { goal_text: goal, deadline: dl ?? null } },
      {
        onSuccess: (response) => {
          setTasks(response.tasks)
          setStep('review')
        },
      },
    )
  }

  const handleConfirm = () => {
    createMutation.mutate(
      { data: { goal_text: goalText, deadline: deadline ?? null, tasks } },
      {
        onSuccess: (project) => {
          navigate({
            to: '/projects/$projectId',
            params: { projectId: project.id },
          })
        },
      },
    )
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      {step === 'goal' ? (
        <>
          <h1 className="text-2xl font-semibold">ゴールを入力してください</h1>
          {previewMutation.isError && (
            <Alert variant="destructive" className="mt-4">
              <AlertDescription>
                タスク分解に失敗しました。もう一度お試しください。
              </AlertDescription>
            </Alert>
          )}
          <GoalForm
            onSubmit={handlePreview}
            isSubmitting={previewMutation.isPending}
          />
        </>
      ) : (
        <>
          <h1 className="text-2xl font-semibold">
            タスクを確認・編集してください
          </h1>
          {createMutation.isError && (
            <Alert variant="destructive" className="mt-4">
              <AlertDescription>
                プロジェクトの作成に失敗しました。もう一度お試しください。
              </AlertDescription>
            </Alert>
          )}
          <TaskReviewList
            tasks={tasks}
            onChange={setTasks}
            onConfirm={handleConfirm}
            isSubmitting={createMutation.isPending}
          />
        </>
      )}
    </main>
  )
}
