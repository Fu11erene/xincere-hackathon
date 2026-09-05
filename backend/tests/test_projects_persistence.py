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


def _fake_db_for_create() -> MagicMock:
    db = MagicMock()

    def table_side_effect(name: str) -> MagicMock:
        table = MagicMock()
        if name == "projects":
            table.insert.return_value.execute.return_value = SimpleNamespace(
                data=[
                    {
                        "id": "project-1",
                        "goal_text": "ゴール",
                        "deadline": None,
                        "created_at": "2026-09-05T00:00:00Z",
                    }
                ]
            )
        elif name == "tasks":
            table.insert.return_value.execute.return_value = SimpleNamespace(
                data=[
                    {
                        "id": "task-a",
                        "project_id": "project-1",
                        "name": "設計",
                        "category": "設計",
                        "original_estimated_duration_hours": 3.0,
                        "current_estimated_duration_hours": 3.0,
                        "status": "todo",
                        "actual_start_at": None,
                        "actual_end_at": None,
                        "skip_count": 0,
                    }
                ]
            )
        elif name == "task_dependencies":
            table.insert.return_value.execute.return_value = SimpleNamespace(data=[])
        return table

    db.table.side_effect = table_side_effect
    return db


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token()}"}


def test_create_project_endpoint_persists_and_returns_detail():
    app.dependency_overrides[get_settings] = lambda: Settings(supabase_jwt_secret=TEST_JWT_SECRET)
    app.dependency_overrides[get_supabase_client] = _fake_db_for_create
    try:
        client = TestClient(app)
        response = client.post(
            "/projects",
            json={
                "goal_text": "ゴール",
                "deadline": None,
                "tasks": [
                    {
                        "temp_id": "a",
                        "name": "設計",
                        "category": "設計",
                        "estimated_duration_hours": 3.0,
                        "depends_on": [],
                    }
                ],
            },
            headers=_auth_headers(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "project-1"
    # tasks[].idはサーバー(create_project)が採番したUUIDであり、
    # モックしたDB行のidは実際には使われない。
    assert body["tasks"][0]["name"] == "設計"
    assert isinstance(body["tasks"][0]["id"], str) and body["tasks"][0]["id"]


def test_get_project_endpoint_returns_404_when_not_found():
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
        response = client.get("/projects/missing", headers=_auth_headers())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
