"""Runtime configuration, read from environment variables (prefix ``LIFE_``)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LIFE_", env_file=".env", extra="ignore")

    table_name: str = "life-api"
    lake_bucket: str = "life-api-lake"
    timezone: str = "America/New_York"

    # Write endpoints are protected by an API key. Set it directly (local dev)
    # or point at an SSM SecureString parameter (AWS).
    api_key: str | None = None
    api_key_param: str | None = None

    google_token_param: str = "/life-api/prod/google-health/token"  # noqa: S105 - SSM path
    google_client_param: str = "/life-api/prod/google-health/client"

    aws_region: str = Field(
        default="us-east-1", validation_alias=AliasChoices("LIFE_AWS_REGION", "AWS_REGION")
    )
    cors_origins: list[str] = ["*"]

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def today(self) -> date:
        return datetime.now(self.tz).date()

    def yesterday(self) -> date:
        return self.today() - timedelta(days=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
