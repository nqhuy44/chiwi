from datetime import datetime

from pydantic import BaseModel, Field


class ReportDocument(BaseModel):
    user_id: str
    report_type: str
    period: str
    data: dict = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
