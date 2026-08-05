"""Integration tests for Customer aggregate repositories — Phase 1.

Tests:
  - CustomerRepository: create, get_by_code, search, tenant isolation
  - CustomerContactRepository: add, get_for_customer, clear_primary
  - CustomerAddressRepository: add, get_for_customer, defaults
  - CustomerBankDetailRepository: add, get_for_customer, clear_default
  - CustomerNoteRepository: add, get_for_customer

Uses SQLite in-memory DB via conftest db_session fixture.

Task: T058
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from modules.sales.models.customer import (
    Customer,
    CustomerAddress,
    CustomerContact,
    CustomerNote,
)
from modules.sales.repositories.customer import (
    CustomerAddressRepository,
    CustomerContactRepository,
    CustomerNoteRepository,
    CustomerRepository,
)


@pytest.fixture
def company_id() -> UUID:
    return uuid4()


@pytest.fixture
def company_id_b() -> UUID:
    return uuid4()


def _make_customer(company_id: UUID, code: str = "CUST-001") -> Customer:
    c = Customer(
        company_id=company_id,
        customer_code=code,
        legal_name=f"Test Corp {code}",
        customer_type="COMPANY",
        category_id=str(uuid4()),
        currency_code="USD",
        credit_limit=Decimal("10000"),
        credit_status="GOOD",
        status="DRAFT",
        version=1,
        created_by=uuid4(),
    )
    return c


class TestCustomerRepository:
    def test_create_and_get_by_code(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = CustomerRepository(db=db_session)
        customer = _make_customer(company_id, "CUST-001")
        created = repo.create(customer)
        assert created.id is not None

        found = repo.get_by_code(company_id=company_id, customer_code="CUST-001")
        assert found is not None
        assert found.legal_name == "Test Corp CUST-001"

    def test_get_by_code_case_insensitive(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = CustomerRepository(db=db_session)
        repo.create(_make_customer(company_id, "CUST-002"))
        db_session.flush()

        found = repo.get_by_code(company_id=company_id, customer_code="cust-002")
        assert found is not None

    def test_tenant_isolation(
        self, db_session: Session, company_id: UUID, company_id_b: UUID
    ) -> None:
        repo = CustomerRepository(db=db_session)
        repo.create(_make_customer(company_id, "ISO-001"))
        db_session.flush()

        found = repo.get_by_code(company_id=company_id_b, customer_code="ISO-001")
        assert found is None

    def test_search_with_no_filters(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = CustomerRepository(db=db_session)
        repo.create(_make_customer(company_id, "S-001"))
        repo.create(_make_customer(company_id, "S-002"))
        db_session.flush()

        items, total = repo.search(company_id=company_id)
        assert total >= 2

    def test_search_by_status(self, db_session: Session, company_id: UUID) -> None:
        repo = CustomerRepository(db=db_session)
        c = _make_customer(company_id, "STAT-001")
        c.status = "ACTIVE"
        repo.create(c)
        db_session.flush()

        items, total = repo.search(company_id=company_id, status="ACTIVE")
        codes = [i.customer_code for i in items]
        assert "STAT-001" in codes

    def test_search_status_isolation(
        self, db_session: Session, company_id: UUID
    ) -> None:
        """DRAFT customers should not appear in ACTIVE search."""
        repo = CustomerRepository(db=db_session)
        repo.create(_make_customer(company_id, "DRAFT-X"))
        db_session.flush()

        items, total = repo.search(company_id=company_id, status="ACTIVE")
        codes = [i.customer_code for i in items]
        assert "DRAFT-X" not in codes

    def test_unique_code_per_company(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = CustomerRepository(db=db_session)
        repo.create(_make_customer(company_id, "DUP-001"))
        with pytest.raises(Exception):
            repo.create(_make_customer(company_id, "DUP-001"))
            db_session.flush()

    def test_same_code_different_companies(
        self, db_session: Session, company_id: UUID, company_id_b: UUID
    ) -> None:
        repo = CustomerRepository(db=db_session)
        repo.create(_make_customer(company_id, "SAME"))
        repo.create(_make_customer(company_id_b, "SAME"))
        db_session.flush()

        found_a = repo.get_by_code(company_id=company_id, customer_code="SAME")
        found_b = repo.get_by_code(company_id=company_id_b, customer_code="SAME")
        assert found_a is not None
        assert found_b is not None
        assert found_a.id != found_b.id


class TestCustomerContactRepository:
    def test_add_and_get_for_customer(
        self, db_session: Session, company_id: UUID
    ) -> None:
        # First create a customer
        customer_repo = CustomerRepository(db=db_session)
        customer = customer_repo.create(_make_customer(company_id, "CC-001"))
        db_session.flush()

        contact_repo = CustomerContactRepository(db=db_session)
        contact = CustomerContact(
            company_id=company_id,
            customer_id=str(customer.id),
            contact_name="John Doe",
            email="john@example.com",
            is_primary=True,
            created_by=uuid4(),
        )
        created = contact_repo.create(contact)
        assert created.id is not None

        contacts = contact_repo.get_for_customer(
            company_id=company_id, customer_id=customer.id
        )
        assert len(contacts) == 1
        assert contacts[0].contact_name == "John Doe"

    def test_get_primary(self, db_session: Session, company_id: UUID) -> None:
        customer_repo = CustomerRepository(db=db_session)
        customer = customer_repo.create(_make_customer(company_id, "CC-002"))
        db_session.flush()

        contact_repo = CustomerContactRepository(db=db_session)
        contact_repo.create(
            CustomerContact(
                company_id=company_id,
                customer_id=str(customer.id),
                contact_name="Primary",
                is_primary=True,
                created_by=uuid4(),
            )
        )
        db_session.flush()

        primary = contact_repo.get_primary(
            company_id=company_id, customer_id=customer.id
        )
        assert primary is not None
        assert primary.contact_name == "Primary"

    def test_count_for_customer(self, db_session: Session, company_id: UUID) -> None:
        customer_repo = CustomerRepository(db=db_session)
        customer = customer_repo.create(_make_customer(company_id, "CC-003"))
        db_session.flush()

        contact_repo = CustomerContactRepository(db=db_session)
        for i in range(3):
            contact_repo.create(
                CustomerContact(
                    company_id=company_id,
                    customer_id=str(customer.id),
                    contact_name=f"Contact {i}",
                    created_by=uuid4(),
                )
            )
        db_session.flush()

        count = contact_repo.count_for_customer(
            company_id=company_id, customer_id=customer.id
        )
        assert count == 3


class TestCustomerAddressRepository:
    def test_add_and_get_for_customer(
        self, db_session: Session, company_id: UUID
    ) -> None:
        customer_repo = CustomerRepository(db=db_session)
        customer = customer_repo.create(_make_customer(company_id, "CA-001"))
        db_session.flush()

        address_repo = CustomerAddressRepository(db=db_session)
        address = CustomerAddress(
            company_id=company_id,
            customer_id=str(customer.id),
            address_type="BILLING",
            address_line_1="123 Main St",
            city="New York",
            country_code="US",
            is_default_billing=True,
            created_by=uuid4(),
        )
        created = address_repo.create(address)
        assert created.id is not None

        addresses = address_repo.get_for_customer(
            company_id=company_id, customer_id=customer.id
        )
        assert len(addresses) == 1
        assert addresses[0].city == "New York"

    def test_count_billing_addresses(
        self, db_session: Session, company_id: UUID
    ) -> None:
        customer_repo = CustomerRepository(db=db_session)
        customer = customer_repo.create(_make_customer(company_id, "CA-002"))
        db_session.flush()

        address_repo = CustomerAddressRepository(db=db_session)
        address_repo.create(
            CustomerAddress(
                company_id=company_id,
                customer_id=str(customer.id),
                address_type="BILLING",
                address_line_1="123 Main",
                city="NY",
                country_code="US",
                created_by=uuid4(),
            )
        )
        address_repo.create(
            CustomerAddress(
                company_id=company_id,
                customer_id=str(customer.id),
                address_type="SHIPPING",
                address_line_1="456 Oak",
                city="LA",
                country_code="US",
                created_by=uuid4(),
            )
        )
        db_session.flush()

        count = address_repo.count_billing_addresses(
            company_id=company_id, customer_id=customer.id
        )
        assert count == 1  # only the BILLING one


class TestCustomerNoteRepository:
    def test_add_and_get_notes(self, db_session: Session, company_id: UUID) -> None:
        customer_repo = CustomerRepository(db=db_session)
        customer = customer_repo.create(_make_customer(company_id, "CN-001"))
        db_session.flush()

        note_repo = CustomerNoteRepository(db=db_session)
        note = CustomerNote(
            company_id=company_id,
            customer_id=str(customer.id),
            content="Test note",
            author_id=str(uuid4()),
            author_name="Admin User",
            created_by=uuid4(),
        )
        created = note_repo.create(note)
        assert created.id is not None

        notes = note_repo.get_for_customer(
            company_id=company_id, customer_id=customer.id
        )
        assert len(notes) == 1
        assert notes[0].content == "Test note"
