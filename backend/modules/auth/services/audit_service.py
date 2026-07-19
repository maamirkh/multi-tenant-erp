"""AuditService — structured security event logging.

Every authentication event (login, logout, password change, …) is recorded
as an immutable ``AuditLog`` row via this service.  Failures inside
``AuditService`` are caught and logged at ERROR level but NEVER re-raised —
a broken audit trail must not prevent the primary authentication action from
completing.

Sensitive data sanitisation:
  Any metadata dict passed to ``emit()`` is automatically scrubbed of
  well-known sensitive field names before persistence so that raw tokens,
  passwords, or cookie values never reach the audit log table.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import Request

from core.logging.setup import REQUEST_ID_CONTEXT
from modules.auth.models.enums import AuditEventType
from modules.auth.repositories.audit_log_repository import AuditLogRepository

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "token",
        "refresh_token",
        "access_token",
        "authorization",
        "cookie",
        "set-cookie",
        "jwt",
        "secret",
        "hash",
        "password_hash",
        "token_hash",
    }
)


def _sanitise_metadata(metadata: dict | None) -> dict | None:
    """Remove or mask sensitive fields from *metadata* before persistence."""
    if metadata is None:
        return None
    return {
        k: "***REDACTED***" if k.lower() in _SENSITIVE_KEYS else v
        for k, v in metadata.items()
    }


class AuditService:
    """Records security events to the ``audit_logs`` table.

    Args:
        db: SQLAlchemy session (shared with other services in the request).
    """

    def __init__(self, db) -> None:
        self._repo = AuditLogRepository(db)

    def emit(
        self,
        event_type: AuditEventType,
        outcome: str,
        request: Request,
        user_id: UUID | None = None,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Record a security event to the audit log.

        This method catches and logs any internal exception so that a broken
        audit write never causes the caller to fail.

        Args:
            event_type: The type of security event.
            outcome:    ``"SUCCESS"`` or ``"FAILURE"``.
            request:    FastAPI request object (used to extract IP and UA).
            user_id:    Associated user UUID (nullable for pre-auth events).
            reason:     Short description of the outcome (e.g. "INVALID_PASSWORD").
            metadata:   Additional context dict; sensitive keys are auto-redacted.
        """
        try:
            ip_address = self._extract_ip(request)
            user_agent = request.headers.get("user-agent")
            request_id = REQUEST_ID_CONTEXT.get(None)

            self._repo.create(
                event_type=event_type,
                outcome=outcome,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                reason=reason,
                metadata=_sanitise_metadata(metadata),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Failed to write audit log entry",
                extra={
                    "event_type": event_type.value,
                    "outcome": outcome,
                    "user_id": str(user_id) if user_id else None,
                    "error": str(exc),
                },
                exc_info=True,
            )

    @staticmethod
    def _extract_ip(request: Request) -> str | None:
        """Extract the real client IP, honouring X-Forwarded-For if present."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        client = request.client
        return client.host if client else None
