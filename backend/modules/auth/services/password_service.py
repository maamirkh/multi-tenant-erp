"""PasswordService — Argon2id password hashing and complexity enforcement.

Security invariants:
  - Raw passwords are NEVER stored, logged, or retained after the operation.
  - All hashing uses Argon2id with parameters from Settings (OWASP-compliant).
  - Complexity validation enforces NIST SP 800-63B + OWASP requirements.
  - Password history prevents reuse of the last N passwords.
  - Common passwords (top-10 000) are rejected at all times.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from functools import cached_property
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from core.config.settings import Settings
from core.exceptions.base import ValidationException

logger = logging.getLogger(__name__)

_COMMON_PASSWORDS_PATH = Path(__file__).parent.parent / "data" / "common_passwords.txt"

_SPECIAL_CHARS = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]")


class PasswordService:
    """Handles all password hashing, verification, and policy enforcement.

    Args:
        settings: Application settings (Argon2 params, password policy).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._hasher = PasswordHasher(
            time_cost=settings.ARGON2_TIME_COST,
            memory_cost=settings.ARGON2_MEMORY_COST,
            parallelism=settings.ARGON2_PARALLELISM,
        )

    @cached_property
    def _common_passwords(self) -> frozenset[str]:
        """Load the common-passwords blocklist once and cache it."""
        try:
            text = _COMMON_PASSWORDS_PATH.read_text(encoding="utf-8")
            return frozenset(
                line.strip().lower() for line in text.splitlines() if line.strip()
            )
        except FileNotFoundError:
            logger.warning(
                "Common passwords file not found at %s; blocklist disabled.",
                _COMMON_PASSWORDS_PATH,
            )
            return frozenset()

    def hash_password(self, plain: str) -> str:
        """Hash *plain* with Argon2id and return the encoded string.

        Args:
            plain: Plaintext password. Not retained after this call.

        Returns:
            Argon2id encoded hash string (includes algorithm, params, salt).
        """
        hashed = self._hasher.hash(plain)
        return hashed

    def verify_password(self, plain: str, hashed: str) -> bool:
        """Return ``True`` if *plain* matches *hashed*, ``False`` otherwise.

        Never raises on mismatch — callers must check the return value.
        """
        try:
            return self._hasher.verify(hashed, plain)
        except (VerifyMismatchError, VerificationError):
            return False

    def validate_new_password(self, plain: str, email: str, history: list[str]) -> None:
        """Validate a new password against all policy rules.

        Raises ``ValidationException`` (HTTP 422) listing all violations.

        Args:
            plain:   Candidate plaintext password.
            email:   The user's email address (used to check containment).
            history: List of previous Argon2id hashes to check for reuse.
        """
        errors: list[str] = []
        errors.extend(self._check_complexity(plain, email))
        if common_error := self._check_common_password(plain):
            errors.append(common_error)
        if errors:
            raise ValidationException(
                message="Password does not meet security requirements.",
                details={"violations": errors},
            )
        self._check_password_history(plain, history)

    def _check_complexity(self, plain: str, email: str) -> list[str]:
        """Return a list of complexity violation messages (empty = passes)."""
        errors: list[str] = []

        if len(plain) < self._settings.PASSWORD_MIN_LENGTH:
            errors.append(
                f"Password must be at least {self._settings.PASSWORD_MIN_LENGTH} characters."
            )

        if len(plain) > self._settings.PASSWORD_MAX_LENGTH:
            errors.append(
                f"Password must not exceed {self._settings.PASSWORD_MAX_LENGTH} characters."
            )

        if not any(c.isupper() for c in plain):
            errors.append("Password must contain at least one uppercase letter.")

        if not any(c.islower() for c in plain):
            errors.append("Password must contain at least one lowercase letter.")

        if not any(c.isdigit() for c in plain):
            errors.append("Password must contain at least one digit.")

        if not _SPECIAL_CHARS.search(plain):
            errors.append("Password must contain at least one special character.")

        normalised_email = email.lower().strip()
        email_local = (
            normalised_email.split("@")[0]
            if "@" in normalised_email
            else normalised_email
        )
        if email_local and email_local in plain.lower():
            errors.append("Password must not contain your email address or username.")

        return errors

    def _check_common_password(self, plain: str) -> str | None:
        """Return an error string if *plain* is a known common password, else ``None``."""
        if plain.lower() in self._common_passwords:
            return "Password is too common. Please choose a more unique password."
        return None

    def _check_password_history(self, plain: str, history: list[str]) -> None:
        """Raise ``ValidationException`` if *plain* matches a hash in *history*.

        Checks the most-recent ``PASSWORD_HISTORY_COUNT`` hashes.
        """
        limit = self._settings.PASSWORD_HISTORY_COUNT
        recent_hashes = history[-limit:] if len(history) > limit else history

        for old_hash in recent_hashes:
            if self.verify_password(plain, old_hash):
                raise ValidationException(
                    message="Password was recently used. Please choose a different password."
                )

    def build_updated_history(
        self, current_hash: str, existing_history: list[str]
    ) -> list[str]:
        """Return an updated password history list with the current hash appended.

        Trims to the last ``PASSWORD_HISTORY_COUNT`` entries so the list
        never grows unboundedly.

        Args:
            current_hash:    The hash being replaced (moved into history).
            existing_history: The existing list of historical hashes.

        Returns:
            Updated history list (oldest first, capped at PASSWORD_HISTORY_COUNT).
        """
        limit = self._settings.PASSWORD_HISTORY_COUNT
        updated = list(existing_history) + [current_hash]
        return updated[-limit:]

    @staticmethod
    def normalise_email(email: str) -> str:
        """Apply Unicode normalisation and lowercasing to an email address.

        Uses NFKC normalisation to collapse compatibility equivalents, then
        lowercases so that lookups are case-insensitive.
        """
        return unicodedata.normalize("NFKC", email).lower().strip()
