"""Unit tests for PasswordService.

Covers: hashing, verification, complexity, common-password check, history.
All tests use mocked or minimal Settings to avoid loading .env.
"""

from __future__ import annotations

from typing import cast

import pytest

from core.config.settings import Settings
from core.exceptions.base import ValidationException
from modules.auth.services.password_service import PasswordService

_SETTINGS = Settings(
    DATABASE_URL="postgresql://x:x@localhost/x",
    SECRET_KEY="test-secret-key-minimum-32-chars-ok",
    JWT_SECRET_KEY="test-jwt-secret-key-min-32-chars-ok!",
    PASSWORD_MIN_LENGTH=12,
    PASSWORD_MAX_LENGTH=128,
    PASSWORD_HISTORY_COUNT=5,
    # Test-only Argon2 performance settings (not a security relaxation —
    # these are the cheapest values the shared Settings model already
    # permits; production defaults are untouched). This file hashes/
    # verifies real passwords in every test, so this materially speeds
    # up the suite. See tests/conftest.py's `_TEST_ARGON2_KWARGS`.
    ARGON2_TIME_COST=1,
    ARGON2_MEMORY_COST=19456,
    ARGON2_PARALLELISM=1,
)

_VALID_PASSWORD = "ValidPass@12345"
_VALID_EMAIL = "user@example.com"


@pytest.fixture
def svc() -> PasswordService:
    return PasswordService(_SETTINGS)


class TestHashAndVerify:
    def test_hash_returns_argon2_string(self, svc: PasswordService) -> None:
        result = svc.hash_password(_VALID_PASSWORD)
        assert result.startswith("$argon2")

    def test_verify_correct_password_returns_true(self, svc: PasswordService) -> None:
        hashed = svc.hash_password(_VALID_PASSWORD)
        assert svc.verify_password(_VALID_PASSWORD, hashed) is True

    def test_verify_wrong_password_returns_false(self, svc: PasswordService) -> None:
        hashed = svc.hash_password(_VALID_PASSWORD)
        assert svc.verify_password("WrongPassword@1", hashed) is False

    def test_different_hashes_for_same_password(self, svc: PasswordService) -> None:
        h1 = svc.hash_password(_VALID_PASSWORD)
        h2 = svc.hash_password(_VALID_PASSWORD)
        assert h1 != h2  # Argon2 uses random salt


class TestComplexityValidation:
    def test_valid_password_passes(self, svc: PasswordService) -> None:
        svc.validate_new_password(_VALID_PASSWORD, _VALID_EMAIL, [])

    def test_too_short_raises(self, svc: PasswordService) -> None:
        with pytest.raises(ValidationException) as exc_info:
            svc.validate_new_password("Short@1", _VALID_EMAIL, [])
        violations = cast(list[str], exc_info.value.details.get("violations", []))
        assert any("at least" in v.lower() for v in violations)

    def test_too_long_raises(self, svc: PasswordService) -> None:
        long_pass = "A" * 64 + "a" * 32 + "@1" + "b" * 35
        with pytest.raises(ValidationException):
            svc.validate_new_password(long_pass, _VALID_EMAIL, [])

    def test_no_uppercase_raises(self, svc: PasswordService) -> None:
        with pytest.raises(ValidationException) as exc_info:
            svc.validate_new_password("lowercase@1234567", _VALID_EMAIL, [])
        violations = cast(list[str], exc_info.value.details.get("violations", []))
        assert any("uppercase" in v.lower() for v in violations)

    def test_no_lowercase_raises(self, svc: PasswordService) -> None:
        with pytest.raises(ValidationException) as exc_info:
            svc.validate_new_password("UPPERCASE@1234567", _VALID_EMAIL, [])
        violations = cast(list[str], exc_info.value.details.get("violations", []))
        assert any("lowercase" in v.lower() for v in violations)

    def test_no_digit_raises(self, svc: PasswordService) -> None:
        with pytest.raises(ValidationException) as exc_info:
            svc.validate_new_password("NoDigitHere@!!##", _VALID_EMAIL, [])
        violations = cast(list[str], exc_info.value.details.get("violations", []))
        assert any("digit" in v.lower() for v in violations)

    def test_no_special_char_raises(self, svc: PasswordService) -> None:
        with pytest.raises(ValidationException) as exc_info:
            svc.validate_new_password("NoSpecialChar1234", _VALID_EMAIL, [])
        violations = cast(list[str], exc_info.value.details.get("violations", []))
        assert any("special" in v.lower() for v in violations)

    def test_contains_email_local_raises(self, svc: PasswordService) -> None:
        email = "alice@example.com"
        with pytest.raises(ValidationException) as exc_info:
            svc.validate_new_password("Alice@1234567890", email, [])
        violations = cast(list[str], exc_info.value.details.get("violations", []))
        assert any("email" in v.lower() for v in violations)


class TestCommonPasswordCheck:
    def test_common_password_returns_error_string(self, svc: PasswordService) -> None:
        """_check_common_password returns an error string for known common passwords."""
        svc._common_passwords  # trigger cached_property load
        if "password" in svc._common_passwords:
            result = svc._check_common_password("password")
            assert result is not None
            assert "common" in result.lower()

    def test_uncommon_password_returns_none(self, svc: PasswordService) -> None:
        result = svc._check_common_password("xK9!mQ#4vL$2pZ8n")
        assert result is None

    def test_common_password_rejected_by_validate_new_password(
        self, svc: PasswordService
    ) -> None:
        """validate_new_password raises for common passwords that also meet complexity."""
        svc._common_passwords  # ensure loaded
        # Find a word in the list that could form a valid-looking password
        # by wrapping it. We test by injecting a known value.
        from unittest.mock import patch

        with patch.object(
            type(svc),
            "_common_passwords",
            new_callable=lambda: property(lambda self: frozenset(["validpass@12345"])),
        ):
            with pytest.raises(ValidationException):
                svc.validate_new_password("ValidPass@12345", _VALID_EMAIL, [])


class TestPasswordHistory:
    def test_reused_password_raises(self, svc: PasswordService) -> None:
        old_hash = svc.hash_password(_VALID_PASSWORD)
        with pytest.raises(ValidationException) as exc_info:
            svc._check_password_history(_VALID_PASSWORD, [old_hash])
        assert "recently used" in exc_info.value.message.lower()

    def test_new_password_not_in_history_passes(self, svc: PasswordService) -> None:
        old_hash = svc.hash_password("OtherPass@9999999")
        svc._check_password_history(_VALID_PASSWORD, [old_hash])

    def test_history_limit_respected(self, svc: PasswordService) -> None:
        # Build 6 hashes in history; the 6th-oldest should no longer be checked.
        hashes = [svc.hash_password(f"OldPass@{i}12345") for i in range(6)]
        # The first hash is older than PASSWORD_HISTORY_COUNT (5) so it should pass.
        old_password = "OldPass@012345"
        svc._check_password_history(old_password, hashes)


class TestBuildUpdatedHistory:
    def test_appends_current_hash(self, svc: PasswordService) -> None:
        current = "hash_a"
        existing = ["hash_b", "hash_c"]
        result = svc.build_updated_history(current, existing)
        assert current in result

    def test_caps_at_password_history_count(self, svc: PasswordService) -> None:
        existing = [f"hash_{i}" for i in range(10)]
        result = svc.build_updated_history("hash_new", existing)
        assert len(result) <= _SETTINGS.PASSWORD_HISTORY_COUNT


class TestNormaliseEmail:
    def test_lowercases_email(self) -> None:
        assert (
            PasswordService.normalise_email("UPPER@EXAMPLE.COM") == "upper@example.com"
        )

    def test_strips_whitespace(self) -> None:
        assert (
            PasswordService.normalise_email("  user@example.com  ")
            == "user@example.com"
        )
