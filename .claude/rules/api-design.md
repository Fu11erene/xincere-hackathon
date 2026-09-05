# API設計

出典: `docs/requirements/cpm-dynamic-replanning.md`

RESTful・リソース指向で設計する。認証はSupabaseが発行するJWTを`Authorization: Bearer`ヘッダで受け取る（ログイン自体は自分のAPIに持たせず、Supabase Auth側で完結させる。詳細は [[auth-and-data-isolation]]）。

| メソッド | パス | 用途 |
|---|---|---|
| POST | `/projects/preview` | ゴール文と締切からAIタスク分解のプレビューを返す（**非永続化**）。body: `{goal_text, deadline}` → `{tasks: [{temp_id, name, category, estimated_duration_hours, depends_on: [temp_id...]}]}` |
| POST | `/projects` | プレビューを軽く編集した結果を確定保存。body: `{goal_text, deadline, tasks: [...]}` → Project+Task+TaskDependencyを永続化して201返却 |
| GET | `/projects` | 自分のプロジェクト一覧 |
| GET | `/projects/{project_id}` | プロジェクト詳細（生のタスクデータ） |
| GET | `/projects/{project_id}/schedule` | **CPM計算済み**スケジュールを返す（ES/EF/LS/LF/スラック/`is_critical`、学習係数反映後の見積もり）。ダッシュボードと補助ビューはどちらもこれを叩き、「今日やるべきこと」はクライアント側でフィルタする |
| POST | `/tasks/{task_id}/events` | 進捗記録。body: `{event_type: "complete" \| "skip"}` → Task状態更新＋ProgressEvent作成＋UserPaceProfile再計算をトリガーし、更新後のtaskを返す |

任意（Should〜Could）:
- `PATCH /projects/{project_id}/tasks/{task_id}` — 確定後の軽微な修正（リネーム等）
- `GET /demo/sample-goals` — デモで使う事前検証済みのゴール例一覧（チップ表示用）

## 設計のポイント

- タスク分解の**プレビューと確定を分離**しており、編集画面自体はAPIを介さずクライアント側の状態だけで完結し、確定時に一度だけPOSTする
- CPM計算結果は永続化しない方針のため（[[data-model]] 参照）、`/schedule`は毎回サーバー側で再計算した結果を返す専用エンドポイントとして`/projects/{id}`と責務を分離する
- 進捗記録を`complete`/`skip`で1エンドポイントにまとめ、`event_type`で分岐させることで、ProgressEventというエンティティ設計とAPIの形を一致させている

## OpenAPI(Swagger)によるフロント・バックエンド連携

- FastAPIは各エンドポイントのPydanticモデル定義からOpenAPI仕様を自動生成する（`/docs`でSwagger UI、`/openapi.json`で仕様を確認できる）。仕様書を手書きする必要はない
- フロントエンドはこの仕様から型・APIクライアントを自動生成し、手動での型定義の重複・ズレを防ぐ。生成ツールは`orval`を推奨する。理由は、OpenAPI仕様からTypeScriptの型とReact Query製のフックを自動生成でき、「完了/スキップ記録後に`/projects/{id}/schedule`を再取得してダッシュボードへ反映する」という本機能の中核挙動を、React Queryのキャッシュ無効化の仕組みでそのまま実装できるため
- 開発フロー: バックエンドのPydanticモデルを変更→OpenAPI仕様が自動更新→`orval`を再実行してフロントの型・フックを再生成。2日間のハッカソン規模ではCI連携までは不要で、手動実行で十分
