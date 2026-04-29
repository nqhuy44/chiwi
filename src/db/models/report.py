from datetime import UTC, datetime
from beanie import Document
from pydantic import Field


class ReportDocument(Document):
    user_id: str
    report_type: str
    period: str
    data: dict = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "reports"
