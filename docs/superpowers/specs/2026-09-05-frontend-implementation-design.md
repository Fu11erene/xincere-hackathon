# フロントエンド実装設計

出典: `/CLAUDE.md`, `.claude/rules/*`（特に `tech-stack.md`, `api-design.md`, `ui-screens.md`, `ai-task-decomposition.md`, `cpm-algorithm.md`, `auth-and-data-isolation.md`）

## 背景

`backend/` は既に4エンドポイント（`/projects/preview`, `/projects`, `/projects/{id}`, `/projects/{id}/schedule`, `/tasks/{id}/events`）とCPM計算ロジックが実装済み（`tasks/{id}/events`のみ501未実装）。`frontend/` はVite + React 19 + TanStack Router/Query + Tailwind v4 + shadcn(radix-nova style) のスキャフォールドのみで、画面は未実装。本設計はこのスキャフォールドの上に4画面を実装するもの。

## ルーティング構成（TanStack Router, ファイルベース）

| パス | 役割 |
|---|---|
| `/login` | Google OAuthログイン画面 |
| `/` | 起点。プロジェクト一覧取得→0件なら`/new`へ、1件以上なら最新プロジェクトの`/projects/$projectId`へリダイレクト |
| `/new` | 画面1(ゴール入力)+画面2(タスク確認・編集)を1ページの2ステップで実装 |
| `/projects/$projectId` | 画面3「今日やるべきこと」ダッシュボード（メイン画面） |
| `/projects/$projectId/overview` | 画面4 補助全体ビュー |

認証ガードは `src/routes/__root.tsx` の `beforeLoad` でSupabaseセッションを確認し、未ログインなら `/login` へリダイレクトする。

### `/new` の内部設計（プレビュー/確定分離）

api-design.mdの方針「編集画面自体はAPIを介さずクライアント側の状態だけで完結し、確定時に一度だけPOSTする」に従い、別ルートに分割せず単一コンポーネント内のuseState（`step: 'goal' | 'review'`, `previewTasks: TaskPreview[]`）で管理する。

1. ステップ`goal`: ゴール文＋締切（任意）を入力しPOST `/projects/preview`
2. ステップ`review`: 返ってきた`tasks[]`をローカルstateで保持し、名前・見積もり時間の微調整・タスク削除ができるようにする（依存関係はAI生成のまま表示、大幅な編集はスコープ外）
3. 確定時にPOST `/projects`し、成功したら作成された`project.id`で`/projects/$projectId`へ遷移

## API連携

`orval` を導入し、backendのOpenAPI仕様からTanStack Query対応フックを自動生成する。

- 設定ファイル: `frontend/orval.config.ts`
- 入力: backendをローカル起動して取得した `http://localhost:8000/openapi.json`（`uv run fastapi dev` などで、Supabase/Anthropicキー未設定でも起動可能なことを確認済み）
- 出力: `frontend/src/api/generated/`（型定義 + TanStack Queryフック）
- カスタムfetchインスタンス: `frontend/src/api/mutator.ts` で、Supabaseセッションから取得したJWTを`Authorization: Bearer`ヘッダに付与し、`import.meta.env.VITE_API_BASE_URL`をベースURLにする。401応答時はSupabaseサインアウト+`/login`へリダイレクトする
- `package.json`に `"generate:api": "orval"` スクリプトを追加
- MSWモックハンドラの生成・利用は今回のスコープ外（実バックエンドに接続して検証する方針）

## 認証（Supabase Auth / Google OAuth）

- `frontend/src/lib/supabase.ts`: `createClient(VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY)` を初期化するシングルトン
- `frontend/src/lib/auth.tsx`: `AuthProvider` + `useAuth()`。`supabase.auth.getSession()`初期取得＋`onAuthStateChange`購読でセッション状態を保持する
- `/login`: 「Googleでログイン」ボタン→`supabase.auth.signInWithOAuth({ provider: 'google' })`
- ルートの`beforeLoad`（もしくは`AuthProvider`のローディング完了後にコンポーネント側でリダイレクト）でセッション有無を判定

## コンポーネント

shadcn CLIで以下を追加: `card`, `input`, `textarea`, `label`, `badge`, `skeleton`, `sonner`（トースト）, `dropdown-menu`, `separator`, `alert`。

画面固有コンポーネント:

- `GoalForm`（`/new` ステップ1）
- `TaskReviewList` / `TaskEditRow`（`/new` ステップ2。タスク名・時間の編集、削除、依存関係の読み取り専用表示）
- `TaskCard`（ダッシュボード用。クリティカルパスバッジ、残り見積もり時間、完了/スキップのワンタップボタン）
- `OverviewTaskRow`（開始日順フラット一覧の1行。クリティカルパスは左ボーダー色＋バッジで強調、スラックをテキストで併記、見積もり時間に比例した幅のCSSバーを添える）

## 状態管理

- サーバー状態: TanStack Query（orval生成フック）のみ。Zustand等の追加ライブラリは導入しない
- `/tasks/{id}/events` のmutation成功時に `/projects/{id}/schedule` のqueryキーをinvalidateし、ダッシュボードのライブ再計算を反映する（React Queryのキャッシュ無効化。api-design.md/tech-stack.md記載の中核挙動）
- `/new`のゴール→レビューの2ステップ遷移はコンポーネントローカルのuseStateで完結させる

## エラー処理

- APIエラー（AI分解失敗、ネットワークエラー、409循環依存等）は`Alert`コンポーネントで画面内表示
- 401は`mutator.ts`内で捕捉しSupabaseサインアウト＋`/login`リダイレクト
- ローディング状態は`Skeleton`で表示

## テスト方針

フロントエンドに既存のテスト基盤（vitest等）がなく、tech-stack.mdもフロントエンドについては「ビルド確認のみ」をCIの最小構成としているため、新規にテストランナーは導入しない。実装後は`npm run dev`で実ブラウザ操作により以下の一連の動線を確認する:

1. ログイン→`/new`でゴール入力→プレビュー生成→軽微編集→確定→ダッシュボード遷移
2. ダッシュボードでタスクの完了/スキップを記録→スケジュールが再計算されて表示に反映されることを確認
3. 補助ビュー（`/overview`）でクリティカルパス強調・スラック表記・比例バーが表示されることを確認

## 環境変数

`frontend/.env.example`に既にある`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_BASE_URL`をそのまま使用する。実装者が自分のSupabaseプロジェクトの値を`.env`に設定する前提とし、未設定時はログイン画面が表示されるだけで以降には進めない（想定通りの挙動）。
