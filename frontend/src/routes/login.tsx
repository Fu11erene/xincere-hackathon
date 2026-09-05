import { createFileRoute } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { supabase } from '@/lib/supabase'

export const Route = createFileRoute('/login')({
  component: LoginPage,
})

function LoginPage() {
  const handleLogin = () => {
    supabase.auth.signInWithOAuth({ provider: 'google' })
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <div className="text-center">
        <h1 className="text-2xl font-semibold">Human Time Hack</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Googleアカウントでログインして、計画の立て直しをAIに任せましょう
        </p>
      </div>
      <Button onClick={handleLogin}>Googleでログイン</Button>
    </main>
  )
}
