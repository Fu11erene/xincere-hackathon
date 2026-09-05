import jwt
from fastapi.testclient import TestClient

from backend.config import Settings, get_settings
from backend.main import app

TEST_JWT_SECRET = "test-secret-at-least-32-bytes-long!!"


def _make_token(user_id: str = "user-1") -> str:
    return jwt.encode(
        {"sub": user_id, "aud": "authenticated"},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def test_record_task_event_returns_501_not_implemented():
    app.dependency_overrides[get_settings] = lambda: Settings(supabase_jwt_secret=TEST_JWT_SECRET)
    try:
        client = TestClient(app)
        response = client.post(
            "/tasks/task-1/events",
            json={"event_type": "complete"},
            headers={"Authorization": f"Bearer {_make_token()}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 501
