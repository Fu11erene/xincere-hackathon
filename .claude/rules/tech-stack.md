# 技術スタック

出典: `docs/requirements/cpm-dynamic-replanning.md`

デモは審査員自身がリンクから試せる形にする（発表者のローカル実行のみにはしない）ため、以下の構成とする。

- **フロントエンド**: React + Vite（軽量SPA）。デプロイ先はVercel
- **バックエンド**: FastAPI（Python）。CPM計算ロジック、進捗記録API、AIタスク分解の呼び出しを担当。デプロイ先はRenderまたはRailway
  - 補足: VercelはNext.js等のフロント／サーバーレス向けで常時稼働のPythonバックエンドとは相性が悪いため、フロントとバックエンドのデプロイ先を分ける
- **データベース**: Supabase（Postgres）。Task/Project/ProgressEventは依存関係を持つ関係データのため、NoSQLのFirestoreよりPostgresの方が素直に表現できる。FastAPIから`supabase-py`で接続
- **AI**: Claude API。[[ai-task-decomposition]] で定義したtool use（Structured Output）で構造化JSONを取得。呼び出しは`anthropic`公式Python SDKを使用
- **UIライブラリ/スタイリング**: Tailwind CSS + shadcn/ui
- **フロントの状態管理**: TanStack Query（React Query）。orvalが生成するフックと組み合わせ、進捗記録後の`/projects/{id}/schedule`再取得をキャッシュ無効化で実装する
- **バックエンドの設定管理**: `pydantic-settings`でAPIキー等の環境変数を管理
- **DBマイグレーション**: Supabase CLIでスキーマ変更を管理する
- **テスト方針**: CPM計算ロジック（`compute_schedule`）を中心に`pytest`で最低限のユニットテストを用意する
- **リポジトリ構成**: モノレポ（1リポジトリ内に`/frontend`と`/backend`を配置）。Vercel（frontend）・Render/Railway（backend）それぞれのデプロイ設定でルートディレクトリを個別指定する。Turborepo等のモノレポ管理ツールは使わず、単純なフォルダ分割のみで済ませる（2日間規模のため）
- **フロントのルーティング**: TanStack Router（TanStack Queryと同系統でまとめる）
- **バックエンドのPythonパッケージ管理**: `uv`
- **バックエンドのJWT検証**: `PyJWT`でSupabaseのJWT Secret（HS256）を検証する依存関係をFastAPIに実装する（詳細は [[auth-and-data-isolation]]）
- **CORS**: FastAPI側でVercelのフロントエンドオリジンを許可する設定を入れる（実装時の設定項目）
- **CI**: GitHub Actionsを導入する。push/PR時に、バックエンドは`pytest`（CPM計算ロジック中心）、フロントエンドはビルド確認を実行する最小構成とする
- **Lint/Formatter**: フロントエンドは`Biome`、バックエンドは`Ruff`。GitHub Actionsのpush/PR時チェックにも組み込む
- **APIモック戦略**: `orval`がOpenAPI仕様から生成するMSW（Mock Service Worker）モックハンドラを利用し、バックエンド未完成でもフロントエンドを並行開発できるようにする
- **Supabaseのローカル開発環境**: Supabase CLIの`supabase start`でローカルにDocker経由のPostgres/Authを立てて開発する（共有リモートプロジェクトへの直接接続はしない）
- **本番用Supabaseプロジェクト**: 審査員向けデプロイ先として、ローカル開発用とは別にホスティングされたSupabaseプロジェクトを用意する。Google OAuthのリダイレクトURIは、ローカル用（`http://localhost:54321`等）と本番用でそれぞれGoogle Cloud Console・Supabase側に個別登録する
- **バックエンドのデプロイ方式**: Docker化はせず、Render/Railwayのネイティブbuildpackに任せる（2日間規模のため）。ただしネイティブのPythonビルドパックは`requirements.txt`前提のことが多いため、`uv`管理のままデプロイする場合はビルドコマンドを明示的に上書きする（例:`uv export -o requirements.txt && pip install -r requirements.txt`）
- **環境変数管理**: フロント・バックエンドとも`.env.example`をリポジトリにコミットし、実際の`.env`はコミットしない運用とする
