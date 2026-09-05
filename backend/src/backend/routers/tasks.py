from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from backend.auth import get_current_user_id
from backend.db import progress_events as progress_events_db
from backend.db.client import get_supabase_client
from backend.schemas import ProgressEventRequest, TaskResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/{task_id}/events", response_model=TaskResponse, operation_id="recordTaskEvent")
def record_task_event(
    task_id: str,
    body: ProgressEventRequest,
    user_id: str = Depends(get_current_user_id),
    db: Client = Depends(get_supabase_client),
) -> TaskResponse:
    """進捗記録(complete/skip)。Task状態更新+ProgressEvent作成+
    UserPaceProfile再計算をトリガーし、更新後のtaskを返す。
    """
    task = progress_events_db.record_task_event(db, user_id, task_id, body.event_type)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task
