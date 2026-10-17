from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRETS = frozenset(
    {
        "",
        "change-me",
        "changeme",
        "secret",
        "replace-with-a-long-random-value",
        "replace-me",
    }
)
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_env: Literal["demo", "production"] = "demo"
    database_url: str = "sqlite:///./data/app.db"
    secret_key: SecretStr = SecretStr("")
    cors_origins: str = ""
    first_admin_email: str | None = None
    first_admin_password: SecretStr | None = None
    git_sha: str = "dev"
    build_time: str = "unknown"
    app_version: str = "0.1.0"
    upload_dir: str = "./data/uploads"
    session_ttl_hours: int = 12
    cookie_secure: bool | None = None
    login_max_attempts: int = 5
    login_window_seconds: int = 900

    @field_validator("first_admin_email", "first_admin_password", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cookie_is_secure(self) -> bool:
        """Secure cookies are mandatory in production; elsewhere they follow the setting."""
        return True if self.is_production else bool(self.cookie_secure)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def secret_problem(self) -> str | None:
        """Why SECRET_KEY is unacceptable in production, or None if it is fine."""
        value = self.secret_key.get_secret_value()
        if value.strip().lower() in PLACEHOLDER_SECRETS:
            return "SECRET_KEY is missing or is a placeholder value"
        if len(value) < MIN_SECRET_LENGTH:
            return f"SECRET_KEY is shorter than {MIN_SECRET_LENGTH} characters"
        return None
