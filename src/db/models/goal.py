from datetime import UTC, datetime
from typing import Literal
from beanie import Document
from pydantic import Field


class GoalDocument(Document):
    user_id: str
    name: str
    target_amount: float
    currency: str = "VND"
    current_amount: float = 0.0
    deadline: datetime | None = None
    category_id: str | None = None
    status: Literal["active", "achieved", "cancelled"] = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "goals"
