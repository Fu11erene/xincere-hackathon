import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useEffect } from 'react'
import { useListProjects } from '@/api/generated/endpoints'

export const Route = createFileRoute('/')({
  component: IndexRedirect,
})

function IndexRedirect() {
  const navigate = useNavigate()
  const { data: projects, isLoading } = useListProjects()

  useEffect(() => {
    if (isLoading || !projects) return
    if (projects.length === 0) {
      navigate({ to: '/new' })
      return
    }
    const latest = [...projects].sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )[0]
    navigate({ to: '/projects/$projectId', params: { projectId: latest.id } })
  }, [projects, isLoading, navigate])

  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
      読み込み中...
    </div>
  )
}
