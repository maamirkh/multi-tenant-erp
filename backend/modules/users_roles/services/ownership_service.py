"""OwnershipService — orchestrates atomic company ownership transfer.

Business rules enforced:
- Actor must be an active member with the Owner role (rank 100).
- Target must be an active member of the same company.
- Actor cannot transfer ownership to themselves.
- Owner role is atomically assigned to target; actor is demoted to Admin.
- companies.owner_id is updated in the same flush window.
- An OWNERSHIP_TRANSFERRED audit log entry is appended.
- An OwnershipTransferredEvent is written to the event outbox.

Each public method is a complete unit of work:
    validate → state change → audit log → domain event → commit.

Spec reference: Epic 4, Phase 15 (T126).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.events.outbox import EventOutboxRepository
from core.utils.datetime import utcnow
from modules.companies.repositories.company_repository import CompanyRepository
from modules.companies.services.company_audit_service import CompanyAuditService
from modules.users_roles.constants import OWNER_RANK
from modules.users_roles.events import OwnershipTransferredEvent
from modules.users_roles.exceptions import (
    InsufficientRankError,
    LastOwnerProtectionError,
    MemberNotFoundError,
    RoleNotFoundError,
)
from modules.users_roles.models.enums import MembershipStatus
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from modules.users_roles.repositories.role_repository import RoleRepository

logger = logging.getLogger(__name__)


def _new_correlation_id() -> str:
    return str(uuid.uuid4())


class OwnershipService:
    """Orchestrates company ownership transfer.

    Args:
        db: SQLAlchemy ``Session`` shared by all repositories.
        member_repo: Injected ``CompanyMemberRepository``.
        role_repo: Injected ``RoleRepository``.
        company_repo: Injected ``CompanyRepository`` (updates ``owner_id``).
        audit_service: Injected ``CompanyAuditService``.
        outbox_repo: Injected ``EventOutboxRepository``.
    """

    def __init__(
        self,
        db: Session,
        member_repo: CompanyMemberRepository,
        role_repo: RoleRepository,
        company_repo: CompanyRepository,
        audit_service: CompanyAuditService,
        outbox_repo: EventOutboxRepository,
    ) -> None:
        self._db = db
        self._member_repo = member_repo
        self._role_repo = role_repo
        self._company_repo = company_repo
        self._audit_service = audit_service
        self._outbox_repo = outbox_repo

    def transfer_ownership(
        self,
        *,
        company_id: UUID,
        actor_user_id: UUID,
        target_member_id: UUID,
        request_context: dict[str, Any] | None = None,
    ) -> None:
        """Transfer company ownership from the current Owner to an active member.

        Steps:
        1. Load the actor's membership — must be active.
        2. Validate actor holds the Owner role (rank = 100).
        3. Load the target member by ``target_member_id`` — must be active.
        4. Validate target is not the actor (self-transfer is a no-op / disallowed).
        5. Resolve Owner and Admin system roles for the company.
        6. Atomically swap roles: target → Owner, actor → Admin.
        7. Update ``companies.owner_id`` to the target's ``user_id``.
        8. Append OWNERSHIP_TRANSFERRED audit log entry.
        9. Publish ``OwnershipTransferredEvent`` to the outbox.
        10. Commit the transaction.

        Args:
            company_id: UUID of the company whose ownership is being transferred.
            actor_user_id: UUID of the user initiating the transfer (current Owner).
            target_member_id: UUID of the ``CompanyMember`` record for the new Owner.
            request_context: Optional dict with ``ip_address``, ``request_id``,
                ``user_agent`` for audit enrichment.

        Raises:
            InsufficientRankError: Actor is not an active Owner.
            MemberNotFoundError: Target member does not exist in the company.
            LastOwnerProtectionError: Actor attempts to transfer to themselves.
            RoleNotFoundError: Owner or Admin system roles are missing (data integrity error).
        """
        ctx = request_context or {}

        # 1. Load actor membership
        actor_member = self._member_repo.get_by_user_id(
            user_id=actor_user_id, company_id=company_id
        )
        if actor_member is None or actor_member.status != MembershipStatus.active.value:
            raise InsufficientRankError(
                message="Only an active Owner can transfer ownership."
            )

        # 2. Validate actor is Owner (rank == OWNER_RANK)
        actor_role = self._role_repo.get_by_id_or_none(
            id=actor_member.role_id, company_id=company_id
        )
        if actor_role is None or actor_role.rank < OWNER_RANK:
            raise InsufficientRankError(
                message="Only the company Owner can transfer ownership."
            )

        # 3. Load target member
        target_member = self._member_repo.get_by_id_or_none(
            id=target_member_id, company_id=company_id
        )
        if target_member is None:
            raise MemberNotFoundError(details={"member_id": str(target_member_id)})

        # 4. Prevent self-transfer
        if target_member.user_id == actor_user_id:
            raise LastOwnerProtectionError(
                message="Cannot transfer ownership to yourself."
            )

        # 5. Target must be active
        if target_member.status != MembershipStatus.active.value:
            raise MemberNotFoundError(
                message="Target member must be active to receive ownership.",
                details={
                    "member_id": str(target_member_id),
                    "current_status": target_member.status,
                },
            )

        # 6. Resolve system roles
        owner_role = self._role_repo.get_by_slug(company_id, "owner")
        admin_role = self._role_repo.get_by_slug(company_id, "admin")
        if owner_role is None or admin_role is None:
            raise RoleNotFoundError(
                message="System roles 'owner' or 'admin' not found. "
                "Ensure roles are seeded for this company.",
                details={"company_id": str(company_id)},
            )

        now = utcnow()
        former_owner_user_id = actor_user_id
        new_owner_user_id = target_member.user_id

        # 7. Atomic role swap
        target_member.role_id = owner_role.id
        actor_member.role_id = admin_role.id
        self._db.flush()

        # 8. Update company.owner_id
        company = self._company_repo.get_by_id(company_id)
        if company is not None:
            company.owner_id = new_owner_user_id
            self._db.flush()

        # 9. Audit log
        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="OWNERSHIP_TRANSFERRED",
            before_state={
                "owner_user_id": str(former_owner_user_id),
                "former_owner_member_id": str(actor_member.id),
            },
            after_state={
                "owner_user_id": str(new_owner_user_id),
                "new_owner_member_id": str(target_member.id),
            },
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        # 10. Domain event → outbox
        event = OwnershipTransferredEvent(
            company_id=company_id,
            from_user_id=former_owner_user_id,
            to_user_id=new_owner_user_id,
            transferred_at=now,
        )
        self._outbox_repo.create(
            event.to_outbox_record(_new_correlation_id(), actor_user_id)
        )

        self._db.commit()

        logger.info(
            "Ownership transferred",
            extra={
                "company_id": str(company_id),
                "from_user_id": str(former_owner_user_id),
                "to_user_id": str(new_owner_user_id),
            },
        )
