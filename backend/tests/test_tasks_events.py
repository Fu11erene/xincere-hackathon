from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
import pytest
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


def _table_mock() -> MagicMock:
    return MagicMock()


def _fake_db(tables: dict[str, MagicMock]) -> MagicMock:
    db = MagicMock()
    db.table.side_effect = lambda name: tables[name]
    return db


def _post_event(db: MagicMock, task_id: str, event_type: str, user_id: str = "user-1"):
    app.dependency_overrides[get_settings] = lambda: Settings(supabase_jwt_secret=TEST_JWT_SECRET)
    app.dependency_overrides[get_supabase_client] = lambda: db
    try:
        client = TestClient(app)
        return client.post(
            f"/tasks/{task_id}/events",
            json={"event_type": event_type},
            headers={"Authorization": f"Bearer {_make_token(user_id)}"},
        )
    finally:
        app.dependency_overrides.clear()


def test_complete_event_marks_task_done_and_records_actual_duration():
    tasks_table = _table_mock()
    tasks_table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "id": "task-1",
                "project_id": "project-1",
                "category": "実装",
                "original_estimated_duration_hours": 2.0,
                "status": "todo",
                "actual_start_at": "2026-09-05T00:00:00+00:00",
                "actual_end_at": None,
                "skip_count": 0,
                "created_at": "2026-09-05T00:00:00+00:00",
            }
        ]
    )
    tasks_table.update.return_value.eq.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "id": "task-1",
                "project_id": "project-1",
                "name": "実装する",
                "category": "実装",
                "original_estimated_duration_hours": 2.0,
                "current_estimated_duration_hours": 2.0,
                "status": "done",
                "actual_start_at": "2026-09-05T00:00:00+00:00",
                "actual_end_at": "2026-09-05T04:00:00+00:00",
                "skip_count": 0,
            }
        ]
    )

    projects_table = _table_mock()
    projects_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[{"id": "project-1", "user_id": "user-1"}])
    )

    progress_events_table = _table_mock()
    deps_table = _table_mock()
    deps_table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=[])

    pace_profile_table = _table_mock()
    pace_profile_table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(
        data=[]
    )

    db = _fake_db(
        {
            "tasks": tasks_table,
            "projects": projects_table,
            "progress_events": progress_events_table,
            "task_dependencies": deps_table,
            "user_pace_profile": pace_profile_table,
        }
    )

    fixed_now = datetime(2026, 9, 5, 4, 0, 0, tzinfo=UTC)
    with patch("backend.db.progress_events.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        mock_datetime.fromisoformat.side_effect = datetime.fromisoformat
        response = _post_event(db, "task-1", "complete")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["actual_end_at"] is not None

    progress_events_table.insert.assert_called_once()
    inserted = progress_events_table.insert.call_args[0][0]
    assert inserted["event_type"] == "complete"
    assert inserted["actual_duration_hours"] == 4.0

    pace_profile_table.upsert.assert_called_once()
    upserted = pace_profile_table.upsert.call_args[0][0]
    assert upserted["user_id"] == "user-1"
    # LEARNING_RATE(0.3) * (4.0/2.0) + 0.7 * 1.0(初期値) = 1.3
    assert upserted["pace_coefficient"] == pytest.approx(1.3)


def test_skip_event_keeps_status_and_increments_skip_count():
    tasks_table = _table_mock()
    tasks_table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "id": "task-1",
                "project_id": "project-1",
                "category": "調査",
                "original_estimated_duration_hours": 3.0,
                "status": "todo",
                "actual_start_at": None,
                "actual_end_at": None,
                "skip_count": 1,
                "created_at": "2026-09-05T00:00:00+00:00",
            }
        ]
    )
    tasks_table.update.return_value.eq.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "id": "task-1",
                "project_id": "project-1",
                "name": "調査する",
                "category": "調査",
                "original_estimated_duration_hours": 3.0,
                "current_estimated_duration_hours": 3.0,
                "status": "todo",
                "actual_start_at": None,
                "actual_end_at": None,
                "skip_count": 2,
            }
        ]
    )

    projects_table = _table_mock()
    projects_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[{"id": "project-1", "user_id": "user-1"}])
    )

    progress_events_table = _table_mock()
    deps_table = _table_mock()
    deps_table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=[])

    pace_profile_table = _table_mock()
    pace_profile_table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(
        data=[]
    )

    db = _fake_db(
        {
            "tasks": tasks_table,
            "projects": projects_table,
            "progress_events": progress_events_table,
            "task_dependencies": deps_table,
            "user_pace_profile": pace_profile_table,
        }
    )

    response = _post_event(db, "task-1", "skip")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "todo"
    assert body["skip_count"] == 2

    tasks_table.update.assert_called_once_with({"skip_count": 2})

    upserted = pace_profile_table.upsert.call_args[0][0]
    # LEARNING_RATE(0.3) * 1(skip) + 0.7 * 0.0(初期値) = 0.3
    assert upserted["skip_rate_by_category"]["調査"] == 0.3


def test_event_for_task_not_owned_by_user_returns_404():
    tasks_table = _table_mock()
    tasks_table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(
        data=[
            {
                "id": "task-1",
                "project_id": "project-1",
                "category": "調査",
                "original_estimated_duration_hours": 3.0,
                "status": "todo",
                "actual_start_at": None,
                "actual_end_at": None,
                "skip_count": 0,
                "created_at": "2026-09-05T00:00:00+00:00",
            }
        ]
    )

    projects_table = _table_mock()
    projects_table.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
        SimpleNamespace(data=[])
    )

    db = _fake_db({"tasks": tasks_table, "projects": projects_table})

    response = _post_event(db, "task-1", "complete", user_id="someone-else")

    assert response.status_code == 404


def test_event_for_nonexistent_task_returns_404():
    tasks_table = _table_mock()
    tasks_table.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=[])

    db = _fake_db({"tasks": tasks_table})

    response = _post_event(db, "does-not-exist", "complete")

    assert response.status_code == 404
