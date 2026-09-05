# xincere-hackathon

Human Time Hack ― CPMベースの動的タスク再計画アプリ。詳細な要件は `docs/requirements/cpm-dynamic-replanning.md`、AI向けに分割したルールは `.claude/rules/` を参照。

## 構成

```
backend/    FastAPI + uv (AIタスク分解・CPM計算・Supabase永続化)
frontend/   React + Vite + TanStack Query/Router + shadcn/ui
supabase/   DBマイグレーション (Supabase CLI)
```

## 前提ツール

- [uv](https://docs.astral.sh/uv/)（`brew install uv`）
- Node.js 24+ / npm
- [Supabase CLI](https://supabase.com/docs/guides/cli)（`brew install supabase/tap/supabase`）
- Anthropic APIキー（`sk-ant-...`）
- Supabaseプロジェクト（ローカルSupabase or ホスティング済みプロジェクトのURL/キー）

## Supabase

このリポジトリのSupabaseプロジェクトにリンクしてマイグレーションを取得・適用する場合:

```bash
supabase login
supabase link --project-ref <project-ref>
supabase db push --linked
```

ローカルでDocker経由のSupabaseを使う場合は `supabase start` で起動する（`tech-stack.md` 参照）。

## バックエンド (`backend/`)

```bash
cd backend
uv sync                    # 依存関係インストール(仮想環境も自動作成)
cp .env.example .env       # 値を埋める(下記参照)
uv run pytest -q           # テスト
uv run ruff check .        # lint
uv run uvicorn backend.main:app --reload --port 8000
```

`.env` に設定する値:

| 変数 | 取得元 |
|---|---|
| `SUPABASE_URL` | Supabaseダッシュボード → Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | 同上(secret) |
| `SUPABASE_JWT_SECRET` | 同上 → JWT Settings（legacy HS256シークレットを有効化しておくこと。`.claude/rules/auth-and-data-isolation.md` 参照） |
| `ANTHROPIC_API_KEY` | Anthropic Console |
| `ANTHROPIC_MODEL` | 任意。既定値は `claude-sonnet-4-5`。最新のモデルIDは [docs.claude.com](https://docs.claude.com/en/docs/about-claude/models) で確認 |
| `CORS_ALLOW_ORIGINS` | フロントエンドのオリジンをJSON配列で指定。既定値は `["http://localhost:5173"]` |

起動後 http://localhost:8000/health が `{"status":"ok"}` を返せば起動成功。API仕様は http://localhost:8000/docs (Swagger UI)。

## フロントエンド (`frontend/`)

```bash
cd frontend
npm install
cp .env.example .env        # 値を埋める(下記参照)
npm run dev                 # http://localhost:5173
npm run lint                # biome check
npm run build                # 型チェック + ビルド
```

`.env` に設定する値:

| 変数 | 取得元 |
|---|---|
| `VITE_SUPABASE_URL` | バックエンドと同じSupabaseプロジェクトのURL |
| `VITE_SUPABASE_ANON_KEY` | Supabaseダッシュボード → Settings → API の `anon`/`publishable` キー |
| `VITE_API_BASE_URL` | ローカルバックエンドのURL。既定値 `http://localhost:8000` |

## デプロイ先(参考)

- バックエンド: Railway（`backend/` をルートにデプロイ。`uv run uvicorn backend.main:app --host 0.0.0.0 --port $PORT` をstart commandとして設定）
- フロントエンド: Vercel
- DB/Auth: Supabase(ホスティング済みプロジェクト)
