"""InvitationService — handles membership invitation lifecycle.

Manages invitation creation for unregistered emails, acceptance flow,
re-invitation for expired invitations, and expiry checking.

Spec reference: BR-061, tasks T028.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.config.settings import Settings
from core.events.outbox import EventOutboxRepository
from core.utils.datetime import utcnow
from modules.companies.services.company_audit_service import CompanyAuditService
from modules.users_roles.events import InvitationAcceptedEvent
from modules.users_roles.exceptions import (
    InvalidStatusTransitionError,
    InvitationExpiredError,
    MemberNotFoundError,
)
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.enums import MembershipStatus
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)

logger = logging.getLogger(__name__)


def _new_correlation_id() -> str:
    return str(uuid.uuid4())


class InvitationService:
    """Manages the invitation lifecycle for company memberships.

    Args:
        db: SQLAlchemy ``Session`` shared by all repositories.
        member_repo: Injected ``CompanyMemberRepository``.
        audit_service: Injected ``CompanyAuditService``.
        outbox_repo: Injected ``EventOutboxRepository``.
        settings: Application settings.
    """

    def __init__(
        self,
        db: Session,
        member_repo: CompanyMemberRepository,
        audit_service: CompanyAuditService,
        outbox_repo: EventOutboxRepository,
        settings: Settings,
    ) -> None:
        self._db = db
        self._member_repo = member_repo
        self._audit_service = audit_service
        self._outbox_repo = outbox_repo
        self._settings = settings

    def accept_invitation(
        self,
        *,
        member_id: UUID,
        company_id: UUID,
        user_id: UUID,
        request_context: dict[str, Any] | None = None,
    ) -> CompanyMember:
        """Accept a pending invitation, transitioning status to active.

        Args:
            member_id: The membership record ID.
            company_id: The company being joined.
            user_id: The user accepting the invitation.
            request_context: Optional audit context.

        Returns:
            Updated ``CompanyMember`` with status=active.

        Raises:
            MemberNotFoundError: Membership does not exist.
            InvalidStatusTransitionError: Membership is not in pending_invitation.
            InvitationExpiredError: Invitation has expired.
        """
        ctx = request_context or {}

        member = self._member_repo.get_by_id_or_none(
            id=member_id, company_id=company_id
        )
        if member is None or member.user_id != user_id:
            raise MemberNotFoundError(details={"member_id": str(member_id)})

        if member.status != MembershipStatus.pending_invitation.value:
            raise InvalidStatusTransitionError(
                details={
                    "current_status": member.status,
                    "target_status": MembershipStatus.active.value,
                }
            )

        # Check expiry (BR-061)
        if self._is_invitation_expired(member):
            raise InvitationExpiredError(details={"member_id": str(member_id)})

        now = utcnow()
        member.status = MembershipStatus.active.value
        member.invitation_accepted_at = now
        self._db.flush()

        self._audit_service.record(
            company_id=company_id,
            actor_user_id=user_id,
            action="INVITATION_ACCEPTED",
            after_state={
                "member_id": str(member.id),
                "user_id": str(user_id),
                "status": member.status,
                "accepted_at": now.isoformat(),
            },
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        event = InvitationAcceptedEvent(
            company_id=company_id,
            user_id=user_id,
            accepted_at=now,
        )
        self._outbox_repo.create(event.to_outbox_record(_new_correlation_id(), user_id))

        self._db.commit()
        self._db.refresh(member)

        logger.info(
            "Invitation accepted",
            extra={
                "company_id": str(company_id),
                "member_id": str(member.id),
            },
        )
        return member

    def is_expired(self, member_id: UUID, company_id: UUID) -> bool:
        """Check if a pending invitation has expired.

        Returns ``True`` if the invitation is expired, ``False`` otherwise.
        Returns ``False`` for non-pending memberships.
        """
        member = self._member_repo.get_by_id_or_none(
            id=member_id, company_id=company_id
        )
        if member is None:
            return False
        if member.status != MembershipStatus.pending_invitation.value:
            return False
        return self._is_invitation_expired(member)

    def reinvite(
        self,
        *,
        member_id: UUID,
        company_id: UUID,
        actor_user_id: UUID,
        request_context: dict[str, Any] | None = None,
    ) -> CompanyMember:
        """Re-invite an expired pending member by resetting created_at.

        Args:
            member_id: The membership record ID.
            company_id: The company.
            actor_user_id: User performing the re-invitation.
            request_context: Optional audit context.

        Returns:
            Updated ``CompanyMember`` with refreshed invitation.

        Raises:
            MemberNotFoundError: Membership does not exist.
            InvalidStatusTransitionError: Membership is not in pending_invitation.
        """
        ctx = request_context or {}

        member = self._member_repo.get_by_id_or_none(
            id=member_id, company_id=company_id
        )
        if member is None:
            raise MemberNotFoundError(details={"member_id": str(member_id)})

        if member.status != MembershipStatus.pending_invitation.value:
            raise InvalidStatusTransitionError(
                message="Only pending invitations can be re-sent.",
                details={
                    "current_status": member.status,
                    "member_id": str(member_id),
                },
            )

        member.invited_by = actor_user_id
        member.invitation_accepted_at = None
        self._db.flush()

        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="INVITATION_RESENT",
            after_state={
                "member_id": str(member.id),
                "user_id": str(member.user_id),
            },
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        self._db.commit()
        self._db.refresh(member)

        logger.info(
            "Invitation re-sent",
            extra={
                "company_id": str(company_id),
                "member_id": str(member.id),
            },
        )
        return member

    def _is_invitation_expired(self, member: CompanyMember) -> bool:
        """Check if a pending invitation has expired based on created_at."""
        expiry_days = self._settings.INVITATION_EXPIRY_DAYS
        expiry_cutoff = utcnow() - timedelta(days=expiry_days)
        created = member.created_at
        if created.tzinfo is None:
            from datetime import UTC

            created = created.replace(tzinfo=UTC)
        return created < expiry_cutoff
