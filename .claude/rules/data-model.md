# データベース設計

出典: `docs/requirements/cpm-dynamic-replanning.md`

## 概念モデル

**エンティティと主要属性**
- **ユーザー**: 識別子（審査員が個別に試せるよう、プロジェクトをユーザー単位で分離するために必要）
- **プロジェクト**: ゴール、締切
- **タスク**: タスク名、見積もり時間、状態（未着手/進行中/完了/スキップ）、カテゴリ
- **進捗イベント**: 種別（完了/スキップ）、発生日時

**関連（カーディナリティ）**
- ユーザー は 複数の プロジェクト を持つ（1:N）
- プロジェクト は 複数の タスク から構成される（1:N）
- タスク は 他の タスク に先行する（M:N、自己関連＝依存関係）
- タスク は 複数の 進捗イベント を持つ（1:N）

## 論理モデル：決定事項

- タスク間の依存関係（M:N自己関連）は`TaskDependency`中間テーブルで解決する
- タスクの見積もり時間は「AIの初期見積もり（`original_estimated_duration_hours`、不変）」と「学習係数反映後の現在値（`current_estimated_duration_hours`）」に分離して保持する
- ユーザーの完了ペース係数・カテゴリ別スキップ率は`UserPaceProfile`にキャッシュし、進捗イベント記録のたびに再計算してupsertする（デモ用シードデータもこのテーブルへ直接値を入れるだけで済む。[[demo-seed-strategy]] 参照）
- CPM計算結果（ES/EF/LS/LF/スラック/クリティカルパス判定）は永続化せず、ダッシュボード表示のたびにバックエンドで再計算する（[[cpm-algorithm]] 参照）

## ER図

```mermaid
erDiagram
    USER ||--o{ PROJECT : has
    PROJECT ||--o{ TASK : contains
    TASK ||--o{ TASK_DEPENDENCY : "is predecessor in (depends_on_task_id)"
    TASK ||--o{ TASK_DEPENDENCY : "is successor in (task_id)"
    TASK ||--o{ PROGRESS_EVENT : has
    USER ||--o| USER_PACE_PROFILE : has

    USER {
        uuid id PK
    }
    PROJECT {
        uuid id PK
        uuid user_id FK
        text goal_text
        date deadline
        timestamp created_at
    }
    TASK {
        uuid id PK
        uuid project_id FK
        string name
        string category
        decimal original_estimated_duration_hours
        decimal current_estimated_duration_hours
        string status
        timestamp actual_start_at
        timestamp actual_end_at
        int skip_count
        timestamp created_at
    }
    TASK_DEPENDENCY {
        uuid id PK
        uuid task_id FK
        uuid depends_on_task_id FK
    }
    PROGRESS_EVENT {
        uuid id PK
        uuid task_id FK
        string event_type
        timestamp occurred_at
        decimal actual_duration_hours
    }
    USER_PACE_PROFILE {
        uuid user_id PK "FK"
        decimal pace_coefficient
        json skip_rate_by_category
        timestamp updated_at
    }
```
