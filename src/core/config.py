from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "ChiWi"
    log_level: str = "INFO"
    debug: bool = False

    # Gemini
    gemini_api_key: str = ""

    # Telegram
    telegram_bot_token: str = ""
    telegram_allowed_user_ids: str = ""
    telegram_webhook_url: str = ""

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "chiwi"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Security
    pii_mask_enabled: bool = True

    @property
    def allowed_user_ids(self) -> list[str]:
        if not self.telegram_allowed_user_ids:
            return []
        return [uid.strip() for uid in self.telegram_allowed_user_ids.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
