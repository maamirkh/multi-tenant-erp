"""Cross-module boundary tests — CRM <-> Sales, CRM <-> Accounting (T059).

Verifies, at runtime (not just on paper), the boundaries plan.md's §5/§15/
§16 and ADR-1/ADR-2/ADR-3/ADR-6 describe:

  - ``LeadConversionService`` never manipulates a Sales ORM object
    directly — it only ever writes to Sales through ``CustomerService``
    (confirmed both structurally, via its own module's imports, and at
    runtime, via a matched-customer conversion that writes zero rows to
    any Sales table).
  - ``Customer360Service`` is genuinely read-only — it issues zero
    INSERT/UPDATE/DELETE statements of any kind for a full Customer 360
    composition.
  - Setting ``Opportunity.quotation_id`` via ``PATCH /crm/opportunities/{id}``
    (plan.md §15.2's UI-orchestrated handoff) is a pure CRM-side field
    update — it validates the Quotation's existence with a read-only
    lookup but never writes to any Sales table.

Task: T059 (tasks.md Phase 7).
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from modules.accounting.dependencies import build_ar_service
from modules.crm.models.lead import Lead
from modules.crm.models.opportunity import Opportunity
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage
from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.audit_log import CrmAuditLogRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository
from modules.crm.schemas.opportunity import OpportunityUpdate
from modules.crm.services.audit_service import CrmAuditService
from modules.crm.services.customer_360_service import Customer360Service
from modules.crm.services.lead_conversion_service import LeadConversionService
from modules.crm.services.opportunity_service import OpportunityService
from modules.crm.services.pipeline_service import PipelineService
from modules.crm.services.provisioning_service import CrmProvisioningService
from modules.sales.models.customer import Customer, CustomerContact
from modules.sales.models.master import CustomerCategory
from modules.sales.models.quotation import SalesQuotation
from modules.sales.repositories.customer import (
    CustomerAddressRepository,
    CustomerContactRepository,
    CustomerRepository,
)
from modules.sales.repositories.master import CustomerCategoryRepository
from modules.sales.repositories.quotation import SalesQuotationRepository
from modules.sales.services.customer_service import CustomerService
from modules.sales.services.master_data_service import CustomerCategoryService
from modules.sales.services.sequence_service import SalesSequenceService
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)

#: Every Sales table that must remain untouched by a purely CRM-side
#: read-only operation (Customer 360) or a matched-customer conversion.
_SALES_TABLES = (
    "customers",
    "customer_contacts",
    "customer_addresses",
    "customer_categories",
    "sales_quotations",
    "quotation_lines",
    "sales_orders",
    "order_lines",
    "sales_invoices",
    "invoice_lines",
    "delivery_notes",
)


@contextmanager
def _track_write_statements(db_session: Session):
    """Yield a list capturing every INSERT/UPDATE/DELETE statement issued
    on this session's connection while the context is open."""
    writes: list[str] = []
    connection = db_session.get_bind()

    def _before_cursor_execute(
        conn: Any, cursor: Any, statement: str, *args: Any, **kwargs: Any
    ) -> None:
        verb = statement.strip().split(None, 1)[0].upper() if statement.strip() else ""
        if verb in ("INSERT", "UPDATE", "DELETE"):
            writes.append(statement)

    event.listen(connection, "before_cursor_execute", _before_cursor_execute)
    try:
        yield writes
    finally:
        event.remove(connection, "before_cursor_execute", _before_cursor_execute)


def _sales_tables_touched(writes: list[str]) -> list[str]:
    return [stmt for stmt in writes if any(table in stmt for table in _SALES_TABLES)]


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


def _existing_customer_with_email(
    db_session: Session, company_id: UUID, email: str
) -> Customer:
    category = CustomerCategoryRepository(db_session).create(
        CustomerCategory(
            company_id=company_id, code=f"CAT-{uuid4().hex[:6]}", name="Pre-existing"
        )
    )
    customer = CustomerRepository(db_session).create(
        Customer(
            company_id=company_id,
            customer_code=f"CUST-{uuid4().hex[:8]}",
            legal_name="Boundary Test Co",
            customer_type="COMPANY",
            category_id=str(category.id),
            currency_code="USD",
            status="ACTIVE",
        )
    )
    CustomerContactRepository(db_session).create(
        CustomerContact(
            company_id=company_id,
            customer_id=str(customer.id),
            contact_name="Primary",
            email=email,
            is_primary=True,
        )
    )
    return customer


def _create_customer(
    db_session: Session, company_id: UUID, **overrides: Any
) -> Customer:
    category = CustomerCategoryRepository(db_session).create(
        CustomerCategory(
            company_id=company_id, code=f"CAT-{uuid4().hex[:6]}", name="Test Category"
        )
    )
    fields: dict[str, Any] = {
        "company_id": company_id,
        "customer_code": f"CUST-{uuid4().hex[:8]}",
        "legal_name": "Boundary 360 Customer",
        "customer_type": "COMPANY",
        "category_id": str(category.id),
        "currency_code": "USD",
        "status": "ACTIVE",
    }
    fields.update(overrides)
    return CustomerRepository(db_session).create(Customer(**fields))


class TestLeadConversionNeverManipulatesSalesOrmDirectly:
    def test_no_sales_module_ships_a_raw_orm_import_in_conversion_service(self) -> None:
        """Structural boundary check: the conversion service only imports
        Sales *services* (``CustomerService``), never a Sales ORM model
        class — every Sales write it can possibly cause is mediated by
        Sales' own service layer, not raw CRM-side session manipulation."""
        import inspect

        import modules.crm.services.lead_conversion_service as mod

        source = inspect.getsource(mod)
        assert "from modules.sales.models" not in source
        assert (
            "modules.sales.services.customer_service import CustomerService" in source
        )

    def test_matched_customer_conversion_writes_zero_sales_rows(
        self, db_session: Session
    ) -> None:
        """The matched-customer path (spec.md §16.1) reuses an existing
        Customer by reference only — it must not INSERT/UPDATE/DELETE any
        Sales-owned row at all (no new Customer, no touched Contact)."""
        company_id = uuid4()
        email = f"boundary-{uuid4().hex[:8]}@example.com"
        existing = _existing_customer_with_email(db_session, company_id, email)

        service = _build_conversion_service(db_session)
        # Pre-provision the default Pipeline/Category OUTSIDE the tracked
        # window — those writes are legitimate and already covered by
        # T034/T035; this test isolates convert()'s own write footprint.
        service._provisioning_service.ensure_defaults(company_id, created_by=uuid4())

        lead = LeadRepository(db_session).create(
            Lead(
                company_id=company_id,
                first_name="Match",
                last_name="Prospect",
                email=email,
                status="QUALIFIED",
                qualification_notes="ok",
            )
        )

        with _track_write_statements(db_session) as writes:
            result = service.convert(lead.id, company_id, actor_id=uuid4())

        assert result.customer_id == existing.id
        assert result.customer_matched is True
        touched = _sales_tables_touched(writes)
        assert touched == [], f"Unexpected Sales-table writes: {touched}"


class TestCustomer360IsReadOnly:
    def test_get_customer_360_issues_zero_write_statements(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        customer = _create_customer(db_session, company_id)
        service = Customer360Service(
            db=db_session,
            customer_repo=CustomerRepository(db_session),
            lead_repo=LeadRepository(db_session),
            opportunity_repo=OpportunityRepository(db_session),
            activity_repo=ActivityRepository(db_session),
            ar_service=build_ar_service(db_session, with_sales_sync=False),
        )

        with _track_write_statements(db_session) as writes:
            service.get_customer_360(company_id, customer.id)

        assert writes == [], f"Customer360Service issued write(s): {writes}"
        # Also confirm the ORM session itself has nothing pending —
        # belt-and-suspenders alongside the statement-level check above.
        assert not db_session.new
        assert not db_session.dirty
        assert not db_session.deleted


class TestOpportunityQuotationLinkBackDoesNotTouchSales:
    def test_patch_quotation_id_is_pure_crm_side_update(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        customer = _create_customer(db_session, company_id)
        pipeline = PipelineRepository(db_session).create(
            Pipeline(company_id=company_id, name="P", is_default=True)
        )
        stage = PipelineStageRepository(db_session).create(
            PipelineStage(
                company_id=company_id,
                pipeline_id=pipeline.id,
                name="Qualification",
                sequence=1,
                probability=20,
            )
        )
        opportunity = OpportunityRepository(db_session).create(
            Opportunity(
                company_id=company_id,
                name="Deal",
                customer_id=str(customer.id),
                owner_id=str(uuid4()),
                pipeline_id=pipeline.id,
                stage_id=stage.id,
                value=Decimal("5000"),
                currency_code="USD",
                probability=20,
            )
        )
        quotation = SalesQuotationRepository(db_session).create(
            SalesQuotation(
                company_id=company_id,
                quotation_number=f"QUO-{uuid4().hex[:8]}",
                customer_id=str(customer.id),
                currency_code="USD",
                quotation_date="2026-01-01",
                validity_date="2026-01-31",
                sales_rep_id=str(uuid4()),
            )
        )

        service = OpportunityService(
            db=db_session,
            repo=OpportunityRepository(db_session),
            stage_repo=PipelineStageRepository(db_session),
            customer_repo=CustomerRepository(db_session),
            member_repo=CompanyMemberRepository(db_session),
            quotation_repo=SalesQuotationRepository(db_session),
            audit_service=CrmAuditService(CrmAuditLogRepository(db_session)),
        )

        with _track_write_statements(db_session) as writes:
            updated = service.update(
                opportunity.id,
                company_id,
                OpportunityUpdate(quotation_id=quotation.id),
            )

        assert updated.quotation_id == str(quotation.id)
        touched = _sales_tables_touched(writes)
        assert touched == [], f"Unexpected Sales-table writes: {touched}"
        # The only write in this call should be the Opportunity's own
        # UPDATE against crm_opportunities.
        assert any("crm_opportunities" in stmt for stmt in writes)

    def test_quotation_id_from_another_company_is_rejected(
        self, db_session: Session
    ) -> None:
        company_a = uuid4()
        company_b = uuid4()
        customer = _create_customer(db_session, company_a)
        pipeline = PipelineRepository(db_session).create(
            Pipeline(company_id=company_a, name="P", is_default=True)
        )
        stage = PipelineStageRepository(db_session).create(
            PipelineStage(
                company_id=company_a,
                pipeline_id=pipeline.id,
                name="Qualification",
                sequence=1,
                probability=20,
            )
        )
        opportunity = OpportunityRepository(db_session).create(
            Opportunity(
                company_id=company_a,
                name="Deal",
                customer_id=str(customer.id),
                owner_id=str(uuid4()),
                pipeline_id=pipeline.id,
                stage_id=stage.id,
                value=Decimal("5000"),
                currency_code="USD",
                probability=20,
            )
        )
        other_customer = _create_customer(db_session, company_b)
        foreign_quotation = SalesQuotationRepository(db_session).create(
            SalesQuotation(
                company_id=company_b,
                quotation_number=f"QUO-{uuid4().hex[:8]}",
                customer_id=str(other_customer.id),
                currency_code="USD",
                quotation_date="2026-01-01",
                validity_date="2026-01-31",
                sales_rep_id=str(uuid4()),
            )
        )

        service = OpportunityService(
            db=db_session,
            repo=OpportunityRepository(db_session),
            stage_repo=PipelineStageRepository(db_session),
            customer_repo=CustomerRepository(db_session),
            member_repo=CompanyMemberRepository(db_session),
            quotation_repo=SalesQuotationRepository(db_session),
            audit_service=CrmAuditService(CrmAuditLogRepository(db_session)),
        )

        from core.exceptions.base import ValidationException

        with pytest.raises(ValidationException):
            service.update(
                opportunity.id,
                company_a,
                OpportunityUpdate(quotation_id=foreign_quotation.id),
            )
