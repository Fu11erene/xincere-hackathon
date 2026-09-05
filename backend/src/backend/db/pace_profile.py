from supabase import Client

from backend.cpm.schedule import PaceProfile


def get_pace_profile(db: Client, user_id: str) -> PaceProfile:
    rows = db.table("user_pace_profile").select("*").eq("user_id", user_id).execute().data
    if not rows:
        return PaceProfile()

    row = rows[0]
    return PaceProfile(
        pace_coefficient=row["pace_coefficient"],
        skip_rate_by_category=row["skip_rate_by_category"] or {},
    )
