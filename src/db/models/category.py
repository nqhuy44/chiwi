from pydantic import BaseModel


class CategoryDocument(BaseModel):
    name: str
    icon_emoji: str
    parent_category: str | None = None
    is_system: bool = True


DEFAULT_CATEGORIES = [
    CategoryDocument(name="Food & Beverage", icon_emoji="\U0001f354"),
    CategoryDocument(
        name="Cafe", icon_emoji="\u2615", parent_category="Food & Beverage"
    ),
    CategoryDocument(name="Transportation", icon_emoji="\U0001f697"),
    CategoryDocument(name="Shopping", icon_emoji="\U0001f6d2"),
    CategoryDocument(name="Housing", icon_emoji="\U0001f3e0"),
    CategoryDocument(
        name="Utilities", icon_emoji="\U0001f4a1", parent_category="Housing"
    ),
    CategoryDocument(name="Entertainment", icon_emoji="\U0001f3ac"),
    CategoryDocument(name="Hobbies", icon_emoji="\U0001f4f8"),
    CategoryDocument(name="Health", icon_emoji="\U0001f48a"),
    CategoryDocument(name="Education", icon_emoji="\U0001f4da"),
    CategoryDocument(name="Income", icon_emoji="\U0001f4b0"),
    CategoryDocument(name="Transfer", icon_emoji="\U0001f504"),
    CategoryDocument(name="Uncategorized", icon_emoji="\u2753"),
]
