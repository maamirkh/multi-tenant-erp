"""Integration test: Lead conversion atomicity + idempotency (tasks.md T038).

The single most important test file in the epic (plan.md §27.2/§33 R-07/
R-09) — proves spec.md §16 end-to-end against a real (SQLite) database
through the full ``LeadConversionService`` -> ``CustomerService`` ->
repository stack, not mocks.

Scenarios:
  (a) New-customer path — no matching Customer, one is created.
  (b) Matched-customer path — an existing Customer (matched by contact
      email) is reused, no duplicate created.
  (c) Repeat conversion — idempotent, no duplicate Customer/Opportunity.
  (d) Forced failure — Customer-creation raises; Lead and DB are untouched.
  (e) Soft-deleted-Customer edge case — a matching-but-deleted Customer is
      excluded; a new Customer is created instead (spec.md Edge Cases).

Task: T038 (tasks.md Phase 4).
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from modules.crm.exceptions import LeadNotFoundError, LeadNotQualifiedError
from modules.crm.models.lead import Lead
from modules.crm.repositories.audit_log import CrmAuditLogRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository
from modules.crm.services.audit_service import CrmAuditService
from modules.crm.services.lead_conversion_service import LeadConversionService
from modules.crm.services.pipeline_service import PipelineService
from modules.crm.services.provisioning_service import CrmProvisioningService
from modules.sales.models.customer import Customer, CustomerContact
from modules.sales.models.master import CustomerCategory
from modules.sales.repositories.customer import (
    CustomerAddressRepository,
    CustomerContactRepository,
    CustomerRepository,
)
from modules.sales.repositories.master import CustomerCategoryRepository
from modules.sales.services.customer_service import CustomerService
from modules.sales.services.master_data_service import CustomerCategoryService
from modules.sales.services.sequence_service import SalesSequenceService


def _build_conversion_service(db_session: Session) -> LeadConversionService:
    lead_repo = LeadRepository(db_session)
    opportunity_repo = OpportunityRepository(db_session)
    pipeline_repo = PipelineRepository(db_session)
    stage_repo = PipelineStageRepository(db_session)
    pipeline_service = PipelineService(db_session, pipeline_repo, stage_repo)
    category_repo = CustomerCategoryRepository(db_session)
    category_service = CustomerCategoryService(db_session, category_repo)
    provisioning_service = CrmProvisioningService(
        db_session, pipeline_repo, pipeline_service, category_repo, category_service
    )
    customer_service = CustomerService(
        db=db_session,
        customer_repo=CustomerRepository(db_session),
        contact_repo=CustomerContactRepository(db_session),
        address_repo=CustomerAddressRepository(db_session),
        sequence_service=SalesSequenceService(db=db_session),
    )
    return LeadConversionService(
        db=db_session,
        lead_repo=lead_repo,
        opportunity_repo=opportunity_repo,
        pipeline_repo=pipeline_repo,
        pipeline_stage_repo=stage_repo,
        provisioning_service=provisioning_service,
        customer_service=customer_service,
        audit_service=CrmAuditService(CrmAuditLogRepository(db_session)),
    )


def _qualified_lead(db_session: Session, company_id: UUID, **overrides: object) -> Lead:
    repo = LeadRepository(db_session)
    fields: dict[str, object] = {
        "company_id": company_id,
        "first_name": "Jane",
        "last_name": "Prospect",
        "email": f"jane-{uuid4().hex[:8]}@example.com",
        "status": "QUALIFIED",
        "qualification_notes": "Confirmed budget and timeline",
    }
    fields.update(overrides)
    return repo.create(Lead(**fields))


def _existing_customer_with_email(
    db_session: Session,
    company_id: UUID,
    email: str,
    *,
    legal_name: str = "Acme Inc",
    soft_deleted: bool = False,
) -> Customer:
    category_repo = CustomerCategoryRepository(db_session)
    category = category_repo.create(
        CustomerCategory(
            company_id=company_id,
            code=f"CAT-{uuid4().hex[:6]}",
            name="Pre-existing Category",
        )
    )
    customer_repo = CustomerRepository(db_session)
    customer = customer_repo.create(
        Customer(
            company_id=company_id,
            customer_code=f"CUST-{uuid4().hex[:8]}",
            legal_name=legal_name,
            customer_type="COMPANY",
            category_id=str(category.id),
            currency_code="USD",
            status="DRAFT",
        )
    )
    contact_repo = CustomerContactRepository(db_session)
    contact_repo.create(
        CustomerContact(
            company_id=company_id,
            customer_id=str(customer.id),
            contact_name="Primary Contact",
            email=email,
            is_primary=True,
        )
    )
    if soft_deleted:
        customer_repo.soft_delete(id=customer.id, company_id=company_id)
    return customer


class TestNewCustomerPath:
    def test_creates_new_customer_and_opportunity_lead_converted(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        service = _build_conversion_service(db_session)
        lead = _qualified_lead(db_session, company_id)

        result = service.convert(lead.id, company_id, actor_id=uuid4())

        customers, customer_total = CustomerRepository(db_session).list(
            company_id=company_id
        )
        opportunities, opp_total = OpportunityRepository(db_session).list(
            company_id=company_id
        )
        assert customer_total == 1
        assert opp_total == 1
        assert customers[0].id == result.customer_id
        assert opportunities[0].id == result.opportunity_id
        assert opportunities[0].source_lead_id == lead.id
        assert result.customer_matched is False

        fresh_lead = LeadRepository(db_session).get_by_id_or_none(
            id=lead.id, company_id=company_id
        )
        assert fresh_lead is not None
        assert fresh_lead.status == "CONVERTED"
        # INV-002: both linkage IDs always populated together.
        assert fresh_lead.converted_customer_id is not None
        assert fresh_lead.converted_opportunity_id is not None
        assert fresh_lead.converted_customer_id == str(result.customer_id)
        assert fresh_lead.converted_opportunity_id == result.opportunity_id
        assert fresh_lead.converted_at is not None


class TestMatchedCustomerPath:
    def test_matches_existing_customer_by_email_no_duplicate(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = f"match-{uuid4().hex[:8]}@example.com"
        existing = _existing_customer_with_email(db_session, company_id, email)
        service = _build_conversion_service(db_session)
        lead = _qualified_lead(db_session, company_id, email=email)

        result = service.convert(lead.id, company_id, actor_id=uuid4())

        assert result.customer_id == existing.id
        assert result.customer_matched is True

        _, customer_total = CustomerRepository(db_session).list(company_id=company_id)
        assert customer_total == 1  # no new Customer created

        opportunities, opp_total = OpportunityRepository(db_session).list(
            company_id=company_id
        )
        assert opp_total == 1
        assert opportunities[0].customer_id == str(existing.id)


class TestRepeatConversionIdempotency:
    def test_repeat_conversion_returns_identical_result_no_duplicates(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        service = _build_conversion_service(db_session)
        lead = _qualified_lead(db_session, company_id)

        first = service.convert(lead.id, company_id, actor_id=uuid4())
        second = service.convert(lead.id, company_id, actor_id=uuid4())

        assert first.customer_id == second.customer_id
        assert first.opportunity_id == second.opportunity_id
        # T096/Phase-10 regression: the idempotent-retry branch must recall
        # the *original* conversion's customer_matched fact (via the audit
        # log), not hardcode it — a prior defect always returned True here.
        assert first.customer_matched is False
        assert second.customer_matched == first.customer_matched

        _, customer_total = CustomerRepository(db_session).list(company_id=company_id)
        _, opp_total = OpportunityRepository(db_session).list(company_id=company_id)
        assert customer_total == 1
        assert opp_total == 1

    def test_repeat_conversion_on_matched_customer_path_preserves_flag(
        self, db_session: Session
    ) -> None:
        """Regression test for a Phase-10 defect: the idempotent-retry
        branch of ``LeadConversionService.convert()`` unconditionally
        returned ``customer_matched=True``, which happened to be correct
        only when the *original* conversion itself matched an existing
        Customer. Repeating a *new-customer-path* conversion silently
        mis-reported ``customer_matched=True`` on the second call even
        though the first call correctly reported ``False`` — surfaced by
        T096's SEC-10 API test. Fixed via
        ``CrmAuditService.find_latest_after_state()`` recalling the
        original fact instead of assuming one. This test covers the
        matched-path side explicitly (already-True case), complementing
        the sibling test above (new-customer/False case)."""
        company_id = uuid4()
        email = f"match-repeat-{uuid4().hex[:8]}@example.com"
        existing = _existing_customer_with_email(db_session, company_id, email)
        service = _build_conversion_service(db_session)
        lead = _qualified_lead(db_session, company_id, email=email)

        first = service.convert(lead.id, company_id, actor_id=uuid4())
        second = service.convert(lead.id, company_id, actor_id=uuid4())

        assert first.customer_matched is True
        assert second.customer_matched is True
        assert first.customer_id == existing.id
        assert second.customer_id == existing.id


class TestForcedFailureAtomicity:
    def test_customer_creation_failure_leaves_lead_and_db_untouched(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        service = _build_conversion_service(db_session)
        lead = _qualified_lead(db_session, company_id)

        with patch.object(
            service._customer_service,
            "create",
            side_effect=RuntimeError("simulated mid-conversion failure"),
        ):
            with pytest.raises(RuntimeError):
                service.convert(lead.id, company_id, actor_id=uuid4())

        fresh_lead = LeadRepository(db_session).get_by_id_or_none(
            id=lead.id, company_id=company_id
        )
        assert fresh_lead is not None
        assert fresh_lead.status == "QUALIFIED"
        assert fresh_lead.converted_customer_id is None
        assert fresh_lead.converted_opportunity_id is None

        _, customer_total = CustomerRepository(db_session).list(company_id=company_id)
        _, opp_total = OpportunityRepository(db_session).list(company_id=company_id)
        assert customer_total == 0
        assert opp_total == 0


class TestSoftDeletedCustomerEdgeCase:
    def test_soft_deleted_matching_customer_excluded_new_one_created(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        email = f"deleted-{uuid4().hex[:8]}@example.com"
        deleted_customer = _existing_customer_with_email(
            db_session, company_id, email, soft_deleted=True
        )
        service = _build_conversion_service(db_session)
        lead = _qualified_lead(db_session, company_id, email=email)

        result = service.convert(lead.id, company_id, actor_id=uuid4())

        assert result.customer_id != deleted_customer.id
        assert result.customer_matched is False

        _, customer_total = CustomerRepository(db_session).list(
            company_id=company_id, include_deleted=True
        )
        assert customer_total == 2  # the deleted one + the newly created one


class TestPreconditions:
    def test_convert_unknown_lead_raises_not_found(self, db_session: Session) -> None:
        service = _build_conversion_service(db_session)
        with pytest.raises(LeadNotFoundError):
            service.convert(uuid4(), uuid4(), actor_id=uuid4())

    def test_convert_non_qualified_lead_raises_conflict(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        service = _build_conversion_service(db_session)
        lead = _qualified_lead(
            db_session, company_id, status="NEW", email="x@example.com"
        )

        with pytest.raises(LeadNotQualifiedError):
            service.convert(lead.id, company_id, actor_id=uuid4())

    def test_convert_cross_tenant_lead_raises_not_found(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        other_company_id = uuid4()
        service = _build_conversion_service(db_session)
        lead = _qualified_lead(db_session, company_id)

        with pytest.raises(LeadNotFoundError):
            service.convert(lead.id, other_company_id, actor_id=uuid4())
