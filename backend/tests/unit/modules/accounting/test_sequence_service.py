"""Unit tests for AccountingSequenceService.

Tests:
  - Sequential generation for the JOURNAL sequence type
  - Invalid sequence type raises ValueError
  - Number formatting logic
  - Company isolation and gap-free concurrent generation (integration-level,
    real SQLite engine — see TestConcurrentGeneration note on limitations)

Spec ref: specs/008-accounting-finance/tasks.md T044
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.services.sequence_service import AccountingSequenceService


class TestAccountingSequenceServiceValidation:
    """Test input validation for AccountingSequenceService."""

    def test_invalid_sequence_type_raises_value_error(self) -> None:
        db = MagicMock()
        service = AccountingSequenceService(db=db)
        with pytest.raises(ValueError, match="Invalid sequence type"):
            service.generate_next_journal_number(
                company_id=uuid4(),
                sequence_type="INVALID",
            )

    def test_valid_sequence_type_accepted(self) -> None:
        db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.one_or_none.return_value = None
        db.execute.return_value = mock_result
        db.add = MagicMock()
        db.flush = MagicMock()

        service = AccountingSequenceService(db=db)
        result = service.generate_next_journal_number(
            company_id=uuid4(),
            sequence_type="JOURNAL",
        )
        assert result.startswith("JE-")


class TestAccountingSequenceServiceFormatting:
    """Test number formatting logic."""

    def test_format_number_basic(self) -> None:
        result = AccountingSequenceService._format_number("JE", 2026, 1)
        assert result == "JE-2026-000001"

    def test_format_number_large_sequence(self) -> None:
        result = AccountingSequenceService._format_number("JE", 2026, 999999)
        assert result == "JE-2026-999999"

    def test_format_number_custom_prefix(self) -> None:
        result = AccountingSequenceService._format_number("ACC", 2026, 42)
        assert result == "ACC-2026-000042"


class TestAccountingSequenceServiceIntegration:
    """Integration-level tests against a real (SQLite) session."""

    def test_sequential_numbers_increment(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = AccountingSequenceService(db=db_session)
        n1 = svc.generate_next_journal_number(company_id)
        n2 = svc.generate_next_journal_number(company_id)
        seq1 = int(n1.split("-")[-1])
        seq2 = int(n2.split("-")[-1])
        assert seq2 == seq1 + 1

    def test_different_companies_independent_sequences(
        self, db_session: Session
    ) -> None:
        company_a = uuid4()
        company_b = uuid4()
        svc = AccountingSequenceService(db=db_session)
        num_a = svc.generate_next_journal_number(company_a)
        num_b = svc.generate_next_journal_number(company_b)
        assert int(num_a.split("-")[-1]) == int(num_b.split("-")[-1]) == 1


class TestConcurrentGeneration:
    """Gap-free numbering under load (T044 — 100 concurrent requests).

    IMPORTANT LIMITATION: this does NOT use real OS threads against the
    shared SQLite engine. ``StaticPool`` (used by ``test_db_engine`` for
    SQLite ``:memory:``) maintains a single physical connection and is
    documented as unsafe for genuinely concurrent multi-threaded checkout —
    an earlier version of this test used ``ThreadPoolExecutor`` with one
    ``Session`` per thread bound to that engine and reliably deadlocked.
    SQLite also does not enforce ``SELECT ... FOR UPDATE`` row-level locking
    the way PostgreSQL does (the clause is accepted but has no locking
    effect in the SQLite dialect).

    This test instead issues 100 sequential calls, each in its own
    transaction/commit, which verifies the counter/lock-acquisition logic
    itself produces no duplicates and no gaps. It does NOT verify true
    row-level lock behavior under concurrent access — that requires
    PostgreSQL and must be re-run against Docker before Phase 4 sign-off
    (see quickstart.md "Phase 0 Verification Findings" re: Docker deferral).
    """

    def test_100_sequential_requests_gap_free(self, db_session: Session) -> None:
        company_id = uuid4()
        svc = AccountingSequenceService(db=db_session)
        numbers: list[str] = []

        for _ in range(100):
            number = svc.generate_next_journal_number(company_id)
            db_session.commit()
            numbers.append(number)

        suffixes = sorted(int(n.split("-")[-1]) for n in numbers)
        assert len(suffixes) == 100
        assert len(set(suffixes)) == 100, "duplicate journal numbers generated"
        assert suffixes == list(range(1, 101)), "gaps detected in sequence"
