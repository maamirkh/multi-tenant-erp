"""Unit tests for Warehouse and WarehouseLocation ORM models.

Tests:
  - Table name and column presence
  - Status and type CHECK constraints (via table_args inspection)
  - UniqueConstraint naming
  - Model instantiation
  - WarehouseService state machine logic (pure, no DB)

Spec ref: specs/005-inventory-management/spec.md §16
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint

from modules.inventory.models.warehouse import Warehouse, WarehouseLocation
from modules.inventory.services.warehouse_service import (
    _VALID_STATUS_TRANSITIONS,
    InvalidWarehouseStateTransitionError,
    WarehouseHasStockError,
    WarehouseService,
)

# =============================================================================
# Warehouse model tests
# =============================================================================


class TestWarehouseModel:
    """ORM model structural tests for Warehouse."""

    def test_tablename(self):
        assert Warehouse.__tablename__ == "inventory_warehouses"

    def test_has_code_column(self):
        assert hasattr(Warehouse, "code")

    def test_has_name_column(self):
        assert hasattr(Warehouse, "name")

    def test_has_warehouse_type_column(self):
        assert hasattr(Warehouse, "warehouse_type")

    def test_has_status_column(self):
        assert hasattr(Warehouse, "status")

    def test_has_branch_id_nullable(self):
        col = Warehouse.__table__.c.get("branch_id")
        assert col is not None
        assert col.nullable is True

    def test_has_address_columns(self):
        for col_name in ("address_line1", "city", "country_code", "postal_code"):
            assert hasattr(Warehouse, col_name)

    def test_has_phone_and_notes(self):
        assert hasattr(Warehouse, "phone")
        assert hasattr(Warehouse, "notes")

    def test_unique_constraint_company_code(self):
        constraint_names = {
            c.name
            for c in Warehouse.__table__.constraints
            if isinstance(c, UniqueConstraint)
        }
        assert "uq_inv_warehouses_company_code" in constraint_names

    def test_check_constraint_status(self):
        constraint_names = {
            c.name
            for c in Warehouse.__table__.constraints
            if isinstance(c, CheckConstraint)
        }
        assert "ck_inv_warehouses_status" in constraint_names

    def test_check_constraint_type(self):
        constraint_names = {
            c.name
            for c in Warehouse.__table__.constraints
            if isinstance(c, CheckConstraint)
        }
        assert "ck_inv_warehouses_type" in constraint_names

    def test_instantiation(self):
        wh = Warehouse(
            id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            code="WH-MAIN",
            name="Main Warehouse",
            warehouse_type="MAIN",
            status="ACTIVE",
        )
        assert wh.code == "WH-MAIN"
        assert wh.status == "ACTIVE"
        assert wh.branch_id is None


# =============================================================================
# WarehouseLocation model tests
# =============================================================================


class TestWarehouseLocationModel:
    """ORM model structural tests for WarehouseLocation."""

    def test_tablename(self):
        assert WarehouseLocation.__tablename__ == "inventory_warehouse_locations"

    def test_has_warehouse_id_fk(self):
        col = WarehouseLocation.__table__.c.get("warehouse_id")
        assert col is not None
        assert col.nullable is False

    def test_has_location_code(self):
        assert hasattr(WarehouseLocation, "location_code")

    def test_has_aisle_zone_shelf(self):
        for col_name in ("aisle", "zone", "shelf"):
            assert hasattr(WarehouseLocation, col_name)

    def test_has_is_active(self):
        assert hasattr(WarehouseLocation, "is_active")

    def test_unique_constraint(self):
        constraint_names = {
            c.name
            for c in WarehouseLocation.__table__.constraints
            if isinstance(c, UniqueConstraint)
        }
        assert "uq_inv_wh_locations_wh_code" in constraint_names

    def test_instantiation(self):
        loc = WarehouseLocation(
            id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            warehouse_id=str(uuid.uuid4()),
            location_code="A-01-01",
            aisle="A",
            zone="Zone1",
            shelf="01",
            is_active=True,
        )
        assert loc.location_code == "A-01-01"
        assert loc.is_active is True


# =============================================================================
# WarehouseService state machine (pure logic, no DB)
# =============================================================================


class TestWarehouseStatusTransitions:
    """Verify the service enforces the correct state machine."""

    def test_active_to_inactive_allowed(self):
        assert "INACTIVE" in _VALID_STATUS_TRANSITIONS["ACTIVE"]

    def test_active_to_archived_not_allowed(self):
        assert "ARCHIVED" not in _VALID_STATUS_TRANSITIONS["ACTIVE"]

    def test_inactive_to_active_allowed(self):
        assert "ACTIVE" in _VALID_STATUS_TRANSITIONS["INACTIVE"]

    def test_inactive_to_archived_allowed(self):
        assert "ARCHIVED" in _VALID_STATUS_TRANSITIONS["INACTIVE"]

    def test_archived_has_no_transitions(self):
        assert len(_VALID_STATUS_TRANSITIONS["ARCHIVED"]) == 0


class TestWarehouseServiceStateMachine:
    """Unit tests for WarehouseService.transition_status using mocks."""

    def _make_service(self, warehouse: Warehouse) -> WarehouseService:
        """Build a WarehouseService with mocked repos."""
        db = MagicMock()
        db.flush = MagicMock()
        wh_repo = MagicMock()
        wh_repo.get_by_id_or_none.return_value = warehouse
        wh_repo.has_stock.return_value = False
        loc_repo = MagicMock()
        return WarehouseService(db=db, warehouse_repo=wh_repo, location_repo=loc_repo)

    def _make_warehouse(self, status: str) -> Warehouse:
        cid = uuid.uuid4()
        wh = Warehouse(
            id=uuid.uuid4(),
            company_id=cid,
            code="WH-TEST",
            name="Test",
            warehouse_type="MAIN",
            status=status,
        )
        # Simulate ORM by making company_id available as UUID
        return wh

    def test_active_to_inactive(self):
        wh = self._make_warehouse("ACTIVE")
        svc = self._make_service(wh)
        result = svc.transition_status(
            company_id=wh.company_id,
            warehouse_id=wh.id,
            target_status="INACTIVE",
        )
        assert result.status == "INACTIVE"

    def test_invalid_transition_raises(self):
        wh = self._make_warehouse("ACTIVE")
        svc = self._make_service(wh)
        with pytest.raises(InvalidWarehouseStateTransitionError):
            svc.transition_status(
                company_id=wh.company_id,
                warehouse_id=wh.id,
                target_status="ARCHIVED",
            )

    def test_archive_with_stock_raises(self):
        wh = self._make_warehouse("INACTIVE")
        svc = self._make_service(wh)
        svc._repo.has_stock.return_value = True
        with pytest.raises(WarehouseHasStockError):
            svc.transition_status(
                company_id=wh.company_id,
                warehouse_id=wh.id,
                target_status="ARCHIVED",
            )

    def test_archive_without_stock_succeeds(self):
        wh = self._make_warehouse("INACTIVE")
        svc = self._make_service(wh)
        svc._repo.has_stock.return_value = False
        result = svc.transition_status(
            company_id=wh.company_id,
            warehouse_id=wh.id,
            target_status="ARCHIVED",
        )
        assert result.status == "ARCHIVED"

    def test_terminal_archived_raises(self):
        wh = self._make_warehouse("ARCHIVED")
        svc = self._make_service(wh)
        with pytest.raises(InvalidWarehouseStateTransitionError):
            svc.transition_status(
                company_id=wh.company_id,
                warehouse_id=wh.id,
                target_status="ACTIVE",
            )
