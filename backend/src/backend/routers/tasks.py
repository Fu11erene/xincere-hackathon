from fastapi import APIRouter, Depends, HTTPException, status

from backend.auth import get_current_user_id
from backend.schemas import ProgressEventRequest, TaskResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/{task_id}/events", response_model=TaskResponse)
def record_task_event(
    task_id: str,
    body: ProgressEventRequest,
    user_id: str = Depends(get_current_user_id),
) -> TaskResponse:
    """進捗記録(complete/skip)。Task状態更新+ProgressEvent作成+
    UserPaceProfile再計算をトリガーし、更新後のtaskを返す。
    """
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="not implemented")
