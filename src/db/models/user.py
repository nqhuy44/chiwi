from datetime import datetime

from pydantic import BaseModel, Field


class UserDocument(BaseModel):
    telegram_user_id: str
    telegram_chat_id: str
    display_name: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserProfileDocument(BaseModel):
    user_id: str
    occupation: str = ""
    hobbies: list[str] = Field(default_factory=list)
    financial_goals: dict = Field(default_factory=dict)
    monthly_income: float = 0.0
    currency: str = "VND"
    preferences: dict = Field(default_factory=dict)
