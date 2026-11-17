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
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_dist_path: str | None = None
    database_url: str = "postgresql+psycopg://localhost/safarismart"
    auth_secret_key: SecretStr | None = None
    auth_access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    auth_issuer: str = "safarismart-api"
    auth_audience: str = "safarismart-operator"
    sms_enabled: bool = False
    sms_provider: Literal["africastalking", "local"] = "africastalking"
    africastalking_environment: Literal["sandbox", "production"] = "sandbox"
    africastalking_username: str | None = None
    africastalking_api_key: SecretStr | None = None
    africastalking_sender_id: str | None = None
    ai_provider: Literal["fallback", "ollama"] = "fallback"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_seconds: float = Field(default=5.0, ge=0.5, le=30.0)
    ussd_rate_limit_per_minute: int = Field(default=30, ge=1, le=120)
    ussd_rate_limit_max_sessions: int = Field(default=10_000, ge=100, le=100_000)

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

    @field_validator("frontend_origins")
    @classmethod
    def validate_frontend_origins(cls, value: str) -> str:
        """Normalize an explicit comma-separated CORS allowlist."""

        origins = [origin.strip().rstrip("/") for origin in value.split(",")]
        if not origins or any(
            not origin.startswith(("http://", "https://")) or "*" in origin
            for origin in origins
        ):
            raise ValueError(
                "FRONTEND_ORIGINS must be an explicit comma-separated HTTP(S) allowlist"
            )
        return ",".join(dict.fromkeys(origins))

    @property
    def allowed_frontend_origins(self) -> list[str]:
        """Return the normalized CORS allowlist for FastAPI middleware."""

        return self.frontend_origins.split(",")

    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama_base_url(cls, value: str) -> str:
        """Allow only an explicit HTTP(S) endpoint for the local model service."""

        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("OLLAMA_BASE_URL must use http:// or https://")
        return normalized

    @field_validator("ollama_model")
    @classmethod
    def validate_ollama_model(cls, value: str) -> str:
        """Reject blank model identifiers early."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("OLLAMA_MODEL cannot be blank")
        return normalized

    @field_validator(
        "frontend_dist_path",
        "auth_secret_key",
        "africastalking_username",
        "africastalking_api_key",
        "africastalking_sender_id",
        mode="before",
    )
    @classmethod
    def normalize_optional_configuration(cls, value: object) -> object:
        """Treat empty optional environment values as unconfigured."""

        return None if isinstance(value, str) and not value.strip() else value

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

    @model_validator(mode="after")
    def validate_sms_configuration(self) -> "Settings":
        """Keep SMS disabled or require one internally consistent credential set."""

        username = self.africastalking_username
        api_key = self.africastalking_api_key
        has_any_credentials = username is not None or api_key is not None

        if self.sms_provider == "local" and self.app_env in {
            "staging",
            "production",
        }:
            raise ValueError("The local SMS provider is limited to development and test")

        if (
            self.sms_enabled
            and self.sms_provider == "africastalking"
            and not has_any_credentials
        ):
            raise ValueError(
                "AFRICASTALKING_USERNAME and AFRICASTALKING_API_KEY "
                "must be configured together"
            )

        if has_any_credentials:
            if username is None or api_key is None:
                raise ValueError(
                    "AFRICASTALKING_USERNAME and AFRICASTALKING_API_KEY "
                    "must be configured together"
                )

            normalized_username = username.strip()
            if self.africastalking_environment == "sandbox":
                if normalized_username.lower() != "sandbox":
                    raise ValueError(
                        "The Africa's Talking sandbox username must be 'sandbox'"
                    )
            elif normalized_username.lower() == "sandbox":
                raise ValueError(
                    "Production SMS cannot use the Africa's Talking sandbox username"
                )

            secret = api_key.get_secret_value().strip()
            insecure_markers = ("placeholder", "your-api-key", "change-me", "<", ">")
            if len(secret) < 8 or any(
                marker in secret.lower() for marker in insecure_markers
            ):
                raise ValueError("AFRICASTALKING_API_KEY is not a valid configured key")

        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance for the running process."""

    return Settings()
