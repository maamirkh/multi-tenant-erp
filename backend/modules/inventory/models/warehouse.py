"""Warehouse ORM models — Warehouse aggregate and WarehouseLocation child entity.

Multi-tenancy: Inherits ``company_id`` from ``TenantBaseModel``.

Status transitions:
    ACTIVE → INACTIVE → ARCHIVED  (terminal)
    INACTIVE → ACTIVE              (reactivation)
    ARCHIVED is terminal — no further transitions

Warehouse types:
    MAIN        — Primary warehouse for the company
    BRANCH      — Branch or satellite warehouse
    TRANSIT     — In-transit / staging warehouse
    VIRTUAL     — Virtual / consignment-tracked (no physical location)
    CONSIGNMENT — Goods held at customer/supplier premises

Spec ref: specs/005-inventory-management/spec.md §16
Data model: specs/005-inventory-management/data-model.md §warehouse
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models.tenant_base import TenantBaseModel

_WAREHOUSE_STATUSES = "('ACTIVE', 'INACTIVE', 'ARCHIVED')"
_WAREHOUSE_TYPES = "('MAIN', 'BRANCH', 'TRANSIT', 'VIRTUAL', 'CONSIGNMENT')"


class Warehouse(TenantBaseModel):
    """Warehouse aggregate root.

    Invariants:
    - ``code`` unique per company
    - Status transitions follow the defined state machine
    - Archival blocked when non-zero stock exists (enforced in service)
    - ``branch_id`` reserved for future branch-linkage; nullable now
    """

    __tablename__ = "inventory_warehouses"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "code",
            name="uq_inv_warehouses_company_code",
        ),
        Index("ix_inv_warehouses_company_id", "company_id"),
        Index("ix_inv_warehouses_company_status", "company_id", "status"),
        CheckConstraint(
            f"status IN {_WAREHOUSE_STATUSES}",
            name="ck_inv_warehouses_status",
        ),
        CheckConstraint(
            f"warehouse_type IN {_WAREHOUSE_TYPES}",
            name="ck_inv_warehouses_type",
        ),
        {"comment": "Warehouse aggregate root, scoped per company"},
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Unique warehouse code per company (e.g. 'WH-MAIN')",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable warehouse name",
    )

    warehouse_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="MAIN",
        doc="MAIN | BRANCH | TRANSIT | VIRTUAL | CONSIGNMENT",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="ACTIVE",
        doc="ACTIVE | INACTIVE | ARCHIVED",
    )

    # Reserved for future branch-linkage (Epic 3 Company → Branch model)
    branch_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to branch (reserved — nullable, not enforced yet)",
    )

    # Address value object — embedded columns
    address_line1: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
        doc="Street address line 1",
    )

    address_line2: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
        doc="Street address line 2 (optional)",
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="City",
    )

    state_province: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="State or province",
    )

    postal_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Postal / ZIP code",
    )

    country_code: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        doc="ISO 3166-1 alpha-2/3 country code",
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Contact phone number",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Internal notes about this warehouse",
    )

    # Relationships
    locations: Mapped[list[WarehouseLocation]] = relationship(
        "WarehouseLocation",
        back_populates="warehouse",
        cascade="all, delete-orphan",
        lazy="select",
    )


class WarehouseLocation(TenantBaseModel):
    """Physical or logical location within a warehouse (aisle/zone/shelf).

    Child entity of ``Warehouse`` — cannot exist without a parent warehouse.

    ``location_code`` is unique within the warehouse (not globally).
    """

    __tablename__ = "inventory_warehouse_locations"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "warehouse_id",
            "location_code",
            name="uq_inv_wh_locations_wh_code",
        ),
        Index("ix_inv_wh_locations_warehouse_id", "warehouse_id"),
        {"comment": "Physical/logical locations within a warehouse"},
    )

    warehouse_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_warehouses.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to the parent Warehouse",
    )

    location_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="Location code unique within the warehouse (e.g. 'A-01-01')",
    )

    aisle: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Aisle identifier (e.g. 'A', 'B')",
    )

    zone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Zone or area within the warehouse",
    )

    shelf: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Shelf or bin level (e.g. 'Top', '01')",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Whether this location is currently in use",
    )

    # Relationship back to parent
    warehouse: Mapped[Warehouse] = relationship(
        "Warehouse",
        back_populates="locations",
        lazy="select",
    )
