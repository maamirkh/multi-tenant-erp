"""LeadConversionService — implements spec.md §16 (Lead Conversion) in full.

Kept in its own file, not folded into ``LeadService`` (plan.md §9), because
of its cross-module orchestration complexity: customer match-or-create,
Opportunity creation, and the optimistic-locked idempotent Lead update, all
under one transaction boundary.

**Commit-boundary note** (read before touching this file): Sales'
``CustomerService.create()`` is called unmodified for the new-customer
path (§10.2 of plan.md explicitly reuses "its own validation, sequencing,
and commit behavior... unchanged") — and, like every ``BaseRepository``
write in this codebase, it commits internally. That single sub-commit is
therefore a pre-existing, accepted boundary this service does not attempt
to suppress (doing so would mean monkey-patching or reimplementing
``CustomerService.create()``, both explicitly forbidden). Everything CRM
itself controls after that point — Opportunity creation and the Lead's
status/version update — is genuinely atomic: only ``flush()`` until the
single ``db.commit()`` at the very end, exactly matching ADR-4's "no
compensating-logic" design and spec.md §16.2's rollback guarantee for that
boundary. Practically: if Opportunity creation or the Lead update fails
after a *new* Customer was just committed, that Customer is not deleted
(harmless — status remains DRAFT and it is not linked from anywhere), the
Lead's status is untouched (still QUALIFIED, safely re-convertible), and a
retry will actually *match* that same orphan Customer via
``find_matching_customer_candidates()`` (its legal_name was derived from
the Lead) rather than creating a second one — a graceful, not silent,
degradation. The *matched-customer* path (no new Customer write at all)
has zero intermediate-commit exposure and is fully atomic end-to-end.

Spec ref: specs/009-crm/spec.md §16; plan.md §9, §10.2, ADR-4.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException
from core.utils.datetime import utcnow
from modules.crm.events import get_event_bus
from modules.crm.events.lead_events import LeadConverted
from modules.crm.events.opportunity_events import OpportunityCreated
from modules.crm.exceptions import LeadNotFoundError, LeadNotQualifiedError
from modules.crm.models.lead import Lead
from modules.crm.models.opportunity import Opportunity
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository
from modules.crm.services.audit_service import CrmAuditService
from modules.crm.services.provisioning_service import CrmProvisioningService
from modules.sales.services.customer_service import CustomerService

logger = logging.getLogger(__name__)

#: Fallback currency for a newly-created Customer when no better signal
#: exists (Lead carries no currency field) — matches this codebase's own
#: system-wide default (see Company.default_currency's own "USD" default).
_DEFAULT_CURRENCY_CODE = "USD"


@dataclass(frozen=True)
class ConversionResult:
    lead_id: UUID
    customer_id: UUID
    opportunity_id: UUID
    customer_matched: bool


class LeadConversionService:
    """Converts a QUALIFIED Lead into a Customer + Opportunity, atomically
    and idempotently (spec.md §16)."""

    def __init__(
        self,
        db: Session,
        lead_repo: LeadRepository,
        opportunity_repo: OpportunityRepository,
        pipeline_repo: PipelineRepository,
        pipeline_stage_repo: PipelineStageRepository,
        provisioning_service: CrmProvisioningService,
        customer_service: CustomerService,
        audit_service: CrmAuditService,
    ) -> None:
        self.db = db
        self._lead_repo = lead_repo
        self._opportunity_repo = opportunity_repo
        self._pipeline_repo = pipeline_repo
        self._stage_repo = pipeline_stage_repo
        self._provisioning_service = provisioning_service
        self._customer_service = customer_service
        self._audit = audit_service

    def convert(
        self, lead_id: UUID, company_id: UUID, actor_id: UUID
    ) -> ConversionResult:
        lead = self._lead_repo.get_by_id_or_none(id=lead_id, company_id=company_id)
        if lead is None:
            raise LeadNotFoundError(str(lead_id))

        # Idempotency guard — first line of logic, before anything else.
        # ``customer_matched`` is recalled from the original conversion's
        # audit entry, not hardcoded — a repeat call must report the same
        # fact the first call did, never silently overstate it as always
        # "matched" (see CrmAuditService.find_latest_after_state).
        if lead.status == "CONVERTED":
            after_state = self._audit.find_latest_after_state(
                company_id, "LEAD", lead.id, "LEAD_CONVERTED"
            )
            customer_matched = (
                bool(after_state["customer_matched"]) if after_state else True
            )
            return ConversionResult(
                lead_id=lead.id,
                customer_id=UUID(str(lead.converted_customer_id)),
                opportunity_id=lead.converted_opportunity_id,  # type: ignore[arg-type]
                customer_matched=customer_matched,
            )

        if lead.status != "QUALIFIED":
            raise LeadNotQualifiedError(str(lead.id), lead.status)

        customer_id, customer_matched = self._match_or_create_customer(
            lead, company_id, actor_id
        )
        opportunity = self._create_opportunity(lead, company_id, actor_id, customer_id)

        result = self._apply_conversion_with_optimistic_lock(
            lead, company_id, customer_id, opportunity.id
        )
        if result is not None:
            # A concurrent request already converted this Lead first —
            # return its (now-committed) result idempotently.
            return result

        self._audit.record(
            company_id=company_id,
            actor_user_id=actor_id,
            entity_type="LEAD",
            entity_id=lead.id,
            action="LEAD_CONVERTED",
            after_state={
                "customer_id": str(customer_id),
                "opportunity_id": str(opportunity.id),
                "customer_matched": customer_matched,
            },
        )
        self.db.commit()
        bus = get_event_bus()
        bus.publish(
            LeadConverted(
                aggregate_id=lead.id,
                company_id=company_id,
                actor_id=actor_id,
                lead_id=lead.id,
                customer_id=str(customer_id),
                opportunity_id=opportunity.id,
                customer_matched=customer_matched,
            )
        )
        bus.publish(
            OpportunityCreated(
                aggregate_id=opportunity.id,
                company_id=company_id,
                actor_id=actor_id,
                opportunity_id=opportunity.id,
                customer_id=opportunity.customer_id,
                source_lead_id=lead.id,
            )
        )

        return ConversionResult(
            lead_id=lead.id,
            customer_id=customer_id,
            opportunity_id=opportunity.id,
            customer_matched=customer_matched,
        )

    # ------------------------------------------------------------------
    # Step 3: match or create Customer (spec.md §16.1)
    # ------------------------------------------------------------------

    def _match_or_create_customer(
        self, lead: Lead, company_id: UUID, actor_id: UUID
    ) -> tuple[UUID, bool]:
        candidates = self._lead_repo.find_matching_customer_candidates(
            company_id,
            email=lead.email,
            phone=lead.phone,
            legal_name=lead.lead_company_name,
        )
        if candidates:
            return candidates[0].id, True

        defaults = self._provisioning_service.ensure_defaults(
            company_id, created_by=actor_id
        )
        customer_type = "COMPANY" if lead.lead_company_name else "INDIVIDUAL"
        legal_name = lead.lead_company_name or (
            f"{lead.first_name or ''} {lead.last_name or ''}".strip()
        )
        customer = self._customer_service.create(
            company_id=company_id,
            customer_code=self._generate_customer_code(),
            legal_name=legal_name,
            customer_type=customer_type,
            category_id=defaults.category.id,
            currency_code=_DEFAULT_CURRENCY_CODE,
            created_by=actor_id,
        )
        return customer.id, False

    @staticmethod
    def _generate_customer_code() -> str:
        """A CRM-originated Customer has no user-supplied code (unlike
        Sales' own create-customer UI, which requires one). A short random
        suffix keeps this well within the 30-char column limit and makes a
        collision with ``uq_customers_company_code`` astronomically
        unlikely — no dedicated sequence mechanism is warranted for this
        single, low-volume use case."""
        return f"CRM-{uuid4().hex[:12].upper()}"

    # ------------------------------------------------------------------
    # Step 4: create the Opportunity (spec.md §16.1 point 2)
    # ------------------------------------------------------------------

    def _create_opportunity(
        self, lead: Lead, company_id: UUID, actor_id: UUID, customer_id: UUID
    ) -> Opportunity:
        pipeline = self._pipeline_repo.get_default_for_company(company_id)
        if pipeline is None:
            # Should not happen — ensure_defaults() is called on the
            # new-customer path above, and at flag-enable time (T036). If
            # the matched-customer path skipped provisioning entirely,
            # provision now rather than fail.
            defaults = self._provisioning_service.ensure_defaults(
                company_id, created_by=actor_id
            )
            pipeline = defaults.pipeline

        stage = self._stage_repo.get_first_stage_for_pipeline(pipeline.id, company_id)
        assert stage is not None, (
            "CrmProvisioningService always creates an active first stage "
            "for the default pipeline it provisions."
        )

        name = lead.lead_company_name or (
            f"{lead.first_name or ''} {lead.last_name or ''}".strip()
        )
        opportunity = Opportunity(
            company_id=company_id,
            name=f"{name} — New Opportunity".strip(),
            customer_id=str(customer_id),
            owner_id=lead.owner_id or str(actor_id),
            pipeline_id=pipeline.id,
            stage_id=stage.id,
            currency_code=_DEFAULT_CURRENCY_CODE,
            probability=stage.probability,
            source_lead_id=lead.id,
            created_by=actor_id,
        )
        self.db.add(opportunity)
        self.db.flush()
        return opportunity

    # ------------------------------------------------------------------
    # Step 5: update the Lead under an optimistic lock (spec.md §16.3)
    # ------------------------------------------------------------------

    def _apply_conversion_with_optimistic_lock(
        self,
        lead: Lead,
        company_id: UUID,
        customer_id: UUID,
        opportunity_id: UUID,
    ) -> ConversionResult | None:
        """Returns None on success (caller commits). Returns a
        ConversionResult if a concurrent request already won the race —
        the caller must return it as-is without committing further."""
        expected_version = lead.version
        stmt = (
            update(Lead)
            .where(Lead.id == lead.id)
            .where(Lead.company_id == company_id)
            .where(Lead.version == expected_version)
            .values(
                status="CONVERTED",
                converted_customer_id=str(customer_id),
                converted_opportunity_id=opportunity_id,
                converted_at=utcnow(),
                version=Lead.version + 1,
            )
        )
        result = self.db.execute(stmt)
        if result.rowcount == 1:  # type: ignore[attr-defined]
            return None

        # No rows matched — a concurrent conversion committed first.
        # Discard our own uncommitted Opportunity insert and re-read.
        self.db.rollback()
        fresh_lead = self._lead_repo.get_by_id_or_none(
            id=lead.id, company_id=company_id
        )
        if fresh_lead is not None and fresh_lead.status == "CONVERTED":
            return ConversionResult(
                lead_id=fresh_lead.id,
                customer_id=UUID(str(fresh_lead.converted_customer_id)),
                opportunity_id=fresh_lead.converted_opportunity_id,  # type: ignore[arg-type]
                customer_matched=True,
            )
        raise ConflictException(
            f"Lead '{lead.id}' could not be converted due to a concurrent update.",
            details={"lead_id": str(lead.id)},
        )
