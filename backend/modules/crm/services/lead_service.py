"""LeadService — application service for the Lead aggregate.

Covers: create, update (incl. status transitions via ``_transition_status``,
matching the exact idiom already used by
``modules/inventory/services/product_service.py``), qualify, disqualify,
assign (with active-membership validation, spec.md §30.3), soft-delete.

Audit (``CrmAuditService.record(...)``) and domain-event publication
(``get_event_bus().publish(...)``) are wired for real as of Phase 8
(plan.md §18, §19) — every mutating method below issues its audit record
(spec.md §44's action list: LEAD_CREATED, LEAD_STATUS_CHANGED,
LEAD_ASSIGNED) immediately followed by its own ``db.commit()``.
``BaseRepository.create()``/``.update()`` already commit internally per
call (this codebase's established, audited convention), so the audit row
lands in its own small follow-up commit rather than a single joint
transaction with the entity write — the same two-commit shape every
other simple-CRUD CRM service already has; only Lead Conversion
(spec.md §16.2) requires strict single-transaction atomicity, and it has
its own bespoke, non-``BaseRepository`` commit discipline for exactly
that reason.

Spec ref: specs/009-crm/spec.md §14, §15, §30.3, §44; plan.md §9, §11, §18.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import ValidationException
from modules.crm.constants import LEAD_VALID_TRANSITIONS
from modules.crm.events import get_event_bus
from modules.crm.events.lead_events import (
    LeadAssigned,
    LeadCreated,
    LeadQualified,
    LeadStatusChanged,
)
from modules.crm.exceptions import InvalidLeadTransitionError, LeadNotFoundError
from modules.crm.models.lead import Lead
from modules.crm.repositories.lead import LeadRepository
from modules.crm.schemas.lead import LeadCreate, LeadUpdate
from modules.crm.services.audit_service import CrmAuditService
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)


def _lead_snapshot(lead: Lead) -> dict[str, object]:
    return {
        "status": lead.status,
        "owner_id": lead.owner_id,
        "source_id": str(lead.source_id) if lead.source_id else None,
    }


class LeadService:
    """Application service for Lead capture, lifecycle, and assignment."""

    def __init__(
        self,
        db: Session,
        repo: LeadRepository,
        member_repo: CompanyMemberRepository,
        audit_service: CrmAuditService,
    ) -> None:
        self.db = db
        self._repo = repo
        self._member_repo = member_repo
        self._audit = audit_service

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, lead_id: UUID, company_id: UUID) -> Lead:
        return self._get_or_raise(lead_id, company_id)

    def list_filtered(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        source_id: UUID | None = None,
        owner_id: UUID | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Lead], int]:
        return self._repo.list_filtered(
            company_id,
            status=status,
            source_id=source_id,
            owner_id=owner_id,
            created_from=created_from,
            created_to=created_to,
            search=search,
            page=page,
            page_size=page_size,
        )

    # ------------------------------------------------------------------
    # Create / Update
    # ------------------------------------------------------------------

    def create(
        self, company_id: UUID, data: LeadCreate, *, created_by: UUID | None = None
    ) -> Lead:
        lead = Lead(
            company_id=company_id,
            created_by=created_by,
            **data.model_dump(exclude_unset=True),
        )
        lead = self._repo.create(lead)
        self._audit.record(
            company_id=company_id,
            actor_user_id=created_by,
            entity_type="LEAD",
            entity_id=lead.id,
            action="LEAD_CREATED",
            after_state=_lead_snapshot(lead),
        )
        self.db.commit()
        get_event_bus().publish(
            LeadCreated(
                aggregate_id=lead.id,
                company_id=company_id,
                actor_id=created_by,
                lead_id=lead.id,
                source_id=lead.source_id,
            )
        )
        return lead

    def update(
        self,
        lead_id: UUID,
        company_id: UUID,
        data: LeadUpdate,
        *,
        actor_user_id: UUID | None = None,
    ) -> Lead:
        """Apply field updates and, if ``status`` is included and differs
        from the current value, perform the lifecycle transition in the
        same commit (spec.md §15 — qualify/disqualify are just a
        constrained status change on this same endpoint, not separate
        actions)."""
        lead = self._get_or_raise(lead_id, company_id)
        fields = data.model_dump(exclude_unset=True, exclude={"status"})
        for field, value in fields.items():
            setattr(lead, field, value)

        target_status = data.status
        if target_status is not None and target_status != lead.status:
            return self._transition_status(lead, target_status, actor_user_id)

        return self._repo.update(lead)

    # ------------------------------------------------------------------
    # Lifecycle transitions (spec.md §14.2)
    # ------------------------------------------------------------------

    def _transition_status(
        self, lead: Lead, target: str, actor_user_id: UUID | None = None
    ) -> Lead:
        """Validate and apply a Lead status transition, per spec.md §14.2.

        Enforces BR-005 (disqualification_reason required for UNQUALIFIED/
        LOST) and spec.md §15 (qualification_notes required for QUALIFIED)
        before the transition is applied.
        """
        allowed = LEAD_VALID_TRANSITIONS.get(lead.status, frozenset())
        if target not in allowed:
            raise InvalidLeadTransitionError(lead.status, target)

        if target in ("UNQUALIFIED", "LOST") and not lead.disqualification_reason:
            raise ValidationException(
                f"disqualification_reason is required when a Lead becomes {target}.",
                details={"lead_id": str(lead.id), "target_status": target},
            )
        if target == "QUALIFIED" and not lead.qualification_notes:
            raise ValidationException(
                "qualification_notes must be set before a Lead can be QUALIFIED.",
                details={"lead_id": str(lead.id)},
            )

        from_status = lead.status
        lead.status = target
        self.db.flush()
        self._audit.record(
            company_id=lead.company_id,
            actor_user_id=actor_user_id,
            entity_type="LEAD",
            entity_id=lead.id,
            action="LEAD_STATUS_CHANGED",
            before_state={"status": from_status},
            after_state={"status": target},
        )
        self.db.commit()
        self.db.refresh(lead)
        bus = get_event_bus()
        bus.publish(
            LeadStatusChanged(
                aggregate_id=lead.id,
                company_id=lead.company_id,
                actor_id=actor_user_id,
                lead_id=lead.id,
                from_status=from_status,
                to_status=target,
            )
        )
        if target == "QUALIFIED":
            bus.publish(
                LeadQualified(
                    aggregate_id=lead.id,
                    company_id=lead.company_id,
                    actor_id=actor_user_id,
                    lead_id=lead.id,
                )
            )
        return lead

    def qualify(
        self,
        lead_id: UUID,
        company_id: UUID,
        qualification_notes: str | None = None,
        *,
        actor_user_id: UUID | None = None,
    ) -> Lead:
        lead = self._get_or_raise(lead_id, company_id)
        if qualification_notes is not None:
            lead.qualification_notes = qualification_notes
        return self._transition_status(lead, "QUALIFIED", actor_user_id)

    def disqualify(
        self,
        lead_id: UUID,
        company_id: UUID,
        reason: str,
        target_status: str = "UNQUALIFIED",
        *,
        actor_user_id: UUID | None = None,
    ) -> Lead:
        if target_status not in ("UNQUALIFIED", "LOST"):
            raise ValueError("target_status must be UNQUALIFIED or LOST")
        lead = self._get_or_raise(lead_id, company_id)
        lead.disqualification_reason = reason
        return self._transition_status(lead, target_status, actor_user_id)

    # ------------------------------------------------------------------
    # Assignment (spec.md §30.3)
    # ------------------------------------------------------------------

    def assign(
        self,
        lead_id: UUID,
        company_id: UUID,
        owner_id: UUID,
        *,
        actor_user_id: UUID | None = None,
    ) -> Lead:
        """Reassign a Lead's owner, rejecting a user with no active
        membership in this company (spec.md §30.3, SEC-12)."""
        lead = self._get_or_raise(lead_id, company_id)
        member = self._member_repo.get_by_user_id(owner_id, company_id)
        if member is None or member.status != "active":
            raise ValidationException(
                "owner_id must be an active member of this company.",
                details={"owner_id": str(owner_id)},
            )
        previous_owner_id = lead.owner_id
        lead.owner_id = str(owner_id)
        result = self._repo.update(lead)
        self._audit.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            entity_type="LEAD",
            entity_id=lead.id,
            action="LEAD_ASSIGNED",
            before_state={"owner_id": previous_owner_id},
            after_state={"owner_id": str(owner_id)},
        )
        self.db.commit()
        get_event_bus().publish(
            LeadAssigned(
                aggregate_id=lead.id,
                company_id=company_id,
                actor_id=actor_user_id,
                lead_id=lead.id,
                owner_id=str(owner_id),
            )
        )
        return result

    # ------------------------------------------------------------------
    # Soft delete
    # ------------------------------------------------------------------

    def soft_delete(self, lead_id: UUID, company_id: UUID) -> None:
        self._repo.soft_delete(id=lead_id, company_id=company_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_or_raise(self, lead_id: UUID, company_id: UUID) -> Lead:
        lead = self._repo.get_by_id_or_none(id=lead_id, company_id=company_id)
        if lead is None:
            raise LeadNotFoundError(str(lead_id))
        return lead
