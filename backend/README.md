# backend

FastAPI + uv。AIタスク分解(Claude)、CPM計算エンジン、Supabase永続化を担当。

ローカルセットアップ手順はリポジトリルートの `README.md` を参照。

## スクリプト

- `uv run uvicorn backend.main:app --reload --port 8000` — 開発サーバー起動
- `uv run pytest -q` — テスト
- `uv run ruff check .` — lint
- `uv run ruff format .` — フォーマット
