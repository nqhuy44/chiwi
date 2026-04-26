"""Load user personalization profiles from a JSON config file.

Profiles live outside the codebase (default `config/user_profiles.json`)
so the user can edit occupation, hobbies, and tone without redeploying.
The path can be overridden via the `USER_PROFILES_FILE` env var.

The file is a flat object keyed by ``telegram_user_id``. A ``"default"``
key provides the fallback used when a specific user has no entry. Keys
beginning with ``_`` (e.g. ``_example_*``) are ignored — useful for
shipping example entries in the bundled file.
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
def _load_raw() -> dict[str, dict]:
    path = _resolve_path()
    if not path.exists():
        logger.warning("User profiles file not found at %s", path)
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        logger.error("User profiles file must be a JSON object: %s", path)
        return {}
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def get_profile(user_id: str) -> UserProfile:
    """Return the profile for ``user_id`` or the default profile.

    Never raises — falls back to a blank :class:`UserProfile` if neither
    the user nor the default is configured. Coercion errors in a single
    profile entry log a warning and degrade to default.
    """
    raw = _load_raw()
    entry = raw.get(user_id) or raw.get(_DEFAULT_KEY) or {}
    try:
        return UserProfile(**entry)
    except Exception:
        logger.exception("Invalid profile entry for user_id=%s", user_id)
        return UserProfile()


def configured_user_ids() -> list[str]:
    """Return the list of user_ids with an explicit profile (excluding default).

    Used by the worker to fan out scheduled nudge analyses.
    """
    return [k for k in _load_raw().keys() if k != _DEFAULT_KEY]


def reload() -> None:
    """Drop the cached profiles. Call after editing the file at runtime."""
    _load_raw.cache_clear()
