"""InstallmentSequence ORM model.

Gap-free sequence counter for installment contract numbering
(``IC-YYYY-NNNNNN``). Concurrency safety: locked via
``SELECT ... FOR UPDATE`` on this row by
``InstallmentSequenceRepository.generate_next_number()`` to guarantee no
gaps and no duplicates under concurrent contract creation, mirroring
``AccountingSequence``/``SalesSequence``'s exact locking pattern.

Spec ref: specs/010-installments/data-model.md "InstallmentSequence".
"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class InstallmentSequence(TenantBaseModel):
    """Gap-free auto-numbering sequence for Installments contract numbers."""

    __tablename__ = "installment_sequences"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "document_type",
            "year",
            name="uq_installment_sequences_company_type_year",
        ),
        CheckConstraint(
            "document_type IN ('IC')", name="ck_installment_sequences_document_type"
        ),
        CheckConstraint(
            "current_value >= 0", name="ck_installment_sequences_current_value"
        ),
        {
            "comment": "Gap-free auto-numbering sequences for Installments contract "
            "numbers, locked with SELECT FOR UPDATE"
        },
    )

    document_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Document type this sequence generates numbers for ('IC')",
    )
    prefix: Mapped[str] = mapped_column(
        String(10), server_default="IC", nullable=False, doc="Number prefix"
    )
    current_value: Mapped[int] = mapped_column(
        Integer, server_default="0", nullable=False, doc="Last issued sequence value"
    )
    year: Mapped[int | None] = mapped_column(
        Integer, nullable=True, doc="Calendar year this counter applies to"
    )
    reset_yearly: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    format_pattern: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="{PREFIX}-{YEAR}-{SEQ:06d}",
    )
