"""[Epic 10, Phase 10, T166] Service tests —
InstallmentContractService.default_command() — the externally-callable,
idempotency-protected wrapper around mark_defaulted() (distinct from the
internal transition primitive, T078).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.accounting.models.payments import Payment
from modules.installments.exceptions import (
    InstallmentIdempotencyConflictError,
    InstallmentIllegalTransitionError,
)
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.idempotency import InstallmentIdempotencyKey
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_contract_service,
)


class TestDefaultCommand:
    def test_default_command_transitions_active_to_defaulted(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        svc = build_contract_service(db_session)

        updated = svc.default_command(
            ctx["company_id"],
            ctx["contract"].id,
            "Missed 3 consecutive installments",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )
        assert updated.status == "DEFAULTED"
        assert updated.defaulted_at is not None

    def test_default_command_makes_zero_accounting_calls(self, db_session) -> None:
        """BR-INST-013: reaching DEFAULTED never implies a posting."""
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        svc = build_contract_service(db_session)

        svc.default_command(
            ctx["company_id"],
            ctx["contract"].id,
            "reason",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )

        payments = (
            db_session.execute(
                select(Payment).where(Payment.company_id == ctx["company_id"])
            )
            .scalars()
            .all()
        )
        assert payments == []

    def test_default_command_rejected_from_non_active_status(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        svc = build_contract_service(db_session)
        svc.default_command(
            ctx["company_id"],
            ctx["contract"].id,
            "reason",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )

        with pytest.raises(InstallmentIllegalTransitionError):
            svc.default_command(
                ctx["company_id"],
                ctx["contract"].id,
                "reason again",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

    def test_default_command_commits_durably(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        svc = build_contract_service(db_session)
        svc.default_command(
            ctx["company_id"],
            ctx["contract"].id,
            "reason",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )

        db_session.expire_all()
        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.status == "DEFAULTED"

    def test_default_command_replay_with_same_key_returns_same_result(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        svc = build_contract_service(db_session)
        idem_key = str(uuid.uuid4())

        first = svc.default_command(
            ctx["company_id"],
            ctx["contract"].id,
            "reason",
            idempotency_key=idem_key,
            actor_id=None,
        )
        second = svc.default_command(
            ctx["company_id"],
            ctx["contract"].id,
            "reason",
            idempotency_key=idem_key,
            actor_id=None,
        )
        assert first.id == second.id
        assert first.status == second.status == "DEFAULTED"

        reservations = (
            db_session.execute(
                select(InstallmentIdempotencyKey)
                .where(InstallmentIdempotencyKey.company_id == ctx["company_id"])
                .where(InstallmentIdempotencyKey.operation == "contract.default")
            )
            .scalars()
            .all()
        )
        assert len(reservations) == 1
        assert reservations[0].status == "COMPLETED"

    def test_default_command_conflicting_replay_with_different_reason(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        svc = build_contract_service(db_session)
        idem_key = str(uuid.uuid4())

        svc.default_command(
            ctx["company_id"],
            ctx["contract"].id,
            "reason A",
            idempotency_key=idem_key,
            actor_id=None,
        )

        with pytest.raises(InstallmentIdempotencyConflictError):
            svc.default_command(
                ctx["company_id"],
                ctx["contract"].id,
                "reason B",
                idempotency_key=idem_key,
                actor_id=None,
            )
