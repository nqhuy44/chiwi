from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class TransactionDocument(BaseModel):
    user_id: str
    source: Literal["notification", "chat", "voice", "manual"]
    amount: float
    currency: str = "VND"
    direction: Literal["inflow", "outflow"]
    raw_text: str
    merchant_name: str | None = None
    category_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    transaction_time: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    agent_confidence: Literal["high", "medium", "low"] = "low"
    user_corrected: bool = False
    ai_metadata: dict = Field(default_factory=dict)
