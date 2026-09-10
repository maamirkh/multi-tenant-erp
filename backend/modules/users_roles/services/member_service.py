"""MemberService — orchestrates member creation and management.

Implements the add-member flow (US1), role change flow (US2), and
membership lifecycle (US5): validates company membership limit, checks
for duplicate memberships, handles archived member reactivation, enforces
rank hierarchy, creates and updates CompanyMember records, executes
state-machine transitions (BR-020), revokes sessions on status change,
writes audit logs, and publishes domain events.

Each method is a complete unit of work: validate → state change →
audit log → domain event → commit.

Spec reference: FR-001 through FR-006, FR-020 through FR-024, FR-030 through FR-037,
BR-001/005/010/011/013/020/022/023/032/044/050, tasks T027, T040, T068-T070, T080.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from types import EllipsisType
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.config.settings import Settings
from core.events.outbox import EventOutboxRepository
from core.utils.datetime import utcnow
from modules.auth.repositories.session_repository import SessionRepository
from modules.companies.services.company_audit_service import CompanyAuditService
from modules.users_roles.constants import OWNER_RANK
from modules.users_roles.events import (
    MemberArchivedEvent,
    MemberCreatedEvent,
    MemberDeactivatedEvent,
    MemberLockedEvent,
    MemberRestoredEvent,
    MemberRoleChangedEvent,
    MemberSuspendedEvent,
)
from modules.users_roles.exceptions import (
    CannotModifyOwnRoleError,
    EmployeeIdConflictError,
    HireDateInFutureError,
    InsufficientRankError,
    InvalidStatusTransitionError,
    LastOwnerProtectionError,
    MemberAlreadyExistsError,
    MemberLimitExceededError,
    MemberNotFoundError,
    RoleNotFoundError,
)
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.enums import MembershipStatus
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from modules.users_roles.repositories.role_repository import RoleRepository

# ---------------------------------------------------------------------------
# Lifecycle state machine (BR-020)
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    MembershipStatus.pending_invitation.value: frozenset(
        {MembershipStatus.active.value}
    ),
    MembershipStatus.active.value: frozenset(
        {
            MembershipStatus.inactive.value,
            MembershipStatus.suspended.value,
            MembershipStatus.locked.value,
            MembershipStatus.archived.value,
        }
    ),
    MembershipStatus.inactive.value: frozenset(
        {
            MembershipStatus.active.value,
            MembershipStatus.archived.value,
        }
    ),
    MembershipStatus.suspended.value: frozenset(
        {
            MembershipStatus.active.value,
            MembershipStatus.archived.value,
        }
    ),
    MembershipStatus.locked.value: frozenset(
        {
            MembershipStatus.active.value,
            MembershipStatus.suspended.value,
            MembershipStatus.archived.value,
        }
    ),
    MembershipStatus.archived.value: frozenset({MembershipStatus.active.value}),
}

# Statuses that indicate a member is the "last owner" candidate
_OWNER_ACTIVE_STATUSES: frozenset[str] = frozenset(
    {
        MembershipStatus.active.value,
        MembershipStatus.pending_invitation.value,
    }
)

logger = logging.getLogger(__name__)


def _new_correlation_id() -> str:
    return str(uuid.uuid4())


class MemberService:
    """Orchestrates company member operations.

    Args:
        db: SQLAlchemy ``Session`` shared by all repositories.
        member_repo: Injected ``CompanyMemberRepository``.
        role_repo: Injected ``RoleRepository``.
        audit_service: Injected ``CompanyAuditService``.
        outbox_repo: Injected ``EventOutboxRepository``.
        session_repo: Injected ``SessionRepository`` for session revocation on
            status change (FR-035).
        settings: Application settings.
    """

    def __init__(
        self,
        db: Session,
        member_repo: CompanyMemberRepository,
        role_repo: RoleRepository,
        audit_service: CompanyAuditService,
        outbox_repo: EventOutboxRepository,
        settings: Settings,
        session_repo: SessionRepository | None = None,
    ) -> None:
        self._db = db
        self._member_repo = member_repo
        self._role_repo = role_repo
        self._audit_service = audit_service
        self._outbox_repo = outbox_repo
        self._settings = settings
        self._session_repo = session_repo

    def list_members(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        role_id: UUID | None = None,
        department: str | None = None,
        search: str | None = None,
        sort_by: str = "name",
        sort_order: str = "asc",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CompanyMember], int]:
        """Return a paginated, filterable list of company members.

        Delegates filter logic to ``CompanyMemberRepository.list_by_company_filtered``.
        Eagerly loads ``user`` and ``role`` relationships so callers can
        construct ``MemberListItem`` responses without additional queries.

        Args:
            company_id:  Target company (tenant scope).
            status:      Optional membership status filter.
            role_id:     Optional role filter.
            department:  Optional exact department filter.
            search:      Optional case-insensitive substring search on
                         display_name, email, and employee_id.
            sort_by:     Sort column: ``name`` | ``created_at`` |
                         ``role_rank`` | ``department``.
            sort_order:  ``asc`` or ``desc``.
            page:        1-indexed page number.
            page_size:   Number of items per page (max 100).

        Returns:
            Tuple of ``(members, total_count)``.
        """
        skip = (page - 1) * page_size
        return self._member_repo.list_by_company_filtered(
            company_id,
            status=status,
            role_id=role_id,
            department=department,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            skip=skip,
            limit=page_size,
        )

    def add_member(
        self,
        *,
        company_id: UUID,
        user_id: UUID,
        role_id: UUID,
        actor_user_id: UUID,
        actor_role_rank: int,
        employee_id: str | None = None,
        job_title: str | None = None,
        department: str | None = None,
        work_phone: str | None = None,
        hire_date: Any = None,
        notes: str | None = None,
        request_context: dict[str, Any] | None = None,
    ) -> CompanyMember:
        """Add a new member to a company.

        Steps:
        1. Validate membership count limit (FR-006)
        2. Check for duplicate active membership (FR-005)
        3. Handle archived member reactivation (BR-044)
        4. Validate role exists in company
        5. Enforce rank hierarchy (BR-011)
        6. Create CompanyMember record
        7. Write audit log (MEMBER_CREATED)
        8. Publish MemberCreatedEvent to outbox

        Args:
            company_id: Target company.
            user_id: User being added.
            role_id: Role to assign.
            actor_user_id: User performing the action.
            actor_role_rank: Rank of the actor's role.
            employee_id: Optional company-assigned employee ID.
            job_title: Optional position title.
            department: Optional department name.
            work_phone: Optional work phone.
            hire_date: Optional employment start date.
            notes: Optional internal notes.
            request_context: Optional dict with ip_address, request_id, user_agent.

        Returns:
            Newly created ``CompanyMember``.

        Raises:
            MemberLimitExceededError: Company member count at limit.
            MemberAlreadyExistsError: Active membership already exists.
            RoleNotFoundError: Role does not exist in company.
            InsufficientRankError: Actor rank is not high enough.
        """
        ctx = request_context or {}

        # 1. Check membership count limit (FR-006)
        current_count = self._member_repo.count_by_company(company_id)
        if current_count >= self._settings.COMPANY_MAX_MEMBERS:
            raise MemberLimitExceededError(
                details={
                    "company_id": str(company_id),
                    "current_count": current_count,
                    "max_members": self._settings.COMPANY_MAX_MEMBERS,
                }
            )

        # 2. Check for existing membership (including archived for reactivation)
        existing = self._member_repo.get_by_company_and_user(
            company_id, user_id, include_deleted=True
        )

        if existing is not None:
            # 3. Handle archived member reactivation (BR-044)
            if (
                existing.status == MembershipStatus.archived.value
                or existing.is_deleted
            ):
                return self._reactivate_archived_member(
                    member=existing,
                    role_id=role_id,
                    actor_user_id=actor_user_id,
                    actor_role_rank=actor_role_rank,
                    employee_id=employee_id,
                    job_title=job_title,
                    department=department,
                    work_phone=work_phone,
                    hire_date=hire_date,
                    notes=notes,
                    request_context=ctx,
                )
            # Active, pending, or other non-archived membership exists
            raise MemberAlreadyExistsError(
                details={
                    "company_id": str(company_id),
                    "user_id": str(user_id),
                    "current_status": existing.status,
                }
            )

        # 4. Validate role exists in company
        role = self._role_repo.get_by_id_or_none(id=role_id, company_id=company_id)
        if role is None:
            raise RoleNotFoundError(
                details={"role_id": str(role_id), "company_id": str(company_id)}
            )

        # 5. Enforce rank hierarchy (BR-011): actor must have higher rank
        if actor_role_rank <= role.rank:
            raise InsufficientRankError(
                message="You cannot assign a role with equal or higher rank than your own.",
                details={
                    "actor_rank": actor_role_rank,
                    "target_role_rank": role.rank,
                },
            )

        # 6. Create CompanyMember record
        now = utcnow()
        member = CompanyMember(
            company_id=company_id,
            user_id=user_id,
            role_id=role_id,
            status=MembershipStatus.pending_invitation.value,
            employee_id=employee_id,
            job_title=job_title,
            department=department,
            work_phone=work_phone,
            hire_date=hire_date,
            notes=notes,
            invited_by=actor_user_id,
            created_by=actor_user_id,
        )
        self._db.add(member)
        self._db.flush()

        # 7. Write audit log
        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="MEMBER_CREATED",
            after_state={
                "member_id": str(member.id),
                "user_id": str(user_id),
                "role_id": str(role_id),
                "role_name": role.name,
                "status": member.status,
                "employee_id": employee_id,
            },
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        # 8. Publish domain event
        event = MemberCreatedEvent(
            company_id=company_id,
            user_id=user_id,
            role_id=role_id,
            invited_by=actor_user_id,
            created_at=now,
        )
        self._outbox_repo.create(
            event.to_outbox_record(_new_correlation_id(), actor_user_id)
        )

        self._db.commit()
        self._db.refresh(member)

        logger.info(
            "Member added",
            extra={
                "company_id": str(company_id),
                "user_id": str(user_id),
                "member_id": str(member.id),
            },
        )
        return member

    def create_bootstrap_owner(
        self,
        *,
        company_id: UUID,
        user_id: UUID,
        request_context: dict[str, Any] | None = None,
    ) -> CompanyMember:
        """Create the initial active Owner membership for a company creator.

        Called immediately after role seeding during company creation.  Bypasses
        the normal rank-hierarchy enforcement because no members exist yet.
        The resulting membership is ``active`` (not ``pending_invitation``) since
        the creator is the owner and does not need to accept an invitation.

        Args:
            company_id: The newly created company.
            user_id: UUID of the user who created the company (becomes Owner).
            request_context: Optional dict with ``ip_address``, ``request_id``,
                ``user_agent`` for audit enrichment.

        Returns:
            The newly persisted :class:`CompanyMember` record with status=active.

        Raises:
            RoleNotFoundError: If the Owner system role is missing (seeding failed).
        """
        ctx = request_context or {}

        owner_role = self._role_repo.get_by_slug(company_id, "owner")
        if owner_role is None:
            raise RoleNotFoundError(
                message="Owner system role not found for company. "
                "Ensure roles are seeded before creating bootstrap membership.",
                details={"company_id": str(company_id)},
            )

        now = utcnow()
        member = CompanyMember(
            company_id=company_id,
            user_id=user_id,
            role_id=owner_role.id,
            status=MembershipStatus.active.value,
            created_by=user_id,
            invitation_accepted_at=now,
        )
        self._db.add(member)
        self._db.flush()

        self._audit_service.record(
            company_id=company_id,
            actor_user_id=user_id,
            action="MEMBER_CREATED",
            after_state={
                "member_id": str(member.id),
                "user_id": str(user_id),
                "role_id": str(owner_role.id),
                "role_name": owner_role.name,
                "status": MembershipStatus.active.value,
            },
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        event = MemberCreatedEvent(
            company_id=company_id,
            user_id=user_id,
            role_id=owner_role.id,
            invited_by=None,
            created_at=now,
        )
        self._outbox_repo.create(event.to_outbox_record(_new_correlation_id(), user_id))

        self._db.commit()
        self._db.refresh(member)

        logger.info(
            "Bootstrap owner membership created",
            extra={
                "company_id": str(company_id),
                "user_id": str(user_id),
                "member_id": str(member.id),
            },
        )
        return member

    def get_member(self, member_id: UUID, company_id: UUID) -> CompanyMember:
        """Return a member by ID, scoped to company.

        Raises:
            MemberNotFoundError: If the member does not exist.
        """
        member = self._member_repo.get_by_id_or_none(
            id=member_id, company_id=company_id
        )
        if member is None:
            raise MemberNotFoundError(details={"member_id": str(member_id)})
        return member

    def change_role(
        self,
        *,
        company_id: UUID,
        member_id: UUID,
        new_role_id: UUID,
        actor_user_id: UUID,
        actor_role_rank: int,
        request_context: dict[str, Any] | None = None,
    ) -> CompanyMember:
        """Change a member's role assignment.

        Steps:
        1. Resolve the target member (MemberNotFoundError if missing)
        2. Prevent self-role-change (BR-013)
        3. Enforce actor rank > target's current rank (BR-011)
        4. Validate new role exists in company (BR-010)
        5. Enforce actor rank > new role rank (BR-011)
        6. Protect last Owner from demotion (BR-001)
        7. Update role_id
        8. Write audit log (MEMBER_ROLE_CHANGED with before/after)
        9. Publish MemberRoleChangedEvent

        Raises:
            MemberNotFoundError: Target member not found.
            CannotModifyOwnRoleError: Actor is trying to change own role.
            InsufficientRankError: Actor rank too low.
            RoleNotFoundError: New role does not exist.
            LastOwnerProtectionError: Cannot demote the last Owner.
        """
        ctx = request_context or {}

        # 1. Resolve target member
        member = self._member_repo.get_by_id_or_none(
            id=member_id, company_id=company_id
        )
        if member is None:
            raise MemberNotFoundError(details={"member_id": str(member_id)})

        # 2. Prevent self-role-change (BR-013)
        if member.user_id == actor_user_id:
            raise CannotModifyOwnRoleError()

        # 3. Enforce actor rank > target's current role rank (BR-011)
        #    Exception: Owner (rank 100) can manage other Owners (same rank).
        current_role = self._role_repo.get_by_id_or_none(
            id=member.role_id, company_id=company_id
        )
        current_role_rank = current_role.rank if current_role else 0
        if actor_role_rank < current_role_rank or (
            actor_role_rank == current_role_rank and actor_role_rank != OWNER_RANK
        ):
            raise InsufficientRankError(
                message="You cannot change the role of a member with higher rank.",
                details={
                    "actor_rank": actor_role_rank,
                    "target_current_rank": current_role_rank,
                },
            )

        # 4. Validate new role exists in company (BR-010)
        new_role = self._role_repo.get_by_id_or_none(
            id=new_role_id, company_id=company_id
        )
        if new_role is None:
            raise RoleNotFoundError(
                details={"role_id": str(new_role_id), "company_id": str(company_id)}
            )

        # 5. Enforce actor rank > new role rank (BR-011)
        if actor_role_rank <= new_role.rank:
            raise InsufficientRankError(
                message="You cannot assign a role with equal or higher rank than your own.",
                details={
                    "actor_rank": actor_role_rank,
                    "target_role_rank": new_role.rank,
                },
            )

        # 6. Protect last Owner from demotion (BR-001)
        if current_role and current_role.slug == "owner" and new_role.slug != "owner":
            owner_role = current_role
            owner_count = self._member_repo.count_owners(company_id, owner_role.id)
            if owner_count <= 1:
                raise LastOwnerProtectionError()

        # 7. Update role_id
        old_role_id = member.role_id
        member.role_id = new_role_id
        self._db.flush()

        # 8. Write audit log
        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="MEMBER_ROLE_CHANGED",
            before_state={
                "member_id": str(member_id),
                "role_id": str(old_role_id),
                "role_name": current_role.name if current_role else "unknown",
                "role_rank": current_role_rank,
            },
            after_state={
                "member_id": str(member_id),
                "role_id": str(new_role_id),
                "role_name": new_role.name,
                "role_rank": new_role.rank,
            },
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        # 9. Publish domain event
        now = utcnow()
        event = MemberRoleChangedEvent(
            company_id=company_id,
            user_id=member.user_id,
            old_role_id=old_role_id,
            new_role_id=new_role_id,
            changed_at=now,
        )
        self._outbox_repo.create(
            event.to_outbox_record(_new_correlation_id(), actor_user_id)
        )

        self._db.commit()
        self._db.refresh(member)

        logger.info(
            "Member role changed",
            extra={
                "company_id": str(company_id),
                "member_id": str(member_id),
                "old_role_id": str(old_role_id),
                "new_role_id": str(new_role_id),
            },
        )
        return member

    def update_member(
        self,
        *,
        company_id: UUID,
        member_id: UUID,
        actor_user_id: UUID,
        actor_role_rank: int,
        role_id: UUID | None = None,
        employee_id: str | None | EllipsisType = ...,
        job_title: str | None | EllipsisType = ...,
        department: str | None | EllipsisType = ...,
        work_phone: str | None | EllipsisType = ...,
        hire_date: Any = ...,
        notes: str | None | EllipsisType = ...,
        request_context: dict[str, Any] | None = None,
    ) -> CompanyMember:
        """Update a member's role and/or employee information.

        If ``role_id`` is provided and differs from current, delegates to
        ``change_role``.  Employee fields use sentinel ``...`` to distinguish
        "not provided" from explicit ``None`` (clear).

        Raises:
            MemberNotFoundError: Target member not found.
            InsufficientRankError: Actor rank too low.
        """
        ctx = request_context or {}

        # Handle role change if requested
        if role_id is not None:
            member = self._member_repo.get_by_id_or_none(
                id=member_id, company_id=company_id
            )
            if member is None:
                raise MemberNotFoundError(details={"member_id": str(member_id)})
            if member.role_id != role_id:
                member = self.change_role(
                    company_id=company_id,
                    member_id=member_id,
                    new_role_id=role_id,
                    actor_user_id=actor_user_id,
                    actor_role_rank=actor_role_rank,
                    request_context=ctx,
                )
        else:
            member = self._member_repo.get_by_id_or_none(
                id=member_id, company_id=company_id
            )
            if member is None:
                raise MemberNotFoundError(details={"member_id": str(member_id)})

        # Update employee fields (sentinel ... means "not provided")
        _FIELDS = (
            "employee_id",
            "job_title",
            "department",
            "work_phone",
            "hire_date",
            "notes",
        )
        _VALUES = (employee_id, job_title, department, work_phone, hire_date, notes)

        # ── Validate before mutating ──────────────────────────────────────────
        if employee_id is not ... and employee_id is not None:
            # BR-032: employee_id must be unique within company (exclude self)
            existing = self._member_repo.get_by_employee_id(company_id, employee_id)
            if existing is not None and existing.id != member.id:
                raise EmployeeIdConflictError(
                    details={
                        "company_id": str(company_id),
                        "employee_id": employee_id,
                    }
                )

        if hire_date is not ... and hire_date is not None:
            # Hire date must not be in the future
            today = date.today()
            hire_date_value = (
                hire_date
                if isinstance(hire_date, date)
                else date.fromisoformat(str(hire_date))
            )
            if hire_date_value > today:
                raise HireDateInFutureError(
                    details={
                        "hire_date": str(hire_date_value),
                        "today": str(today),
                    }
                )

        # ── Capture before state and apply changes ────────────────────────────
        before_state: dict[str, Any] = {}
        updated_fields: dict[str, Any] = {}
        for field_name, field_value in zip(_FIELDS, _VALUES):
            if field_value is not ...:
                before_state[field_name] = (
                    str(getattr(member, field_name))
                    if getattr(member, field_name) is not None
                    else None
                )
                setattr(member, field_name, field_value)
                updated_fields[field_name] = (
                    str(field_value) if field_value is not None else None
                )

        if updated_fields:
            self._db.flush()

            self._audit_service.record(
                company_id=company_id,
                actor_user_id=actor_user_id,
                action="MEMBER_UPDATED",
                before_state={
                    "member_id": str(member_id),
                    "updated_fields": before_state,
                },
                after_state={
                    "member_id": str(member_id),
                    "updated_fields": updated_fields,
                },
                ip_address=ctx.get("ip_address"),
                request_id=ctx.get("request_id"),
                user_agent=ctx.get("user_agent"),
            )

            self._db.commit()
            self._db.refresh(member)

        return member

    def _reactivate_archived_member(
        self,
        member: CompanyMember,
        role_id: UUID,
        actor_user_id: UUID,
        actor_role_rank: int,
        request_context: dict[str, Any],
        **employee_fields: Any,
    ) -> CompanyMember:
        """Reactivate an archived membership (BR-044).

        Resets status to pending_invitation, clears deletion fields,
        and updates role and employee info.
        """
        # Validate role
        role = self._role_repo.get_by_id_or_none(
            id=role_id, company_id=member.company_id
        )
        if role is None:
            raise RoleNotFoundError(details={"role_id": str(role_id)})

        # Enforce rank hierarchy
        if actor_role_rank <= role.rank:
            raise InsufficientRankError(
                message="You cannot assign a role with equal or higher rank than your own.",
                details={
                    "actor_rank": actor_role_rank,
                    "target_role_rank": role.rank,
                },
            )

        # Reactivate
        member.role_id = role_id
        member.status = MembershipStatus.pending_invitation.value
        member.is_deleted = False
        member.deleted_at = None
        member.deletion_reason = None
        member.suspended_reason = None
        member.invited_by = actor_user_id
        member.invitation_accepted_at = None

        # Update employee fields
        for field in (
            "employee_id",
            "job_title",
            "department",
            "work_phone",
            "hire_date",
            "notes",
        ):
            if field in employee_fields:
                setattr(member, field, employee_fields[field])

        self._db.flush()

        # Audit log
        self._audit_service.record(
            company_id=member.company_id,
            actor_user_id=actor_user_id,
            action="MEMBER_REACTIVATED",
            after_state={
                "member_id": str(member.id),
                "user_id": str(member.user_id),
                "role_id": str(role_id),
                "role_name": role.name,
                "status": member.status,
                "reactivation_type": "archived_to_pending",
            },
            ip_address=request_context.get("ip_address"),
            request_id=request_context.get("request_id"),
            user_agent=request_context.get("user_agent"),
        )

        # Domain event
        event = MemberCreatedEvent(
            company_id=member.company_id,
            user_id=member.user_id,
            role_id=role_id,
            invited_by=actor_user_id,
            created_at=utcnow(),
        )
        self._outbox_repo.create(
            event.to_outbox_record(_new_correlation_id(), actor_user_id)
        )

        self._db.commit()
        self._db.refresh(member)

        logger.info(
            "Archived member reactivated",
            extra={
                "company_id": str(member.company_id),
                "member_id": str(member.id),
            },
        )
        return member

    # =========================================================================
    # Lifecycle methods — US5 (T068/T069/T070)
    # =========================================================================

    def _validate_transition(
        self,
        member_id: UUID,
        current_status: str,
        target_status: str,
    ) -> None:
        """Raise ``InvalidStatusTransitionError`` if transition is not allowed by BR-020.

        Args:
            member_id:      Member UUID (used in error details).
            current_status: The member's current status string.
            target_status:  The desired target status string.

        Raises:
            InvalidStatusTransitionError: Transition is not in ``_VALID_TRANSITIONS``.
        """
        allowed = _VALID_TRANSITIONS.get(current_status, frozenset())
        if target_status not in allowed:
            raise InvalidStatusTransitionError(
                details={
                    "member_id": str(member_id),
                    "current_status": current_status,
                    "target_status": target_status,
                    "allowed_from_current": sorted(allowed),
                }
            )

    def _resolve_member(
        self,
        member_id: UUID,
        company_id: UUID,
    ) -> CompanyMember:
        """Return an active (non-deleted) CompanyMember or raise ``MemberNotFoundError``."""
        member = self._member_repo.get_by_id_or_none(
            id=member_id, company_id=company_id
        )
        if member is None:
            raise MemberNotFoundError(details={"member_id": str(member_id)})
        return member

    def _check_last_owner_protection(
        self,
        member: CompanyMember,
        company_id: UUID,
    ) -> None:
        """Raise ``LastOwnerProtectionError`` if member is the last active Owner.

        Args:
            member:     The target member.
            company_id: The company scope.

        Raises:
            LastOwnerProtectionError: Member is the sole remaining active Owner.
        """
        role = self._role_repo.get_by_id_or_none(
            id=member.role_id, company_id=company_id
        )
        if role is not None and role.slug == "owner":
            owner_count = self._member_repo.count_owners(company_id, role.id)
            if owner_count <= 1:
                raise LastOwnerProtectionError()

    def _revoke_sessions(self, user_id: UUID) -> None:
        """Revoke all active sessions for ``user_id`` (FR-035).

        Uses Auth module's ``SessionRepository.revoke_all_by_user()``.
        If ``session_repo`` was not injected, logs a warning and continues.

        Args:
            user_id: The user whose sessions should be revoked.
        """
        if self._session_repo is None:
            logger.warning(
                "SessionRepository not injected; skipping session revocation",
                extra={"user_id": str(user_id)},
            )
            return
        self._session_repo.revoke_all_by_user(user_id)
        logger.debug("Sessions revoked", extra={"user_id": str(user_id)})

    def deactivate_member(
        self,
        *,
        company_id: UUID,
        member_id: UUID,
        actor_user_id: UUID,
        request_context: dict[str, Any] | None = None,
    ) -> CompanyMember:
        """Set member status to ``inactive`` and revoke all active sessions.

        Valid from: ``active`` only (BR-020).
        Last Owner protection: raises ``LastOwnerProtectionError`` if the
        member is the sole active Owner.

        Args:
            company_id:      Target company.
            member_id:       Target member UUID.
            actor_user_id:   User performing the action.
            request_context: Optional audit context (ip_address, request_id, …).

        Returns:
            Updated ``CompanyMember``.

        Raises:
            MemberNotFoundError:         Member not found.
            InvalidStatusTransitionError: Invalid transition from current status.
            LastOwnerProtectionError:    Last Owner cannot be deactivated.
        """
        ctx = request_context or {}
        member = self._resolve_member(member_id, company_id)
        self._validate_transition(
            member_id, member.status, MembershipStatus.inactive.value
        )
        self._check_last_owner_protection(member, company_id)

        before = {"status": member.status}
        member.status = MembershipStatus.inactive.value
        self._db.flush()

        self._revoke_sessions(member.user_id)

        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="MEMBER_DEACTIVATED",
            before_state=before,
            after_state={"member_id": str(member_id), "status": member.status},
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        now = utcnow()
        self._outbox_repo.create(
            MemberDeactivatedEvent(
                company_id=company_id,
                user_id=member.user_id,
                deactivated_at=now,
            ).to_outbox_record(_new_correlation_id(), actor_user_id)
        )

        self._db.commit()
        self._db.refresh(member)
        logger.info(
            "Member deactivated",
            extra={"company_id": str(company_id), "member_id": str(member_id)},
        )
        return member

    def reactivate_member(
        self,
        *,
        company_id: UUID,
        member_id: UUID,
        actor_user_id: UUID,
        request_context: dict[str, Any] | None = None,
    ) -> CompanyMember:
        """Set member status to ``active`` from ``inactive``, ``suspended``, or ``locked``.

        Audit action is context-sensitive:
        - From ``inactive`` → ``MEMBER_REACTIVATED``
        - From ``suspended`` → ``MEMBER_UNSUSPENDED``
        - From ``locked`` → ``MEMBER_UNLOCKED``

        Args:
            company_id:      Target company.
            member_id:       Target member UUID.
            actor_user_id:   User performing the action.
            request_context: Optional audit context.

        Returns:
            Updated ``CompanyMember``.

        Raises:
            MemberNotFoundError:         Member not found.
            InvalidStatusTransitionError: Invalid transition from current status.
        """
        ctx = request_context or {}
        member = self._resolve_member(member_id, company_id)
        from_status = member.status
        self._validate_transition(member_id, from_status, MembershipStatus.active.value)

        _ACTION_MAP = {
            MembershipStatus.inactive.value: "MEMBER_REACTIVATED",
            MembershipStatus.suspended.value: "MEMBER_UNSUSPENDED",
            MembershipStatus.locked.value: "MEMBER_UNLOCKED",
        }
        action = _ACTION_MAP.get(from_status, "MEMBER_REACTIVATED")

        before = {"status": from_status}
        member.status = MembershipStatus.active.value
        if from_status == MembershipStatus.suspended.value:
            member.suspended_reason = None
        self._db.flush()

        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action=action,
            before_state=before,
            after_state={"member_id": str(member_id), "status": member.status},
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        self._db.commit()
        self._db.refresh(member)
        logger.info(
            "Member reactivated",
            extra={
                "company_id": str(company_id),
                "member_id": str(member_id),
                "action": action,
            },
        )
        return member

    def suspend_member(
        self,
        *,
        company_id: UUID,
        member_id: UUID,
        actor_user_id: UUID,
        reason: str,
        request_context: dict[str, Any] | None = None,
    ) -> CompanyMember:
        """Set member status to ``suspended``, record reason, revoke sessions.

        Valid from: ``active``, ``locked`` (BR-020).
        Requires ``reason`` (BR-022).

        Args:
            company_id:      Target company.
            member_id:       Target member UUID.
            actor_user_id:   User performing the action.
            reason:          Mandatory suspension reason (BR-022).
            request_context: Optional audit context.

        Returns:
            Updated ``CompanyMember``.

        Raises:
            MemberNotFoundError:         Member not found.
            InvalidStatusTransitionError: Invalid transition from current status.
            LastOwnerProtectionError:    Last Owner cannot be suspended.
        """
        ctx = request_context or {}
        member = self._resolve_member(member_id, company_id)
        self._validate_transition(
            member_id, member.status, MembershipStatus.suspended.value
        )
        self._check_last_owner_protection(member, company_id)

        before = {"status": member.status, "suspended_reason": member.suspended_reason}
        member.status = MembershipStatus.suspended.value
        member.suspended_reason = reason
        self._db.flush()

        self._revoke_sessions(member.user_id)

        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="MEMBER_SUSPENDED",
            before_state=before,
            after_state={
                "member_id": str(member_id),
                "status": member.status,
                "reason": reason,
            },
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        now = utcnow()
        self._outbox_repo.create(
            MemberSuspendedEvent(
                company_id=company_id,
                user_id=member.user_id,
                reason=reason,
                suspended_at=now,
            ).to_outbox_record(_new_correlation_id(), actor_user_id)
        )

        self._db.commit()
        self._db.refresh(member)
        logger.info(
            "Member suspended",
            extra={"company_id": str(company_id), "member_id": str(member_id)},
        )
        return member

    def lock_member(
        self,
        *,
        company_id: UUID,
        member_id: UUID,
        actor_user_id: UUID,
        request_context: dict[str, Any] | None = None,
    ) -> CompanyMember:
        """Set member status to ``locked`` and revoke sessions (BR-025).

        Valid from: ``active`` only (BR-020).

        Args:
            company_id:      Target company.
            member_id:       Target member UUID.
            actor_user_id:   User performing the action.
            request_context: Optional audit context.

        Returns:
            Updated ``CompanyMember``.

        Raises:
            MemberNotFoundError:         Member not found.
            InvalidStatusTransitionError: Invalid transition from current status.
        """
        ctx = request_context or {}
        member = self._resolve_member(member_id, company_id)
        self._validate_transition(
            member_id, member.status, MembershipStatus.locked.value
        )

        before = {"status": member.status}
        member.status = MembershipStatus.locked.value
        self._db.flush()

        self._revoke_sessions(member.user_id)

        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="MEMBER_LOCKED",
            before_state=before,
            after_state={"member_id": str(member_id), "status": member.status},
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        now = utcnow()
        self._outbox_repo.create(
            MemberLockedEvent(
                company_id=company_id,
                user_id=member.user_id,
                locked_at=now,
            ).to_outbox_record(_new_correlation_id(), actor_user_id)
        )

        self._db.commit()
        self._db.refresh(member)
        logger.info(
            "Member locked",
            extra={"company_id": str(company_id), "member_id": str(member_id)},
        )
        return member

    def archive_member(
        self,
        *,
        company_id: UUID,
        member_id: UUID,
        actor_user_id: UUID,
        reason: str,
        request_context: dict[str, Any] | None = None,
    ) -> CompanyMember:
        """Soft-delete a member: set status to ``archived``, record ``deleted_at`` and reason.

        Valid from: ``active``, ``inactive``, ``suspended``, ``locked`` (BR-020).
        Requires ``reason`` (BR-023).

        Args:
            company_id:      Target company.
            member_id:       Target member UUID.
            actor_user_id:   User performing the action.
            reason:          Mandatory archival reason (BR-023).
            request_context: Optional audit context.

        Returns:
            Updated ``CompanyMember``.

        Raises:
            MemberNotFoundError:         Member not found.
            InvalidStatusTransitionError: Invalid transition from current status.
            LastOwnerProtectionError:    Last Owner cannot be archived.
        """
        ctx = request_context or {}
        member = self._resolve_member(member_id, company_id)
        self._validate_transition(
            member_id, member.status, MembershipStatus.archived.value
        )
        self._check_last_owner_protection(member, company_id)

        before = {"status": member.status}
        now = utcnow()
        member.status = MembershipStatus.archived.value
        member.deletion_reason = reason
        member.is_deleted = True
        member.deleted_at = now
        self._db.flush()

        self._revoke_sessions(member.user_id)

        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="MEMBER_ARCHIVED",
            before_state=before,
            after_state={
                "member_id": str(member_id),
                "status": member.status,
                "reason": reason,
                "deleted_at": now.isoformat(),
            },
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        self._outbox_repo.create(
            MemberArchivedEvent(
                company_id=company_id,
                user_id=member.user_id,
                reason=reason,
                archived_at=now,
            ).to_outbox_record(_new_correlation_id(), actor_user_id)
        )

        self._db.commit()
        self._db.refresh(member)
        logger.info(
            "Member archived",
            extra={"company_id": str(company_id), "member_id": str(member_id)},
        )
        return member

    def restore_member(
        self,
        *,
        company_id: UUID,
        member_id: UUID,
        actor_user_id: UUID,
        request_context: dict[str, Any] | None = None,
    ) -> CompanyMember:
        """Restore an archived member to ``active`` status and clear soft-delete fields.

        Valid from: ``archived`` only (BR-020).

        Args:
            company_id:      Target company.
            member_id:       Target member UUID.
            actor_user_id:   User performing the action.
            request_context: Optional audit context.

        Returns:
            Updated ``CompanyMember``.

        Raises:
            MemberNotFoundError:         Member not found.
            InvalidStatusTransitionError: Invalid transition from current status.
        """
        ctx = request_context or {}
        # archived members have is_deleted=True; use soft-delete-inclusive lookup
        member = self._member_repo.get_by_id_or_none(
            id=member_id, company_id=company_id
        )
        if member is None:
            # Try including deleted
            member = self._member_repo.get_deleted_by_id(
                member_id=member_id, company_id=company_id
            )
        if member is None:
            raise MemberNotFoundError(details={"member_id": str(member_id)})

        self._validate_transition(
            member_id, member.status, MembershipStatus.active.value
        )

        before = {"status": member.status}
        member.status = MembershipStatus.active.value
        member.is_deleted = False
        member.deleted_at = None
        member.deletion_reason = None
        self._db.flush()

        now = utcnow()
        self._audit_service.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            action="MEMBER_RESTORED",
            before_state=before,
            after_state={"member_id": str(member_id), "status": member.status},
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        self._outbox_repo.create(
            MemberRestoredEvent(
                company_id=company_id,
                user_id=member.user_id,
                restored_at=now,
            ).to_outbox_record(_new_correlation_id(), actor_user_id)
        )

        self._db.commit()
        self._db.refresh(member)
        logger.info(
            "Member restored",
            extra={"company_id": str(company_id), "member_id": str(member_id)},
        )
        return member
