# CPM計算アルゴリズムの実装詳細

出典: `docs/requirements/cpm-dynamic-replanning.md`

実績のあるタスクは固定アンカーとして扱い、未着手タスクは現在時刻起点で計算し直す点がポイント。学習係数（完了ペース・スキップ傾向）はフォワードパスの見積もり時間に乗せる形で反映する。データモデルは [[data-model]] を参照。

## 入力

- タスク一覧（`status`, `current_estimated_duration_hours`, `actual_start_at`, `actual_end_at`）
- 依存関係（TaskDependencyのエッジ）
- 現在時刻（`now`）、プロジェクトの締切（あれば）
- `UserPaceProfile`（`pace_coefficient`, `skip_rate_by_category`）

## 0. 前処理：トポロジカルソート

依存グラフを`networkx`の`DiGraph`に読み込み、`topological_sort`で処理順を決める。タスク作成時の循環依存検知（`is_directed_acyclic_graph`）も同じライブラリで賄い、実装を使い回す（[[ai-task-decomposition]] の後処理と共通）。

## 1. フォワードパス（ES/EF）

トポロジカル順に処理する。
- `status == done`: ES=`actual_start_at`, EF=`actual_end_at`（実績値。固定し再計算しない）
- それ以外:
  - `ES = max(now, 先行タスク全てのEFの最大値)`（先行タスクがなければ`now`）
  - `EF = ES + current_estimated_duration_hours`
  - `current_estimated_duration_hours = original_estimated_duration_hours × pace_coefficient × (1 + skip_rate_by_category[category] × 0.5)`
    - `pace_coefficient`: ユーザーの完了ペース傾向
    - スキップ率が高いカテゴリほどバッファが乗る（係数0.5は初期値。デモでの見え方を見ながら調整する）

## 2. バックワードパス（LS/LF）

- 後続を持たないタスク（シンクノード）のLF = プロジェクト締切（未設定ならフォワードパスで出た全体完了予定日＝全シンクノードのEFの最大値）
- 逆トポロジカル順に:`LF = min(後続タスクのLSの最小値)`、`LS = LF − current_estimated_duration_hours`
- `done`タスクはLS=ES, LF=EFとして扱い、スラック計算の対象外とする

## 3. スラック・クリティカルパス判定

- `slack = LS − ES`
- `is_critical = slack <= 微小な閾値（例: 0.01時間）`（浮動小数点誤差対策）

## 4. 学習係数の更新（`complete`/`skip`イベント発生時）

- `complete`時: `pace_coefficient`を指数移動平均で更新
  `new = 0.3 × (actual_duration_hours / original_estimated_duration_hours) + 0.7 × old`（α=0.3は初期値）
- `skip`時: 該当カテゴリの`skip_rate_by_category`を「直近N件中のスキップ比率」で更新
- どちらも`UserPaceProfile`をupsertするのみで、CPM自体はこの時点では再計算しない

## 5. 再計算タイミング

`POST /tasks/{id}/events`は`UserPaceProfile`とTaskの状態のみ更新し、CPM計算そのものは`GET /projects/{id}/schedule`が呼ばれるたびに上記1〜3を実行して都度返す（CPM結果を永続化しない方針と一致。[[api-design]] 参照）。`compute_schedule(tasks, dependencies, pace_profile, now, deadline) -> ScheduleResult`という副作用のない純粋関数に切り出し、テストしやすくする（`pytest`でユニットテスト。[[tech-stack]] 参照）。
