"""Integration tests for WarehouseRepository and WarehouseLocationRepository.

Tests:
  - Warehouse CRUD with company_id scoping
  - get_by_code, list_for_company (with status filter)
  - has_stock stub (always False in Phase 4)
  - WarehouseLocation CRUD, get_by_code, list_for_warehouse
  - Tenant isolation (Company A cannot see Company B warehouses)

Spec ref: specs/005-inventory-management/spec.md §16
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from modules.inventory.models.warehouse import Warehouse, WarehouseLocation
from modules.inventory.repositories.warehouse_repository import (
    WarehouseLocationRepository,
    WarehouseRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_warehouse(
    db: Session,
    company_id: uuid.UUID,
    code: str | None = None,
    warehouse_type: str = "MAIN",
    status: str = "ACTIVE",
) -> Warehouse:
    wh = Warehouse(
        company_id=company_id,
        code=code or f"WH-{uuid.uuid4().hex[:4].upper()}",
        name="Test Warehouse",
        warehouse_type=warehouse_type,
        status=status,
    )
    db.add(wh)
    db.flush()
    return wh


def _make_location(
    db: Session,
    company_id: uuid.UUID,
    warehouse: Warehouse,
    code: str | None = None,
    is_active: bool = True,
) -> WarehouseLocation:
    loc = WarehouseLocation(
        company_id=company_id,
        warehouse_id=str(warehouse.id),
        location_code=code or f"LOC-{uuid.uuid4().hex[:4].upper()}",
        aisle="A",
        zone="Zone1",
        shelf="Top",
        is_active=is_active,
    )
    db.add(loc)
    db.flush()
    return loc


# ---------------------------------------------------------------------------
# WarehouseRepository tests
# ---------------------------------------------------------------------------


class TestWarehouseRepository:
    def test_create_and_get_by_id(self, db_session: Session):
        cid = uuid.uuid4()
        repo = WarehouseRepository(db_session)
        wh = _make_warehouse(db_session, cid)

        fetched = repo.get_by_id(wh.id, cid)
        assert fetched is not None
        assert fetched.code == wh.code
        assert str(fetched.company_id) == str(cid)

    def test_get_by_code(self, db_session: Session):
        cid = uuid.uuid4()
        repo = WarehouseRepository(db_session)
        wh = _make_warehouse(db_session, cid, code="WH-FIND")

        found = repo.get_by_code(company_id=cid, code="WH-FIND")
        assert found is not None
        assert str(found.id) == str(wh.id)

    def test_get_by_code_returns_none_for_other_company(self, db_session: Session):
        cid1 = uuid.uuid4()
        cid2 = uuid.uuid4()
        repo = WarehouseRepository(db_session)
        _make_warehouse(db_session, cid1, code="WH-CROSS")

        found = repo.get_by_code(company_id=cid2, code="WH-CROSS")
        assert found is None

    def test_list_for_company_returns_all(self, db_session: Session):
        cid = uuid.uuid4()
        repo = WarehouseRepository(db_session)
        _make_warehouse(db_session, cid, code="WH-A", status="ACTIVE")
        _make_warehouse(db_session, cid, code="WH-B", status="INACTIVE")

        result = repo.list_for_company(cid)
        codes = {w.code for w in result}
        assert "WH-A" in codes
        assert "WH-B" in codes

    def test_list_for_company_filter_by_status(self, db_session: Session):
        cid = uuid.uuid4()
        repo = WarehouseRepository(db_session)
        _make_warehouse(db_session, cid, code="WH-ACT", status="ACTIVE")
        _make_warehouse(db_session, cid, code="WH-INA", status="INACTIVE")

        active = repo.list_for_company(cid, status="ACTIVE")
        codes = {w.code for w in active}
        assert "WH-ACT" in codes
        assert "WH-INA" not in codes

    def test_list_for_company_isolation(self, db_session: Session):
        cid1 = uuid.uuid4()
        cid2 = uuid.uuid4()
        repo = WarehouseRepository(db_session)
        wh1 = _make_warehouse(db_session, cid1, code="WH-C1")
        wh2 = _make_warehouse(db_session, cid2, code="WH-C2")

        result = repo.list_for_company(cid1)
        ids = {str(w.id) for w in result}
        assert str(wh1.id) in ids
        assert str(wh2.id) not in ids

    def test_soft_delete_excludes_from_list(self, db_session: Session):
        cid = uuid.uuid4()
        repo = WarehouseRepository(db_session)
        wh = _make_warehouse(db_session, cid, code="WH-DEL")
        wh.is_deleted = True
        db_session.flush()

        result = repo.list_for_company(cid)
        ids = {str(w.id) for w in result}
        assert str(wh.id) not in ids

    def test_has_stock_returns_false_stub(self, db_session: Session):
        cid = uuid.uuid4()
        repo = WarehouseRepository(db_session)
        wh = _make_warehouse(db_session, cid)

        # Phase 4 stub: always False
        assert repo.has_stock(company_id=cid, warehouse_id=wh.id) is False


# ---------------------------------------------------------------------------
# WarehouseLocationRepository tests
# ---------------------------------------------------------------------------


class TestWarehouseLocationRepository:
    def test_create_and_list(self, db_session: Session):
        cid = uuid.uuid4()
        loc_repo = WarehouseLocationRepository(db_session)
        wh = _make_warehouse(db_session, cid)

        _make_location(db_session, cid, wh, code="A-01")
        locations = loc_repo.list_for_warehouse(cid, wh.id)
        codes = {loc.location_code for loc in locations}
        assert "A-01" in codes

    def test_get_by_code(self, db_session: Session):
        cid = uuid.uuid4()
        loc_repo = WarehouseLocationRepository(db_session)
        wh = _make_warehouse(db_session, cid)
        _make_location(db_session, cid, wh, code="B-02")

        found = loc_repo.get_by_code(
            company_id=cid, warehouse_id=wh.id, location_code="B-02"
        )
        assert found is not None
        assert found.location_code == "B-02"

    def test_get_by_code_wrong_warehouse_returns_none(self, db_session: Session):
        cid = uuid.uuid4()
        loc_repo = WarehouseLocationRepository(db_session)
        wh1 = _make_warehouse(db_session, cid, code="WH-X")
        wh2 = _make_warehouse(db_session, cid, code="WH-Y")
        _make_location(db_session, cid, wh1, code="C-03")

        found = loc_repo.get_by_code(
            company_id=cid, warehouse_id=wh2.id, location_code="C-03"
        )
        assert found is None

    def test_active_only_filter(self, db_session: Session):
        cid = uuid.uuid4()
        loc_repo = WarehouseLocationRepository(db_session)
        wh = _make_warehouse(db_session, cid)
        _make_location(db_session, cid, wh, code="D-ACT", is_active=True)
        _make_location(db_session, cid, wh, code="D-INA", is_active=False)

        all_locs = loc_repo.list_for_warehouse(cid, wh.id)
        active_only = loc_repo.list_for_warehouse(cid, wh.id, active_only=True)

        all_codes = {loc.location_code for loc in all_locs}
        active_codes = {loc.location_code for loc in active_only}
        assert "D-ACT" in all_codes
        assert "D-INA" in all_codes
        assert "D-ACT" in active_codes
        assert "D-INA" not in active_codes

    def test_company_isolation(self, db_session: Session):
        cid1 = uuid.uuid4()
        cid2 = uuid.uuid4()
        loc_repo = WarehouseLocationRepository(db_session)
        wh1 = _make_warehouse(db_session, cid1)
        wh2 = _make_warehouse(db_session, cid2)
        _make_location(db_session, cid1, wh1, code="E-01")
        _make_location(db_session, cid2, wh2, code="E-02")

        locs_c1 = loc_repo.list_for_warehouse(cid1, wh1.id)
        codes = {loc.location_code for loc in locs_c1}
        assert "E-01" in codes
        assert "E-02" not in codes
