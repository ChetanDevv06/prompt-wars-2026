"""
Unit tests for application configuration.
"""

from __future__ import annotations

import pytest


class TestSettings:
    """Tests for the Settings class."""

    def setup_method(self) -> None:
        from app.core.config import get_settings
        get_settings.cache_clear()

    def teardown_method(self) -> None:
        from app.core.config import get_settings
        get_settings.cache_clear()

    def test_default_settings_load(self) -> None:
        """Settings can be instantiated with defaults."""
        from app.core.config import Settings

        s = Settings(
            app_env="test",
            database_url="postgresql://u:p@localhost/db",
        )
        assert s.app_env == "test"
        assert s.app_debug is False

    def test_valid_log_levels(self) -> None:
        """All valid log level strings are accepted."""
        from app.core.config import Settings

        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            s = Settings(
                app_env="test",
                app_log_level=level,
                database_url="postgresql://u:p@localhost/db",
            )
            assert s.app_log_level == level

    def test_log_level_case_insensitive(self) -> None:
        """Log level is normalised to uppercase."""
        from app.core.config import Settings

        s = Settings(
            app_env="test",
            app_log_level="debug",
            database_url="postgresql://u:p@localhost/db",
        )
        assert s.app_log_level == "DEBUG"

    def test_invalid_log_level_raises(self) -> None:
        """Invalid log level raises a validation error."""
        from pydantic import ValidationError

        from app.core.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                app_env="test",
                app_log_level="VERBOSE",
                database_url="postgresql://u:p@localhost/db",
            )

    def test_valid_environments(self) -> None:
        """All valid environment names are accepted."""
        from app.core.config import Settings

        for env in ("development", "test", "staging", "production"):
            s = Settings(app_env=env, database_url="postgresql://u:p@localhost/db")
            assert s.app_env == env

    def test_invalid_environment_raises(self) -> None:
        """Invalid environment raises a validation error."""
        from pydantic import ValidationError

        from app.core.config import Settings

        with pytest.raises(ValidationError):
            Settings(
                app_env="unknown",
                database_url="postgresql://u:p@localhost/db",
            )

    def test_is_test_property(self) -> None:
        """is_test returns True for test environment."""
        from app.core.config import Settings

        s = Settings(app_env="test", database_url="postgresql://u:p@localhost/db")
        assert s.is_test is True
        assert s.is_production is False
        assert s.is_development is False

    def test_get_settings_is_cached(self) -> None:
        """get_settings returns the same instance on repeated calls."""
        from app.core.config import get_settings

        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
