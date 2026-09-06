"""PlatformRbacService — effective-permission resolution, role assignment
with self-escalation prevention (BR-9A-012), and last-Platform-Owner
protection (plan.md §8/§26).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from modules.platform_admin.constants import PLATFORM_PERMISSION_CODES
from modules.platform_admin.exceptions import (
    LastPlatformOwnerError,
    SelfEscalationError,
    UnknownPlatformPermissionError,
)
from modules.platform_admin.repositories.platform_administrator_repository import (
    PlatformAdministratorRepository,
)
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.platform_audit_service import PlatformAuditService

_PLATFORM_OWNER_ROLE_CODE = "platform_owner"


class PlatformRbacService:
    """Platform RBAC domain service."""

    def __init__(
        self,
        db: Session,
        repo: PlatformRbacRepository,
        admin_repo: PlatformAdministratorRepository,
        audit: PlatformAuditService,
    ) -> None:
        self._db = db
        self._repo = repo
        self._admin_repo = admin_repo
        self._audit = audit

    # ------------------------------------------------------------------
    # T063 — effective-permission resolver (FR-9A-142/221)
    # ------------------------------------------------------------------

    def get_effective_permissions(
        self, platform_administrator_id: UUID
    ) -> frozenset[str]:
        """Union of all of the administrator's assigned roles' permissions,
        resolved fresh from the database on every call — never cached in
        the token or anywhere else (FR-9A-221)."""
        return self._repo.get_effective_permissions(platform_administrator_id)

    def has_permission(self, platform_administrator_id: UUID, code: str) -> bool:
        return code in self.get_effective_permissions(platform_administrator_id)

    # ------------------------------------------------------------------
    # T069 — role create/update (POST /roles)
    # ------------------------------------------------------------------

    def create_or_update_role(
        self,
        *,
        code: str,
        name: str,
        description: str | None,
        permission_codes: set[str],
        actor_platform_administrator_id: UUID,
        reason: str | None = None,
    ):
        """Create a new Platform Role, or update an existing one's name/
        description/permission bundle, keyed by *code*. Rejects any code
        not present in the seeded ``PLATFORM_PERMISSION_CODES`` catalogue
        (T033) — permissions are configuration data, but a role can never
        reference a code that was never seeded. Audited atomically;
        re-submitting an identical bundle is a genuine no-op on the
        join table (mirrors the seed service's idempotency guard).

        Raises:
            UnknownPlatformPermissionError: *permission_codes* contains a
                code absent from the catalogue.
        """
        unknown = set(permission_codes) - PLATFORM_PERMISSION_CODES
        if unknown:
            raise UnknownPlatformPermissionError(
                message=(
                    "Unknown Platform permission code(s): "
                    f"{', '.join(sorted(unknown))}."
                ),
                details={"unknown_codes": sorted(unknown)},
            )

        role = self._repo.get_role_by_code(code)
        is_create = role is None
        before_state = None
        if role is None:
            role = self._repo.create_role(code=code, name=name, description=description)
        else:
            before_state = {
                "name": role.name,
                "description": role.description,
                "permission_codes": sorted(
                    self._repo.get_role_permission_codes(role.id)
                ),
            }
            self._repo.update_role(role, name=name, description=description)

        target = frozenset(permission_codes)
        current = self._repo.get_role_permission_codes(role.id)
        if current != target:
            self._repo.set_role_permissions(role.id, set(target))

        self._audit.record(
            action=(
                "platform_rbac.role.create"
                if is_create
                else "platform_rbac.role.update"
            ),
            target_type="PlatformRole",
            target_id=role.id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=before_state,
            after_state={
                "code": code,
                "name": name,
                "description": description,
                "permission_codes": sorted(target),
            },
        )
        self._db.commit()
        return role

    # ------------------------------------------------------------------
    # T066 — last-Platform-Owner protection
    # ------------------------------------------------------------------

    def is_last_active_owner(self, platform_administrator_id: UUID) -> bool:
        """True if *platform_administrator_id* is currently an active
        `platform_owner`-role holder AND removing that status would leave
        zero active owners."""
        if not self._repo.has_role(
            platform_administrator_id, _PLATFORM_OWNER_ROLE_CODE
        ):
            return False
        active_owner_count = self._repo.count_active_administrators_with_role(
            _PLATFORM_OWNER_ROLE_CODE
        )
        return active_owner_count <= 1

    def assert_not_last_owner_removal(
        self,
        platform_administrator_id: UUID,
        *,
        actor_platform_administrator_id: UUID | None = None,
        reason: str | None = None,
    ) -> None:
        """Raises `LastPlatformOwnerError` if removing/deactivating
        *platform_administrator_id* would leave the platform with zero
        active owners. Service-level check — not expressible as a
        single-row CHECK constraint (plan.md §26).

        The rejected attempt itself is audited (T075) — committed on its
        own, since no domain state changed for this call to bundle it
        with; this mirrors `assign_role`'s self-escalation denial below.
        """
        if self.is_last_active_owner(platform_administrator_id):
            self._audit.record(
                action="platform_rbac.last_owner_removal.denied",
                target_type="PlatformAdministrator",
                target_id=platform_administrator_id,
                actor_platform_administrator_id=actor_platform_administrator_id,
                reason=reason,
                before_state=None,
                after_state={"denial_reason": "last_platform_owner"},
            )
            self._db.commit()
            raise LastPlatformOwnerError()

    # ------------------------------------------------------------------
    # T065 — role assignment with self-escalation prevention (BR-9A-012)
    # ------------------------------------------------------------------

    def assign_role(
        self,
        *,
        platform_administrator_id: UUID,
        role_id: UUID,
        actor_platform_administrator_id: UUID,
        reason: str | None = None,
    ):
        """Assign a Platform Role to an administrator. Requires
        `platform.rbac.manage` (enforced at the router); assigning
        `platform_owner` additionally requires the actor to already hold
        that same role (BR-9A-012) — a role can never grant a role of
        equal-or-higher privilege the actor doesn't already have.
        Audited atomically via T037's helper.

        Raises:
            SelfEscalationError: Assigning `platform_owner` without the
                actor already holding it.
        """
        role = self._repo.get_role_by_id(role_id)
        target_is_owner_role = (
            role is not None and role.code == _PLATFORM_OWNER_ROLE_CODE
        )

        if target_is_owner_role and not self._repo.has_role(
            actor_platform_administrator_id, _PLATFORM_OWNER_ROLE_CODE
        ):
            # The rejected attempt itself is audited (T075) — committed on
            # its own, since no domain state changed for this call to
            # bundle it with.
            self._audit.record(
                action="platform_rbac.role.assign.denied",
                target_type="PlatformAdminRoleAssignment",
                target_id=None,
                actor_platform_administrator_id=actor_platform_administrator_id,
                reason=reason,
                before_state=None,
                after_state={
                    "platform_administrator_id": str(platform_administrator_id),
                    "role_id": str(role_id),
                    "role_code": role.code if role is not None else None,
                    "denial_reason": "self_escalation",
                },
            )
            self._db.commit()
            raise SelfEscalationError(
                "Only an existing Platform Owner may grant the Platform Owner role."
            )

        assignment = self._repo.assign_role(
            platform_administrator_id=platform_administrator_id,
            role_id=role_id,
            assigned_by=actor_platform_administrator_id,
            assigned_at=datetime.now(UTC),
        )

        self._audit.record(
            action="platform_rbac.role.assign",
            target_type="PlatformAdminRoleAssignment",
            target_id=assignment.id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=None,
            after_state={
                "platform_administrator_id": str(platform_administrator_id),
                "role_id": str(role_id),
                "role_code": role.code if role is not None else None,
            },
        )
        self._db.commit()
        return assignment

    def remove_role_assignment(
        self,
        *,
        platform_administrator_id: UUID,
        role_id: UUID,
        actor_platform_administrator_id: UUID,
        reason: str | None = None,
    ) -> None:
        """Remove a role assignment. Not exposed via any HTTP route this
        phase (T069 — the contract declares no DELETE role-assignment
        operation); provided for repository/service-layer completeness
        and enforces the same last-owner guard T066 requires.

        Raises:
            LastPlatformOwnerError: This removal would leave zero active
                Platform Owners.
        """
        role = self._repo.get_role_by_id(role_id)
        if role is not None and role.code == _PLATFORM_OWNER_ROLE_CODE:
            self.assert_not_last_owner_removal(
                platform_administrator_id,
                actor_platform_administrator_id=actor_platform_administrator_id,
                reason=reason,
            )

        before_state = {
            "platform_administrator_id": str(platform_administrator_id),
            "role_id": str(role_id),
        }
        self._repo.remove_assignment(
            platform_administrator_id=platform_administrator_id, role_id=role_id
        )
        self._audit.record(
            action="platform_rbac.role.remove",
            target_type="PlatformAdminRoleAssignment",
            target_id=None,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=before_state,
            after_state=None,
        )
        self._db.commit()
