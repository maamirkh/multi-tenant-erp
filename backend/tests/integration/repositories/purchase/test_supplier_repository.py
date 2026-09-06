"""Integration tests for Supplier-aggregate repositories — Phase 1.

Tests:
  - SupplierRepository: CRUD, get_by_code, search (ILIKE), status filter,
    category filter, preferred filter, pagination, count_by_status,
    soft-delete exclusion, tenant isolation
  - SupplierContactRepository: CRUD, get_for_supplier, get_primary,
    clear_primary, tenant isolation
  - SupplierAddressRepository: CRUD, get_for_supplier, get_default,
    clear_default, tenant isolation

Pattern: uses db.add()+db.flush() for test data setup (matching inventory repo test
conventions), then tests repository query methods independently.

All tests run against SQLite in-memory DB (FTS falls back to ILIKE).

Task: T051
Spec ref: specs/006-purchase-management/data-model.md §Supplier Aggregate
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.purchase.models.supplier import Supplier, SupplierAddress, SupplierContact
from modules.purchase.repositories.supplier import (
    SupplierAddressRepository,
    SupplierContactRepository,
    SupplierRepository,
)

# ---------------------------------------------------------------------------
# Helpers — use db.add() + db.flush() pattern (same as inventory tests)
# ---------------------------------------------------------------------------


def _add_supplier(
    db: Session,
    company_id: UUID,
    *,
    code: str = "SUP-001",
    legal_name: str = "Acme Corp",
    status: str = "DRAFT",
    supplier_type: str = "GOODS",
    is_preferred: bool = False,
    category_id: UUID | None = None,
) -> Supplier:
    s = Supplier(
        company_id=company_id,
        supplier_code=code,
        legal_name=legal_name,
        supplier_type=supplier_type,
        status=status,
        is_preferred=is_preferred,
        currency_code="USD",
    )
    if category_id:
        s.category_id = str(category_id)
    db.add(s)
    db.flush()
    return s


def _add_contact(
    db: Session,
    company_id: UUID,
    supplier_id: UUID,
    *,
    first_name: str = "John",
    last_name: str = "Doe",
    is_primary: bool = False,
) -> SupplierContact:
    c = SupplierContact(
        company_id=company_id,
        supplier_id=str(supplier_id),
        first_name=first_name,
        last_name=last_name,
        is_primary=is_primary,
    )
    db.add(c)
    db.flush()
    return c


def _add_address(
    db: Session,
    company_id: UUID,
    supplier_id: UUID,
    *,
    address_type: str = "BILLING",
    city: str = "New York",
    is_default: bool = False,
) -> SupplierAddress:
    a = SupplierAddress(
        company_id=company_id,
        supplier_id=str(supplier_id),
        address_type=address_type,
        address_line_1="123 Main St",
        city=city,
        country_code="US",
        is_default=is_default,
    )
    db.add(a)
    db.flush()
    return a


# ---------------------------------------------------------------------------
# SupplierRepository — get_by_code
# ---------------------------------------------------------------------------


class TestSupplierRepositoryGetByCode:
    def test_get_by_code_found(self, db_session: Session) -> None:
        cid = uuid4()
        _add_supplier(db_session, cid, code="SUP-001")
        repo = SupplierRepository(db_session)

        result = repo.get_by_code(cid, "SUP-001")
        assert result is not None
        assert result.supplier_code == "SUP-001"

    def test_get_by_code_wrong_company_returns_none(self, db_session: Session) -> None:
        cid_a = uuid4()
        cid_b = uuid4()
        _add_supplier(db_session, cid_a, code="SUP-001")
        repo = SupplierRepository(db_session)

        result = repo.get_by_code(cid_b, "SUP-001")
        assert result is None

    def test_get_by_code_case_insensitive(self, db_session: Session) -> None:
        """supplier_code is uppercased on storage; lookup by lower also works."""
        cid = uuid4()
        _add_supplier(db_session, cid, code="SUP-ABC")
        repo = SupplierRepository(db_session)

        # get_by_code uppercases the lookup key
        result = repo.get_by_code(cid, "sup-abc")
        assert result is not None
        assert result.supplier_code == "SUP-ABC"

    def test_get_by_code_after_soft_delete_returns_none(
        self, db_session: Session
    ) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid, code="SUP-DEL")
        supplier.is_deleted = True
        db_session.flush()

        repo = SupplierRepository(db_session)
        result = repo.get_by_code(cid, "SUP-DEL")
        assert result is None


# ---------------------------------------------------------------------------
# SupplierRepository — get_active
# ---------------------------------------------------------------------------


class TestSupplierRepositoryGetActive:
    def test_only_active_returned(self, db_session: Session) -> None:
        cid = uuid4()
        _add_supplier(db_session, cid, code="S1", status="ACTIVE", legal_name="Alpha")
        _add_supplier(db_session, cid, code="S2", status="DRAFT", legal_name="Beta")
        _add_supplier(db_session, cid, code="S3", status="INACTIVE", legal_name="Gamma")
        repo = SupplierRepository(db_session)

        active = repo.get_active(cid)
        codes = {s.supplier_code for s in active}
        assert "S1" in codes
        assert "S2" not in codes
        assert "S3" not in codes

    def test_active_from_other_company_excluded(self, db_session: Session) -> None:
        cid_a = uuid4()
        cid_b = uuid4()
        _add_supplier(db_session, cid_a, code="S1", status="ACTIVE", legal_name="Alpha")
        _add_supplier(db_session, cid_b, code="S1", status="ACTIVE", legal_name="Beta")
        repo = SupplierRepository(db_session)

        active_a = repo.get_active(cid_a)
        assert len(active_a) == 1
        assert active_a[0].legal_name == "Alpha"

    def test_empty_company_returns_empty_list(self, db_session: Session) -> None:
        cid = uuid4()
        repo = SupplierRepository(db_session)
        assert repo.get_active(cid) == []


# ---------------------------------------------------------------------------
# SupplierRepository — search (ILIKE in SQLite)
# ---------------------------------------------------------------------------


class TestSupplierRepositorySearch:
    def test_search_by_legal_name(self, db_session: Session) -> None:
        cid = uuid4()
        _add_supplier(db_session, cid, code="S1", legal_name="Acme Corporation")
        _add_supplier(db_session, cid, code="S2", legal_name="Beta Supplies")
        repo = SupplierRepository(db_session)

        items, total = repo.search(cid, query="acme")
        assert total == 1
        assert items[0].supplier_code == "S1"

    def test_search_by_supplier_code(self, db_session: Session) -> None:
        cid = uuid4()
        _add_supplier(db_session, cid, code="VENDOR-99", legal_name="Some Co")
        _add_supplier(db_session, cid, code="VENDOR-01", legal_name="Other Co")
        repo = SupplierRepository(db_session)

        items, total = repo.search(cid, query="VENDOR-99")
        assert total == 1
        assert items[0].legal_name == "Some Co"

    def test_search_no_query_returns_all(self, db_session: Session) -> None:
        cid = uuid4()
        _add_supplier(db_session, cid, code="S1", legal_name="Alpha")
        _add_supplier(db_session, cid, code="S2", legal_name="Beta")
        _add_supplier(db_session, cid, code="S3", legal_name="Gamma")
        repo = SupplierRepository(db_session)

        items, total = repo.search(cid)
        assert total == 3
        assert len(items) == 3

    def test_search_status_filter(self, db_session: Session) -> None:
        cid = uuid4()
        _add_supplier(db_session, cid, code="S1", status="ACTIVE", legal_name="Alpha")
        _add_supplier(db_session, cid, code="S2", status="DRAFT", legal_name="Beta")
        _add_supplier(db_session, cid, code="S3", status="ACTIVE", legal_name="Gamma")
        repo = SupplierRepository(db_session)

        items, total = repo.search(cid, status="ACTIVE")
        assert total == 2
        assert all(s.status == "ACTIVE" for s in items)

    def test_search_category_filter(self, db_session: Session) -> None:
        cid = uuid4()
        cat_id = uuid4()
        _add_supplier(
            db_session, cid, code="S1", legal_name="Alpha", category_id=cat_id
        )
        _add_supplier(db_session, cid, code="S2", legal_name="Beta")
        repo = SupplierRepository(db_session)

        items, total = repo.search(cid, category_id=cat_id)
        assert total == 1
        assert items[0].supplier_code == "S1"

    def test_search_preferred_filter(self, db_session: Session) -> None:
        cid = uuid4()
        _add_supplier(
            db_session, cid, code="S1", legal_name="Preferred", is_preferred=True
        )
        _add_supplier(
            db_session, cid, code="S2", legal_name="Normal", is_preferred=False
        )
        repo = SupplierRepository(db_session)

        items, total = repo.search(cid, is_preferred=True)
        assert total == 1
        assert items[0].supplier_code == "S1"

    def test_search_pagination(self, db_session: Session) -> None:
        cid = uuid4()
        for i in range(5):
            _add_supplier(
                db_session, cid, code=f"S{i:03d}", legal_name=f"Supplier {i:03d}"
            )
        repo = SupplierRepository(db_session)

        page1, total = repo.search(cid, skip=0, limit=3)
        page2, _ = repo.search(cid, skip=3, limit=3)

        assert total == 5
        assert len(page1) == 3
        assert len(page2) == 2
        codes1 = {s.supplier_code for s in page1}
        codes2 = {s.supplier_code for s in page2}
        assert codes1.isdisjoint(codes2)

    def test_search_excludes_soft_deleted(self, db_session: Session) -> None:
        cid = uuid4()
        s = _add_supplier(db_session, cid, code="DELETED", legal_name="DeletedCo")
        _add_supplier(db_session, cid, code="ALIVE", legal_name="AliveCo")
        s.is_deleted = True
        db_session.flush()
        repo = SupplierRepository(db_session)

        items, total = repo.search(cid)
        assert total == 1
        assert items[0].supplier_code == "ALIVE"

    def test_search_combined_query_and_status(self, db_session: Session) -> None:
        cid = uuid4()
        _add_supplier(
            db_session, cid, code="S1", legal_name="Acme Active", status="ACTIVE"
        )
        _add_supplier(
            db_session, cid, code="S2", legal_name="Acme Draft", status="DRAFT"
        )
        repo = SupplierRepository(db_session)

        items, total = repo.search(cid, query="acme", status="ACTIVE")
        assert total == 1
        assert items[0].supplier_code == "S1"

    def test_search_empty_results(self, db_session: Session) -> None:
        cid = uuid4()
        _add_supplier(db_session, cid, code="S1", legal_name="Acme Corp")
        repo = SupplierRepository(db_session)

        items, total = repo.search(cid, query="nonexistent_xyz_123")
        assert total == 0
        assert items == []


# ---------------------------------------------------------------------------
# SupplierRepository — tenant isolation
# ---------------------------------------------------------------------------


class TestSupplierRepositoryTenantIsolation:
    def test_company_a_cannot_see_company_b_suppliers(
        self, db_session: Session
    ) -> None:
        cid_a = uuid4()
        cid_b = uuid4()
        _add_supplier(db_session, cid_a, code="S-A", legal_name="Company A Supplier")
        _add_supplier(db_session, cid_b, code="S-B", legal_name="Company B Supplier")
        repo = SupplierRepository(db_session)

        items_a, total_a = repo.search(cid_a)
        items_b, total_b = repo.search(cid_b)

        assert total_a == 1
        assert total_b == 1
        assert items_a[0].supplier_code == "S-A"
        assert items_b[0].supplier_code == "S-B"

    def test_get_by_code_only_finds_own_company(self, db_session: Session) -> None:
        cid_a = uuid4()
        cid_b = uuid4()
        _add_supplier(db_session, cid_a, code="SHARED", legal_name="Company A")
        _add_supplier(db_session, cid_b, code="SHARED", legal_name="Company B")
        repo = SupplierRepository(db_session)

        # Same code exists in both companies; each company sees only their own
        result_a = repo.get_by_code(cid_a, "SHARED")
        result_b = repo.get_by_code(cid_b, "SHARED")

        assert result_a is not None
        assert result_b is not None
        assert result_a.legal_name == "Company A"
        assert result_b.legal_name == "Company B"


# ---------------------------------------------------------------------------
# SupplierRepository — count_by_status
# ---------------------------------------------------------------------------


class TestSupplierRepositoryCountByStatus:
    def test_count_by_status(self, db_session: Session) -> None:
        cid = uuid4()
        _add_supplier(db_session, cid, code="S1", status="ACTIVE", legal_name="A1")
        _add_supplier(db_session, cid, code="S2", status="ACTIVE", legal_name="A2")
        _add_supplier(db_session, cid, code="S3", status="DRAFT", legal_name="D1")
        repo = SupplierRepository(db_session)

        assert repo.count_by_status(cid, "ACTIVE") == 2
        assert repo.count_by_status(cid, "DRAFT") == 1
        assert repo.count_by_status(cid, "ARCHIVED") == 0

    def test_count_excludes_soft_deleted(self, db_session: Session) -> None:
        cid = uuid4()
        s = _add_supplier(
            db_session, cid, code="S1", status="ACTIVE", legal_name="ToDelete"
        )
        _add_supplier(db_session, cid, code="S2", status="ACTIVE", legal_name="Keep")
        s.is_deleted = True
        db_session.flush()
        repo = SupplierRepository(db_session)

        assert repo.count_by_status(cid, "ACTIVE") == 1

    def test_count_zero_for_nonexistent_company(self, db_session: Session) -> None:
        cid = uuid4()
        repo = SupplierRepository(db_session)
        assert repo.count_by_status(cid, "ACTIVE") == 0


# ---------------------------------------------------------------------------
# SupplierContactRepository
# ---------------------------------------------------------------------------


class TestSupplierContactRepository:
    def test_create_and_get_for_supplier(self, db_session: Session) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid)
        _add_contact(
            db_session, cid, supplier.id, first_name="Alice", last_name="Smith"
        )
        repo = SupplierContactRepository(db_session)

        contacts = repo.get_for_supplier(cid, supplier.id)
        assert len(contacts) == 1
        assert contacts[0].first_name == "Alice"

    def test_get_primary_contact(self, db_session: Session) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid)
        _add_contact(
            db_session,
            cid,
            supplier.id,
            first_name="Alice",
            last_name="Smith",
            is_primary=False,
        )
        _add_contact(
            db_session,
            cid,
            supplier.id,
            first_name="Bob",
            last_name="Jones",
            is_primary=True,
        )
        repo = SupplierContactRepository(db_session)

        result = repo.get_primary(cid, supplier.id)
        assert result is not None
        assert result.first_name == "Bob"

    def test_get_primary_when_none_returns_none(self, db_session: Session) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid)
        _add_contact(db_session, cid, supplier.id, is_primary=False)
        repo = SupplierContactRepository(db_session)

        assert repo.get_primary(cid, supplier.id) is None

    def test_clear_primary(self, db_session: Session) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid)
        _add_contact(
            db_session, cid, supplier.id, first_name="A", last_name="A", is_primary=True
        )
        _add_contact(
            db_session, cid, supplier.id, first_name="B", last_name="B", is_primary=True
        )
        repo = SupplierContactRepository(db_session)

        repo.clear_primary(cid, supplier.id)

        all_contacts = repo.get_for_supplier(cid, supplier.id)
        assert all(not c.is_primary for c in all_contacts)

    def test_get_for_supplier_excludes_soft_deleted(self, db_session: Session) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid)
        c1 = _add_contact(
            db_session, cid, supplier.id, first_name="Alice", last_name="A"
        )
        _add_contact(db_session, cid, supplier.id, first_name="Bob", last_name="B")
        c1.is_deleted = True
        db_session.flush()
        repo = SupplierContactRepository(db_session)

        contacts = repo.get_for_supplier(cid, supplier.id)
        assert len(contacts) == 1
        assert contacts[0].first_name == "Bob"

    def test_contacts_isolated_by_company(self, db_session: Session) -> None:
        cid_a = uuid4()
        cid_b = uuid4()
        sup_a = _add_supplier(db_session, cid_a, code="S1")
        sup_b = _add_supplier(db_session, cid_b, code="S1")
        _add_contact(db_session, cid_a, sup_a.id, first_name="Alpha")
        _add_contact(db_session, cid_b, sup_b.id, first_name="Beta")
        repo = SupplierContactRepository(db_session)

        contacts_a = repo.get_for_supplier(cid_a, sup_a.id)
        contacts_b = repo.get_for_supplier(cid_b, sup_b.id)

        assert len(contacts_a) == 1
        assert contacts_a[0].first_name == "Alpha"
        assert len(contacts_b) == 1
        assert contacts_b[0].first_name == "Beta"

    def test_multiple_contacts_ordered_primary_first(self, db_session: Session) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid)
        _add_contact(
            db_session,
            cid,
            supplier.id,
            first_name="Charlie",
            last_name="C",
            is_primary=False,
        )
        _add_contact(
            db_session,
            cid,
            supplier.id,
            first_name="Alice",
            last_name="A",
            is_primary=True,
        )
        repo = SupplierContactRepository(db_session)

        contacts = repo.get_for_supplier(cid, supplier.id)
        assert contacts[0].is_primary is True  # primary first


# ---------------------------------------------------------------------------
# SupplierAddressRepository
# ---------------------------------------------------------------------------


class TestSupplierAddressRepository:
    def test_create_and_get_for_supplier(self, db_session: Session) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid)
        _add_address(
            db_session, cid, supplier.id, address_type="BILLING", city="New York"
        )
        _add_address(
            db_session, cid, supplier.id, address_type="SHIPPING", city="Chicago"
        )
        repo = SupplierAddressRepository(db_session)

        addresses = repo.get_for_supplier(cid, supplier.id)
        assert len(addresses) == 2
        cities = {a.city for a in addresses}
        assert "New York" in cities
        assert "Chicago" in cities

    def test_get_default_address(self, db_session: Session) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid)
        _add_address(
            db_session,
            cid,
            supplier.id,
            address_type="BILLING",
            city="NY",
            is_default=False,
        )
        _add_address(
            db_session,
            cid,
            supplier.id,
            address_type="BILLING",
            city="LA",
            is_default=True,
        )
        repo = SupplierAddressRepository(db_session)

        default = repo.get_default(cid, supplier.id, "BILLING")
        assert default is not None
        assert default.city == "LA"

    def test_get_default_returns_none_when_unset(self, db_session: Session) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid)
        _add_address(
            db_session, cid, supplier.id, address_type="BILLING", is_default=False
        )
        repo = SupplierAddressRepository(db_session)

        assert repo.get_default(cid, supplier.id, "BILLING") is None

    def test_clear_default(self, db_session: Session) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid)
        _add_address(
            db_session,
            cid,
            supplier.id,
            address_type="BILLING",
            city="NY",
            is_default=True,
        )
        _add_address(
            db_session,
            cid,
            supplier.id,
            address_type="BILLING",
            city="LA",
            is_default=True,
        )
        repo = SupplierAddressRepository(db_session)

        repo.clear_default(cid, supplier.id, "BILLING")

        all_addrs = repo.get_for_supplier(cid, supplier.id)
        assert all(not a.is_default for a in all_addrs)

    def test_clear_default_only_affects_type(self, db_session: Session) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid)
        _add_address(
            db_session,
            cid,
            supplier.id,
            address_type="BILLING",
            city="NY",
            is_default=True,
        )
        _add_address(
            db_session,
            cid,
            supplier.id,
            address_type="SHIPPING",
            city="LA",
            is_default=True,
        )
        repo = SupplierAddressRepository(db_session)

        repo.clear_default(cid, supplier.id, "BILLING")

        shipping = repo.get_default(cid, supplier.id, "SHIPPING")
        assert shipping is not None  # SHIPPING default unchanged

    def test_get_for_supplier_excludes_soft_deleted(self, db_session: Session) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid)
        a1 = _add_address(db_session, cid, supplier.id, city="NY")
        _add_address(db_session, cid, supplier.id, city="LA")
        a1.is_deleted = True
        db_session.flush()
        repo = SupplierAddressRepository(db_session)

        addresses = repo.get_for_supplier(cid, supplier.id)
        assert len(addresses) == 1
        assert addresses[0].city == "LA"

    def test_addresses_isolated_by_company(self, db_session: Session) -> None:
        cid_a = uuid4()
        cid_b = uuid4()
        sup_a = _add_supplier(db_session, cid_a, code="S1")
        sup_b = _add_supplier(db_session, cid_b, code="S1")
        _add_address(db_session, cid_a, sup_a.id, city="Boston")
        _add_address(db_session, cid_b, sup_b.id, city="Austin")
        repo = SupplierAddressRepository(db_session)

        addrs_a = repo.get_for_supplier(cid_a, sup_a.id)
        addrs_b = repo.get_for_supplier(cid_b, sup_b.id)

        assert len(addrs_a) == 1
        assert addrs_a[0].city == "Boston"
        assert len(addrs_b) == 1
        assert addrs_b[0].city == "Austin"

    def test_no_addresses_returns_empty_list(self, db_session: Session) -> None:
        cid = uuid4()
        supplier = _add_supplier(db_session, cid)
        repo = SupplierAddressRepository(db_session)

        assert repo.get_for_supplier(cid, supplier.id) == []
