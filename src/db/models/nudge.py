from datetime import datetime

from pydantic import BaseModel, Field


class NudgeDocument(BaseModel):
    user_id: str
    nudge_type: str
    message: str
    trigger_reason: str = ""
    was_read: bool = False
    user_acted: bool = False
    sent_at: datetime = Field(default_factory=datetime.utcnow)
