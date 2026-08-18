"""ActivityService — application service for the Activity aggregate.

``complete()`` implements spec.md §19.2 / plan.md §13's single-transaction
Lead-cascade: idempotent no-op if already COMPLETED; else, within one
commit, marks the Activity COMPLETED and (if ``lead_id`` is set)
atomically advances the linked Lead's ``last_contact_date``/``status``.

**GREATEST() portability note**: plan.md §13 specifies a raw SQL
``GREATEST(last_contact_date, :now)`` expression to avoid a read-compare-
write race between two near-simultaneous completions. ``GREATEST()`` is a
Postgres/MySQL function with no SQLite equivalent, and this codebase's
test suite runs against SQLite. The same race-free, single-UPDATE
semantics are expressed here with a portable ``CASE WHEN ... THEN ...
ELSE ...`` expression instead (identical behavior on both dialects,
including treating ``NULL`` as "always superseded" the same way
``GREATEST(NULL, x)`` does in Postgres) — not a functional change, a
dialect-portable rendering of the same guarantee.

Audit (spec.md §44): only the status-change transition (``complete()``)
is audited — Activity creation/field-update is deliberately NOT audited,
per spec.md §44's explicit scoping ("create/update of subject/description
is not separately audited — only status transitions, to avoid excessive
audit noise on routine note-taking").

Spec ref: specs/009-crm/spec.md §19, §30.3, §30.4, §44; plan.md §13, §18.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import case, or_, update
from sqlalchemy.orm import Session

from core.exceptions.base import ValidationException
from core.utils.datetime import utcnow
from modules.crm.events import get_event_bus
from modules.crm.events.activity_events import ActivityCompleted, ActivityCreated
from modules.crm.exceptions import ActivityNotFoundError
from modules.crm.models.activity import Activity
from modules.crm.models.lead import Lead
from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.schemas.activity import ActivityCreate, ActivityUpdate
from modules.crm.services.audit_service import CrmAuditService
from modules.sales.repositories.customer import CustomerRepository
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)


class ActivityService:
    """Application service for Activity CRUD, completion, and the
    Lead-cascade side effect."""

    def __init__(
        self,
        db: Session,
        repo: ActivityRepository,
        lead_repo: LeadRepository,
        customer_repo: CustomerRepository,
        opportunity_repo: OpportunityRepository,
        member_repo: CompanyMemberRepository,
        audit_service: CrmAuditService,
    ) -> None:
        self.db = db
        self._repo = repo
        self._lead_repo = lead_repo
        self._customer_repo = customer_repo
        self._opportunity_repo = opportunity_repo
        self._member_repo = member_repo
        self._audit = audit_service

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, activity_id: UUID, company_id: UUID) -> Activity:
        return self._get_or_raise(activity_id, company_id)

    def list_filtered(
        self, company_id: UUID, **kwargs: object
    ) -> tuple[list[Activity], int]:
        return self._repo.list_filtered(company_id, **kwargs)  # type: ignore[arg-type]

    def list_overdue(
        self, company_id: UUID, *, owner_id: UUID | None = None
    ) -> list[Activity]:
        return self._repo.list_overdue(company_id, owner_id=owner_id)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self, company_id: UUID, data: ActivityCreate, *, created_by: UUID | None = None
    ) -> Activity:
        self._validate_active_member(data.assigned_to, company_id)

        if data.lead_id is not None:
            lead = self._lead_repo.get_by_id_or_none(
                id=data.lead_id, company_id=company_id
            )
            if lead is None:
                raise ValidationException(
                    "lead_id must reference a Lead in this company.",
                    details={"lead_id": str(data.lead_id)},
                )
        if data.customer_id is not None:
            customer = self._customer_repo.get_by_id_or_none(
                id=data.customer_id, company_id=company_id
            )
            if customer is None:
                raise ValidationException(
                    "customer_id must reference a Customer in this company.",
                    details={"customer_id": str(data.customer_id)},
                )
        if data.opportunity_id is not None:
            opportunity = self._opportunity_repo.get_by_id_or_none(
                id=data.opportunity_id, company_id=company_id
            )
            if opportunity is None:
                raise ValidationException(
                    "opportunity_id must reference an Opportunity in this company.",
                    details={"opportunity_id": str(data.opportunity_id)},
                )

        activity = Activity(
            company_id=company_id,
            activity_type=data.activity_type,
            subject=data.subject,
            description=data.description,
            priority=data.priority,
            due_date=data.due_date,
            assigned_to=str(data.assigned_to),
            lead_id=data.lead_id,
            customer_id=str(data.customer_id) if data.customer_id else None,
            opportunity_id=data.opportunity_id,
            created_by=created_by,
        )
        result = self._repo.create(activity)
        # No audit record here — spec.md §44 scopes Activity auditing to
        # status transitions only (see module docstring).
        get_event_bus().publish(
            ActivityCreated(
                aggregate_id=result.id,
                company_id=company_id,
                actor_id=created_by,
                activity_id=result.id,
                activity_type=result.activity_type,
            )
        )
        return result

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(
        self, activity_id: UUID, company_id: UUID, data: ActivityUpdate
    ) -> Activity:
        activity = self._get_or_raise(activity_id, company_id)
        if data.assigned_to is not None:
            self._validate_active_member(data.assigned_to, company_id)

        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "assigned_to":
                setattr(activity, field, str(value))
            else:
                setattr(activity, field, value)
        return self._repo.update(activity)

    # ------------------------------------------------------------------
    # Complete (spec.md §19.2 / plan.md §13)
    # ------------------------------------------------------------------

    def complete(
        self,
        activity_id: UUID,
        company_id: UUID,
        *,
        actor_user_id: UUID | None = None,
    ) -> Activity:
        activity = self._get_or_raise(activity_id, company_id)
        if activity.status == "COMPLETED":
            return activity  # idempotent no-op, spec.md §43

        now = utcnow()
        activity.status = "COMPLETED"
        activity.completed_at = now
        self.db.flush()

        if activity.lead_id is not None:
            completed_date = now.date()
            stmt = (
                update(Lead)
                .where(Lead.id == activity.lead_id)
                .where(Lead.company_id == company_id)
                .values(
                    last_contact_date=case(
                        (
                            or_(
                                Lead.last_contact_date.is_(None),
                                Lead.last_contact_date < completed_date,
                            ),
                            completed_date,
                        ),
                        else_=Lead.last_contact_date,
                    ),
                    status=case(
                        (Lead.status == "NEW", "CONTACTED"),
                        else_=Lead.status,
                    ),
                )
            )
            self.db.execute(stmt)

        self._audit.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            entity_type="ACTIVITY",
            entity_id=activity.id,
            action="ACTIVITY_COMPLETED",
            before_state={"status": "PLANNED"},
            after_state={"status": "COMPLETED"},
        )
        self.db.commit()
        self.db.refresh(activity)
        get_event_bus().publish(
            ActivityCompleted(
                aggregate_id=activity.id,
                company_id=company_id,
                actor_id=actor_user_id,
                activity_id=activity.id,
                activity_type=activity.activity_type,
            )
        )
        return activity

    # ------------------------------------------------------------------
    # Soft delete
    # ------------------------------------------------------------------

    def soft_delete(self, activity_id: UUID, company_id: UUID) -> None:
        self._repo.soft_delete(id=activity_id, company_id=company_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_or_raise(self, activity_id: UUID, company_id: UUID) -> Activity:
        activity = self._repo.get_by_id_or_none(id=activity_id, company_id=company_id)
        if activity is None:
            raise ActivityNotFoundError(str(activity_id))
        return activity

    def _validate_active_member(self, user_id: UUID, company_id: UUID) -> None:
        member = self._member_repo.get_by_user_id(user_id, company_id)
        if member is None or member.status != "active":
            raise ValidationException(
                "assigned_to must be an active member of this company.",
                details={"assigned_to": str(user_id)},
            )
