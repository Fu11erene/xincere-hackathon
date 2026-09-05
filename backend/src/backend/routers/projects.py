from datetime import UTC, datetime

from anthropic import Anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from backend.ai.client import get_anthropic_client
from backend.ai.task_decomposition import decompose_goal
from backend.auth import get_current_user_id
from backend.config import Settings, get_settings
from backend.cpm.schedule import CyclicDependencyError, TaskInput, compute_schedule
from backend.db import pace_profile as pace_profile_db
from backend.db import projects as projects_db
from backend.db.client import get_supabase_client
from backend.schemas import (
    ProjectCreateRequest,
    ProjectDetail,
    ProjectPreviewRequest,
    ProjectPreviewResponse,
    ProjectSummary,
    ScheduledTask,
    ScheduleResponse,
)
from backend.validation import validate_task_graph

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/preview", response_model=ProjectPreviewResponse, operation_id="previewProject")
def preview_project(
    body: ProjectPreviewRequest,
    user_id: str = Depends(get_current_user_id),
    client: Anthropic = Depends(get_anthropic_client),
    settings: Settings = Depends(get_settings),
) -> ProjectPreviewResponse:
    """ゴール文からAIタスク分解のプレビューを返す(非永続化)。"""
    tasks = decompose_goal(client, settings.anthropic_model, body.goal_text, body.deadline)
    return ProjectPreviewResponse(tasks=tasks)


@router.post("", response_model=ProjectDetail, status_code=201, operation_id="createProject")
def create_project(
    body: ProjectCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: Client = Depends(get_supabase_client),
) -> ProjectDetail:
    """プレビューを軽く編集した結果を確定保存する。"""
    validate_task_graph(body.tasks)
    return projects_db.create_project(db, user_id, body.goal_text, body.deadline, body.tasks)


@router.get("", response_model=list[ProjectSummary], operation_id="listProjects")
def list_projects(
    user_id: str = Depends(get_current_user_id),
    db: Client = Depends(get_supabase_client),
) -> list[ProjectSummary]:
    """自分のプロジェクト一覧を返す。"""
    return projects_db.list_projects(db, user_id)


@router.get("/{project_id}", response_model=ProjectDetail, operation_id="getProject")
def get_project(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Client = Depends(get_supabase_client),
) -> ProjectDetail:
    """プロジェクト詳細(生のタスクデータ)を返す。"""
    project = projects_db.get_project(db, user_id, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("/{project_id}/schedule", response_model=ScheduleResponse, operation_id="getProjectSchedule")
def get_project_schedule(
    project_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Client = Depends(get_supabase_client),
) -> ScheduleResponse:
    """CPM計算済みスケジュール(ES/EF/LS/LF/スラック/is_critical)を返す。"""
    project = projects_db.get_project(db, user_id, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    pace_profile = pace_profile_db.get_pace_profile(db, user_id)
    task_inputs = [
        TaskInput(
            id=task.id,
            category=task.category,
            status=task.status,
            original_estimated_duration_hours=task.original_estimated_duration_hours,
            actual_start_at=task.actual_start_at,
            actual_end_at=task.actual_end_at,
            depends_on=task.depends_on,
        )
        for task in project.tasks
    ]

    try:
        result = compute_schedule(task_inputs, datetime.now(UTC), project.deadline, pace_profile)
    except CyclicDependencyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    scheduled_by_id = {t.id: t for t in result.tasks}
    scheduled_tasks = []
    for task in project.tasks:
        scheduled = scheduled_by_id[task.id]
        merged = task.model_dump()
        merged.update(
            current_estimated_duration_hours=scheduled.current_estimated_duration_hours,
            earliest_start=scheduled.earliest_start,
            earliest_finish=scheduled.earliest_finish,
            latest_start=scheduled.latest_start,
            latest_finish=scheduled.latest_finish,
            slack_hours=scheduled.slack_hours,
            is_critical=scheduled.is_critical,
        )
        scheduled_tasks.append(ScheduledTask(**merged))

    return ScheduleResponse(
        project_id=project.id,
        tasks=scheduled_tasks,
        projected_completion_at=result.projected_completion_at,
    )
