"""CompanyAddress ORM model — physical address records for a company.

A company may hold multiple addresses, one per ``AddressType``.
Exactly one address of each type may be marked ``is_primary=True``,
enforced by a partial unique index in the migration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models.base_model import BaseModel
from modules.companies.models.enums import AddressType

if TYPE_CHECKING:
    from modules.companies.models.company import Company


class CompanyAddress(BaseModel):
    """Physical or mailing address belonging to a Company.

    Inherits ``id``, ``created_at``, ``updated_at`` from ``BaseModel``.
    """

    __tablename__ = "company_addresses"

    __table_args__ = (
        Index("ix_company_addresses_company_id_type", "company_id", "address_type"),
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Parent company. ON DELETE RESTRICT prevents orphaned addresses.",
    )
    address_type: Mapped[AddressType] = mapped_column(
        Enum(AddressType, name="addresstype", create_type=True),
        nullable=False,
        doc="Purpose of this address record.",
    )
    street_line_1: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Primary street address line.",
    )
    street_line_2: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Secondary address line (suite, floor, unit).",
    )
    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="City or municipality.",
    )
    state_province: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="State, province, or region. Optional for countries without subdivisions.",
    )
    postal_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Postal or ZIP code. Optional for countries without postal zones.",
    )
    country: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        doc="ISO 3166-1 alpha-2 country code.",
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="Marks this address as the primary address of its type for the company.",
    )

    # ── Relationship ──────────────────────────────────────────────────────────

    company: Mapped[Company] = relationship(
        "Company",
        back_populates="addresses",
        lazy="select",
    )
