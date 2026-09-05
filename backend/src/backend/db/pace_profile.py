from typing import Literal

from supabase import Client

from backend.cpm.schedule import PaceProfile

# cpm-algorithm.md §4の指数移動平均の学習率(初期値)。pace_coefficientと
# skip_rate_by_categoryの両方で同じ値を使う。
LEARNING_RATE = 0.3


def get_pace_profile(db: Client, user_id: str) -> PaceProfile:
    rows = db.table("user_pace_profile").select("*").eq("user_id", user_id).execute().data
    if not rows:
        return PaceProfile()

    row = rows[0]
    return PaceProfile(
        pace_coefficient=row["pace_coefficient"],
        skip_rate_by_category=row["skip_rate_by_category"] or {},
    )


def compute_pace_profile_update(
    pace_profile: PaceProfile,
    category: str,
    event_type: Literal["complete", "skip"],
    actual_duration_hours: float | None,
    original_estimated_duration_hours: float,
) -> PaceProfile:
    """進捗イベント1件をpace_profileに反映した、更新後の値を返す副作用のない純粋関数。

    - pace_coefficient: complete時のみ、実績/見積り比を指数移動平均で反映する
      (cpm-algorithm.md §4: new = 0.3 * (actual/original) + 0.7 * old)
    - skip_rate_by_category: complete/skipどちらのイベントでも、該当カテゴリの
      「直近イベントがスキップだったか」を0/1の指標として指数移動平均で反映する。
      データモデルにイベント単位の集計テーブルを持たない前提での簡易近似。
    """
    if (
        event_type == "complete"
        and actual_duration_hours is not None
        and original_estimated_duration_hours > 0
    ):
        pace_ratio = actual_duration_hours / original_estimated_duration_hours
        new_pace_coefficient = (
            LEARNING_RATE * pace_ratio + (1 - LEARNING_RATE) * pace_profile.pace_coefficient
        )
    else:
        new_pace_coefficient = pace_profile.pace_coefficient

    skip_indicator = 1.0 if event_type == "skip" else 0.0
    old_skip_rate = pace_profile.skip_rate_by_category.get(category, 0.0)
    new_skip_rate = LEARNING_RATE * skip_indicator + (1 - LEARNING_RATE) * old_skip_rate

    new_skip_rate_by_category = dict(pace_profile.skip_rate_by_category)
    new_skip_rate_by_category[category] = new_skip_rate

    return PaceProfile(
        pace_coefficient=new_pace_coefficient,
        skip_rate_by_category=new_skip_rate_by_category,
    )


def upsert_pace_profile(db: Client, user_id: str, pace_profile: PaceProfile) -> None:
    db.table("user_pace_profile").upsert(
        {
            "user_id": user_id,
            "pace_coefficient": pace_profile.pace_coefficient,
            "skip_rate_by_category": pace_profile.skip_rate_by_category,
        }
    ).execute()
