from functools import lru_cache

from supabase import Client, create_client

from backend.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """service_roleキーで接続するクライアント。RLSを完全にバイパスするため、
    呼び出し側(db/*.py)は全クエリで明示的にuser_idフィルタを書くこと。
    .claude/rules/auth-and-data-isolation.md 参照。
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
