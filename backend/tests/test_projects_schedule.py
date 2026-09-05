from types import SimpleNamespace
from unittest.mock import MagicMock

import jwt
from fastapi.testclient import TestClient

from backend.config import Settings, get_settings
from backend.db.client import get_supabase_client
from backend.main import app

TEST_JWT_SECRET = "test-secret-at-least-32-bytes-long!!"


def _make_token(user_id: str = "user-1") -> str:
    return jwt.encode(
        {"sub": user_id, "aud": "authenticated"},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def _task_row(id_: str, depends_on_ids: list[str] | None = None) -> dict:
    return {
        "id": id_,
        "project_id": "project-1",
        "name": f"task-{id_}",
        "category": "実装",
        "original_estimated_duration_hours": 2.0,
        "current_estimated_duration_hours": 2.0,
        "status": "todo",
        "actual_start_at": None,
        "actual_end_at": None,
        "skip_count": 0,
    }


def _fake_db() -> MagicMock:
    db = MagicMock()

    def table_side_effect(name: str) -> MagicMock:
        table = MagicMock()
        if name == "projects":
            table.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
                SimpleNamespace(
                    data=[
                        {
                            "id": "project-1",
                            "goal_text": "ゴール",
                            "deadline": None,
                            "created_at": "2026-09-05T00:00:00Z",
                        }
                    ]
                )
            )
        elif name == "tasks":
            table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(
                data=[_task_row("a"), _task_row("b")]
            )
        elif name == "task_dependencies":
            table.select.return_value.in_.return_value.execute.return_value = SimpleNamespace(
                data=[{"task_id": "b", "depends_on_task_id": "a"}]
            )
        elif name == "user_pace_profile":
            table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(
                data=[]
            )
        return table

    db.table.side_effect = table_side_effect
    return db


def test_get_schedule_returns_cpm_computed_tasks():
    app.dependency_overrides[get_settings] = lambda: Settings(supabase_jwt_secret=TEST_JWT_SECRET)
    app.dependency_overrides[get_supabase_client] = _fake_db
    try:
        client = TestClient(app)
        response = client.get(
            "/projects/project-1/schedule",
            headers={"Authorization": f"Bearer {_make_token()}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    tasks_by_id = {t["id"]: t for t in body["tasks"]}

    assert tasks_by_id["a"]["is_critical"] is True
    assert tasks_by_id["b"]["is_critical"] is True
    assert tasks_by_id["b"]["depends_on"] == ["a"]
    assert "projected_completion_at" in body


def test_get_schedule_returns_404_for_missing_project():
    db = MagicMock()
    table = MagicMock()
    table.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[])
    )
    db.table.side_effect = lambda name: table

    app.dependency_overrides[get_settings] = lambda: Settings(supabase_jwt_secret=TEST_JWT_SECRET)
    app.dependency_overrides[get_supabase_client] = lambda: db
    try:
        client = TestClient(app)
        response = client.get(
            "/projects/missing/schedule",
            headers={"Authorization": f"Bearer {_make_token()}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
