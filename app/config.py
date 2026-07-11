"""Application configuration from environment."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_secret_key: str = "change-me"
    app_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    database_url: str = "sqlite:///./data/email_agent.db"

    default_tenant_id: str = "default"
    default_tenant_name: str = "Moving Company"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b-instruct"
    ollama_read_timeout_seconds: int = 600
    ollama_max_thread_chars: int = 4500
    ollama_num_predict: int = 512
    # Extract-specific (smaller = faster on weak CPU; enrich fills the rest)
    ollama_extract_num_predict: int = 400
    ollama_extract_max_chars: int = 3500

    classify_enabled: bool = True
    classify_max_chars: int = 2500

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    pricing_sheet_id: str = ""
    google_service_account_file: str = ""

    reply_mode: str = "draft"  # draft | send

    scheduler_enabled: bool = True
    poll_gmail_interval_minutes: int = 5
    reminder_check_interval_minutes: int = 60
    followup_check_interval_minutes: int = 60

    followup_wait_days: int = 3
    followup_max_attempts: int = 2

    reminder_days: str = "3,1"

    rules_file: str = "config/rules.yaml"

    # Allow HTTP OAuth redirect (required for http://sslip.io testing). Use HTTPS in production.
    oauth_allow_insecure_transport: bool = False

    @property
    def reminder_day_list(self) -> list[int]:
        return [int(d.strip()) for d in self.reminder_days.split(",") if d.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def data_dir(self) -> Path:
        return Path("data")

    @property
    def tokens_dir(self) -> Path:
        return Path("data/tokens")


@lru_cache
def get_settings() -> Settings:
    return Settings()
