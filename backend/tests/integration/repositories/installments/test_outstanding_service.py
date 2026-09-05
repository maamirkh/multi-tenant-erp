"""[Epic 10, Phase 6, T108] Tests for
``InstallmentOutstandingService.assert_zero_outstanding()`` (plan.md
§9.3) — the single authoritative completion guard.

Uses the real-Postgres throwaway-database fixtures
(``pg_test_db``/``alembic_upgrade``/``db_engine``) established by
``test_schedule_persistence.py`` (Phase 4) — ``InstallmentScheduleLine``/
``InstallmentScheduleVersion`` both rely on ``server_default=text("now()")``,
which SQLite's in-memory test engine cannot resolve, so this is not a
Postgres-vs-SQLite style choice, it is a hard requirement of the schema
under test.

Covers both documented, correct-by-omission extension points explicitly:
today, with no ``InstallmentAllocationReference``/``InstallmentLateCharge``
model in existence yet, the raw schedule-line sum is always the correct
answer (fail-closed — an unpaid line always blocks completion) and no
late-charge check can meaningfully run (nothing to check).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, sessionmaker

from modules.installments.exceptions import InstallmentOutstandingBalanceRemainsError
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.schedule import (
    InstallmentScheduleLine,
    InstallmentScheduleVersion,
)
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.outstanding_service import (
    InstallmentOutstandingService,
)
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
def db_session(pg_engine):
    session_factory = sessionmaker(bind=pg_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _persist_contract(db: Session, company_id: uuid.UUID) -> InstallmentContract:
    contract = InstallmentContract(
        company_id=company_id,
        contract_number=f"IC-2026-{uuid.uuid4().hex[:6]}",
        customer_id=uuid.uuid4(),
        sales_invoice_id=uuid.uuid4(),
        contract_date=date(2026, 1, 1),
        principal_amount=Decimal("900.00"),
        down_payment_amount=Decimal("100.00"),
        markup_amount=Decimal("0"),
        contractual_total=Decimal("900.00"),
        installment_count=3,
        frequency="MONTHLY",
        first_due_date=date(2026, 2, 1),
        maturity_date=date(2026, 4, 1),
        currency_code="USD",
        status="ACTIVE",
        terms_snapshot={"note": "outstanding-service fixture"},
    )
    db.add(contract)
    db.flush()
    return contract


def _persist_active_schedule(
    db: Session,
    company_id: uuid.UUID,
    contract: InstallmentContract,
    line_amounts: list[Decimal],
) -> None:
    repo = InstallmentScheduleRepository(db)
    version = InstallmentScheduleVersion(
        company_id=company_id,
        contract_id=contract.id,
        version_number=1,
        status="ACTIVE",
    )
    lines = [
        InstallmentScheduleLine(
            company_id=company_id,
            sequence=i + 1,
            due_date=date(2026, 2 + i, 1),
            scheduled_amount=amount,
        )
        for i, amount in enumerate(line_amounts)
    ]
    repo.create_version_with_lines(version, lines)
    db.commit()


class _FakeAccountingGateway:
    """T108 depends on the read-only gateway only for its Phase 8
    late-charge extension point, unused today — never called by any
    current test."""

    def get_ar_transaction(self, company_id, ar_transaction_id):
        raise AssertionError(
            "no InstallmentLateCharge exists yet in Phase 6 — this must "
            "never be called until Phase 8 wires the late-charge check"
        )


@pytest.fixture
def outstanding_service(db_session: Session) -> InstallmentOutstandingService:
    return InstallmentOutstandingService(
        schedule_repo=InstallmentScheduleRepository(db_session),
        accounting_gateway=_FakeAccountingGateway(),
    )


class TestAssertZeroOutstanding:
    def test_raises_when_schedule_outstanding_remains(
        self, db_session: Session, outstanding_service: InstallmentOutstandingService
    ) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(db_session, company_id)
        _persist_active_schedule(
            db_session,
            company_id,
            contract,
            [Decimal("300.00"), Decimal("300.00"), Decimal("300.00")],
        )

        with pytest.raises(InstallmentOutstandingBalanceRemainsError) as exc_info:
            outstanding_service.assert_zero_outstanding(company_id, contract.id)

        assert exc_info.value.details["kind"] == "SCHEDULE"

    def test_passes_when_no_active_schedule_version_exists(
        self, db_session: Session, outstanding_service: InstallmentOutstandingService
    ) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(db_session, company_id)

        outstanding_service.assert_zero_outstanding(company_id, contract.id)

    def test_tenant_isolation_does_not_see_another_companys_schedule(
        self, db_session: Session, outstanding_service: InstallmentOutstandingService
    ) -> None:
        company_a = uuid.uuid4()
        company_b = uuid.uuid4()
        contract_a = _persist_contract(db_session, company_a)
        _persist_active_schedule(db_session, company_a, contract_a, [Decimal("500.00")])

        # A different company's identical contract_id can never collide
        # in practice (PKs are globally unique UUIDs); this proves the
        # company_id filter is genuinely applied, not just coincidentally
        # correct — querying company_b for company_a's contract_id finds
        # no active version and passes cleanly.
        outstanding_service.assert_zero_outstanding(company_b, contract_a.id)
