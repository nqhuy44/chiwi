from datetime import UTC, datetime
from beanie import Document
from pydantic import Field


class UserDocument(Document):
    """Platform-agnostic user identity."""
    user_id: str                              # internal unique id (uuid or username)
    username: str                             # unique login name
    hashed_password: str | None = None        # for mobile login
    refresh_token_hash: str | None = None     # for token rotation
    full_name: str = ""
    telegram_chat_id: str | None = None       # linked Telegram ID
    link_code: str | None = None              # 6-digit code for account linking
    link_code_expires: datetime | None = None # expiry for the link code
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "users"


class UserProfileDocument(Document):
    """Personalization preferences — editable via Android Settings."""
    user_id: str
    timezone: str = "Asia/Ho_Chi_Minh"
    occupation: str = ""
    hobbies: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    communication_tone: str = "friendly"      # friendly | playful | formal | concise
    nudge_frequency: str = "daily"            # off | daily | weekly
    language: str = "vi"
    extras: dict = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "user_profiles"
