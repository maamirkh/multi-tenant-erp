"""WarehouseService — application service for warehouse management.

Business rules enforced:
  - Warehouse code unique per company
  - Status transitions: ACTIVE→INACTIVE, INACTIVE→ACTIVE, INACTIVE→ARCHIVED
  - ARCHIVED is terminal — no further transitions allowed
  - Archival blocked when warehouse has non-zero stock (Phase 5 guard)
  - WarehouseLocation code unique within the parent warehouse

Spec ref: specs/005-inventory-management/spec.md §16
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.inventory.domain_events import (
    WarehouseArchived,
    WarehouseCreated,
    WarehouseDeactivated,
    WarehouseUpdated,
)
from modules.inventory.events import get_event_bus
from modules.inventory.exceptions import (
    WarehouseCodeConflictError,
    WarehouseNotFoundError,
)
from modules.inventory.models.warehouse import Warehouse, WarehouseLocation
from modules.inventory.repositories.warehouse_repository import (
    WarehouseLocationRepository,
    WarehouseRepository,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

_VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "ACTIVE": {"INACTIVE"},
    "INACTIVE": {"ACTIVE", "ARCHIVED"},
    "ARCHIVED": set(),  # terminal
}

_VALID_STATUSES = frozenset({"ACTIVE", "INACTIVE", "ARCHIVED"})
_VALID_TYPES = frozenset({"MAIN", "BRANCH", "TRANSIT", "VIRTUAL", "CONSIGNMENT"})


class InvalidWarehouseStateTransitionError(Exception):
    """Status transition not permitted."""


class WarehouseHasStockError(Exception):
    """Cannot archive a warehouse that has non-zero stock."""


class LocationCodeConflictError(Exception):
    """Location code already exists within the warehouse."""


class LocationNotFoundError(Exception):
    """Warehouse location does not exist."""


class WarehouseService:
    """Application service for Warehouse aggregate and WarehouseLocation management."""

    def __init__(
        self,
        db: Session,
        warehouse_repo: WarehouseRepository,
        location_repo: WarehouseLocationRepository,
    ) -> None:
        self._db = db
        self._repo = warehouse_repo
        self._loc_repo = location_repo

    # ------------------------------------------------------------------
    # Warehouse CRUD
    # ------------------------------------------------------------------

    def create_warehouse(
        self,
        *,
        company_id: UUID,
        code: str,
        name: str,
        warehouse_type: str = "MAIN",
        address_line1: str | None = None,
        address_line2: str | None = None,
        city: str | None = None,
        state_province: str | None = None,
        postal_code: str | None = None,
        country_code: str | None = None,
        phone: str | None = None,
        notes: str | None = None,
        actor_id: UUID | None = None,
    ) -> Warehouse:
        """Create a new warehouse for a company."""
        code_upper = code.strip().upper()

        if self._repo.get_by_code(company_id=company_id, code=code_upper):
            raise WarehouseCodeConflictError(
                f"Warehouse code '{code_upper}' already exists in this company"
            )

        if warehouse_type not in _VALID_TYPES:
            raise ValueError(f"Invalid warehouse_type: {warehouse_type}")

        wh = Warehouse(
            id=uuid4(),
            company_id=company_id,
            code=code_upper,
            name=name.strip(),
            warehouse_type=warehouse_type,
            status="ACTIVE",
            address_line1=address_line1,
            address_line2=address_line2,
            city=city,
            state_province=state_province,
            postal_code=postal_code,
            country_code=country_code,
            phone=phone,
            notes=notes,
            created_by=actor_id,
        )
        self._db.add(wh)
        self._db.flush()
        # Defect found during Epic 1-8 consolidated live verification (2026-08-14):
        # this method never committed — flush() alone makes the row visible
        # within the current session/transaction (enough to build a 201
        # response) but core.database.session.get_db() has no commit-on-
        # success step, so the row was silently rolled back when the request's
        # session closed. Invisible to the SQLite test suite because
        # TestClient's get_db override shares the SAME session as the test's
        # own assertions. Scoped fix — see live-verification report for the
        # full (much wider) scope found in Inventory/Purchase/Sales services.
        self._db.commit()
        get_event_bus().publish(
            WarehouseCreated(
                aggregate_id=wh.id,
                company_id=company_id,
                warehouse_code=wh.code,
                warehouse_name=wh.name,
            )
        )
        logger.info("Warehouse created: %s / %s", company_id, wh.id)
        return wh

    def get_warehouse(self, *, company_id: UUID, warehouse_id: UUID) -> Warehouse:
        """Get warehouse by ID, enforcing company ownership."""
        wh = self._repo.get_by_id_or_none(company_id=company_id, id=warehouse_id)
        if not wh or wh.is_deleted:
            raise WarehouseNotFoundError(f"Warehouse {warehouse_id} not found")
        return wh

    def update_warehouse(
        self,
        *,
        company_id: UUID,
        warehouse_id: UUID,
        name: str | None = None,
        warehouse_type: str | None = None,
        address_line1: str | None = None,
        address_line2: str | None = None,
        city: str | None = None,
        state_province: str | None = None,
        postal_code: str | None = None,
        country_code: str | None = None,
        phone: str | None = None,
        notes: str | None = None,
        actor_id: UUID | None = None,
    ) -> Warehouse:
        """Update mutable warehouse fields."""
        wh = self.get_warehouse(company_id=company_id, warehouse_id=warehouse_id)

        if name is not None:
            wh.name = name.strip()
        if warehouse_type is not None:
            if warehouse_type not in _VALID_TYPES:
                raise ValueError(f"Invalid warehouse_type: {warehouse_type}")
            wh.warehouse_type = warehouse_type
        if address_line1 is not None:
            wh.address_line1 = address_line1
        if address_line2 is not None:
            wh.address_line2 = address_line2
        if city is not None:
            wh.city = city
        if state_province is not None:
            wh.state_province = state_province
        if postal_code is not None:
            wh.postal_code = postal_code
        if country_code is not None:
            wh.country_code = country_code
        if phone is not None:
            wh.phone = phone
        if notes is not None:
            wh.notes = notes

        self._db.flush()
        # Missing-commit defect fixed during pre-Epic-9 hardening audit
        # (2026-08-14) — see create_warehouse's comment above.
        self._db.commit()
        get_event_bus().publish(
            WarehouseUpdated(
                aggregate_id=wh.id,
                company_id=company_id,
            )
        )
        return wh

    def transition_status(
        self,
        *,
        company_id: UUID,
        warehouse_id: UUID,
        target_status: str,
        actor_id: UUID | None = None,
    ) -> Warehouse:
        """Apply a status transition to the warehouse.

        Raises:
            InvalidWarehouseStateTransitionError: if transition not allowed
            WarehouseHasStockError: if archiving a warehouse with stock
        """
        wh = self.get_warehouse(company_id=company_id, warehouse_id=warehouse_id)

        allowed = _VALID_STATUS_TRANSITIONS.get(wh.status, set())
        if target_status not in allowed:
            raise InvalidWarehouseStateTransitionError(
                f"Cannot transition warehouse from '{wh.status}' to '{target_status}'"
            )

        if target_status == "ARCHIVED":
            if self._repo.has_stock(company_id=company_id, warehouse_id=warehouse_id):
                raise WarehouseHasStockError(
                    "Cannot archive warehouse with non-zero stock positions"
                )

        wh.status = target_status
        self._db.flush()
        self._db.commit()

        _EVENT_CLS = {
            "INACTIVE": WarehouseDeactivated,
            "ARCHIVED": WarehouseArchived,
        }
        evt_cls = _EVENT_CLS.get(target_status)
        if evt_cls is not None:
            get_event_bus().publish(
                evt_cls(
                    aggregate_id=wh.id,
                    company_id=company_id,
                    warehouse_code=wh.code,
                )
            )

        logger.info("Warehouse %s status → %s", warehouse_id, target_status)
        return wh

    def list_warehouses(
        self,
        *,
        company_id: UUID,
        status: str | None = None,
    ) -> list[Warehouse]:
        """List warehouses for a company."""
        return self._repo.list_for_company(company_id=company_id, status=status)

    # ------------------------------------------------------------------
    # Location management
    # ------------------------------------------------------------------

    def add_location(
        self,
        *,
        company_id: UUID,
        warehouse_id: UUID,
        location_code: str,
        aisle: str | None = None,
        zone: str | None = None,
        shelf: str | None = None,
        is_active: bool = True,
        actor_id: UUID | None = None,
    ) -> WarehouseLocation:
        """Add a location to a warehouse."""
        # Ensure warehouse exists and belongs to company
        self.get_warehouse(company_id=company_id, warehouse_id=warehouse_id)

        code = location_code.strip().upper()
        if self._loc_repo.get_by_code(
            company_id=company_id,
            warehouse_id=warehouse_id,
            location_code=code,
        ):
            raise LocationCodeConflictError(
                f"Location code '{code}' already exists in warehouse {warehouse_id}"
            )

        loc = WarehouseLocation(
            id=uuid4(),
            company_id=company_id,
            warehouse_id=str(warehouse_id),
            location_code=code,
            aisle=aisle,
            zone=zone,
            shelf=shelf,
            is_active=is_active,
            created_by=actor_id,
        )
        self._db.add(loc)
        self._db.flush()
        self._db.commit()
        return loc

    def list_locations(
        self,
        *,
        company_id: UUID,
        warehouse_id: UUID,
        active_only: bool = False,
    ) -> list[WarehouseLocation]:
        """List locations for a warehouse."""
        # Ensure warehouse exists and belongs to company
        self.get_warehouse(company_id=company_id, warehouse_id=warehouse_id)
        return self._loc_repo.list_for_warehouse(
            company_id=company_id,
            warehouse_id=warehouse_id,
            active_only=active_only,
        )

    def update_location(
        self,
        *,
        company_id: UUID,
        warehouse_id: UUID,
        location_id: UUID,
        aisle: str | None = None,
        zone: str | None = None,
        shelf: str | None = None,
        is_active: bool | None = None,
        actor_id: UUID | None = None,
    ) -> WarehouseLocation:
        """Update a warehouse location."""
        # Ensure parent warehouse is accessible
        self.get_warehouse(company_id=company_id, warehouse_id=warehouse_id)

        loc = self._loc_repo.get_by_id_or_none(company_id=company_id, id=location_id)
        if (
            not loc
            or str(loc.company_id) != str(company_id)
            or loc.warehouse_id != str(warehouse_id)
            or loc.is_deleted
        ):
            raise LocationNotFoundError(f"Location {location_id} not found")

        if aisle is not None:
            loc.aisle = aisle
        if zone is not None:
            loc.zone = zone
        if shelf is not None:
            loc.shelf = shelf
        if is_active is not None:
            loc.is_active = is_active

        self._db.flush()
        self._db.commit()
        return loc
