from pydantic import BaseModel


class CategoryDocument(BaseModel):
    name: str
    icon_emoji: str
    parent_category: str | None = None
    is_system: bool = True


def default_categories() -> list["CategoryDocument"]:
    """Return the seed category list loaded from `settings.categories_file`."""
    from src.core.categories import load_categories

    return load_categories()
