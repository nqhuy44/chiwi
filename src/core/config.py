from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "ChiWi"
    log_level: str = "INFO"
    debug: bool = False

    # Gemini
    gemini_api_key: str = ""
    gemini_model_flash: str = "gemini-2.5-flash"
    gemini_model_pro: str = "gemini-2.5-pro"

    # Telegram
    telegram_bot_token: str = ""
    telegram_allowed_user_ids: str = ""
    telegram_webhook_url: str = ""
    telegram_webhook_secret: str = ""
    telegram_message_max_age_seconds: int = 120  # Drop messages older than this
    telegram_rate_limit_per_minute: int = 20  # Max messages per user per minute

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "chiwi"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Security
    pii_mask_enabled: bool = True

    # Business timezone — used for day-boundary math (reports, budgets,
    # "hôm nay"). Storage stays in UTC.
    business_timezone: str = "Asia/Ho_Chi_Minh"

    # Categories — path to a JSON file with the list of spending categories
    # used by the Tagging Agent and seeded into the categories collection.
    # Empty → use the bundled default at <project>/config/categories.json.
    categories_file: str = ""

    # User profiles — JSON map keyed by telegram_user_id. Drives the
    # Behavioral Agent's nudge personalization. Empty → bundled default
    # at <project>/config/user_profiles.json.
    user_profiles_file: str = ""

    # Behavioral / nudge limits.
    nudge_max_per_day: int = 2
    nudge_quiet_hour_start: int = 22  # inclusive, local time
    nudge_quiet_hour_end: int = 7  # exclusive, local time

    @property
    def allowed_user_ids(self) -> list[str]:
        if not self.telegram_allowed_user_ids:
            return []
        return [uid.strip() for uid in self.telegram_allowed_user_ids.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
