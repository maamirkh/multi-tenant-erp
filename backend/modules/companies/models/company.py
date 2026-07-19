"""Company ORM model — primary tenant entity.

The ``companies`` table is the root of the multi-tenant architecture.
Every future ERP module's data table references a row here via ``company_id``
as a non-nullable foreign key.

Column notes:
  - ``status``: stored as VARCHAR with a CHECK constraint so that adding new
    enum values in future migrations requires only an ALTER TABLE … ADD CHECK,
    not a PostgreSQL ENUM type migration.
  - ``business_type``: uses a PostgreSQL-native ENUM type via SQLAlchemy's
    ``Enum`` mapping for type safety.
  - ``number_format``, ``settings``, ``metadata``: JSONB with empty-object
    server defaults for schema-less extensibility.
  - ``subscription_id``: nullable UUID placeholder for future billing FK.
  - ``custom_domain``: nullable with a partial unique index in the migration.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database.models.base_model import BaseModel
from modules.companies.models.enums import BusinessType, CompanyStatus

if TYPE_CHECKING:
    from modules.companies.models.company_address import CompanyAddress
    from modules.companies.models.company_audit_log import CompanyAuditLog


class Company(BaseModel):
    """Tenant-boundary entity — one row per registered business.

    Inherits ``id``, ``created_at``, ``updated_at`` from ``BaseModel``.
    """

    __tablename__ = "companies"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_setup','active','inactive','suspended','deleted')",
            name="ck_companies_status",
        ),
        Index("ix_companies_slug", "slug", unique=True),
        Index("ix_companies_owner_id", "owner_id"),
        Index("ix_companies_status", "status"),
        Index("ix_companies_status_deleted_at", "status", "deleted_at"),
        Index("ix_companies_subscription_id", "subscription_id"),
        Index("ix_companies_created_at", "created_at"),
    )

    # ── Identity ──────────────────────────────────────────────────────────────

    legal_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Official registered company name. Case-insensitive global uniqueness enforced by migration index.",
    )
    trade_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Doing-business-as (DBA) name. Not required to be globally unique.",
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="URL-safe lowercase hyphenated identifier. Globally unique. Immutable after first active transition.",
    )

    # ── Status ────────────────────────────────────────────────────────────────

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CompanyStatus.pending_setup.value,
        server_default=text("'pending_setup'"),
        doc="Company lifecycle state. Constrained by ck_companies_status CHECK.",
    )

    # ── Ownership ─────────────────────────────────────────────────────────────

    owner_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        doc="User who created this company; holds absolute authority within the tenant.",
    )
    primary_admin_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        doc="Designated primary administrator. May differ from the Owner.",
    )

    # ── Contact ───────────────────────────────────────────────────────────────

    email: Mapped[str] = mapped_column(
        String(254),
        nullable=False,
        doc="Primary company contact email.",
    )
    phone_primary: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Primary phone number in E.164 format.",
    )
    phone_secondary: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Secondary phone number in E.164 format.",
    )
    website: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        doc="Company website URL.",
    )

    # ── Legal / Tax ───────────────────────────────────────────────────────────

    tax_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="VAT / EIN / GST number. Format validated per country.",
    )
    registration_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Business registration / company number.",
    )
    business_category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Industry category label.",
    )
    business_type: Mapped[BusinessType | None] = mapped_column(
        Enum(BusinessType, name="businesstype", create_type=True),
        nullable=True,
        doc="Legal structure of the business.",
    )
    incorporation_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Date of legal incorporation or founding.",
    )

    # ── Regional / Localisation ───────────────────────────────────────────────

    default_currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        doc="ISO 4217 3-letter currency code (e.g. USD, EUR).",
    )
    default_timezone: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="IANA timezone identifier (e.g. America/New_York).",
    )
    default_language: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        doc="IETF BCP 47 language tag (e.g. en-US).",
    )
    country: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
        doc="ISO 3166-1 alpha-2 country code (e.g. US, GB).",
    )
    fiscal_year_start_month: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=1,
        server_default=text("1"),
        doc="Month number (1–12) when the fiscal year begins. Default: January.",
    )
    date_format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="YYYY-MM-DD",
        server_default=text("'YYYY-MM-DD'"),
        doc="Date display format token string.",
    )
    number_format: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
        doc="Decimal and thousands separator preferences (JSONB).",
    )

    # ── Branding ──────────────────────────────────────────────────────────────

    logo_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        doc="Object storage URL for the current company logo.",
    )
    logo_previous_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        doc="Previous logo URL retained for CDN cache invalidation (30-day TTL).",
    )
    brand_color_primary: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
        doc="Primary hex brand color (e.g. #FF5733).",
    )
    brand_color_secondary: Mapped[str | None] = mapped_column(
        String(7),
        nullable=True,
        doc="Secondary hex brand color.",
    )
    tagline: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Short company tagline or description.",
    )

    # ── Extensibility ─────────────────────────────────────────────────────────

    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
        doc="Extensible company settings map (JSONB).",
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
        doc="Future extensibility: custom fields, integration data (JSONB).",
    )

    # ── SaaS / Future ─────────────────────────────────────────────────────────

    subscription_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="Future FK placeholder → subscriptions.id.",
    )
    custom_domain: Mapped[str | None] = mapped_column(
        String(253),
        nullable=True,
        doc="Future custom domain for white-label routing. Unique where not NULL.",
    )

    # ── Soft Delete ───────────────────────────────────────────────────────────

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Set when status transitions to 'deleted'. NULL for non-deleted companies.",
    )
    deletion_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Owner-supplied reason for soft deletion. Required when deleting.",
    )

    # ── Relationships ─────────────────────────────────────────────────────────

    addresses: Mapped[list[CompanyAddress]] = relationship(
        "CompanyAddress",
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="select",
    )
    audit_logs: Mapped[list[CompanyAuditLog]] = relationship(
        "CompanyAuditLog",
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="select",
    )
