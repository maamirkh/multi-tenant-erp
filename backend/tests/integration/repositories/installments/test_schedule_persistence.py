"""[Phase 4] Real-Postgres repository test: schedule version + line
persistence, atomicity (flush-only, no independent commit), and the
unique ``(schedule_version_id, sequence)`` constraint (tasks.md T073).

Partial-unique-index precedent aside, this specific constraint is a
plain ``UniqueConstraint`` — still verified against real Postgres (not
SQLite) for consistency with the module's established real-database-first
discipline and because the schema under test was created by a real
Alembic migration (065).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from modules.installments.models.contract import InstallmentContract
from modules.installments.models.schedule import (
    InstallmentScheduleLine,
    InstallmentScheduleVersion,
)
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from tests.integration.migrations.conftest import (  # noqa: F401
    alembic_upgrade,
    db_engine,
    pg_test_db,
)


@pytest.fixture
def pg_engine(request: pytest.FixtureRequest):
    pg_url = request.getfixturevalue("pg_test_db")
    alembic_upgrade(pg_url, "072")
    engine = db_engine(pg_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _persist_contract(session, company_id: uuid.UUID) -> InstallmentContract:
    contract = InstallmentContract(
        company_id=company_id,
        contract_number=f"IC-2026-{uuid.uuid4().hex[:6]}",
        customer_id=uuid.uuid4(),
        sales_invoice_id=uuid.uuid4(),
        contract_date=date(2026, 1, 1),
        principal_amount=Decimal("1000.00"),
        down_payment_amount=Decimal("100.00"),
        markup_amount=Decimal("0"),
        contractual_total=Decimal("900.00"),
        installment_count=3,
        frequency="MONTHLY",
        first_due_date=date(2026, 2, 1),
        maturity_date=date(2026, 4, 1),
        currency_code="USD",
        status="APPROVED",
        terms_snapshot={"note": "schedule-persistence fixture"},
    )
    session.add(contract)
    session.commit()
    return contract


class TestScheduleVersionAndLinePersistence:
    def test_create_version_with_lines_persists_atomically_flush_only(
        self, pg_session
    ) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(pg_session, company_id)
        repo = InstallmentScheduleRepository(pg_session)

        version = InstallmentScheduleVersion(
            company_id=company_id,
            contract_id=contract.id,
            version_number=1,
            status="ACTIVE",
        )
        lines = [
            InstallmentScheduleLine(
                company_id=company_id,
                sequence=i,
                due_date=date(2026, 1 + i, 1),
                scheduled_amount=Decimal("300.00"),
            )
            for i in range(1, 4)
        ]

        result = repo.create_version_with_lines(version, lines)
        assert result.id is not None
        assert all(line.id is not None for line in lines)
        assert all(line.schedule_version_id == result.id for line in lines)

        # The repository only flushed — nothing is durable until the
        # caller commits. Roll back and confirm nothing persisted.
        pg_session.rollback()

        fresh = repo.get_active_version(company_id, contract.id)
        assert fresh is None

    def test_persisted_version_and_lines_are_retrievable_after_commit(
        self, pg_session
    ) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(pg_session, company_id)
        repo = InstallmentScheduleRepository(pg_session)

        version = InstallmentScheduleVersion(
            company_id=company_id,
            contract_id=contract.id,
            version_number=1,
            status="ACTIVE",
        )
        lines = [
            InstallmentScheduleLine(
                company_id=company_id,
                sequence=i,
                due_date=date(2026, 1 + i, 1),
                scheduled_amount=Decimal("300.00"),
            )
            for i in range(1, 4)
        ]
        repo.create_version_with_lines(version, lines)
        pg_session.commit()

        fetched_version = repo.get_active_version(company_id, contract.id)
        assert fetched_version is not None
        assert fetched_version.version_number == 1

        fetched_by_number = repo.get_version(company_id, contract.id, 1)
        assert fetched_by_number is not None
        assert fetched_by_number.id == fetched_version.id

        fetched_lines = repo.get_lines(company_id, fetched_version.id)
        assert len(fetched_lines) == 3
        assert [line.sequence for line in fetched_lines] == [1, 2, 3]

    def test_duplicate_sequence_within_a_version_violates_unique_constraint(
        self, pg_session
    ) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(pg_session, company_id)
        repo = InstallmentScheduleRepository(pg_session)

        version = InstallmentScheduleVersion(
            company_id=company_id,
            contract_id=contract.id,
            version_number=1,
            status="ACTIVE",
        )
        duplicate_sequence_lines = [
            InstallmentScheduleLine(
                company_id=company_id,
                sequence=1,
                due_date=date(2026, 2, 1),
                scheduled_amount=Decimal("450.00"),
            ),
            InstallmentScheduleLine(
                company_id=company_id,
                sequence=1,  # duplicate — must violate the unique index
                due_date=date(2026, 3, 1),
                scheduled_amount=Decimal("450.00"),
            ),
        ]

        with pytest.raises(IntegrityError) as exc_info:
            repo.create_version_with_lines(version, duplicate_sequence_lines)
        pg_session.rollback()

        diag = getattr(getattr(exc_info.value, "orig", None), "diag", None)
        constraint_name = getattr(diag, "constraint_name", None)
        assert constraint_name == "uq_installment_schedule_lines_version_sequence"

    def test_no_second_non_terminal_version_created_by_this_repository_alone(
        self, pg_session
    ) -> None:
        """The repository itself imposes no versioning-sequence rule (that
        is a service-layer concern in later phases) — this just confirms
        two distinct version rows for the same contract persist
        independently and are each individually retrievable, proving the
        append-only/no-mutation contract holds across multiple versions."""
        company_id = uuid.uuid4()
        contract = _persist_contract(pg_session, company_id)
        repo = InstallmentScheduleRepository(pg_session)

        v1 = InstallmentScheduleVersion(
            company_id=company_id,
            contract_id=contract.id,
            version_number=1,
            status="SUPERSEDED",
        )
        repo.create_version_with_lines(
            v1,
            [
                InstallmentScheduleLine(
                    company_id=company_id,
                    sequence=1,
                    due_date=date(2026, 2, 1),
                    scheduled_amount=Decimal("900.00"),
                )
            ],
        )
        v2 = InstallmentScheduleVersion(
            company_id=company_id,
            contract_id=contract.id,
            version_number=2,
            status="ACTIVE",
            reason="Reschedule",
        )
        repo.create_version_with_lines(
            v2,
            [
                InstallmentScheduleLine(
                    company_id=company_id,
                    sequence=1,
                    due_date=date(2026, 3, 1),
                    scheduled_amount=Decimal("900.00"),
                )
            ],
        )
        pg_session.commit()

        fetched_v1 = repo.get_version(company_id, contract.id, 1)
        fetched_v2 = repo.get_version(company_id, contract.id, 2)
        assert fetched_v1 is not None and fetched_v1.status == "SUPERSEDED"
        assert fetched_v2 is not None and fetched_v2.status == "ACTIVE"
        assert repo.get_active_version(company_id, contract.id).id == fetched_v2.id
