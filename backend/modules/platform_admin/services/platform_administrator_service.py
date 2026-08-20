"""PlatformAdministratorService — account lifecycle domain foundation.

Create/activate/deactivate a ``PlatformAdministrator``, auditing every
change atomically via ``PlatformAuditService`` + a single service-level
``db.commit()`` (ADR-5): this service owns the transaction boundary — it
flushes its own state change, calls the audit helper (which also only
flushes), then commits once. If any step raises, nothing has committed.

**Session revocation is deliberately NOT implemented here.**
``PlatformSessionRepository`` does not exist until Phase 4 (Revision 2
split, tasks.md T040/T054). Deactivation is therefore *not yet* complete
with respect to BR-9A-011 ("deactivating a Platform Administrator MUST
immediately invalidate that account's active platform sessions") — this
service exposes an injectable ``SessionRevoker`` seam so Phase 4's T054
can wire in the real revocation behaviour without rewriting this service.
With no revoker injected (the Phase 3 state), ``deactivate()`` performs
the account-state change and its audit record only.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException
from modules.auth.models.user import User
from modules.platform_admin.exceptions import PlatformAdministratorAlreadyExistsError
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.repositories.platform_administrator_repository import (
    PlatformAdministratorRepository,
)
from modules.platform_admin.services.platform_audit_service import PlatformAuditService


class SessionRevoker(Protocol):
    """Seam for Phase 4's T054 to inject mandatory session revocation on
    deactivation (BR-9A-011), without this service needing to change."""

    def revoke_all_for_administrator(self, platform_administrator_id: UUID) -> None: ...


class PlatformAdministratorService:
    """Domain service for Platform Administrator account lifecycle."""

    def __init__(
        self,
        db: Session,
        repo: PlatformAdministratorRepository,
        audit: PlatformAuditService,
        session_revoker: SessionRevoker | None = None,
    ) -> None:
        self.db = db
        self._repo = repo
        self._audit = audit
        self._session_revoker = session_revoker

    def create(
        self,
        *,
        user_id: UUID,
        actor_platform_administrator_id: UUID | None,
        reason: str | None = None,
    ) -> PlatformAdministrator:
        """Create a Platform Administrator account, independent of any
        tenant membership (FR-9A-030). Audited atomically.

        Raises:
            NotFoundException: No ``User`` exists for *user_id* — checked
                explicitly here rather than relying on the DB FK
                constraint's raw ``IntegrityError`` to surface as a clean
                404 (T068).
            PlatformAdministratorAlreadyExistsError: A ``PlatformAdministrator``
                already exists for *user_id* (T068) — checked explicitly
                here rather than relying on the DB unique constraint's
                raw ``IntegrityError`` to surface as a clean 409.
        """
        if self.db.get(User, user_id) is None:
            raise NotFoundException(message="User not found.")
        if self._repo.get_by_user_id(user_id) is not None:
            raise PlatformAdministratorAlreadyExistsError(
                message=("A Platform Administrator already exists for this user."),
                details={"user_id": str(user_id)},
            )
        administrator = PlatformAdministrator(user_id=user_id, is_active=True)
        self._repo.create(administrator)
        self._audit.record(
            action="platform_administrator.create",
            target_type="PlatformAdministrator",
            target_id=administrator.id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=None,
            after_state={"user_id": str(user_id), "is_active": True},
        )
        self.db.commit()
        return administrator

    def activate(
        self,
        administrator: PlatformAdministrator,
        *,
        actor_platform_administrator_id: UUID | None,
        reason: str | None = None,
    ) -> PlatformAdministrator:
        """Reactivate a previously-deactivated administrator. Audited
        atomically."""
        before_state = {
            "is_active": administrator.is_active,
            "deactivated_at": (
                administrator.deactivated_at.isoformat()
                if administrator.deactivated_at
                else None
            ),
        }
        self._repo.set_active(
            administrator,
            is_active=True,
            deactivated_at=None,
            deactivated_by=None,
        )
        self._audit.record(
            action="platform_administrator.activate",
            target_type="PlatformAdministrator",
            target_id=administrator.id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=before_state,
            after_state={"is_active": True, "deactivated_at": None},
        )
        self.db.commit()
        return administrator

    def deactivate(
        self,
        administrator: PlatformAdministrator,
        *,
        actor_platform_administrator_id: UUID | None,
        reason: str | None = None,
    ) -> PlatformAdministrator:
        """Deactivate a Platform Administrator account.

        NOTE (BR-9A-011, Phase 3 known gap): this does not yet revoke
        active platform sessions unless a ``SessionRevoker`` was injected
        — see the module docstring. Phase 4's T054 completes this.
        """
        before_state = {"is_active": administrator.is_active}
        self._repo.set_active(
            administrator,
            is_active=False,
            deactivated_at=datetime.now(UTC),
            deactivated_by=actor_platform_administrator_id,
        )
        self._audit.record(
            action="platform_administrator.deactivate",
            target_type="PlatformAdministrator",
            target_id=administrator.id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=before_state,
            after_state={"is_active": False},
        )
        if self._session_revoker is not None:
            self._session_revoker.revoke_all_for_administrator(administrator.id)
        self.db.commit()
        return administrator
