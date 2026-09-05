"""プロジェクト/タスクの永続化。

.claude/rules/auth-and-data-isolation.md の方針により、service_roleキー接続では
RLSが効かないため、ここで書く全クエリに明示的なuser_idフィルタを入れることが
データ分離の主たる担保になる。
"""

import uuid
from datetime import date

from supabase import Client

from backend.schemas import ProjectDetail, ProjectSummary, TaskPreview, TaskResponse


def task_row_to_response(row: dict, depends_on: list[str]) -> TaskResponse:
    return TaskResponse(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        category=row["category"],
        original_estimated_duration_hours=row["original_estimated_duration_hours"],
        current_estimated_duration_hours=row["current_estimated_duration_hours"],
        status=row["status"],
        actual_start_at=row["actual_start_at"],
        actual_end_at=row["actual_end_at"],
        skip_count=row["skip_count"],
        depends_on=depends_on,
    )


def create_project(
    db: Client,
    user_id: str,
    goal_text: str,
    deadline: date | None,
    tasks: list[TaskPreview],
) -> ProjectDetail:
    project_row = (
        db.table("projects")
        .insert(
            {
                "user_id": user_id,
                "goal_text": goal_text,
                "deadline": deadline.isoformat() if deadline else None,
            }
        )
        .execute()
        .data[0]
    )
    project_id = project_row["id"]

    # temp_id -> 実際のtask id は、PostgRESTの一括insertの返却順序(SQL的に保証
    # されていない)に頼らず、こちらでUUIDを採番してinsertペイロードに含める。
    # これにより順序ズレによるtask_dependenciesの誤配線を構造的に防ぐ。
    real_id_by_temp_id = {task.temp_id: str(uuid.uuid4()) for task in tasks}

    try:
        db.table("tasks").insert(
            [
                {
                    "id": real_id_by_temp_id[task.temp_id],
                    "project_id": project_id,
                    "name": task.name,
                    "category": task.category,
                    "original_estimated_duration_hours": task.estimated_duration_hours,
                    "current_estimated_duration_hours": task.estimated_duration_hours,
                    "status": "todo",
                }
                for task in tasks
            ]
        ).execute()

        dependency_rows = [
            {
                "task_id": real_id_by_temp_id[task.temp_id],
                "depends_on_task_id": real_id_by_temp_id[dep_temp_id],
            }
            for task in tasks
            for dep_temp_id in task.depends_on
        ]
        if dependency_rows:
            db.table("task_dependencies").insert(dependency_rows).execute()
    except Exception:
        # supabase-pyはマルチステートメントトランザクションを提供しないため、
        # tasks/task_dependenciesの書き込みに失敗した場合はprojectごと手動で
        # ロールバックし、孤立したprojectだけが残らないようにする。
        db.table("projects").delete().eq("id", project_id).execute()
        raise

    task_responses = [
        TaskResponse(
            id=real_id_by_temp_id[task.temp_id],
            project_id=project_id,
            name=task.name,
            category=task.category,
            original_estimated_duration_hours=task.estimated_duration_hours,
            current_estimated_duration_hours=task.estimated_duration_hours,
            status="todo",
            actual_start_at=None,
            actual_end_at=None,
            skip_count=0,
            depends_on=[real_id_by_temp_id[dep_temp_id] for dep_temp_id in task.depends_on],
        )
        for task in tasks
    ]

    return ProjectDetail(
        id=project_id,
        goal_text=project_row["goal_text"],
        deadline=project_row["deadline"],
        created_at=project_row["created_at"],
        tasks=task_responses,
    )


def list_projects(db: Client, user_id: str) -> list[ProjectSummary]:
    rows = (
        db.table("projects")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )
    return [
        ProjectSummary(
            id=row["id"],
            goal_text=row["goal_text"],
            deadline=row["deadline"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def get_project(db: Client, user_id: str, project_id: str) -> ProjectDetail | None:
    project_rows = (
        db.table("projects").select("*").eq("id", project_id).eq("user_id", user_id).execute().data
    )
    if not project_rows:
        return None
    project_row = project_rows[0]

    # tasks/task_dependenciesへのクエリ自体にuser_idフィルタは付けていないが、
    # 直前のprojectsクエリでuser_id一致を確認済みのproject_idにしか絞り込まないため、
    # 他ユーザーのタスクが混入することはない(所有権の担保は上のprojectsクエリ側)。
    task_rows = db.table("tasks").select("*").eq("project_id", project_id).execute().data
    task_ids = [row["id"] for row in task_rows]

    depends_on_by_task_id: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    if task_ids:
        dependency_rows = (
            db.table("task_dependencies").select("*").in_("task_id", task_ids).execute().data
        )
        for dep_row in dependency_rows:
            depends_on_by_task_id[dep_row["task_id"]].append(dep_row["depends_on_task_id"])

    task_responses = [
        task_row_to_response(row, depends_on=depends_on_by_task_id[row["id"]]) for row in task_rows
    ]

    return ProjectDetail(
        id=project_row["id"],
        goal_text=project_row["goal_text"],
        deadline=project_row["deadline"],
        created_at=project_row["created_at"],
        tasks=task_responses,
    )
