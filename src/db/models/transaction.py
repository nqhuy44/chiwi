from datetime import UTC, datetime
from typing import Literal
from beanie import Document
from pydantic import Field


class TransactionDocument(Document):
    user_id: str
    source: Literal["notification", "chat", "voice", "manual"]
    amount: float
    currency: str = "VND"
    direction: Literal["inflow", "outflow", "savingflow"]
    raw_text: str
    merchant_name: str | None = None
    category_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    transaction_time: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_confidence: Literal["high", "medium", "low"] = "low"
    user_corrected: bool = False
    locked: bool = False  # user-confirmed; blocks edits and deletes
    ai_metadata: dict = Field(default_factory=dict)
    subscription_id: str | None = None   # set when this charge matches a registered subscription
    goal_id: str | None = None          # set when this transaction is an accumulation for a goal

    class Settings:
        name = "transactions"
