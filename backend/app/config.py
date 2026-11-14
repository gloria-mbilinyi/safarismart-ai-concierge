"""Environment-based application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a root `.env` file."""

    app_name: str = "SafariSmart AI Concierge"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_debug: bool = False
    api_v1_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://localhost/safarismart"
    auth_secret_key: SecretStr | None = None
    auth_access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    auth_issuer: str = "safarismart-api"
    auth_audience: str = "safarismart-operator"

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        """Normalize the configured API prefix and require an absolute path."""

        if not value.startswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/'")

        return value.rstrip("/")

    @field_validator("auth_secret_key", mode="before")
    @classmethod
    def normalize_auth_secret(cls, value: object) -> object:
        """Treat an empty environment variable as an unconfigured secret."""

        return None if value == "" else value

    @model_validator(mode="after")
    def validate_deployment_security(self) -> "Settings":
        """Reject weak signing keys and local defaults in deployed environments."""

        if self.auth_secret_key is not None:
            secret = self.auth_secret_key.get_secret_value()
            insecure_markers = ("change-me", "development", "placeholder", "<", ">")
            if len(secret) < 32 or any(
                marker in secret.lower() for marker in insecure_markers
            ):
                raise ValueError(
                    "AUTH_SECRET_KEY must be a strong value of at least 32 characters"
                )

        if self.app_env in {"staging", "production"}:
            if self.auth_secret_key is None:
                raise ValueError(
                    "AUTH_SECRET_KEY is required outside development and test"
                )
            if self.database_url == "postgresql+psycopg://localhost/safarismart":
                raise ValueError(
                    "DATABASE_URL must be explicitly configured for deployment"
                )
            if self.app_debug:
                raise ValueError(
                    "APP_DEBUG cannot be enabled in staging or production"
                )

        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for the running process."""

    return Settings()
