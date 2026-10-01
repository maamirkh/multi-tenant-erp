"""Integration tests for CompanyAddressRepository.

Verifies CRUD operations and tenant isolation (every query scoped to company_id).
Uses the shared ``db_session`` fixture (SQLite in-memory with rollback isolation).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from modules.companies.models.company import Company
from modules.companies.models.enums import AddressType
from modules.companies.repositories.company_address_repository import (
    CompanyAddressRepository,
)
from modules.companies.repositories.company_repository import CompanyRepository
from tests.fixtures.company_fixtures import make_address_data, make_company_data

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _company_repo(db: Session) -> CompanyRepository:
    return CompanyRepository(db)


def _addr_repo(db: Session) -> CompanyAddressRepository:
    return CompanyAddressRepository(db)


def _create_company(db: Session, **overrides: Any) -> Company:
    return _company_repo(db).create(make_company_data(**overrides))


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    def test_creates_address_under_company(self, db_session: Session) -> None:
        company = _create_company(db_session, legal_name="Addr Test Corp")
        data = make_address_data()
        address = _addr_repo(db_session).create(company.id, data)
        assert address.id is not None
        assert address.company_id == company.id
        assert address.street_line_1 == "123 Business Ave"
        assert address.is_primary is True

    def test_multiple_addresses_per_company(self, db_session: Session) -> None:
        company = _create_company(db_session)
        _addr_repo(db_session).create(
            company.id, make_address_data(address_type="registered")
        )
        _addr_repo(db_session).create(
            company.id, make_address_data(address_type="mailing", is_primary=False)
        )
        addresses = _addr_repo(db_session).list_by_company(company.id)
        assert len(addresses) == 2


# ---------------------------------------------------------------------------
# get_by_id (tenant-scoped)
# ---------------------------------------------------------------------------


class TestGetById:
    def test_returns_address_for_correct_company(self, db_session: Session) -> None:
        company = _create_company(db_session)
        address = _addr_repo(db_session).create(company.id, make_address_data())
        found = _addr_repo(db_session).get_by_id(address.id, company.id)
        assert found is not None
        assert found.id == address.id

    def test_returns_none_for_wrong_company(self, db_session: Session) -> None:
        """Tenant isolation: address is not accessible via a different company_id."""
        company_a = _create_company(db_session, legal_name="Company A")
        company_b = _create_company(db_session, legal_name="Company B")
        address = _addr_repo(db_session).create(company_a.id, make_address_data())

        result = _addr_repo(db_session).get_by_id(address.id, company_b.id)
        assert result is None

    def test_returns_none_for_unknown_id(self, db_session: Session) -> None:
        company = _create_company(db_session)
        result = _addr_repo(db_session).get_by_id(uuid.uuid4(), company.id)
        assert result is None


# ---------------------------------------------------------------------------
# list_by_company
# ---------------------------------------------------------------------------


class TestListByCompany:
    def test_returns_only_company_addresses(self, db_session: Session) -> None:
        company_a = _create_company(db_session, legal_name="List Corp A")
        company_b = _create_company(db_session, legal_name="List Corp B")
        addr_a = _addr_repo(db_session).create(company_a.id, make_address_data())
        _addr_repo(db_session).create(company_b.id, make_address_data())

        results = _addr_repo(db_session).list_by_company(company_a.id)
        assert len(results) == 1
        assert results[0].id == addr_a.id

    def test_returns_empty_for_company_with_no_addresses(
        self, db_session: Session
    ) -> None:
        company = _create_company(db_session)
        results = _addr_repo(db_session).list_by_company(company.id)
        assert results == []


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class TestUpdate:
    def test_updates_address_fields(self, db_session: Session) -> None:
        company = _create_company(db_session)
        address = _addr_repo(db_session).create(company.id, make_address_data())
        updated = _addr_repo(db_session).update(
            address, {"city": "New York", "postal_code": "10001"}
        )
        assert updated.city == "New York"
        assert updated.postal_code == "10001"


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDelete:
    def test_deletes_address(self, db_session: Session) -> None:
        company = _create_company(db_session)
        address = _addr_repo(db_session).create(company.id, make_address_data())
        address_id = address.id
        _addr_repo(db_session).delete(address)
        result = _addr_repo(db_session).get_by_id(address_id, company.id)
        assert result is None


# ---------------------------------------------------------------------------
# get_primary_by_type
# ---------------------------------------------------------------------------


class TestGetPrimaryByType:
    def test_returns_primary_address(self, db_session: Session) -> None:
        company = _create_company(db_session)
        _addr_repo(db_session).create(
            company.id, make_address_data(address_type="registered", is_primary=True)
        )
        primary = _addr_repo(db_session).get_primary_by_type(
            company.id, AddressType.registered
        )
        assert primary is not None
        assert primary.is_primary is True

    def test_returns_none_when_no_primary(self, db_session: Session) -> None:
        company = _create_company(db_session)
        _addr_repo(db_session).create(
            company.id, make_address_data(address_type="mailing", is_primary=False)
        )
        result = _addr_repo(db_session).get_primary_by_type(
            company.id, AddressType.mailing
        )
        assert result is None
