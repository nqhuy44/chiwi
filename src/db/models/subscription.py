from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class SubscriptionDocument(BaseModel):
    user_id: str
    name: str                    # display name, e.g. "Netflix"
    merchant_name: str           # normalised for transaction matching
    amount: float
    currency: str = "VND"
    period: Literal["weekly", "monthly", "yearly"] = "monthly"
    next_charge_date: datetime
    last_charged_at: datetime | None = None
    is_active: bool = True
    source: Literal["manual", "auto_detected"] = "manual"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Lifecycle fields
    cancelled_at: datetime | None = None
    cancellation_reason: Literal["manual", "replaced"] | None = None
    replaces_id: str | None = None   # _id of the subscription this supersedes
