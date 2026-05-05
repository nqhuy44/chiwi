"""Load the configurable list of spending categories.

Source of truth is a JSON file (default `config/categories.json`); the path
can be overridden via the `CATEGORIES_FILE` env var (see `Settings`). The
same list is consumed by the Tagging Agent's prompt and by the DB seed in
`src/db/models/category.py`, so adding a category in one place updates
classification and storage together.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from src.core.config import settings
from src.db.models.category import CategoryDocument

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PATH = _PROJECT_ROOT / "config" / "categories.json"


def _resolve_path() -> Path:
    if settings.categories_file:
        path = Path(settings.categories_file)
        if not path.is_absolute():
            path = _PROJECT_ROOT / path
        return path
    return _DEFAULT_PATH


@lru_cache(maxsize=1)
def load_categories() -> list[CategoryDocument]:
    """Return the configured categories as `CategoryDocument` instances."""
    raw = json.loads(_resolve_path().read_text(encoding="utf-8"))
    return [CategoryDocument(**item) for item in raw]


def category_names() -> list[str]:
    """Return just the category names, in file order."""
    return [c.name for c in load_categories()]


def resolve_merchant_icon(merchant_name: str | None, category_id: str | None, icons_map: dict[str, str]) -> str:
    """Determine the best icon for a transaction: Brand-specific first, then Category icon."""
    brand_icons = {
        "spotify": "🎵",
        "netflix": "🎬",
        "youtube": "📺",
        "icloud": "☁️",
        "google one": "☁️",
        "openai": "🤖",
        "chatgpt": "🤖",
        "claude": "🤖",
        "adobe": "🎨",
        "capcut": "🎬",
        "canva": "🎨",
    }
    
    merchant_key = (merchant_name or "").lower()
    for brand, brand_icon in brand_icons.items():
        if brand in merchant_key:
            return brand_icon
            
    return icons_map.get(category_id or "Khác", "❓")
