"""
Unit tests for domain exceptions.
"""

from __future__ import annotations

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    LabLinkError,
    NotFoundError,
    UnauthorisedError,
    ValidationError,
)


class TestDomainExceptions:
    """Tests for the LabLink exception hierarchy."""

    def test_not_found_error(self) -> None:
        exc = NotFoundError("Resource not found")
        assert exc.status_code == 404
        assert exc.error_code == "NOT_FOUND"
        assert exc.message == "Resource not found"

    def test_conflict_error(self) -> None:
        exc = ConflictError("Already exists")
        assert exc.status_code == 409
        assert exc.error_code == "CONFLICT"

    def test_validation_error(self) -> None:
        exc = ValidationError("Invalid input")
        assert exc.status_code == 422
        assert exc.error_code == "VALIDATION_ERROR"

    def test_unauthorised_error(self) -> None:
        exc = UnauthorisedError("Login required")
        assert exc.status_code == 401
        assert exc.error_code == "UNAUTHORISED"

    def test_forbidden_error(self) -> None:
        exc = ForbiddenError("Access denied")
        assert exc.status_code == 403
        assert exc.error_code == "FORBIDDEN"

    def test_all_errors_inherit_from_base(self) -> None:
        for cls in (
            NotFoundError,
            ConflictError,
            ValidationError,
            UnauthorisedError,
            ForbiddenError,
        ):
            assert issubclass(cls, LabLinkError)

    def test_base_error_has_message(self) -> None:
        exc = LabLinkError("base message")
        assert str(exc) == "base message"
