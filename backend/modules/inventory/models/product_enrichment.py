"""Product enrichment ORM models — Tags, Custom Field Values, Internal Notes, Import Jobs.

These models extend the Product aggregate with P2 enrichment capabilities:
  - ProductTag         : many-to-many join between products and inventory_tags
  - ProductCustomFieldValue : per-product value for a custom field definition
  - ProductInternalNote : append-only text notes scoped to a product
  - ImportJob          : tracks bulk CSV import state (PENDING → PROCESSING → COMPLETED/FAILED)

Spec ref: specs/005-inventory-management/spec.md §14, §35
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

# =============================================================================
# ProductTag — many-to-many join
# =============================================================================


class ProductTag(TenantBaseModel):
    """Associates a Tag with a Product (many-to-many join).

    A product may have multiple tags; a tag may appear on many products.
    Uniqueness enforced per (company_id, product_id, tag_id).
    """

    __tablename__ = "inventory_product_tags"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "product_id",
            "tag_id",
            name="uq_inv_product_tags_product_tag",
        ),
        Index("ix_inv_product_tags_product_id", "product_id"),
        Index("ix_inv_product_tags_tag_id", "tag_id"),
        {"comment": "Many-to-many join between inventory_products and inventory_tags"},
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_products.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to the tagged Product",
    )

    tag_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_tags.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to the assigned Tag",
    )


# =============================================================================
# ProductCustomFieldValue — per-product custom field value
# =============================================================================


class ProductCustomFieldValue(TenantBaseModel):
    """Stores the value of a custom field for a specific product.

    ``field_key`` must match a ``CustomFieldDefinition.field_key`` for the same
    company with ``entity_type='PRODUCT'``.  Validation of data_type conformance
    is enforced at the service layer.

    Only one value per (company_id, product_id, field_key) is allowed.
    """

    __tablename__ = "inventory_product_custom_field_values"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "product_id",
            "field_key",
            name="uq_inv_product_cfv_product_field",
        ),
        Index("ix_inv_product_cfv_product_id", "product_id"),
        {"comment": "Per-product values for company-defined custom fields"},
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_products.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to the Product that owns this value",
    )

    field_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Custom field key (matches CustomFieldDefinition.field_key)",
    )

    value_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="String/text/date value (stored as text; service casts to correct type)",
    )

    value_number: Mapped[float | None] = mapped_column(
        # Use Numeric-compatible column for numeric values
        String(50),
        nullable=True,
        doc="Numeric value stored as string (preserves precision)",
    )

    value_bool: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        doc="Boolean value for checkbox fields",
    )

    value_json: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="JSON value for list/multi-select fields",
    )


# =============================================================================
# ProductInternalNote — append-only note
# =============================================================================


class ProductInternalNote(TenantBaseModel):
    """Append-only internal note attached to a Product.

    Notes are created but never edited or deleted (audit trail).
    ``author_id`` records who wrote the note.
    """

    __tablename__ = "inventory_product_internal_notes"
    __table_args__ = (
        Index("ix_inv_product_notes_product_id", "product_id"),
        {"comment": "Append-only internal notes for products (no edit/delete)"},
    )

    product_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("inventory_products.id", ondelete="CASCADE"),
        nullable=False,
        doc="FK to the Product this note belongs to",
    )

    note_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Note body text (plain text or Markdown)",
    )

    author_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="User UUID of the note author (nullable for system notes)",
    )


# =============================================================================
# ImportJob — bulk import state tracking
# =============================================================================

_IMPORT_STATUSES = (
    "('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'FAILED_WITH_ERRORS')"
)


class ImportJob(TenantBaseModel):
    """Tracks the state of a bulk product import job.

    State machine:
        PENDING → PROCESSING → COMPLETED
                             → FAILED_WITH_ERRORS  (some rows failed)
                             → FAILED              (entire job failed)

    ``error_rows`` stores a JSON array of {row_number, product_code, errors[]} objects.
    """

    __tablename__ = "inventory_import_jobs"
    __table_args__ = (
        Index("ix_inv_import_jobs_company_id", "company_id"),
        CheckConstraint(
            f"status IN {_IMPORT_STATUSES}",
            name="ck_inv_import_jobs_status",
        ),
        {"comment": "Bulk product import job tracking table"},
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="PENDING",
        doc="Job status: PENDING, PROCESSING, COMPLETED, FAILED, FAILED_WITH_ERRORS",
    )

    file_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Original uploaded file name",
    )

    total_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Total data rows in the uploaded file",
    )

    processed_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Rows successfully processed and imported",
    )

    failed_rows: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        doc="Rows that could not be imported due to validation errors",
    )

    error_rows: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Array of {row_number, product_code, errors} for failed rows",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Top-level error message if the entire job failed",
    )
