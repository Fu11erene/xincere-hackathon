import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createRootRoute,
  Outlet,
  useNavigate,
  useRouterState,
} from '@tanstack/react-router'
import { type ReactNode, useEffect } from 'react'
import { Toaster } from '@/components/ui/sonner'
import { AuthProvider, useAuth } from '@/lib/auth'

const queryClient = new QueryClient()

export const Route = createRootRoute({
  component: RootComponent,
})

function RootComponent() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AuthGate>
          <Outlet />
        </AuthGate>
        <Toaster />
      </AuthProvider>
    </QueryClientProvider>
  )
}

function AuthGate({ children }: { children: ReactNode }) {
  const { session, isLoading } = useAuth()
  const navigate = useNavigate()
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const isLoginRoute = pathname === '/login'

  useEffect(() => {
    if (isLoading) return
    if (!session && !isLoginRoute) {
      navigate({ to: '/login' })
    }
    if (session && isLoginRoute) {
      navigate({ to: '/' })
    }
  }, [session, isLoading, isLoginRoute, navigate])

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        読み込み中...
      </div>
    )
  }

  if (!session && !isLoginRoute) {
    return null
  }

  return <>{children}</>
}
