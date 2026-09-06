"""T093 — Lead conversion performance benchmark (spec.md §47/NFR-002).

Measures ``LeadConversionService.convert()`` latency directly (service
layer, real SQLite DB, no mocks) across both conversion paths — new-customer
and matched-customer — matching the exact service-construction pattern
established by ``tests/integration/repositories/crm/test_lead_conversion.py``.

Unlike T092/T095, this target (p95 < 2s) is asserted at its real,
spec-mandated value, not a scaled-down SQLite guard — a single conversion
is a small, constant-size transaction (a handful of inserts/updates), so
SQLite's lack of cost-based query planning is not a confound here the way
it is for large aggregate scans.

Task: T093 (tasks.md Phase 10). Spec ref: spec.md §47/NFR-002.
"""

from __future__ import annotations

import statistics
import time
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

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

_TARGET_SECONDS = 2.0  # spec.md §47/NFR-002 — the real target, not a scaled guard
_SAMPLE_SIZE = 25  # per path (new-customer, matched-customer)


def _p95(samples: list[float]) -> float:
    return statistics.quantiles(samples, n=100)[94]


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
        "first_name": "Perf",
        "last_name": "Prospect",
        "email": f"perf-{uuid4().hex[:8]}@example.com",
        "status": "QUALIFIED",
        "qualification_notes": "Perf-test qualified lead",
    }
    fields.update(overrides)
    return repo.create(Lead(**fields))


def _existing_customer_with_email(
    db_session: Session, company_id: UUID, email: str
) -> Customer:
    category = CustomerCategoryRepository(db_session).create(
        CustomerCategory(
            company_id=company_id,
            code=f"CAT-{uuid4().hex[:6]}",
            name="Perf Category",
        )
    )
    customer = CustomerRepository(db_session).create(
        Customer(
            company_id=company_id,
            customer_code=f"CUST-{uuid4().hex[:8]}",
            legal_name="Perf Existing Customer",
            customer_type="COMPANY",
            category_id=str(category.id),
            currency_code="USD",
            status="DRAFT",
        )
    )
    CustomerContactRepository(db_session).create(
        CustomerContact(
            company_id=company_id,
            customer_id=str(customer.id),
            contact_name="Primary Contact",
            email=email,
            is_primary=True,
        )
    )
    return customer


class TestConversionPerformance:
    def test_new_customer_path_p95_under_target(self, db_session: Session) -> None:
        company_id = uuid4()
        service = _build_conversion_service(db_session)
        samples: list[float] = []
        for _ in range(_SAMPLE_SIZE):
            lead = _qualified_lead(db_session, company_id)
            start = time.perf_counter()
            result = service.convert(lead.id, company_id, actor_id=uuid4())
            samples.append(time.perf_counter() - start)
            assert result.customer_matched is False

        p95 = _p95(samples)
        print(f"\nNew-customer conversion p95 over {_SAMPLE_SIZE} runs: {p95:.3f}s")
        assert p95 < _TARGET_SECONDS, (
            f"New-customer conversion p95 {p95:.3f}s exceeds {_TARGET_SECONDS}s"
        )

    def test_matched_customer_path_p95_under_target(self, db_session: Session) -> None:
        company_id = uuid4()
        service = _build_conversion_service(db_session)
        samples: list[float] = []
        for _ in range(_SAMPLE_SIZE):
            email = f"perf-match-{uuid4().hex[:8]}@example.com"
            _existing_customer_with_email(db_session, company_id, email)
            lead = _qualified_lead(db_session, company_id, email=email)
            start = time.perf_counter()
            result = service.convert(lead.id, company_id, actor_id=uuid4())
            samples.append(time.perf_counter() - start)
            assert result.customer_matched is True

        p95 = _p95(samples)
        print(f"\nMatched-customer conversion p95 over {_SAMPLE_SIZE} runs: {p95:.3f}s")
        assert p95 < _TARGET_SECONDS, (
            f"Matched-customer conversion p95 {p95:.3f}s exceeds {_TARGET_SECONDS}s"
        )
