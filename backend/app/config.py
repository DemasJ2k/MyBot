from pydantic_settings import BaseSettings
from pydantic import field_validator
import os


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str = ""
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    database_url: str = "sqlite+aiosqlite:///./flowrex_dev.db"
    redis_url: str = "redis://localhost:6379/0"
    debug: bool = True
    csrf_protection_enabled: bool = True

    # TwelveData API
    twelvedata_api_key: str = ""
    twelvedata_base_url: str = "https://api.twelvedata.com"
    twelvedata_rate_limit: int = 8  # requests per minute for free tier

    @field_validator("app_secret_key", "jwt_secret_key", mode="before")
    @classmethod
    def validate_secrets(cls, v: str, info) -> str:
        if not v and os.getenv("APP_ENV", "development") == "development":
            import secrets
            return secrets.token_hex(32)
        if not v:
            raise ValueError(f"{info.field_name} must be set")
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env in ("production", "prod")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
