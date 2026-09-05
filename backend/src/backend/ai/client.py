from functools import lru_cache

from anthropic import Anthropic

from backend.config import get_settings


@lru_cache
def get_anthropic_client() -> Anthropic:
    return Anthropic(api_key=get_settings().anthropic_api_key)
