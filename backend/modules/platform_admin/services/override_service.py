"""OverrideService — entitlement override grant/revoke (T146) and the
real ``OverrideChecker`` implementation consulted by
``PlatformEntitlementService`` (T147, FR-9A-171/172).

Fail-closed atomicity (ADR-5): grant/revoke stage the domain change plus
an audit row (both flush-only), then a single service-level
``db.commit()``.

**Expiry-at-read-time (FR-9A-172)**: ``has_active_override()`` never
trusts a stored ``is_active=true`` value on its own — every read also
checks ``expires_at``. A row whose ``expires_at`` has passed is treated
as inactive for resolution purposes *and* is deterministically reverted
in the same call (``is_active`` set to ``false``, ``revoked_at`` stamped,
an audit entry written, single commit) so the stored state converges to
reality on the very read that discovers the staleness — no separate
sweep/cron job exists or is needed.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException
from core.utils.datetime import ensure_utc, utcnow
from modules.platform_admin.exceptions import EntitlementOverrideAlreadyActiveError
from modules.platform_admin.models.entitlement_override import EntitlementOverride
from modules.platform_admin.repositories.override_repository import OverrideRepository
from modules.platform_admin.services.platform_audit_service import PlatformAuditService


def _snapshot(override: EntitlementOverride) -> dict[str, object]:
    return {
        "company_id": str(override.company_id),
        "capability_key": override.capability_key,
        "reason": override.reason,
        "expires_at": override.expires_at.isoformat() if override.expires_at else None,
        "is_active": override.is_active,
    }


class OverrideService:
    """Domain service for granting/revoking `EntitlementOverride` rows,
    and the authoritative expiry-at-read-time checker consulted by
    `PlatformEntitlementService`'s `OverrideChecker` seam."""

    def __init__(
        self,
        db: Session,
        repo: OverrideRepository,
        audit: PlatformAuditService,
    ) -> None:
        self._db = db
        self._repo = repo
        self._audit = audit

    def grant(
        self,
        *,
        company_id: UUID,
        capability_key: str,
        reason: str,
        actor_platform_administrator_id: UUID,
        expires_at: datetime | None = None,
    ) -> EntitlementOverride:
        """Grant a time-boxed (or permanent) entitlement override.

        Raises:
            EntitlementOverrideAlreadyActiveError: an active override for
                this (company, capability_key) pair already exists —
                mirrors the DB's own partial unique index (migration 059).
        """
        existing = self._repo.get_active_override(company_id, capability_key)
        if existing is not None:
            raise EntitlementOverrideAlreadyActiveError(
                details={
                    "company_id": str(company_id),
                    "capability_key": capability_key,
                    "existing_override_id": str(existing.id),
                }
            )

        override = self._repo.create_override(
            company_id=company_id,
            capability_key=capability_key,
            reason=reason,
            actor_id=actor_platform_administrator_id,
            granted_at=utcnow(),
            expires_at=expires_at,
        )
        self._audit.record(
            action="entitlement_override.grant",
            target_type="EntitlementOverride",
            target_id=override.id,
            company_id=company_id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            after_state=_snapshot(override),
        )
        self._db.commit()
        return override

    def revoke(
        self,
        *,
        override_id: UUID,
        actor_platform_administrator_id: UUID,
        reason: str | None = None,
    ) -> EntitlementOverride:
        """Revoke an active entitlement override.

        Raises:
            NotFoundException: no override exists with this id, or it is
                already inactive.
        """
        override = self._repo.get_by_id(override_id)
        if override is None or not override.is_active:
            raise NotFoundException(
                message="Entitlement override not found or already inactive."
            )

        before_state = _snapshot(override)
        self._repo.revoke(override, revoked_at=utcnow())
        self._audit.record(
            action="entitlement_override.revoke",
            target_type="EntitlementOverride",
            target_id=override.id,
            company_id=override.company_id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=before_state,
            after_state=_snapshot(override),
        )
        self._db.commit()
        return override

    def has_active_override(self, company_id: UUID, capability_key: str) -> bool:
        """The `OverrideChecker` protocol implementation (T147):
        `True` only if an active, non-expired override exists.

        A stored `is_active=true` row whose `expires_at` has passed is
        automatically reverted here (audited, committed) rather than
        trusted — see module docstring.
        """
        override = self._repo.get_active_override(company_id, capability_key)
        if override is None:
            return False

        if (
            override.expires_at is not None
            and ensure_utc(override.expires_at) <= utcnow()
        ):
            before_state = _snapshot(override)
            self._repo.revoke(override, revoked_at=utcnow())
            self._audit.record(
                action="entitlement_override.auto_revert_expired",
                target_type="EntitlementOverride",
                target_id=override.id,
                company_id=override.company_id,
                actor_platform_administrator_id=None,
                reason="Automatic reversion: expires_at has passed (FR-9A-172).",
                before_state=before_state,
                after_state=_snapshot(override),
            )
            self._db.commit()
            return False

        return True
