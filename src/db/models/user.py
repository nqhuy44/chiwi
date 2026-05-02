import uuid
from datetime import UTC, datetime
from beanie import Document, Indexed
from pydantic import Field


class UserDocument(Document):
    """
    Central Identity Document.
    A user has one stable user_id (UUID) and multiple ways to authenticate.
    """
    user_id: Indexed(str, unique=True)        # Permanent internal ID (UUID)
    email: Indexed(str, unique=True) | None = None
    
    # Authentication methods
    username: Indexed(str, unique=True) | None = None  # For local login
    hashed_password: str | None = None
    refresh_token_hash: str | None = None
    reset_code: str | None = None
    reset_code_expires: datetime | None = None
    
    # External identities (for SSO readiness & Account Linking)
    telegram_id: Indexed(str, unique=True) | None = None
    google_id: Indexed(str, unique=True) | None = None
    apple_id: Indexed(str, unique=True) | None = None
    
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "users"


class UserProfileDocument(Document):
    """Personalization preferences linked to the central User via user_id."""
    user_id: Indexed(str, unique=True)
    display_name: str = ""
    timezone: str = "Asia/Ho_Chi_Minh"
    occupation: str = ""
    hobbies: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    communication_tone: str = "friendly"
    assistant_personality: str = "encouraging"
    nudge_frequency: str = "daily"
    language: str = "vi"
    chat_id: str = ""
    extras: dict = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    class Settings:
        name = "user_profiles"
