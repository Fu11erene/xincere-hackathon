from types import SimpleNamespace
from unittest.mock import MagicMock

import jwt
from fastapi.testclient import TestClient

from backend.ai.client import get_anthropic_client
from backend.ai.task_decomposition import TOOL_NAME
from backend.config import Settings, get_settings
from backend.main import app

TEST_JWT_SECRET = "test-secret-at-least-32-bytes-long!!"


def _make_token(user_id: str = "user-1") -> str:
    return jwt.encode(
        {"sub": user_id, "aud": "authenticated"},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def _fake_client(tasks: list[dict]) -> MagicMock:
    block = SimpleNamespace(type="tool_use", name=TOOL_NAME, input={"tasks": tasks})
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(content=[block])
    return client


def test_preview_project_returns_decomposed_tasks():
    tasks = [
        {
            "id": "a",
            "name": "設計",
            "category": "設計",
            "estimated_duration_hours": 3.0,
            "depends_on": [],
        },
        {
            "id": "b",
            "name": "実装",
            "category": "実装",
            "estimated_duration_hours": 5.0,
            "depends_on": ["a"],
        },
    ]

    app.dependency_overrides[get_settings] = lambda: Settings(supabase_jwt_secret=TEST_JWT_SECRET)
    app.dependency_overrides[get_anthropic_client] = lambda: _fake_client(tasks)
    try:
        client = TestClient(app)
        response = client.post(
            "/projects/preview",
            json={"goal_text": "ハッカソンでMVPを作る", "deadline": None},
            headers={"Authorization": f"Bearer {_make_token()}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert [t["temp_id"] for t in body["tasks"]] == ["a", "b"]
    assert body["tasks"][1]["depends_on"] == ["a"]


def test_preview_project_requires_auth():
    client = TestClient(app)
    response = client.post(
        "/projects/preview",
        json={"goal_text": "ハッカソンでMVPを作る", "deadline": None},
    )
    assert response.status_code == 401
