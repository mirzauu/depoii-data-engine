from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Service meta
    APP_NAME: str = "Depoii Commercial Roofing Data Engine"
    VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Security
    API_KEY: str = "depoii-secret-dev-key-2026"
    API_KEY_HEADER: str = "X-Depoii-Key"

    # Database URLs
    DATABASE_URL: str = "sqlite+aiosqlite:///./depoii_local.db"
    SYNC_DATABASE_URL: str = "sqlite:///./depoii_local.db"
    LOCAL_DATABASE_URL: str = "sqlite:///./depoii_local.db"
    USE_LOCAL_DB: bool = True

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # External APIs
    SOCRATA_APP_TOKEN: Optional[str] = None
    NOAA_SPC_API_ENDPOINT: str = "https://www.spc.noaa.gov/climo/reports/today.csv"

    # Observability & Alerts
    SLACK_ALERT_WEBHOOK: Optional[str] = None
    LOG_LEVEL: str = "INFO"


settings = Settings()
