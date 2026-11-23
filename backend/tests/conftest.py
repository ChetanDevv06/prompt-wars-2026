"""
Pytest configuration and shared fixtures.

Uses an isolated test configuration — no production database required
for unit and basic integration tests.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Override environment before any application code runs
os.environ["APP_ENV"] = "test"
os.environ["APP_DEBUG"] = "false"
os.environ["DATABASE_URL"] = "postgresql://lablink:lablink_dev_password@localhost:5432/lablink_test"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"


@pytest.fixture(scope="session", autouse=True)
def _clear_settings_cache() -> None:
    """Clear lru_cache on Settings so test env vars take effect."""
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    """
    Return a TestClient backed by a patched application.

    Database connectivity is mocked so no real Postgres is needed
    for unit-level tests.
    """
    with patch(
        "app.api.v1.endpoints.health.check_database_connection",
        return_value=True,
    ):
        from app.main import app

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


@pytest.fixture(scope="session")
def client_db_down() -> Generator[TestClient, None, None]:
    """TestClient where the database appears unreachable."""
    with patch(
        "app.api.v1.endpoints.health.check_database_connection",
        return_value=False,
    ):
        import app.main as main_module

        importlib.reload(main_module)
        with TestClient(main_module.app, raise_server_exceptions=False) as c:
            yield c
