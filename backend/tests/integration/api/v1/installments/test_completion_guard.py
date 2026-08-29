"""[Epic 10, Phase 9, T163/T164/T165] The authoritative completion guard
(``InstallmentOutstandingService``, plan.md §9.3) — proven directly
(unambiguous, deterministic) AND through the real
``InstallmentCollectionService.record_collection()`` path it gates
(BR-INST-010's exact stated invariant: "a contract cannot transition to
COMPLETED while any authoritative outstanding obligation remains against
it").

Test A: all scheduled lines paid but one late-charge ``ARTransaction``
remains open -> completion is withheld, contract stays ``ACTIVE``.

Test B [CORRECTED — Correction 6: removed incorrect [P] marker, same
implied file as Test A]: scheduled + late-charge AR both fully paid ->
contract completes -- NOT parallel-safe with Test A (same file).

Test C [CORRECTED — Correction 6: removed incorrect [P] marker]:
scheduled paid + late charge validly waived -> contract completes --
NOT parallel-safe with Test A/B (same file).

Real Postgres (schedule tables require it).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from modules.installments.exceptions import InstallmentOutstandingBalanceRemainsError
from modules.installments.models.contract import InstallmentContract
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
    build_delinquency_service,
)

_POLICY = {"enabled": True, "charge_type": "FIXED", "amount": "25.00"}


class TestCompletionGuardWithdrawsOnOpenLateCharge:
    """Test A."""

    def test_full_schedule_payoff_with_open_late_charge_leaves_contract_active(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            late_charge_policy=_POLICY,
        )
        line = ctx["schedule_lines"][0]
        delinquency_service = build_delinquency_service(db_session)
        late_charge = delinquency_service.apply_late_charge(
            ctx["company_id"], ctx["contract"].id, line.id, actor_id=None
        )
        db_session.commit()
        db_session.refresh(late_charge)

        collection_service = build_collection_service(db_session)
        # Exactly the schedule line's own amount — oldest-first ordering
        # allocates the whole payment to the schedule line (inserted
        # before the late charge in the combined outstanding pool, so a
        # same-due-date tie resolves to it first), leaving the late
        # charge's own ARTransaction fully unpaid.
        result = collection_service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        assert result["contract_status"] == "ACTIVE"
        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.status == "ACTIVE"
        assert refreshed.closed_at is None

        # The guard itself, called directly, proves WHY: it raises,
        # naming the still-open late charge — this is BR-INST-010's
        # authoritative check, not merely an artifact of the "remaining
        # amount" arithmetic above happening to be nonzero.
        outstanding_service = collection_service._outstanding
        try:
            outstanding_service.assert_zero_outstanding(
                ctx["company_id"], ctx["contract"].id
            )
            raise AssertionError(
                "expected InstallmentOutstandingBalanceRemainsError(kind=LATE_CHARGE)"
            )
        except InstallmentOutstandingBalanceRemainsError as exc:
            assert exc.details["kind"] == "LATE_CHARGE"
            assert exc.details["ar_transaction_id"] == str(
                late_charge.accounting_ar_transaction_id
            )


class TestCompletionGuardPassesWhenLateChargeAlsoPaid:
    """Test B."""

    def test_schedule_and_late_charge_both_fully_paid_completes_contract(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=2,
            installment_amount=Decimal("100.00"),
            late_charge_policy=_POLICY,
        )
        first_line = ctx["schedule_lines"][0]
        delinquency_service = build_delinquency_service(db_session)
        late_charge = delinquency_service.apply_late_charge(
            ctx["company_id"], ctx["contract"].id, first_line.id, actor_id=None
        )
        db_session.commit()
        db_session.refresh(late_charge)

        collection_service = build_collection_service(db_session)
        # 100 (line 1) + 25 (late charge) + 100 (line 2) — the full pool,
        # paid in one shot.
        result = collection_service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("225.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        assert result["contract_status"] == "COMPLETED"
        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.status == "COMPLETED"
        assert refreshed.closed_at is not None

        # The guard itself now passes cleanly (nothing left to raise on).
        collection_service._outstanding.assert_zero_outstanding(
            ctx["company_id"], ctx["contract"].id
        )


class TestCompletionGuardPassesWhenLateChargeValidlyWaived:
    """Test C."""

    def test_schedule_paid_and_late_charge_waived_completes_contract(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            late_charge_policy=_POLICY,
        )
        line = ctx["schedule_lines"][0]
        delinquency_service = build_delinquency_service(db_session)
        late_charge = delinquency_service.apply_late_charge(
            ctx["company_id"], ctx["contract"].id, line.id, actor_id=None
        )
        db_session.commit()
        db_session.refresh(late_charge)

        delinquency_service.waive_late_charge(
            ctx["company_id"],
            ctx["contract"].id,
            late_charge.id,
            reason="Goodwill waiver — customer service exception",
            actor_id=None,
        )
        db_session.commit()

        collection_service = build_collection_service(db_session)
        # Only the schedule line remains payable — the waived late
        # charge is excluded from the outstanding pool entirely.
        result = collection_service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        assert result["contract_status"] == "COMPLETED"
        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.status == "COMPLETED"
        assert refreshed.closed_at is not None

        collection_service._outstanding.assert_zero_outstanding(
            ctx["company_id"], ctx["contract"].id
        )


class TestCompletionGuardAppliesToDefaultedPayoff:
    """The same guard, exercised via ``DEFAULTED -> COMPLETED`` (spec
    §15.4/FR-INST-356's servicing-continuity payoff) — not merely the
    ``ACTIVE -> COMPLETED`` path Tests A/B/C otherwise exercise, per the
    Phase 9 exit gate's explicit "settlement, ordinary collection, and
    defaulted payoff" wording."""

    def test_defaulted_contract_with_late_charge_completes_once_both_are_paid(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            late_charge_policy=_POLICY,
        )
        line = ctx["schedule_lines"][0]
        delinquency_service = build_delinquency_service(db_session)
        delinquency_service.apply_late_charge(
            ctx["company_id"], ctx["contract"].id, line.id, actor_id=None
        )
        db_session.commit()

        # Directly transition to DEFAULTED — mirrors this module's own
        # convention of bypassing the full lifecycle-service call chain
        # in fixture setup (``build_active_contract_with_schedule()``
        # itself bypasses ``create_draft()``/``activate()`` the same
        # way) since the narrower concern here is the completion guard,
        # not ``mark_defaulted()``'s own transition logic (already
        # covered elsewhere).
        contract = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        contract.status = "DEFAULTED"
        db_session.add(contract)
        db_session.commit()

        collection_service = build_collection_service(db_session)
        result = collection_service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("125.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        assert result["contract_status"] == "COMPLETED"
        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.status == "COMPLETED"
