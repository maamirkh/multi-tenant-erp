"""Unit tests for application exception hierarchy.

T138 — Each subclass must carry the correct default code and http_status.
"""

import pytest

from core.exceptions.base import (
    ApplicationException,
    ConflictException,
    ForbiddenException,
    InfrastructureException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)


class TestApplicationException:
    def test_default_code_is_internal_error(self) -> None:
        exc = ApplicationException("something went wrong")
        assert exc.code == "INTERNAL_ERROR"

    def test_default_http_status_is_500(self) -> None:
        exc = ApplicationException("something went wrong")
        assert exc.http_status == 500

    def test_message_stored_correctly(self) -> None:
        exc = ApplicationException("test message")
        assert exc.message == "test message"

    def test_details_defaults_to_empty_dict(self) -> None:
        exc = ApplicationException("msg")
        assert exc.details == {}

    def test_custom_details_are_stored(self) -> None:
        exc = ApplicationException("msg", details={"field": "value"})
        assert exc.details == {"field": "value"}

    def test_repr_contains_class_name(self) -> None:
        exc = ApplicationException("msg")
        assert "ApplicationException" in repr(exc)

    def test_is_instance_of_exception(self) -> None:
        exc = ApplicationException("msg")
        assert isinstance(exc, Exception)


class TestValidationException:
    def test_code_is_validation_error(self) -> None:
        exc = ValidationException("bad input")
        assert exc.code == "VALIDATION_ERROR"

    def test_http_status_is_422(self) -> None:
        exc = ValidationException("bad input")
        assert exc.http_status == 422

    def test_is_subclass_of_application_exception(self) -> None:
        exc = ValidationException("bad input")
        assert isinstance(exc, ApplicationException)

    def test_details_can_be_passed(self) -> None:
        exc = ValidationException("bad input", details={"field": "name"})
        assert exc.details == {"field": "name"}

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(ValidationException):
            raise ValidationException("invalid")


class TestNotFoundException:
    def test_code_is_not_found(self) -> None:
        exc = NotFoundException("not here")
        assert exc.code == "NOT_FOUND"

    def test_http_status_is_404(self) -> None:
        exc = NotFoundException("not here")
        assert exc.http_status == 404

    def test_is_subclass_of_application_exception(self) -> None:
        exc = NotFoundException("not here")
        assert isinstance(exc, ApplicationException)


class TestConflictException:
    def test_code_is_conflict(self) -> None:
        exc = ConflictException("already exists")
        assert exc.code == "CONFLICT"

    def test_http_status_is_409(self) -> None:
        exc = ConflictException("already exists")
        assert exc.http_status == 409

    def test_is_subclass_of_application_exception(self) -> None:
        exc = ConflictException("already exists")
        assert isinstance(exc, ApplicationException)


class TestUnauthorizedException:
    def test_code_is_unauthorized(self) -> None:
        exc = UnauthorizedException()
        assert exc.code == "UNAUTHORIZED"

    def test_http_status_is_401(self) -> None:
        exc = UnauthorizedException()
        assert exc.http_status == 401

    def test_default_message_is_sensible(self) -> None:
        exc = UnauthorizedException()
        assert exc.message  # non-empty

    def test_custom_message_is_stored(self) -> None:
        exc = UnauthorizedException("please log in")
        assert exc.message == "please log in"

    def test_is_subclass_of_application_exception(self) -> None:
        exc = UnauthorizedException()
        assert isinstance(exc, ApplicationException)


class TestForbiddenException:
    def test_code_is_forbidden(self) -> None:
        exc = ForbiddenException()
        assert exc.code == "FORBIDDEN"

    def test_http_status_is_403(self) -> None:
        exc = ForbiddenException()
        assert exc.http_status == 403

    def test_default_message_is_sensible(self) -> None:
        exc = ForbiddenException()
        assert exc.message  # non-empty

    def test_is_subclass_of_application_exception(self) -> None:
        exc = ForbiddenException()
        assert isinstance(exc, ApplicationException)


class TestInfrastructureException:
    def test_code_is_internal_error(self) -> None:
        exc = InfrastructureException("db down")
        assert exc.code == "INTERNAL_ERROR"

    def test_http_status_is_500(self) -> None:
        exc = InfrastructureException("db down")
        assert exc.http_status == 500

    def test_is_subclass_of_application_exception(self) -> None:
        exc = InfrastructureException("db down")
        assert isinstance(exc, ApplicationException)
