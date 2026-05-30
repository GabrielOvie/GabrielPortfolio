from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    environment: str = "development"
    secret_key: str
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    refresh_token_expire_days: int = 30

    # Database
    database_url: str

    # Redis
    redis_url: str

    # Internal services
    orchestrator_url: str
    orchestrator_api_key: str

    # Object storage
    s3_endpoint_url: str = ""
    s3_bucket: str = "infraforge-artifacts"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Lab limits
    max_concurrent_runs_per_user: int = 2
    default_run_timeout_minutes: int = 90

    # Features
    feature_vm_labs: bool = False
    feature_team_labs: bool = False
    feature_public_portfolio: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
