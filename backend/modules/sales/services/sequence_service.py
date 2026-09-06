"""SalesSequenceService — atomic document number generation.

Generates sequential, human-readable sales document numbers for all
document types (SQ, SO, DN, SI, SR) per company.

Concurrency safety: Uses SELECT FOR UPDATE on the ``sales_sequences`` row
to ensure uniqueness under concurrent document creation. Two simultaneous
requests for the same (company_id, document_type) will serialize correctly.

Number format: ``{PREFIX}-{YEAR}-{SEQ:06d}``
Examples:
  - SO-2026-000001
  - SI-2026-000042
  - DN-2026-001234
  - SR-2026-000007
  - SQ-2026-000015

Year-based reset: When ``reset_yearly=True``, the counter resets to 1 at the
start of each calendar year. The (company_id, document_type, year) unique
constraint ensures the correct sequence row is locked per year.

Research ref: specs/007-sales-management/research.md §Decision 4, §Decision 6
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.sales.constants import DOCUMENT_TYPES
from modules.sales.models.master import SalesSequence

logger = logging.getLogger(__name__)

# Default document prefixes (companies can override via SalesConfiguration)
DEFAULT_PREFIXES: dict[str, str] = {
    "SQ": "SQ",
    "SO": "SO",
    "DN": "DN",
    "SI": "SI",
    "SR": "SR",
}


class SalesSequenceService:
    """Service for generating unique sequential sales document numbers.

    Args:
        db: SQLAlchemy session. The caller is responsible for committing
            the transaction after calling ``generate_next_number``.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_next_number(
        self,
        company_id: UUID,
        document_type: str,
        prefix: str | None = None,
    ) -> str:
        """Generate and claim the next sequential number for a document type.

        This method is transactional. It:
          1. Locks the sequence row with SELECT FOR UPDATE.
          2. Increments the counter.
          3. Returns the formatted document number string.

        The caller's transaction must be committed for the increment to persist.
        If the transaction is rolled back, the number is lost (gap in sequence)
        — this is acceptable per the spec; sequential gaps are preferred over
        uniqueness violations.

        For gap-free invoice numbering (SI), the advisory lock variant ensures
        no gaps by serializing at a higher level.

        Args:
            company_id:     Tenant identifier.
            document_type:  One of: SQ, SO, DN, SI, SR.
            prefix:         Optional prefix override (defaults to document_type).

        Returns:
            Formatted document number string, e.g. ``"SO-2026-000001"``.

        Raises:
            ValueError: If document_type is not a valid sales document type.
        """
        if document_type not in DOCUMENT_TYPES:
            raise ValueError(
                f"Invalid document type: '{document_type}'. "
                f"Valid types: {DOCUMENT_TYPES}"
            )

        now = utcnow()
        current_year = now.year
        effective_prefix = prefix or DEFAULT_PREFIXES[document_type]

        # Lock the sequence row for this company + document_type + year.
        stmt = (
            select(SalesSequence)
            .where(SalesSequence.company_id == company_id)
            .where(SalesSequence.document_type == document_type)
            .where(SalesSequence.year == current_year)
            .where(SalesSequence.is_deleted == False)  # noqa: E712
            .with_for_update()
        )
        sequence = self.db.execute(stmt).scalars().one_or_none()

        if sequence is None:
            # First document of this type for this company this year.
            sequence = SalesSequence(
                company_id=company_id,
                document_type=document_type,
                prefix=effective_prefix,
                current_value=0,
                year=current_year,
                reset_yearly=True,
                format_pattern="{PREFIX}-{YEAR}-{SEQ:06d}",
            )
            self.db.add(sequence)
            self.db.flush()  # Assign server-generated id without committing.

        # Increment the counter.
        sequence.current_value += 1
        next_value = sequence.current_value

        # Build the document number using the format pattern.
        document_number = self._format_number(
            prefix=effective_prefix,
            year=current_year,
            seq=next_value,
        )

        logger.debug(
            "Sequence generated: company=%s type=%s number=%s",
            company_id,
            document_type,
            document_number,
        )

        return document_number

    @staticmethod
    def _format_number(prefix: str, year: int, seq: int) -> str:
        """Format a document number from its components.

        Format: ``{PREFIX}-{YEAR}-{SEQ:06d}``
        """
        return f"{prefix}-{year}-{seq:06d}"
