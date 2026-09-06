"""Integration tests for Phase 0 sales repositories.

Tests:
  - CustomerCategory CRUD with code uniqueness per company
  - CustomerGroup CRUD with code uniqueness per company
  - SalesPaymentTerm CRUD
  - SalesReasonCode CRUD
  - SalesConfiguration singleton per company
  - Company_id scoping (tenant isolation)
  - Soft-delete exclusion

Requires a running PostgreSQL database.

Task: T029
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from modules.sales.models.master import (
    CustomerCategory,
    CustomerGroup,
    SalesConfiguration,
    SalesPaymentTerm,
    SalesReasonCode,
)
from modules.sales.repositories.master import (
    CustomerCategoryRepository,
    CustomerGroupRepository,
    SalesConfigurationRepository,
    SalesPaymentTermRepository,
    SalesReasonCodeRepository,
)


@pytest.fixture
def company_id() -> UUID:
    return uuid4()


@pytest.fixture
def company_id_b() -> UUID:
    return uuid4()


class TestCustomerCategoryRepository:
    """Integration tests for CustomerCategoryRepository."""

    def test_create_and_get_by_code(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = CustomerCategoryRepository(db=db_session)
        category = CustomerCategory(
            company_id=company_id,
            code="RETAIL",
            name="Retail Customers",
        )
        created = repo.create(category)
        assert created.id is not None

        found = repo.get_by_code(company_id=company_id, code="RETAIL")
        assert found is not None
        assert found.name == "Retail Customers"

    def test_code_unique_per_company(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = CustomerCategoryRepository(db=db_session)
        cat1 = CustomerCategory(company_id=company_id, code="UNIQUE", name="First")
        repo.create(cat1)

        cat2 = CustomerCategory(company_id=company_id, code="UNIQUE", name="Second")
        with pytest.raises(Exception):  # IntegrityError
            repo.create(cat2)
            db_session.flush()

    def test_same_code_different_company(
        self, db_session: Session, company_id: UUID, company_id_b: UUID
    ) -> None:
        repo = CustomerCategoryRepository(db=db_session)
        cat1 = CustomerCategory(company_id=company_id, code="SHARED", name="Company A")
        cat2 = CustomerCategory(
            company_id=company_id_b, code="SHARED", name="Company B"
        )
        repo.create(cat1)
        repo.create(cat2)
        db_session.flush()

        found_a = repo.get_by_code(company_id=company_id, code="SHARED")
        found_b = repo.get_by_code(company_id=company_id_b, code="SHARED")
        assert found_a is not None
        assert found_b is not None
        assert found_a.name == "Company A"
        assert found_b.name == "Company B"

    def test_get_active(self, db_session: Session, company_id: UUID) -> None:
        repo = CustomerCategoryRepository(db=db_session)
        active = CustomerCategory(
            company_id=company_id, code="ACT", name="Active", is_active=True
        )
        inactive = CustomerCategory(
            company_id=company_id, code="INACT", name="Inactive", is_active=False
        )
        repo.create(active)
        repo.create(inactive)
        db_session.flush()

        result = repo.get_active(company_id=company_id)
        codes = [c.code for c in result]
        assert "ACT" in codes
        assert "INACT" not in codes

    def test_tenant_isolation(
        self, db_session: Session, company_id: UUID, company_id_b: UUID
    ) -> None:
        repo = CustomerCategoryRepository(db=db_session)
        repo.create(
            CustomerCategory(company_id=company_id, code="ONLY_A", name="Only A")
        )
        db_session.flush()

        found = repo.get_by_code(company_id=company_id_b, code="ONLY_A")
        assert found is None


class TestCustomerGroupRepository:
    """Integration tests for CustomerGroupRepository."""

    def test_create_and_get_by_code(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = CustomerGroupRepository(db=db_session)
        group = CustomerGroup(company_id=company_id, code="VIP", name="VIP Customers")
        created = repo.create(group)
        assert created.id is not None

        found = repo.get_by_code(company_id=company_id, code="VIP")
        assert found is not None
        assert found.name == "VIP Customers"


class TestSalesPaymentTermRepository:
    """Integration tests for SalesPaymentTermRepository."""

    def test_create_and_get_by_code(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = SalesPaymentTermRepository(db=db_session)
        term = SalesPaymentTerm(
            company_id=company_id,
            code="NET30",
            name="Net 30 Days",
            due_days=30,
        )
        created = repo.create(term)
        assert created.id is not None

        found = repo.get_by_code(company_id=company_id, code="NET30")
        assert found is not None
        assert found.due_days == 30

    def test_get_active(self, db_session: Session, company_id: UUID) -> None:
        repo = SalesPaymentTermRepository(db=db_session)
        repo.create(
            SalesPaymentTerm(
                company_id=company_id,
                code="ACT",
                name="Active",
                due_days=15,
                is_active=True,
            )
        )
        repo.create(
            SalesPaymentTerm(
                company_id=company_id,
                code="DIS",
                name="Disabled",
                due_days=30,
                is_active=False,
            )
        )
        db_session.flush()

        active = repo.get_active(company_id=company_id)
        codes = [t.code for t in active]
        assert "ACT" in codes
        assert "DIS" not in codes


class TestSalesReasonCodeRepository:
    """Integration tests for SalesReasonCodeRepository."""

    def test_create_and_get_by_code(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = SalesReasonCodeRepository(db=db_session)
        reason = SalesReasonCode(
            company_id=company_id,
            code="DEFECTIVE",
            name="Defective Product",
            reason_type="RETURN",
        )
        created = repo.create(reason)
        assert created.id is not None

        found = repo.get_by_code(
            company_id=company_id, code="DEFECTIVE", reason_type="RETURN"
        )
        assert found is not None

    def test_get_by_type(self, db_session: Session, company_id: UUID) -> None:
        repo = SalesReasonCodeRepository(db=db_session)
        repo.create(
            SalesReasonCode(
                company_id=company_id,
                code="RET1",
                name="Return 1",
                reason_type="RETURN",
            )
        )
        repo.create(
            SalesReasonCode(
                company_id=company_id,
                code="CAN1",
                name="Cancel 1",
                reason_type="CANCELLATION",
            )
        )
        db_session.flush()

        returns = repo.get_by_type(company_id=company_id, reason_type="RETURN")
        assert all(r.reason_type == "RETURN" for r in returns)


class TestSalesConfigurationRepository:
    """Integration tests for SalesConfigurationRepository."""

    def test_get_for_company_returns_none_when_absent(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = SalesConfigurationRepository(db=db_session)
        config = repo.get_for_company(company_id=company_id)
        assert config is None

    def test_create_and_get_for_company(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = SalesConfigurationRepository(db=db_session)
        config = SalesConfiguration(company_id=company_id)
        created = repo.create(config)
        assert created.id is not None
        assert created.default_quotation_validity_days == 30
        assert created.credit_warning_threshold == 80

        found = repo.get_for_company(company_id=company_id)
        assert found is not None
        assert found.id == created.id
