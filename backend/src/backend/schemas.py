from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ユーザーが自然文で入力するゴール。上限を設けないと、認証済みユーザーが
# 巨大なテキストを/projects/previewに投げてAnthropic APIのトークン消費を
# 際限なく膨らませられてしまう。
GOAL_TEXT_MAX_LENGTH = 2000


class TaskPreview(BaseModel):
    temp_id: str
    name: str
    category: str
    estimated_duration_hours: float
    depends_on: list[str] = []


class ProjectPreviewRequest(BaseModel):
    goal_text: str = Field(max_length=GOAL_TEXT_MAX_LENGTH)
    deadline: date | None = None


class ProjectPreviewResponse(BaseModel):
    tasks: list[TaskPreview]


class ProjectCreateRequest(BaseModel):
    goal_text: str = Field(max_length=GOAL_TEXT_MAX_LENGTH)
    deadline: date | None = None
    tasks: list[TaskPreview]


class TaskResponse(BaseModel):
    id: str
    project_id: str
    name: str
    category: str
    original_estimated_duration_hours: float
    current_estimated_duration_hours: float
    status: Literal["todo", "in_progress", "done", "skipped"]
    actual_start_at: datetime | None = None
    actual_end_at: datetime | None = None
    skip_count: int = 0
    depends_on: list[str] = []


class ProjectSummary(BaseModel):
    id: str
    goal_text: str
    deadline: date | None = None
    created_at: datetime


class ProjectDetail(ProjectSummary):
    tasks: list[TaskResponse]


class ScheduledTask(TaskResponse):
    earliest_start: datetime
    earliest_finish: datetime
    latest_start: datetime
    latest_finish: datetime
    slack_hours: float
    is_critical: bool


class ScheduleResponse(BaseModel):
    project_id: str
    tasks: list[ScheduledTask]
    projected_completion_at: datetime


class ProgressEventRequest(BaseModel):
    event_type: Literal["complete", "skip"]
