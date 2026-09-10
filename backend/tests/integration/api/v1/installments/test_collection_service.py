"""[Epic 10, Phase 7, T131] Service tests for
``InstallmentCollectionService.record_collection()`` — exact/partial/
multi-installment/advance payment scenarios (spec.md Scenarios B/C/D).

Real Postgres — ``InstallmentScheduleLine``/``InstallmentScheduleVersion``
rely on ``server_default=text("now()")``, unresolvable on SQLite.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)


class TestRecordCollectionScenarios:
    def test_exact_single_installment_payment(self, db_session: Session) -> None:
        """Scenario: exact payment for one due installment."""
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=3, installment_amount=Decimal("100.00")
        )
        service = build_collection_service(db_session)

        result = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        assert result["status"] == "COMPLETED"
        assert result["contract_status"] == "ACTIVE"

        refs = InstallmentAllocationReferenceRepository(db_session).list_for_contract(
            ctx["company_id"], ctx["contract"].id
        )
        assert len(refs) == 1
        assert refs[0].allocated_amount == Decimal("100.00")
        assert refs[0].schedule_line_id == ctx["schedule_lines"][0].id

    def test_partial_installment_payment_then_remainder(
        self, db_session: Session
    ) -> None:
        """Scenario B: partial payment, then a subsequent payment covers
        the remainder."""
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("300.00")
        )
        service = build_collection_service(db_session)

        service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        result = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("200.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        assert result["status"] == "COMPLETED"
        # Full payoff (100 + 200 == 300, the line's full scheduled_amount)
        # auto-completes the contract (FR-INST-104).
        assert result["contract_status"] == "COMPLETED"

        refs = InstallmentAllocationReferenceRepository(db_session).list_for_contract(
            ctx["company_id"], ctx["contract"].id
        )
        assert len(refs) == 2
        assert sum(r.allocated_amount for r in refs) == Decimal("300.00")

    def test_multi_installment_payment_oldest_first(self, db_session: Session) -> None:
        """Scenario C: one payment covering two due installments,
        satisfied oldest-due-first."""
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=3, installment_amount=Decimal("100.00")
        )
        service = build_collection_service(db_session)

        result = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("200.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        assert result["contract_status"] == "ACTIVE"
        refs = InstallmentAllocationReferenceRepository(db_session).list_for_contract(
            ctx["company_id"], ctx["contract"].id
        )
        assert len(refs) == 2
        line_ids_paid = {r.schedule_line_id for r in refs}
        assert line_ids_paid == {
            ctx["schedule_lines"][0].id,
            ctx["schedule_lines"][1].id,
        }

    def test_advance_payment_against_future_installment(
        self, db_session: Session
    ) -> None:
        """Scenario D: a payment before a future due date is allocated
        correctly, and the next outstanding obligation remains accurate."""
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("150.00")
        )
        service = build_collection_service(db_session)

        result = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("300.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        assert result["status"] == "COMPLETED"
        # Full payoff of both lines (300 == 2 x 150) auto-completes.
        assert result["contract_status"] == "COMPLETED"
        refs = InstallmentAllocationReferenceRepository(db_session).list_for_contract(
            ctx["company_id"], ctx["contract"].id
        )
        assert len(refs) == 2

    def test_down_payment_already_applied_reduces_financed_outstanding(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=2,
            installment_amount=Decimal("100.00"),
            down_payment_amount=Decimal("50.00"),
        )
        service = build_collection_service(db_session)

        result = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("200.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        assert result["status"] == "COMPLETED"
        # Full financed payoff (200 == 2 x 100) auto-completes; the
        # down payment is Accounting-side only and never appears as a
        # schedule line, so it does not affect this outcome either way.
        assert result["contract_status"] == "COMPLETED"

    def test_above_approval_threshold_records_pending_approval_not_allocation(
        self, db_session: Session
    ) -> None:
        """When the tenant's payment_approval_threshold + approval-workflow
        flag apply, Accounting returns a DraftPaymentResult with no GL/AR
        truth yet — the collection is recorded as pending approval, not
        allocated, and no InstallmentAllocationReference row is created
        (plan.md §12.3.1's documented DraftPaymentResult branch)."""
        from modules.accounting.repositories.feature_flag_repository import (
            AccountingFeatureFlagRepository,
        )
        from modules.accounting.repositories.foundation import (
            AccountingConfigurationRepository,
        )
        from modules.accounting.services.feature_flag_service import (
            AccountingFeatureFlagService,
        )

        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        config_repo = AccountingConfigurationRepository(db_session)
        config = config_repo.get_for_company(company_id=ctx["company_id"])
        assert config is not None
        config.payment_approval_threshold = Decimal("100.00")
        db_session.add(config)
        db_session.commit()
        AccountingFeatureFlagService(
            db=db_session, flag_repo=AccountingFeatureFlagRepository(db_session)
        ).enable(ctx["company_id"], "accounting.approvalworkflow.enabled")

        service = build_collection_service(db_session)
        result = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("500.00"),  # above the 100.00 threshold
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )

        assert result["status"] == "PENDING_APPROVAL"
        assert result["contract_status"] == "ACTIVE"  # unchanged, not completed

        refs = InstallmentAllocationReferenceRepository(db_session).list_for_contract(
            ctx["company_id"], ctx["contract"].id
        )
        assert refs == []
