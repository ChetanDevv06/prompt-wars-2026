"""
Application configuration.

All settings are loaded from environment variables.
No defaults should contain secrets or production values.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    LabLink application settings.

    All values are loaded from environment variables.
    See .env.example for the full list of supported variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = Field(default="development", description="Runtime environment")
    app_debug: bool = Field(default=False, description="Enable debug mode")
    app_host: str = Field(default="0.0.0.0", description="Bind host")
    app_port: int = Field(default=8000, description="Bind port")
    app_log_level: str = Field(default="INFO", description="Logging level")

    # Database
    database_url: str = Field(
        default="postgresql://lablink:lablink_dev_password@localhost:5432/lablink_db",
        description="PostgreSQL connection URL",
    )
    database_pool_size: int = Field(
        default=5,
        ge=1,
        le=50,
        description="SQLAlchemy connection pool size",
    )
    database_max_overflow: int = Field(
        default=10,
        ge=0,
        le=50,
        description="SQLAlchemy connection pool max overflow",
    )
    database_pool_timeout: int = Field(
        default=30,
        ge=1,
        description="SQLAlchemy pool timeout in seconds",
    )
    database_pool_recycle: int = Field(
        default=1800,
        ge=60,
        description="SQLAlchemy pool recycle timeout in seconds",
    )
    database_echo: bool = Field(
        default=False,
        description="Echo SQL queries to logger (debug only)",
    )

    # CORS
    allowed_origins: list[str] | str = Field(
        default=["http://localhost:3000"],
        description="List of allowed CORS origins",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json

                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return [str(item) for item in v]
        return ["http://localhost:3000"]

    @field_validator("app_log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            msg = f"Invalid log level '{v}'. Must be one of {valid}"
            raise ValueError(msg)
        return upper

    @field_validator("app_env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        valid = {"development", "test", "staging", "production"}
        lower = v.lower()
        if lower not in valid:
            msg = f"Invalid environment '{v}'. Must be one of {valid}"
            raise ValueError(msg)
        return lower

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache
def get_settings() -> Settings:
    """
    Return the cached application settings singleton.

    Uses lru_cache so Settings is instantiated exactly once
    per process. In tests, call get_settings.cache_clear()
    before overriding environment variables.
    """
    return Settings()
