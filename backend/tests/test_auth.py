from unittest.mock import MagicMock

import jwt
from fastapi.testclient import TestClient

from backend.config import Settings, get_settings
from backend.db.client import get_supabase_client
from backend.main import app


def test_missing_jwt_secret_returns_401_not_500():
    """SUPABASE_JWT_SECRET未設定(空文字)は設定ミスだが、jwt.decodeが送出する
    InvalidKeyErrorはInvalidTokenErrorのサブクラスではないため、握り漏らすと
    未処理例外による500になっていた(auth.pyでPyJWTError全体を捕捉して修正済み)。
    """
    token = jwt.encode(
        {"sub": "user-1", "aud": "authenticated"},
        "irrelevant-key-of-at-least-32-bytes!!",
        algorithm="HS256",
    )

    app.dependency_overrides[get_settings] = lambda: Settings(supabase_jwt_secret="")
    app.dependency_overrides[get_supabase_client] = lambda: MagicMock()
    try:
        client = TestClient(app)
        response = client.get("/projects", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
