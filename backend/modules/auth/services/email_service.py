"""EmailService — stub for outbound transactional email.

This stub logs generated tokens at DEBUG level so that developers can
retrieve them from logs during development and testing without a real SMTP
server.  It is interface-compatible with a future SMTP/SendGrid integration.

Security contract:
  - Tokens are logged at DEBUG level only — NEVER at INFO or above.
  - DEBUG logs must not be enabled in production (LOG_LEVEL=INFO or higher).
  - No token values are returned to API callers.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Transactional email stub.

    Replace this class with a real SMTP/API implementation in a future Epic
    without changing the calling code in ``AuthService``.
    """

    def send_password_reset_email(self, email: str, token: str) -> None:
        """Log a password reset token for development use.

        In production this method will dispatch an email containing the reset
        URL.  Until then the token is visible only in DEBUG-level logs.

        Args:
            email: Recipient email address.
            token: Raw reset token to embed in the reset URL.
        """
        logger.debug(
            "Password reset token generated (stub — no email sent)",
            extra={"recipient": email, "reset_token": token},
        )

    def send_email_verification_email(self, email: str, token: str) -> None:
        """Log an email verification token for development use.

        Args:
            email: Recipient email address.
            token: Raw verification token to embed in the verification URL.
        """
        logger.debug(
            "Email verification token generated (stub — no email sent)",
            extra={"recipient": email, "verify_token": token},
        )
