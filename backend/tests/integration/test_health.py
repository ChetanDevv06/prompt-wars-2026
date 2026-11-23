"""
Integration tests for the health endpoint and application startup.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


class TestApplicationStartup:
    """Tests that the application initialises correctly."""

    def test_app_imports_without_error(self) -> None:
        """Application module can be imported."""
        import app.main  # noqa: F401

    def test_app_instance_created(self) -> None:
        """FastAPI app instance is accessible."""
        from app.main import app

        assert app is not None
        assert app.title == "LabLink API"

    def test_v1_routes_registered(self) -> None:
        """API v1 routes are registered on the application."""
        from app.main import app

        openapi_paths = app.openapi().get("paths", {})
        assert any(path.startswith("/api/v1") for path in openapi_paths)


class TestHealthEndpoint:
    """Tests for GET /api/v1/health."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Health endpoint returns HTTP 200."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_response_shape(self, client: TestClient) -> None:
        """Health response contains expected keys."""
        response = client.get("/api/v1/health")
        body = response.json()

        assert "status" in body
        assert "timestamp" in body
        assert "version" in body
        assert "environment" in body
        assert "python_version" in body
        assert "database" in body

    def test_health_ok_when_db_connected(self, client: TestClient) -> None:
        """Health status is 'ok' when database is reachable (mocked)."""
        response = client.get("/api/v1/health")
        body = response.json()

        assert body["status"] == "ok"
        assert body["database"]["connected"] is True
        assert body["database"]["status"] == "ok"

    def test_health_environment_is_test(self, client: TestClient) -> None:
        """Health endpoint reports the test environment."""
        response = client.get("/api/v1/health")
        body = response.json()
        assert body["environment"] == "test"

    def test_health_no_secrets_in_response(self, client: TestClient) -> None:
        """Health response does not include sensitive fields."""
        response = client.get("/api/v1/health")
        body = response.json()
        body_str = str(body).lower()

        # Verify no password, token, secret keys appear
        for sensitive in ("password", "secret", "token", "key", "database_url"):
            assert sensitive not in body_str, (
                f"Sensitive field '{sensitive}' found in health response"
            )

    def test_health_version_string(self, client: TestClient) -> None:
        """Health response includes a non-empty version string."""
        response = client.get("/api/v1/health")
        body = response.json()
        assert body["version"]
        assert "." in body["version"]

    def test_request_id_header_present(self, client: TestClient) -> None:
        """Every response includes an X-Request-ID header."""
        response = client.get("/api/v1/health")
        assert "x-request-id" in response.headers


class TestErrorHandling:
    """Tests for centralised error handling."""

    def test_404_for_unknown_route(self, client: TestClient) -> None:
        """Unknown routes return HTTP 404."""
        response = client.get("/api/v1/nonexistent-route")
        assert response.status_code == 404

    def test_method_not_allowed(self, client: TestClient) -> None:
        """Wrong HTTP method returns HTTP 405."""
        response = client.post("/api/v1/health")
        assert response.status_code == 405
