from datetime import UTC, datetime
from typing import Literal
from beanie import Document
from pydantic import Field


class NudgeDocument(Document):
    user_id: str
    nudge_type: str  # spending_alert, budget_warning, etc.
    title: str = "ChiWi Insight"
    message: str
    channel: Literal["telegram", "android", "both"] = "both"
    metadata: dict = Field(default_factory=dict)  # {transaction_id: ..., category_id: ...}
    trigger_reason: str = ""
    was_read: bool = False
    user_acted: bool = False
    sent_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "nudges"
