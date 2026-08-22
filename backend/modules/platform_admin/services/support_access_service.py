"""SupportAccessService — grant initiation, termination, lazy expiry, and
the per-action audit seam (T159/T160/T161, FR-9A-190..197, BR-9A-019/020).

Fail-closed atomicity (ADR-5): `initiate()`/`terminate()` each stage the
domain state change plus an audit row (both flush-only), then a single
service-level `db.commit()` — mirroring `TenantLifecycleService`'s own
suspend/reactivate pattern exactly.

**Grant duration**: the OpenAPI contract's `POST .../support-access`
request body declares only `reason` — no client-supplied `expires_at` —
so the grant window is a server-determined policy, not user input.
`DEFAULT_GRANT_DURATION_HOURS` is a documented Tasks-phase default (spec
mandates only "time-bounded... explicit, visible expiry", FR-9A-193,
never a specific duration), the same kind of plain module constant as
`quota_service.py`'s own `APPROACHING_THRESHOLD_RATIO`.

**Expiry-at-read-time (T160)**: `assert_grant_active()` is the
authoritative check — it never trusts a stored `status='active'` on its
own; a grant whose `expires_at` has passed is lazily flipped to
`expired` (audited, committed) the moment it is next consulted, mirroring
Phase 11's `OverrideService.has_active_override()` auto-reversion
pattern exactly. `terminate()` runs this same check first, so
terminating an already-time-expired grant correctly reports its true
`expired` state rather than overwriting it with a false `terminated`
transition.

**Per-action audit (T161)**: `record_action()` is the general-purpose
seam plan.md §21 describes for any future read wrapper that operates
"within an active grant" — it asserts the grant is genuinely active,
then stages (flush-only) a `PlatformAuditEvent` with
`support_access_grant_id` populated. Deliberately does **not** commit
itself: unlike `initiate()`/`terminate()`, it has no domain mutation of
its own to commit alongside — the calling action's own transaction
commits it, exactly like `PlatformAuditService.record()`'s own
flush-only contract. No caller of `record_action()` exists yet in this
Epic (plan.md §21's inspection wrappers are not part of this phase's
task range, T158-T166) — proven directly by its own unit test instead.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException, ValidationException
from core.utils.datetime import ensure_utc, utcnow
from modules.platform_admin.exceptions import SupportAccessExpiredError
from modules.platform_admin.models.platform_audit_event import PlatformAuditEvent
from modules.platform_admin.models.support_access_grant import SupportAccessGrant
from modules.platform_admin.repositories.support_access_repository import (
    SupportAccessRepository,
)
from modules.platform_admin.services.platform_audit_service import PlatformAuditService

DEFAULT_GRANT_DURATION_HOURS = 4


def _snapshot(grant: SupportAccessGrant) -> dict[str, Any]:
    return {
        "company_id": str(grant.company_id),
        "status": grant.status,
        "expires_at": grant.expires_at.isoformat(),
        "ended_at": grant.ended_at.isoformat() if grant.ended_at else None,
    }


class SupportAccessService:
    """Domain service for the support-access grant lifecycle."""

    def __init__(
        self,
        db: Session,
        repo: SupportAccessRepository,
        audit: PlatformAuditService,
    ) -> None:
        self._db = db
        self._repo = repo
        self._audit = audit

    def initiate(
        self,
        *,
        company_id: UUID,
        reason: str,
        actor_platform_administrator_id: UUID,
    ) -> SupportAccessGrant:
        """Initiate a time-bounded support-access grant for exactly one
        tenant (FR-9A-191).

        Raises:
            ValidationException: *reason* is empty/blank (FR-9A-192).
        """
        if not reason or not reason.strip():
            raise ValidationException("reason is required to initiate support access.")

        started_at = utcnow()
        expires_at = started_at + timedelta(hours=DEFAULT_GRANT_DURATION_HOURS)
        grant = self._repo.create_grant(
            platform_administrator_id=actor_platform_administrator_id,
            company_id=company_id,
            reason=reason,
            started_at=started_at,
            expires_at=expires_at,
        )
        self._audit.record(
            action="support_access.initiate",
            target_type="SupportAccessGrant",
            target_id=grant.id,
            company_id=company_id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            after_state=_snapshot(grant),
            support_access_grant_id=grant.id,
        )
        self._db.commit()
        return grant

    def assert_grant_active(self, grant_id: UUID) -> SupportAccessGrant:
        """The authoritative expiry-at-read-time check (T160, FR-9A-196).

        Raises:
            NotFoundException: no grant exists with this id.
            SupportAccessExpiredError: the grant is expired or terminated
                (403) — including a lazy `active` -> `expired` transition
                discovered and committed by this very call.
        """
        grant = self._repo.get_by_id(grant_id)
        if grant is None:
            raise NotFoundException(message="Support-access grant not found.")

        if grant.status == "active" and ensure_utc(grant.expires_at) <= utcnow():
            before_state = _snapshot(grant)
            self._repo.mark_expired(grant)
            self._audit.record(
                action="support_access.auto_expire",
                target_type="SupportAccessGrant",
                target_id=grant.id,
                company_id=grant.company_id,
                actor_platform_administrator_id=None,
                reason="Automatic expiry: expires_at has passed (FR-9A-196).",
                before_state=before_state,
                after_state=_snapshot(grant),
                support_access_grant_id=grant.id,
            )
            self._db.commit()

        if grant.status != "active":
            raise SupportAccessExpiredError(
                details={"grant_id": str(grant_id), "status": grant.status}
            )
        return grant

    def terminate(
        self,
        *,
        grant_id: UUID,
        actor_platform_administrator_id: UUID,
        reason: str | None = None,
    ) -> SupportAccessGrant:
        """Explicitly terminate an active grant (T160, FR-9A-196) —
        callable by the initiator or any other actor holding
        `platform.support_access.initiate` (the router-level permission
        check *is* the "sufficiently privileged" gate; no additional
        rank check exists in spec.md for this action).

        Raises:
            NotFoundException: no grant exists with this id.
            SupportAccessExpiredError: the grant is already expired or
                already terminated — there is nothing left to terminate.
        """
        grant = self._repo.get_by_id(grant_id)
        if grant is None:
            raise NotFoundException(message="Support-access grant not found.")

        if grant.status == "active" and ensure_utc(grant.expires_at) <= utcnow():
            before_state = _snapshot(grant)
            self._repo.mark_expired(grant)
            self._audit.record(
                action="support_access.auto_expire",
                target_type="SupportAccessGrant",
                target_id=grant.id,
                company_id=grant.company_id,
                actor_platform_administrator_id=None,
                reason="Automatic expiry: expires_at has passed (FR-9A-196).",
                before_state=before_state,
                after_state=_snapshot(grant),
                support_access_grant_id=grant.id,
            )
            self._db.commit()

        if grant.status != "active":
            raise SupportAccessExpiredError(
                details={"grant_id": str(grant_id), "status": grant.status}
            )

        before_state = _snapshot(grant)
        self._repo.terminate(
            grant, ended_at=utcnow(), ended_by=actor_platform_administrator_id
        )
        self._audit.record(
            action="support_access.terminate",
            target_type="SupportAccessGrant",
            target_id=grant.id,
            company_id=grant.company_id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=before_state,
            after_state=_snapshot(grant),
            support_access_grant_id=grant.id,
        )
        self._db.commit()
        return grant

    def record_action(
        self,
        *,
        grant_id: UUID,
        action: str,
        target_type: str = "SupportAccessGrant",
        target_id: UUID | None = None,
        context: dict[str, Any] | None = None,
    ) -> PlatformAuditEvent:
        """Stage a per-action audit entry for an action performed within
        an active grant (T161, BR-9A-020) — flush-only, caller commits
        (see module docstring).

        Raises:
            NotFoundException: no grant exists with this id.
            SupportAccessExpiredError: the grant is not active.
        """
        grant = self.assert_grant_active(grant_id)
        return self._audit.record(
            action=action,
            target_type=target_type,
            target_id=target_id,
            company_id=grant.company_id,
            actor_platform_administrator_id=grant.platform_administrator_id,
            context=context,
            support_access_grant_id=grant.id,
        )
