"""InstallmentSequenceRepository — atomic contract number generation.

Generates sequential, human-readable installment contract numbers
(``IC-YYYY-NNNNNN``). Concurrency safety: uses ``SELECT ... FOR UPDATE``
on the ``installment_sequences`` row to ensure uniqueness under
concurrent contract creation — mirrors ``SalesSequenceService``/
``AccountingSequenceService``'s exact locking pattern.

Number format: ``{PREFIX}-{YEAR}-{SEQ:06d}``, e.g. ``IC-2026-000001``.

Flush-only (never commits) — the caller (``InstallmentContractService``)
owns the transaction and commits the sequence increment together with
the contract row it numbers.

Spec ref: specs/010-installments/plan.md §30 (T028).
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.installments.models.sequence import InstallmentSequence

logger = logging.getLogger(__name__)

_DOCUMENT_TYPE = "IC"


class InstallmentSequenceRepository:
    """Data-access layer for ``installment_sequences``, plus the atomic
    locked-increment number generator."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_next_number(self, company_id: UUID) -> str:
        """Generate and claim the next sequential contract number.

        Locks the sequence row with ``SELECT ... FOR UPDATE``, increments
        the counter, and returns the formatted number. Flush only — the
        caller's transaction must be committed for the increment to
        persist; a rollback loses the number (an acceptable sequence gap,
        matching the platform's existing sequence-service convention).
        """
        current_year = utcnow().year

        stmt = (
            select(InstallmentSequence)
            .where(InstallmentSequence.company_id == company_id)
            .where(InstallmentSequence.document_type == _DOCUMENT_TYPE)
            .where(InstallmentSequence.year == current_year)
            .where(InstallmentSequence.is_deleted == False)  # noqa: E712
            .with_for_update()
        )
        sequence = self.db.execute(stmt).scalars().one_or_none()

        if sequence is None:
            sequence = InstallmentSequence(
                company_id=company_id,
                document_type=_DOCUMENT_TYPE,
                prefix=_DOCUMENT_TYPE,
                current_value=0,
                year=current_year,
                reset_yearly=True,
                format_pattern="{PREFIX}-{YEAR}-{SEQ:06d}",
            )
            self.db.add(sequence)
            self.db.flush()

        sequence.current_value += 1
        next_value = sequence.current_value

        contract_number = self._format_number(
            prefix=sequence.prefix, year=current_year, seq=next_value
        )
        logger.debug(
            "Installment sequence generated: company=%s number=%s",
            company_id,
            contract_number,
        )
        return contract_number

    @staticmethod
    def _format_number(prefix: str, year: int, seq: int) -> str:
        return f"{prefix}-{year}-{seq:06d}"
