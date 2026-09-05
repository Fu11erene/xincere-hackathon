"""進捗イベント(complete/skip)の記録。

.claude/rules/cpm-algorithm.md §4-5の通り、ここではTaskとUserPaceProfileの
状態更新のみを行い、CPM計算自体は`GET /projects/{id}/schedule`側で都度実行する。
"""

from datetime import UTC, datetime
from typing import Literal

from supabase import Client

from backend.db import pace_profile as pace_profile_db
from backend.db.projects import task_row_to_response
from backend.schemas import TaskResponse


class TaskAlreadyDoneError(Exception):
    """完了済みのtaskに対して進捗イベントが送られた場合に送出する。"""


def record_task_event(
    db: Client,
    user_id: str,
    task_id: str,
    event_type: Literal["complete", "skip"],
) -> TaskResponse | None:
    """進捗イベントを記録し、更新後のtaskを返す。

    taskが存在しない、または他ユーザーのtaskの場合はNoneを返す
    (auth-and-data-isolation.mdの方針により、存在有無を明かさず404扱いにする)。
    既にstatus=='done'のtaskに対して呼ばれた場合はTaskAlreadyDoneErrorを送出する
    (cpm-algorithm.md §1の「doneタスクは固定アンカーとして扱い再計算しない」という
    前提を守るため。二重クリックや再送で実績値・pace_coefficientが歪むのを防ぐ)。
    """
    task_rows = db.table("tasks").select("*").eq("id", task_id).execute().data
    if not task_rows:
        return None
    task_row = task_rows[0]

    project_rows = (
        db.table("projects")
        .select("*")
        .eq("id", task_row["project_id"])
        .eq("user_id", user_id)
        .execute()
        .data
    )
    if not project_rows:
        return None

    if task_row["status"] == "done":
        raise TaskAlreadyDoneError(f"Task {task_id} is already done")

    now = datetime.now(UTC)
    original_estimated_duration_hours = task_row["original_estimated_duration_hours"]
    actual_duration_hours: float | None = None

    task_update: dict = {}
    if event_type == "complete":
        previous_actual_start_at = task_row["actual_start_at"]
        if previous_actual_start_at:
            actual_duration_hours = (
                now - datetime.fromisoformat(previous_actual_start_at)
            ).total_seconds() / 3600
            actual_start_at = previous_actual_start_at
        else:
            # 開始時刻が記録されていない(in_progressを経由せずtodoから直接
            # completeされた)場合、created_atからの経過時間は実作業時間の
            # 指標にならない(数日放置後に完了、等)。実績時間が不明な以上、
            # nowを開始・終了の両方に使い、pace_coefficientの更新は
            # actual_duration_hours=Noneとしてスキップする
            # (compute_pace_profile_updateのガード参照)。
            actual_start_at = now.isoformat()
        task_update = {
            "status": "done",
            "actual_start_at": actual_start_at,
            "actual_end_at": now.isoformat(),
        }
    else:
        # skip(後回し)はtodo/in_progressの状態を維持する(status変更せず、
        # skip_countのみ加算。理由はdb/pace_profile.pyのcompute_pace_profile_update
        # docstring、および[[cpm-algorithm]]参照)。
        task_update = {"skip_count": task_row["skip_count"] + 1}

    updated_rows = db.table("tasks").update(task_update).eq("id", task_id).execute().data
    if not updated_rows:
        # RLSや競合削除等でUPDATEが0行しかヒットしなかった場合。呼び出し元は
        # Noneを404として扱うため、この経路でも同様に扱う。
        return None
    updated_task_row = updated_rows[0]

    db.table("progress_events").insert(
        {
            "task_id": task_id,
            "event_type": event_type,
            "occurred_at": now.isoformat(),
            "actual_duration_hours": actual_duration_hours,
        }
    ).execute()

    pace_profile = pace_profile_db.get_pace_profile(db, user_id)
    updated_pace_profile = pace_profile_db.compute_pace_profile_update(
        pace_profile,
        category=task_row["category"],
        event_type=event_type,
        actual_duration_hours=actual_duration_hours,
        original_estimated_duration_hours=original_estimated_duration_hours,
    )
    pace_profile_db.upsert_pace_profile(db, user_id, updated_pace_profile)

    dependency_rows = (
        db.table("task_dependencies").select("*").eq("task_id", task_id).execute().data
    )
    depends_on = [row["depends_on_task_id"] for row in dependency_rows]

    return task_row_to_response(updated_task_row, depends_on=depends_on)
