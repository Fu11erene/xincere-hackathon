import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'
import { useListProjects } from '@/api/generated/endpoints'
import { Alert, AlertDescription } from '@/components/ui/alert'

export const Route = createFileRoute('/')({
  component: IndexRedirect,
})

function IndexRedirect() {
  const navigate = useNavigate()
  const { data: projects, isLoading, isError } = useListProjects()

  useEffect(() => {
    if (isLoading || isError || !projects) return
    if (projects.length === 0) {
      navigate({ to: '/new' })
      return
    }
    const latest = [...projects].sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )[0]
    navigate({ to: '/projects/$projectId', params: { projectId: latest.id } })
  }, [projects, isLoading, isError, navigate])

  if (isError) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <Alert variant="destructive">
          <AlertDescription>
            プロジェクト一覧の取得に失敗しました。時間をおいて再度お試しください。
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
      読み込み中...
    </div>
  )
}
