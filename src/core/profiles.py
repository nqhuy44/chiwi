"""Load user personalization profiles from a JSON config file.

Profiles live outside the codebase (default `config/user_profiles.json`)
so the user can edit occupation, hobbies, and tone without redeploying.
The path can be overridden via the `USER_PROFILES_FILE` env var.
"""

from __future__ import annotations
import json
import logging
from functools import lru_cache
from pathlib import Path

from src.core.config import settings
from src.core.schemas import UserProfile

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _PROJECT_ROOT / "config" / "user_profiles.json"
_DEFAULT_KEY = "default"


def _resolve_path() -> Path:
    if settings.user_profiles_file:
        path = Path(settings.user_profiles_file)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return path
    return _DEFAULT_PATH


@lru_cache(maxsize=1)
def _load_raw_json() -> dict[str, dict]:
    path = _resolve_path()
    if not path.exists():
        logger.warning("User profiles file not found at %s", path)
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        logger.error("User profiles file must be a JSON object: %s", path)
        return {}
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def _get_json_profile(user_id: str) -> UserProfile:
    """Fallback: read from config/user_profiles.json during migration."""
    raw = _load_raw_json()
    entry = raw.get(user_id) or raw.get(_DEFAULT_KEY) or {}
    try:
        return UserProfile(**entry)
    except Exception:
        logger.warning("Invalid JSON profile entry for user_id=%s", user_id)
        return UserProfile()


async def get_profile(user_id: str) -> UserProfile:
    """Return the profile for ``user_id`` or the default profile.

    DB-first logic: check MongoDB via user_repo, fallback to JSON if missing.
    """
    # Lazy import to avoid circular dependency with dependencies.py -> dashboard.py -> profiles.py
    from src.core.dependencies import container
    try:
        db_profile = await container.user_repo.get_profile(user_id)
        if db_profile:
            # db_profile is now a UserProfileDocument (Beanie/Pydantic v2)
            return UserProfile.model_validate(db_profile.model_dump())
    except Exception:
        logger.exception("Error fetching profile from DB for user_id=%s", user_id)

    return _get_json_profile(user_id)


def reload_json() -> None:
    """Drop the cached JSON profiles. Call after editing the file at runtime."""
    _load_raw_json.cache_clear()
