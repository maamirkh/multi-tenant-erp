"""AccountingSequenceService — gap-free journal number generation.

Generates sequential, human-readable journal numbers per company using
``SELECT ... FOR UPDATE`` row locking on the ``accounting_sequences`` table
(research.md Decision 2 — PostingEngine single-gate; T031).

Concurrency safety: locking the sequence row ensures uniqueness AND
gap-freedom under concurrent journal creation. Two simultaneous requests for
the same (company_id, sequence_type, year) serialize correctly — the second
request blocks until the first transaction commits or rolls back.

Unlike ``SalesSequenceService`` (where a rolled-back transaction is an
accepted gap), accounting journal numbers must be gap-free per BR/INV rules
in spec.md — callers MUST generate the number and commit the journal within
the same database transaction so the lock is held for the shortest possible
window and no committed gap is ever produced by a rollback after the number
was issued.

Number format: ``{PREFIX}-{YEAR}-{SEQ:06d}``
Example: ``JE-2026-000001``

Spec ref: specs/008-accounting-finance/tasks.md T031
Research ref: specs/008-accounting-finance/research.md Decision 2
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.accounting.constants import SEQUENCE_TYPES
from modules.accounting.models.foundation import AccountingSequence

logger = logging.getLogger(__name__)

DEFAULT_PREFIXES: dict[str, str] = {
    "JOURNAL": "JE",
}


class AccountingSequenceService:
    """Service for generating unique, gap-free accounting document numbers.

    Args:
        db: SQLAlchemy session. The caller is responsible for committing
            the transaction (together with the document being numbered)
            after calling ``generate_next_journal_number``.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_next_journal_number(
        self,
        company_id: UUID,
        sequence_type: str = "JOURNAL",
        prefix: str | None = None,
    ) -> str:
        """Generate and claim the next sequential journal number.

        This method is transactional. It:
          1. Locks the sequence row with ``SELECT ... FOR UPDATE``.
          2. Increments the counter.
          3. Returns the formatted journal number string.

        The caller's transaction must be committed for the increment to
        persist. Because the lock is held until commit/rollback, concurrent
        callers serialize on this row rather than racing — this is what
        guarantees no gaps and no duplicates under concurrent posting.

        Args:
            company_id:     Tenant identifier.
            sequence_type:  Document type this sequence generates numbers for.
                             Only ``"JOURNAL"`` is used in Phase 1.
            prefix:         Optional prefix override (defaults to type prefix).

        Returns:
            Formatted journal number string, e.g. ``"JE-2026-000001"``.

        Raises:
            ValueError: If ``sequence_type`` is not a recognised type.
        """
        if sequence_type not in SEQUENCE_TYPES:
            raise ValueError(
                f"Invalid sequence type: '{sequence_type}'. "
                f"Valid types: {SEQUENCE_TYPES}"
            )

        now = utcnow()
        current_year = now.year
        effective_prefix = prefix or DEFAULT_PREFIXES[sequence_type]

        stmt = (
            select(AccountingSequence)
            .where(AccountingSequence.company_id == company_id)
            .where(AccountingSequence.sequence_type == sequence_type)
            .where(AccountingSequence.year == current_year)
            .where(AccountingSequence.is_deleted == False)  # noqa: E712
            .with_for_update()
        )
        sequence = self.db.execute(stmt).scalars().one_or_none()

        if sequence is None:
            # First document of this type for this company this year.
            sequence = AccountingSequence(
                company_id=company_id,
                sequence_type=sequence_type,
                prefix=effective_prefix,
                current_value=0,
                year=current_year,
                format_pattern="{PREFIX}-{YEAR}-{SEQ:06d}",
            )
            self.db.add(sequence)
            self.db.flush()  # Assign server-generated id without committing.

        sequence.current_value += 1
        next_value = sequence.current_value

        journal_number = self._format_number(
            prefix=effective_prefix,
            year=current_year,
            seq=next_value,
        )

        logger.debug(
            "Sequence generated: company=%s type=%s number=%s",
            company_id,
            sequence_type,
            journal_number,
        )

        return journal_number

    @staticmethod
    def _format_number(prefix: str, year: int, seq: int) -> str:
        """Format a journal number from its components.

        Format: ``{PREFIX}-{YEAR}-{SEQ:06d}``
        """
        return f"{prefix}-{year}-{seq:06d}"
