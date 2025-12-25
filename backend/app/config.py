"""
Application configuration for Flowrex.

Prompt 17 - Deployment Prep.

Provides:
- Environment-aware settings
- Secrets validation
- CORS configuration
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
import os


class Settings(BaseSettings):
    # Environment
    app_env: str = "development"
    environment: str = ""  # Alias for app_env
    
    # Security
    app_secret_key: str = ""
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./flowrex_dev.db"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Debug
    debug: bool = True
    
    # CSRF
    csrf_protection_enabled: bool = True
    
    # CORS
    cors_allowed_origins: list[str] | str = ["http://localhost:3000"]

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
    def effective_env(self) -> str:
        """Get effective environment name."""
        return self.environment or self.app_env

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.effective_env in ("production", "prod")

    @property
    def is_staging(self) -> bool:
        """Check if running in staging."""
        return self.effective_env in ("staging", "stage")

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.effective_env in ("development", "dev", "")

    @property
    def cors_origins(self) -> list[str]:
        """Return parsed CORS origins as list."""
        if isinstance(self.cors_allowed_origins, list):
            return self.cors_allowed_origins
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra env vars not defined in Settings


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Default instance for backwards compatibility
settings = Settings()
