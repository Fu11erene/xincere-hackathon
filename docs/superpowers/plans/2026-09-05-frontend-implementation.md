# フロントエンド実装 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `frontend/`にHuman Time Hack MVPの4画面（ゴール入力→タスク確認編集、今日やるべきことダッシュボード、補助全体ビュー）と認証(Supabase Google OAuth)、backend APIとの型安全な連携(orval)を実装する。

**Architecture:** TanStack Routerのファイルベースルーティングに4ルートを追加し、`__root.tsx`でSupabaseセッションによる認証ガードを行う。APIはbackendのOpenAPI仕様からorvalでTanStack Query対応フックを自動生成し、axiosベースのカスタムmutatorでJWT付与と401ハンドリングを行う。サーバー状態はTanStack Queryのみで管理し、ゴール→レビューの2ステップはローカルuseStateで完結させる。

**Tech Stack:** React 19, TanStack Router/Query, Vite, Tailwind v4 + shadcn(radix-nova), `@supabase/supabase-js`, `axios`, `orval`

**Spec:** `docs/superpowers/specs/2026-09-05-frontend-implementation-design.md`

## Global Constraints

- ルーティングはTanStack Routerのファイルベース規約(`frontend/src/routes/`)に従う。ルート追加後は`vite dev`のプラグイン(`tanstackRouter`)が`routeTree.gen.ts`を自動生成するため、手動編集しない
- コードスタイルは既存コード(`frontend/src/components/ui/button.tsx`等)に合わせる: セミコロンなし、シングルクォート、2スペースインデント(biome設定に準拠)。各タスク末尾で`cd frontend && npx biome check --write .`を実行して整形する
- `tsconfig.app.json`で`verbatimModuleSyntax: true`が有効なため、型のみのimportは必ず`import type { ... } from '...'`と書く
- UI文言はすべて日本語(`.claude/rules/ui-screens.md`のスクリーン定義・既存コードの文言に準拠)
- 画面固有コンポーネントは`frontend/src/components/`直下に1コンポーネント1ファイルで作成する(既存の`components/ui/`とは分離)
- 各タスクの型チェックは `cd frontend && npx tsc --noEmit -p tsconfig.app.json` で行う(既存にvitest等のテストランナーはなく、新規に導入しない。spec「テスト方針」節に準拠)
- backendは`cd backend && uv run fastapi dev src/backend/main.py`でSupabase/Anthropicキー未設定でも起動できることを確認済み(`config.py`のデフォルト値が空文字のため)。orval生成時のみbackendを起動する

---

## ファイル構成

**新規作成:**
- `frontend/src/lib/supabase.ts` — Supabaseクライアントのシングルトン
- `frontend/src/lib/auth.tsx` — `AuthProvider` / `useAuth()`
- `frontend/src/api/mutator.ts` — orval用axiosカスタムインスタンス(JWT付与・401ハンドリング)
- `frontend/orval.config.ts` — orval設定
- `frontend/src/api/generated/` — orval自動生成コード(型 + TanStack Queryフック)
- `frontend/src/routes/login.tsx` — ログイン画面
- `frontend/src/routes/new.tsx` — ゴール入力+タスク確認編集(2ステップ)
- `frontend/src/routes/projects.$projectId.tsx` — 今日やるべきことダッシュボード
- `frontend/src/routes/projects.$projectId.overview.tsx` — 補助全体ビュー
- `frontend/src/components/GoalForm.tsx`
- `frontend/src/components/TaskEditRow.tsx`
- `frontend/src/components/TaskReviewList.tsx`
- `frontend/src/components/TaskCard.tsx`
- `frontend/src/components/OverviewTaskRow.tsx`
- `frontend/src/components/ui/card.tsx`, `input.tsx`, `textarea.tsx`, `label.tsx`, `badge.tsx`, `skeleton.tsx`, `sonner.tsx`, `alert.tsx` — shadcn CLIで追加
- `frontend/.env` — ローカル専用(コミットしない。`.env.example`から作成)

**変更:**
- `frontend/src/routes/__root.tsx` — `AuthProvider`と認証ガードの組み込み、`Toaster`追加
- `frontend/src/routes/index.tsx` — プロジェクト一覧を見て`/new`または最新プロジェクトへリダイレクト
- `frontend/package.json` — 依存追加、`generate:api`スクリプト追加
- `backend/src/backend/routers/projects.py`, `backend/src/backend/routers/tasks.py` — 各エンドポイントに明示的な`operation_id`を追加(orvalが生成する関数名・フック名を安定させるため)

---

### Task 1: 依存関係とローカル環境のセットアップ

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/.env`(gitignore対象、コミットしない)

**Interfaces:**
- Produces: `@supabase/supabase-js`, `axios`が`dependencies`に、`orval`が`devDependencies`に追加された状態

- [ ] **Step 1: 依存関係を追加する**

```bash
cd frontend
npm install @supabase/supabase-js axios
npm install -D orval
```

- [ ] **Step 2: `.env`をローカル用に作成する**

```bash
cp frontend/.env.example frontend/.env
```

`frontend/.gitignore`に`.env`が含まれていることを確認する(含まれていなければ追記する)。

```bash
grep -n "^\.env$" frontend/.gitignore || echo ".env" >> frontend/.gitignore
```

- [ ] **Step 3: 開発サーバーが起動することを確認する**

```bash
cd frontend && npm run dev
```

ブラウザで`http://localhost:5173`にアクセスし、既存のプレースホルダー画面が表示されることを確認したらサーバーを停止する(Ctrl+C)。

- [ ] **Step 4: コミット**

```bash
git add frontend/package.json frontend/package-lock.json frontend/.gitignore
git commit -m "chore(frontend): add supabase/axios/orval dependencies

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013H7BVdvY5BjDagekk6F7no"
```

---

### Task 2: Supabaseクライアントと認証コンテキスト

**Files:**
- Create: `frontend/src/lib/supabase.ts`
- Create: `frontend/src/lib/auth.tsx`

**Interfaces:**
- Consumes: `import.meta.env.VITE_SUPABASE_URL`, `import.meta.env.VITE_SUPABASE_ANON_KEY`(Task 1で作成した`.env`)
- Produces: `supabase`(`SupabaseClient`インスタンス、`frontend/src/lib/supabase.ts`からexport)、`AuthProvider`コンポーネントと`useAuth(): { session: Session | null; isLoading: boolean }`フック(`frontend/src/lib/auth.tsx`からexport)。後続タスクはこの2つの名前・型をそのまま利用する

- [ ] **Step 1: `supabase.ts`を作成する**

```ts
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
)
```

- [ ] **Step 2: `auth.tsx`を作成する**

```tsx
import type { Session } from '@supabase/supabase-js'
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { supabase } from '@/lib/supabase'

interface AuthContextValue {
  session: Session | null
  isLoading: boolean
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setIsLoading(false)
    })

    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession)
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  return <AuthContext.Provider value={{ session, isLoading }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
```

- [ ] **Step 3: 型チェック**

```bash
cd frontend && npx tsc --noEmit -p tsconfig.app.json
```

Expected: エラーなし

- [ ] **Step 4: フォーマットしてコミット**

```bash
cd frontend && npx biome check --write src/lib/supabase.ts src/lib/auth.tsx
git add frontend/src/lib/supabase.ts frontend/src/lib/auth.tsx
git commit -m "feat(frontend): add supabase client and auth context

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013H7BVdvY5BjDagekk6F7no"
```

---

### Task 3: ログイン画面と認証ガード

**Files:**
- Create: `frontend/src/routes/login.tsx`
- Modify: `frontend/src/routes/__root.tsx`

**Interfaces:**
- Consumes: `AuthProvider`, `useAuth`(Task 2)、`supabase`(Task 2)
- Produces: `/login`ルート。`__root.tsx`は未ログイン時に`/login`以外へのアクセスを`/login`へリダイレクトし、ログイン済みで`/login`にいる場合は`/`へリダイレクトする

- [ ] **Step 1: `login.tsx`を作成する**

```tsx
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
```

- [ ] **Step 2: `__root.tsx`に認証ガードを組み込む**

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createRootRoute, Outlet, useNavigate, useRouterState } from '@tanstack/react-router'
import { useEffect, type ReactNode } from 'react'
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
      </AuthProvider>
    </QueryClientProvider>
  )
}

function AuthGate({ children }: { children: ReactNode }) {
  const { session, isLoading } = useAuth()
  const navigate = useNavigate()
  const pathname = useRouterState({ select: (state) => state.location.pathname })
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
```

- [ ] **Step 3: 型チェック**

```bash
cd frontend && npx tsc --noEmit -p tsconfig.app.json
```

Expected: エラーなし

- [ ] **Step 4: ブラウザで確認する**

`.env`の`VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY`が未設定の場合、Supabaseクライアントは初期化されるがセッションは常に`null`になる。`npm run dev`で起動し、どのパスにアクセスしても`/login`にリダイレクトされ「Googleでログイン」ボタンが表示されることを確認する。

- [ ] **Step 5: フォーマットしてコミット**

```bash
cd frontend && npx biome check --write src/routes/login.tsx src/routes/__root.tsx
git add frontend/src/routes/login.tsx frontend/src/routes/__root.tsx
git commit -m "feat(frontend): add login screen and auth guard

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013H7BVdvY5BjDagekk6F7no"
```

---

### Task 4: backendのoperation_id付与とorvalによるAPIクライアント生成

**Files:**
- Modify: `backend/src/backend/routers/projects.py`
- Modify: `backend/src/backend/routers/tasks.py`
- Create: `frontend/orval.config.ts`
- Create: `frontend/src/api/mutator.ts`
- Create: `frontend/src/api/generated/`(orval自動生成、コミット対象)
- Modify: `frontend/package.json`(`generate:api`スクリプト追加)

**Interfaces:**
- Consumes: `supabase`(Task 2, JWT取得用)、`import.meta.env.VITE_API_BASE_URL`
- Produces: 生成フック `usePreviewProject`, `useCreateProject`, `useListProjects`, `useGetProject`, `useGetProjectSchedule`, `useRecordTaskEvent` と、クエリキー取得関数 `getGetProjectScheduleQueryKey(projectId)`。型 `TaskPreview`, `ProjectPreviewRequest`, `ProjectPreviewResponse`, `ProjectCreateRequest`, `TaskResponse`, `ProjectSummary`, `ProjectDetail`, `ScheduledTask`, `ScheduleResponse`, `ProgressEventRequest`。**注意:** これらはorvalのreact-queryモードの標準命名規則(`use` + PascalCase(operationId)、`get` + PascalCase(operationId) + `QueryKey`)に基づく想定値。Step 5の確認で実際の生成結果と異なっていた場合は、以降のタスクではこのステップで確認した実際の名前を使うこと

- [ ] **Step 1: backendの各エンドポイントに`operation_id`を追加する**

`backend/src/backend/routers/projects.py`の各デコレータを以下のように変更する:

```python
@router.post("/preview", response_model=ProjectPreviewResponse, operation_id="previewProject")
```

```python
@router.post("", response_model=ProjectDetail, status_code=201, operation_id="createProject")
```

```python
@router.get("", response_model=list[ProjectSummary], operation_id="listProjects")
```

```python
@router.get("/{project_id}", response_model=ProjectDetail, operation_id="getProject")
```

```python
@router.get("/{project_id}/schedule", response_model=ScheduleResponse, operation_id="getProjectSchedule")
```

`backend/src/backend/routers/tasks.py`のデコレータを以下のように変更する:

```python
@router.post("/{task_id}/events", response_model=TaskResponse, operation_id="recordTaskEvent")
```

- [ ] **Step 2: backendのテストが引き続き通ることを確認する**

```bash
cd backend && uv run pytest
```

Expected: すべてPASS(`operation_id`追加は挙動を変えないため既存テストに影響しない)

- [ ] **Step 3: backendをローカル起動する(別ターミナル、以降のステップの間起動したままにする)**

```bash
cd backend && uv run fastapi dev src/backend/main.py
```

`http://localhost:8000/openapi.json`がレスポンスを返すことを確認する。

- [ ] **Step 4: `orval.config.ts`を作成する**

```ts
import { defineConfig } from 'orval'

export default defineConfig({
  api: {
    input: 'http://localhost:8000/openapi.json',
    output: {
      mode: 'single',
      target: 'src/api/generated/endpoints.ts',
      schemas: 'src/api/generated/model',
      client: 'react-query',
      override: {
        mutator: {
          path: 'src/api/mutator.ts',
          name: 'customInstance',
        },
      },
    },
  },
})
```

- [ ] **Step 5: `mutator.ts`を作成する**

```ts
import axios, { type AxiosError, type AxiosRequestConfig } from 'axios'
import { supabase } from '@/lib/supabase'

const axiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
})

axiosInstance.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

axiosInstance.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    if (error.response?.status === 401) {
      await supabase.auth.signOut()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export const customInstance = <T>(config: AxiosRequestConfig): Promise<T> => {
  return axiosInstance(config).then((response) => response.data)
}
```

- [ ] **Step 6: `package.json`に生成スクリプトを追加する**

`frontend/package.json`の`scripts`に以下を追加する:

```json
"generate:api": "orval"
```

- [ ] **Step 7: コードを生成し、実際の命名を確認する**

```bash
cd frontend && npm run generate:api
```

生成された`src/api/generated/endpoints.ts`を開き、以下を確認する:

```bash
grep -n "^export const use\|^export const get.*QueryKey" frontend/src/api/generated/endpoints.ts
```

期待される出力に`usePreviewProject`, `useCreateProject`, `useListProjects`, `useGetProject`, `useGetProjectSchedule`, `useRecordTaskEvent`, `getGetProjectScheduleQueryKey`が含まれることを確認する。含まれない場合は実際の名前を控えておき、Task 6〜10で該当箇所を実際の名前に置き換える。

- [ ] **Step 8: 型チェックとビルド確認**

```bash
cd frontend && npx tsc --noEmit -p tsconfig.app.json
```

Expected: エラーなし(生成コードに問題があればmutatorの型シグネチャを実際の生成結果に合わせて調整する)

- [ ] **Step 9: フォーマットしてコミット**

```bash
cd frontend && npx biome check --write orval.config.ts src/api/mutator.ts src/api/generated package.json
git add backend/src/backend/routers/projects.py backend/src/backend/routers/tasks.py \
  frontend/orval.config.ts frontend/src/api/mutator.ts frontend/src/api/generated frontend/package.json
git commit -m "feat: add operation_id to backend routes and generate typed api client via orval

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013H7BVdvY5BjDagekk6F7no"
```

---

### Task 5: shadcn UIコンポーネントの追加

**Files:**
- Create: `frontend/src/components/ui/card.tsx`, `input.tsx`, `textarea.tsx`, `label.tsx`, `badge.tsx`, `skeleton.tsx`, `sonner.tsx`, `alert.tsx`
- Modify: `frontend/src/routes/__root.tsx`(`Toaster`追加)

**Interfaces:**
- Produces: `Card`/`CardHeader`/`CardTitle`/`CardContent`(`card.tsx`)、`Input`(`input.tsx`)、`Textarea`(`textarea.tsx`)、`Label`(`label.tsx`)、`Badge`(`badge.tsx`)、`Skeleton`(`skeleton.tsx`)、`Toaster`(`sonner.tsx`)、`Alert`/`AlertDescription`(`alert.tsx`)。後続タスクはこれらの名前をそのままimportして使う

- [ ] **Step 1: shadcn CLIでコンポーネントを追加する**

```bash
cd frontend
npx shadcn@latest add card input textarea label badge skeleton sonner alert
```

- [ ] **Step 2: 実際にexportされているコンポーネント名を確認する**

```bash
grep -n "^export" frontend/src/components/ui/card.tsx frontend/src/components/ui/alert.tsx
```

`Card`, `CardHeader`, `CardTitle`, `CardContent`, `Alert`, `AlertDescription`が含まれることを確認する(shadcnのバージョンにより`CardAction`等が追加されていても問題ない)。含まれない、または名前が異なる場合は控えておき、Task 8〜9で実際の名前に置き換える。

- [ ] **Step 3: `__root.tsx`に`Toaster`を追加する**

`frontend/src/routes/__root.tsx`の`RootComponent`を以下のように変更する(`AuthGate`の兄弟要素として追加):

```tsx
import { Toaster } from '@/components/ui/sonner'
```

```tsx
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
```

- [ ] **Step 4: 型チェック**

```bash
cd frontend && npx tsc --noEmit -p tsconfig.app.json
```

Expected: エラーなし

- [ ] **Step 5: コミット**

```bash
cd frontend && npx biome check --write src/components/ui src/routes/__root.tsx
git add frontend/src/components/ui frontend/src/routes/__root.tsx
git commit -m "feat(frontend): add shadcn card/input/textarea/label/badge/skeleton/sonner/alert components

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013H7BVdvY5BjDagekk6F7no"
```

---

### Task 6: ルート`/`のリダイレクトロジック

**Files:**
- Modify: `frontend/src/routes/index.tsx`

**Interfaces:**
- Consumes: `useListProjects()`(Task 4。`ProjectSummary[]`を`data`として返すuseQuery)
- Produces: `/`は常に`/new`または`/projects/$projectId`へリダイレクトする(直接表示されるUIを持たない)

- [ ] **Step 1: `index.tsx`を書き換える**

```tsx
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
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )[0]
    navigate({ to: '/projects/$projectId', params: { projectId: latest.id } })
  }, [projects, isLoading, navigate])

  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
      読み込み中...
    </div>
  )
}
```

- [ ] **Step 2: 型チェック**

```bash
cd frontend && npx tsc --noEmit -p tsconfig.app.json
```

Expected: エラーなし

- [ ] **Step 3: コミット**

```bash
cd frontend && npx biome check --write src/routes/index.tsx
git add frontend/src/routes/index.tsx
git commit -m "feat(frontend): redirect root route to newest project or goal input

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013H7BVdvY5BjDagekk6F7no"
```

---

### Task 7: ゴール入力フォーム(`GoalForm`)

**Files:**
- Create: `frontend/src/components/GoalForm.tsx`

**Interfaces:**
- Produces: `GoalForm({ onSubmit: (goalText: string, deadline: string | undefined) => void; isSubmitting: boolean })`。Task 8がこのpropsシグネチャをそのまま利用する

- [ ] **Step 1: `GoalForm.tsx`を作成する**

```tsx
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
```

- [ ] **Step 2: 型チェック**

```bash
cd frontend && npx tsc --noEmit -p tsconfig.app.json
```

Expected: エラーなし

- [ ] **Step 3: コミット**

```bash
cd frontend && npx biome check --write src/components/GoalForm.tsx
git add frontend/src/components/GoalForm.tsx
git commit -m "feat(frontend): add goal input form component

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013H7BVdvY5BjDagekk6F7no"
```

---

### Task 8: タスク確認・編集(`TaskEditRow`, `TaskReviewList`)と`/new`ルート

**Files:**
- Create: `frontend/src/components/TaskEditRow.tsx`
- Create: `frontend/src/components/TaskReviewList.tsx`
- Create: `frontend/src/routes/new.tsx`

**Interfaces:**
- Consumes: `GoalForm`(Task 7)、`usePreviewProject`, `useCreateProject`(Task 4)、`TaskPreview`型(Task 4)、`Alert`/`AlertDescription`(Task 5)
- Produces: `/new`ルート。確定成功時に`/projects/$projectId`へ遷移する

- [ ] **Step 1: `TaskEditRow.tsx`を作成する**

```tsx
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { TaskPreview } from '@/api/generated/model'

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
          onChange({ ...task, estimated_duration_hours: Number(event.target.value) })
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
```

- [ ] **Step 2: `TaskReviewList.tsx`を作成する**

```tsx
import { Button } from '@/components/ui/button'
import { TaskEditRow } from '@/components/TaskEditRow'
import type { TaskPreview } from '@/api/generated/model'

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
        depends_on: task.depends_on.filter((id) => id !== removedId),
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
```

- [ ] **Step 3: `new.tsx`ルートを作成する**

```tsx
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { useCreateProject, usePreviewProject } from '@/api/generated/endpoints'
import type { TaskPreview } from '@/api/generated/model'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { GoalForm } from '@/components/GoalForm'
import { TaskReviewList } from '@/components/TaskReviewList'

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
          navigate({ to: '/projects/$projectId', params: { projectId: project.id } })
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
          <GoalForm onSubmit={handlePreview} isSubmitting={previewMutation.isPending} />
        </>
      ) : (
        <>
          <h1 className="text-2xl font-semibold">タスクを確認・編集してください</h1>
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
```

- [ ] **Step 4: 型チェック**

```bash
cd frontend && npx tsc --noEmit -p tsconfig.app.json
```

Expected: エラーなし。orvalが生成したミューテーションフックの引数型が想定と異なる場合(例: `{data: ...}`ではなく別の形)、生成された`endpoints.ts`内の該当関数の型定義を確認し、`handlePreview`/`handleConfirm`の`mutate`呼び出しを実際の型に合わせて修正する

- [ ] **Step 5: ブラウザで確認する**

backendを起動した状態(`cd backend && uv run fastapi dev src/backend/main.py`)で`npm run dev`を起動し、`.env`にAnthropic/Supabaseキーを設定していれば、ログイン→`/new`でゴールを入力→「タスクに分解する」→レビュー画面が表示されることを確認する。キー未設定の場合は、AI呼び出しがエラーになりAlertが表示されることを確認する(エラーハンドリングの動作確認として許容する)。

- [ ] **Step 6: コミット**

```bash
cd frontend && npx biome check --write src/components/TaskEditRow.tsx src/components/TaskReviewList.tsx src/routes/new.tsx
git add frontend/src/components/TaskEditRow.tsx frontend/src/components/TaskReviewList.tsx frontend/src/routes/new.tsx
git commit -m "feat(frontend): add goal-to-task review flow (/new)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013H7BVdvY5BjDagekk6F7no"
```

---

### Task 9: 今日やるべきことダッシュボード(`TaskCard`)と`/projects/$projectId`ルート

**Files:**
- Create: `frontend/src/components/TaskCard.tsx`
- Create: `frontend/src/routes/projects.$projectId.tsx`

**Interfaces:**
- Consumes: `useGetProjectSchedule`, `useRecordTaskEvent`, `getGetProjectScheduleQueryKey`(Task 4)、`ScheduledTask`型(Task 4)、`Card`系, `Badge`, `Skeleton`(Task 5)
- Produces: `/projects/$projectId`ルート。完了/スキップ記録後に`/projects/{id}/schedule`のqueryを再取得する

- [ ] **Step 1: `TaskCard.tsx`を作成する**

```tsx
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ScheduledTask } from '@/api/generated/model'

interface TaskCardProps {
  task: ScheduledTask
  onEvent: (taskId: string, eventType: 'complete' | 'skip') => void
}

export function TaskCard({ task, onEvent }: TaskCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="text-base">{task.name}</CardTitle>
        {task.is_critical && <Badge variant="destructive">クリティカルパス</Badge>}
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          残り見積もり: 約{task.current_estimated_duration_hours.toFixed(1)}時間
        </p>
        <div className="mt-3 flex gap-2">
          <Button size="sm" onClick={() => onEvent(task.id, 'complete')}>
            完了
          </Button>
          <Button size="sm" variant="outline" onClick={() => onEvent(task.id, 'skip')}>
            後回し
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 2: `projects.$projectId.tsx`ルートを作成する**

```tsx
import { useQueryClient } from '@tanstack/react-query'
import { createFileRoute, Link } from '@tanstack/react-router'
import {
  getGetProjectScheduleQueryKey,
  useGetProjectSchedule,
  useRecordTaskEvent,
} from '@/api/generated/endpoints'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { TaskCard } from '@/components/TaskCard'

export const Route = createFileRoute('/projects/$projectId')({
  component: DashboardPage,
})

function DashboardPage() {
  const { projectId } = Route.useParams()
  const queryClient = useQueryClient()
  const { data: schedule, isLoading } = useGetProjectSchedule(projectId)
  const eventMutation = useRecordTaskEvent()

  const handleEvent = (taskId: string, eventType: 'complete' | 'skip') => {
    eventMutation.mutate(
      { taskId, data: { event_type: eventType } },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: getGetProjectScheduleQueryKey(projectId) })
        },
      },
    )
  }

  if (isLoading || !schedule) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-4 h-32 w-full" />
      </main>
    )
  }

  const now = new Date()
  const endOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59)
  const todayTasks = schedule.tasks
    .filter((task) => task.status === 'todo' || task.status === 'in_progress')
    .filter((task) => new Date(task.earliest_start) <= endOfToday)
    .sort((a, b) => {
      if (a.is_critical !== b.is_critical) return a.is_critical ? -1 : 1
      return new Date(a.earliest_start).getTime() - new Date(b.earliest_start).getTime()
    })

  return (
    <main className="mx-auto max-w-2xl p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">今日やるべきこと</h1>
        <Button variant="outline" size="sm" asChild>
          <Link to="/projects/$projectId/overview" params={{ projectId }}>
            全体を見る
          </Link>
        </Button>
      </div>
      {todayTasks.length === 0 ? (
        <p className="mt-6 text-sm text-muted-foreground">
          今日着手すべきタスクはありません。お疲れさまです。
        </p>
      ) : (
        <div className="mt-6 flex flex-col gap-3">
          {todayTasks.map((task) => (
            <TaskCard key={task.id} task={task} onEvent={handleEvent} />
          ))}
        </div>
      )}
    </main>
  )
}
```

- [ ] **Step 3: 型チェック**

```bash
cd frontend && npx tsc --noEmit -p tsconfig.app.json
```

Expected: エラーなし。`useRecordTaskEvent`の`mutate`引数の実際のキー名(`taskId`ではない可能性)は生成コードを確認して合わせる

- [ ] **Step 4: コミット**

```bash
cd frontend && npx biome check --write src/components/TaskCard.tsx src/routes/projects.\$projectId.tsx
git add frontend/src/components/TaskCard.tsx "frontend/src/routes/projects.\$projectId.tsx"
git commit -m "feat(frontend): add today dashboard (/projects/:id)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013H7BVdvY5BjDagekk6F7no"
```

---

### Task 10: 補助全体ビュー(`OverviewTaskRow`)と`/projects/$projectId/overview`ルート

**Files:**
- Create: `frontend/src/components/OverviewTaskRow.tsx`
- Create: `frontend/src/routes/projects.$projectId.overview.tsx`

**Interfaces:**
- Consumes: `useGetProjectSchedule`(Task 4)、`ScheduledTask`型(Task 4)、`Badge`(Task 5)、`cn`(`@/lib/utils`、既存)
- Produces: `/projects/$projectId/overview`ルート

- [ ] **Step 1: `OverviewTaskRow.tsx`を作成する**

```tsx
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { ScheduledTask } from '@/api/generated/model'

interface OverviewTaskRowProps {
  task: ScheduledTask
  maxDurationHours: number
}

export function OverviewTaskRow({ task, maxDurationHours }: OverviewTaskRowProps) {
  const slackDays = task.slack_hours / 24
  const slackLabel = task.is_critical ? 'スラックなし' : `余裕: ${slackDays.toFixed(1)}日`
  const barWidthPercent = Math.max(
    (task.current_estimated_duration_hours / maxDurationHours) * 100,
    4,
  )

  return (
    <div
      className={cn(
        'rounded-md border-l-4 bg-card p-3',
        task.is_critical ? 'border-l-destructive' : 'border-l-border',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{task.name}</span>
        {task.is_critical && <Badge variant="destructive">クリティカルパス</Badge>}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{slackLabel}</p>
      <div className="mt-2 h-2 rounded-full bg-muted">
        <div className="h-2 rounded-full bg-primary" style={{ width: `${barWidthPercent}%` }} />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: `projects.$projectId.overview.tsx`ルートを作成する**

```tsx
import { createFileRoute, Link } from '@tanstack/react-router'
import { useGetProjectSchedule } from '@/api/generated/endpoints'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { OverviewTaskRow } from '@/components/OverviewTaskRow'

export const Route = createFileRoute('/projects/$projectId/overview')({
  component: OverviewPage,
})

function OverviewPage() {
  const { projectId } = Route.useParams()
  const { data: schedule, isLoading } = useGetProjectSchedule(projectId)

  if (isLoading || !schedule) {
    return (
      <main className="mx-auto max-w-3xl p-8">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="mt-4 h-64 w-full" />
      </main>
    )
  }

  const sortedTasks = [...schedule.tasks].sort(
    (a, b) => new Date(a.earliest_start).getTime() - new Date(b.earliest_start).getTime(),
  )
  const maxDuration = Math.max(...sortedTasks.map((t) => t.current_estimated_duration_hours), 1)

  return (
    <main className="mx-auto max-w-3xl p-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">プロジェクト全体ビュー</h1>
        <Button variant="outline" size="sm" asChild>
          <Link to="/projects/$projectId" params={{ projectId }}>
            今日やるべきことに戻る
          </Link>
        </Button>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">
        完了予定: {new Date(schedule.projected_completion_at).toLocaleString('ja-JP')}
      </p>
      <div className="mt-6 flex flex-col gap-2">
        {sortedTasks.map((task) => (
          <OverviewTaskRow key={task.id} task={task} maxDurationHours={maxDuration} />
        ))}
      </div>
    </main>
  )
}
```

- [ ] **Step 3: 型チェック**

```bash
cd frontend && npx tsc --noEmit -p tsconfig.app.json
```

Expected: エラーなし

- [ ] **Step 4: コミット**

```bash
cd frontend && npx biome check --write src/components/OverviewTaskRow.tsx src/routes/projects.\$projectId.overview.tsx
git add frontend/src/components/OverviewTaskRow.tsx "frontend/src/routes/projects.\$projectId.overview.tsx"
git commit -m "feat(frontend): add auxiliary full-project overview screen

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013H7BVdvY5BjDagekk6F7no"
```

---

### Task 11: 結合確認とビルド検証

**Files:**
- 変更なし(検証のみ)。問題が見つかった場合は該当ファイルを修正する

**Interfaces:**
- Consumes: Task 1〜10で作成したすべてのルート・コンポーネント・API連携

- [ ] **Step 1: ビルド確認**

```bash
cd frontend && npm run build
```

Expected: `tsc -b && vite build`がエラーなく完了する

- [ ] **Step 2: lintチェック**

```bash
cd frontend && npm run lint
```

Expected: エラーなし(警告があれば内容を確認し、明らかな問題は修正する)

- [ ] **Step 3: 実ブラウザでの一連の動線確認**

`.env`にSupabase/Anthropicの実キーを設定できる場合、以下を実施する(設定できない場合はログイン画面までの表示とリダイレクトの動作確認に留め、その旨を最終報告に明記する):

1. `cd backend && uv run fastapi dev src/backend/main.py`でbackend起動
2. `cd frontend && npm run dev`でfrontend起動
3. ブラウザで`http://localhost:5173`にアクセスし、`/login`にリダイレクトされることを確認
4. Googleログイン→`/new`にリダイレクトされることを確認(初回はプロジェクトが0件のため)
5. ゴールと締切を入力し「タスクに分解する」→タスク一覧が表示されることを確認
6. タスク名/時間を編集、1つ削除して「この内容で確定する」→ダッシュボード(`/projects/$id`)に遷移することを確認
7. タスクカードの「完了」または「後回し」を押し、表示が更新される(該当タスクが今日のリストから外れる、または残り時間が変わる)ことを確認
8. 「全体を見る」から補助ビューに遷移し、クリティカルパスのタスクに赤いボーダー/バッジが付き、スラックが表記され、比例バーが表示されることを確認

- [ ] **Step 4: 最終コミット(修正が発生した場合のみ)**

Step 1〜3で修正が発生した場合:

```bash
cd frontend && npx biome check --write .
git add frontend
git commit -m "fix(frontend): address build/lint/manual verification findings

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013H7BVdvY5BjDagekk6F7no"
```
