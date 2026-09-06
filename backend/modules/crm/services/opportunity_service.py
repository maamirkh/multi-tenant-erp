"""OpportunityService — application service for the Opportunity aggregate.

Covers: create (independent of Lead conversion), update, assign,
change_stage, win, lose, soft-delete — spec.md §17.2/§17.3.

``win()``/``change_stage()``/``lose()`` are guarded by
``UPDATE ... WHERE status = 'OPEN'`` (plan.md §12's row-level concurrency
guard — the same idiom as Lead conversion's optimistic lock, but simpler
since Opportunity has no separate ``version`` column: the ``status``
column itself is the guard, since once WON/LOST it never reverts).

Audit (``CrmAuditService.record(...)``) is wired for real as of Phase 8.
``create()``/``assign()`` follow a second, small follow-up commit after
``BaseRepository``'s own internal commit (matching ``LeadService``'s
identical two-commit shape); ``change_stage()``/``win()``/``lose()``
instead flush the audit row INSIDE ``_execute_guarded_transition()``,
before its own single commit — genuinely atomic with the guarded
``UPDATE ... WHERE status = 'OPEN'`` transition, since both go through
the same explicit ``db.commit()`` there.

Spec ref: specs/009-crm/spec.md §17, §30.3, §30.4, §44; plan.md §9, §12, §18.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import Update, update
from sqlalchemy.orm import Session

from core.exceptions.base import ValidationException
from core.utils.datetime import utcnow
from modules.crm.events import get_event_bus
from modules.crm.events.opportunity_events import (
    OpportunityAssigned,
    OpportunityCreated,
    OpportunityLost,
    OpportunityStageChanged,
    OpportunityWon,
)
from modules.crm.exceptions import (
    InvalidOpportunityTransitionError,
    OpportunityNotFoundError,
    PipelineNotFoundError,
)
from modules.crm.models.opportunity import Opportunity
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository
from modules.crm.schemas.opportunity import OpportunityCreate, OpportunityUpdate
from modules.crm.services.audit_service import CrmAuditService
from modules.sales.repositories.customer import CustomerRepository
from modules.sales.repositories.quotation import SalesQuotationRepository
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)


class OpportunityService:
    """Application service for Opportunity CRUD and lifecycle."""

    def __init__(
        self,
        db: Session,
        repo: OpportunityRepository,
        stage_repo: PipelineStageRepository,
        customer_repo: CustomerRepository,
        member_repo: CompanyMemberRepository,
        quotation_repo: SalesQuotationRepository,
        audit_service: CrmAuditService,
    ) -> None:
        self.db = db
        self._repo = repo
        self._stage_repo = stage_repo
        self._customer_repo = customer_repo
        self._member_repo = member_repo
        self._quotation_repo = quotation_repo
        self._audit = audit_service

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, opportunity_id: UUID, company_id: UUID) -> Opportunity:
        return self._get_or_raise(opportunity_id, company_id)

    def list_filtered(
        self, company_id: UUID, **kwargs: object
    ) -> tuple[list[Opportunity], int]:
        return self._repo.list_filtered(company_id, **kwargs)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self,
        company_id: UUID,
        data: OpportunityCreate,
        *,
        created_by: UUID | None = None,
    ) -> Opportunity:
        # SEC-06 (spec.md §30.4): customer_id must belong to this company.
        customer = self._customer_repo.get_by_id_or_none(
            id=data.customer_id, company_id=company_id
        )
        if customer is None:
            raise ValidationException(
                "customer_id must reference a Customer in this company.",
                details={"customer_id": str(data.customer_id)},
            )

        self._validate_active_member(data.owner_id, company_id)

        stage = self._stage_repo.get_by_id_or_none(
            id=data.stage_id, company_id=company_id
        )
        if stage is None:
            raise PipelineNotFoundError(str(data.stage_id))
        # INV-004: stage must belong to the specified pipeline.
        if stage.pipeline_id != data.pipeline_id:
            raise ValidationException(
                "stage_id must belong to the specified pipeline_id.",
                details={
                    "stage_id": str(data.stage_id),
                    "pipeline_id": str(data.pipeline_id),
                },
            )

        opportunity = Opportunity(
            company_id=company_id,
            name=data.name,
            customer_id=str(data.customer_id),
            owner_id=str(data.owner_id),
            pipeline_id=data.pipeline_id,
            stage_id=data.stage_id,
            value=data.value,
            currency_code=data.currency_code or customer.currency_code,
            probability=(
                data.probability if data.probability is not None else stage.probability
            ),
            expected_close_date=data.expected_close_date,
            description=data.description,
            created_by=created_by,
        )
        result = self._repo.create(opportunity)
        self._audit.record(
            company_id=company_id,
            actor_user_id=created_by,
            entity_type="OPPORTUNITY",
            entity_id=result.id,
            action="OPPORTUNITY_CREATED",
            after_state={
                "customer_id": result.customer_id,
                "owner_id": result.owner_id,
                "stage_id": str(result.stage_id),
                "value": str(result.value),
            },
        )
        self.db.commit()
        get_event_bus().publish(
            OpportunityCreated(
                aggregate_id=result.id,
                company_id=company_id,
                actor_id=created_by,
                opportunity_id=result.id,
                customer_id=result.customer_id,
                source_lead_id=None,
            )
        )
        return result

    # ------------------------------------------------------------------
    # Update (BR-003: rejected once WON/LOST)
    # ------------------------------------------------------------------

    def update(
        self, opportunity_id: UUID, company_id: UUID, data: OpportunityUpdate
    ) -> Opportunity:
        opportunity = self._get_or_raise(opportunity_id, company_id)
        if opportunity.status != "OPEN":
            raise InvalidOpportunityTransitionError(opportunity.status)

        updates = data.model_dump(exclude_unset=True)
        if "quotation_id" in updates:
            quotation_id = updates.pop("quotation_id")
            opportunity.quotation_id = self._validated_quotation_id(
                quotation_id, company_id
            )
        for field, value in updates.items():
            setattr(opportunity, field, value)
        return self._repo.update(opportunity)

    def _validated_quotation_id(
        self, quotation_id: UUID | None, company_id: UUID
    ) -> str | None:
        """spec.md §30.4 (SEC-06-equivalent): a linked ``quotation_id`` must
        belong to the same company. This is a pure CRM-side field update —
        it never creates, reads beyond existence-check, or writes any
        Sales row (plan.md §15.2's UI-orchestrated handoff)."""
        if quotation_id is None:
            return None
        quotation = self._quotation_repo.get_by_id_or_none(
            id=quotation_id, company_id=company_id
        )
        if quotation is None:
            raise ValidationException(
                "quotation_id must reference a Quotation in this company.",
                details={"quotation_id": str(quotation_id)},
            )
        return str(quotation_id)

    # ------------------------------------------------------------------
    # Assignment (spec.md §30.3, symmetric with LeadService.assign())
    # ------------------------------------------------------------------

    def assign(
        self,
        opportunity_id: UUID,
        company_id: UUID,
        owner_id: UUID,
        *,
        actor_user_id: UUID | None = None,
    ) -> Opportunity:
        opportunity = self._get_or_raise(opportunity_id, company_id)
        self._validate_active_member(owner_id, company_id)
        previous_owner_id = opportunity.owner_id
        opportunity.owner_id = str(owner_id)
        result = self._repo.update(opportunity)
        self._audit.record(
            company_id=company_id,
            actor_user_id=actor_user_id,
            entity_type="OPPORTUNITY",
            entity_id=opportunity.id,
            action="OPPORTUNITY_ASSIGNED",
            before_state={"owner_id": previous_owner_id},
            after_state={"owner_id": str(owner_id)},
        )
        self.db.commit()
        get_event_bus().publish(
            OpportunityAssigned(
                aggregate_id=opportunity.id,
                company_id=company_id,
                actor_id=actor_user_id,
                opportunity_id=opportunity.id,
                owner_id=str(owner_id),
            )
        )
        return result

    # ------------------------------------------------------------------
    # Stage change (spec.md §17.2/§18.2; INV-004)
    # ------------------------------------------------------------------

    def change_stage(
        self,
        opportunity_id: UUID,
        company_id: UUID,
        stage_id: UUID,
        probability: int | None = None,
        *,
        actor_user_id: UUID | None = None,
    ) -> Opportunity:
        opportunity = self._get_or_raise(opportunity_id, company_id)
        stage = self._stage_repo.get_by_id_or_none(id=stage_id, company_id=company_id)
        if stage is None:
            raise PipelineNotFoundError(str(stage_id))
        if stage.pipeline_id != opportunity.pipeline_id:
            raise ValidationException(
                "stage must belong to the Opportunity's own pipeline (INV-004).",
                details={"stage_id": str(stage_id)},
            )
        if not stage.is_active:
            raise ValidationException(
                "Cannot move an Opportunity to an inactive stage.",
                details={"stage_id": str(stage_id)},
            )

        from_stage_id = str(opportunity.stage_id)
        stmt = (
            update(Opportunity)
            .where(Opportunity.id == opportunity.id)
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.status == "OPEN")
            .values(
                stage_id=stage_id,
                probability=(
                    probability if probability is not None else stage.probability
                ),
            )
        )

        def _audit() -> None:
            self._audit.record(
                company_id=company_id,
                actor_user_id=actor_user_id,
                entity_type="OPPORTUNITY",
                entity_id=opportunity.id,
                action="OPPORTUNITY_STAGE_CHANGED",
                before_state={"stage_id": from_stage_id},
                after_state={"stage_id": str(stage_id)},
            )

        self._execute_guarded_transition(stmt, opportunity, audit_fn=_audit)
        get_event_bus().publish(
            OpportunityStageChanged(
                aggregate_id=opportunity.id,
                company_id=company_id,
                actor_id=actor_user_id,
                opportunity_id=opportunity.id,
                from_stage_id=UUID(from_stage_id),
                to_stage_id=stage_id,
            )
        )
        return opportunity

    # ------------------------------------------------------------------
    # Win / Lose (spec.md §17.2, terminal)
    # ------------------------------------------------------------------

    def win(
        self,
        opportunity_id: UUID,
        company_id: UUID,
        *,
        actor_user_id: UUID | None = None,
    ) -> Opportunity:
        opportunity = self._get_or_raise(opportunity_id, company_id)
        won_stage = self._stage_repo.get_flagged_stage(
            opportunity.pipeline_id, company_id, is_won_stage=True
        )
        values: dict[str, object] = {"status": "WON", "won_at": utcnow()}
        if won_stage is not None:
            values["stage_id"] = won_stage.id
            values["probability"] = won_stage.probability

        stmt = (
            update(Opportunity)
            .where(Opportunity.id == opportunity.id)
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.status == "OPEN")
            .values(**values)
        )

        def _audit() -> None:
            self._audit.record(
                company_id=company_id,
                actor_user_id=actor_user_id,
                entity_type="OPPORTUNITY",
                entity_id=opportunity.id,
                action="OPPORTUNITY_WON",
                before_state={"status": "OPEN"},
                after_state={"status": "WON", "value": str(opportunity.value)},
            )

        self._execute_guarded_transition(stmt, opportunity, audit_fn=_audit)
        get_event_bus().publish(
            OpportunityWon(
                aggregate_id=opportunity.id,
                company_id=company_id,
                actor_id=actor_user_id,
                opportunity_id=opportunity.id,
                value=opportunity.value,
                currency_code=opportunity.currency_code,
            )
        )
        return opportunity

    def lose(
        self,
        opportunity_id: UUID,
        company_id: UUID,
        lost_reason: str,
        *,
        actor_user_id: UUID | None = None,
    ) -> Opportunity:
        opportunity = self._get_or_raise(opportunity_id, company_id)
        lost_stage = self._stage_repo.get_flagged_stage(
            opportunity.pipeline_id, company_id, is_lost_stage=True
        )
        values: dict[str, object] = {
            "status": "LOST",
            "lost_at": utcnow(),
            "lost_reason": lost_reason,
        }
        if lost_stage is not None:
            values["stage_id"] = lost_stage.id
            values["probability"] = lost_stage.probability

        stmt = (
            update(Opportunity)
            .where(Opportunity.id == opportunity.id)
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.status == "OPEN")
            .values(**values)
        )

        def _audit() -> None:
            self._audit.record(
                company_id=company_id,
                actor_user_id=actor_user_id,
                entity_type="OPPORTUNITY",
                entity_id=opportunity.id,
                action="OPPORTUNITY_LOST",
                before_state={"status": "OPEN"},
                after_state={"status": "LOST", "lost_reason": lost_reason},
            )

        self._execute_guarded_transition(stmt, opportunity, audit_fn=_audit)
        get_event_bus().publish(
            OpportunityLost(
                aggregate_id=opportunity.id,
                company_id=company_id,
                actor_id=actor_user_id,
                opportunity_id=opportunity.id,
                lost_reason=lost_reason,
            )
        )
        return opportunity

    # ------------------------------------------------------------------
    # Soft delete — only while OPEN (spec.md §38.4)
    # ------------------------------------------------------------------

    def soft_delete(self, opportunity_id: UUID, company_id: UUID) -> None:
        opportunity = self._get_or_raise(opportunity_id, company_id)
        if opportunity.status != "OPEN":
            raise InvalidOpportunityTransitionError(opportunity.status)
        self._repo.soft_delete(id=opportunity_id, company_id=company_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_or_raise(self, opportunity_id: UUID, company_id: UUID) -> Opportunity:
        opportunity = self._repo.get_by_id_or_none(
            id=opportunity_id, company_id=company_id
        )
        if opportunity is None:
            raise OpportunityNotFoundError(str(opportunity_id))
        return opportunity

    def _validate_active_member(self, user_id: UUID, company_id: UUID) -> None:
        member = self._member_repo.get_by_user_id(user_id, company_id)
        if member is None or member.status != "active":
            raise ValidationException(
                "owner_id must be an active member of this company.",
                details={"owner_id": str(user_id)},
            )

    def _execute_guarded_transition(
        self,
        stmt: Update,
        opportunity: Opportunity,
        *,
        audit_fn: Callable[[], None] | None = None,
    ) -> None:
        """Run an ``UPDATE ... WHERE status = 'OPEN'`` transition, commit,
        and refresh ``opportunity`` in place. Raises
        ``InvalidOpportunityTransitionError`` if the guard rejected the
        update (status was already WON/LOST). ``audit_fn`` (if given) runs
        after the guarded UPDATE succeeds but before the commit, so the
        audit row lands atomically with the state transition itself."""
        result = self.db.execute(stmt)
        if result.rowcount != 1:  # type: ignore[attr-defined]
            raise InvalidOpportunityTransitionError(opportunity.status)
        if audit_fn is not None:
            audit_fn()
        self.db.commit()
        self.db.refresh(opportunity)
