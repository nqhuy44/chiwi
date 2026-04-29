from datetime import UTC, datetime
from beanie import Document
from pydantic import Field


class CorrectionDocument(Document):
    user_id: str
    transaction_id: str
    merchant_name: str | None = None
    old_category: str | None = None
    new_category: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "corrections"
