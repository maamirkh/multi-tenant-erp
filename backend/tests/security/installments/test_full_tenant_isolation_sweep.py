"""[Epic 10, Phase 11, T197] Full tenant-isolation sweep — Company A
cannot reach Company B's installment resources by ID, by search, by
collection, or by settlement, across every endpoint group.

``router.py`` endpoints are deliberately thin controllers (module
docstring: "validate -> authN -> authZ -> call service -> return
schema") that pass the URL's ``company_id`` straight into the
corresponding service method with no additional business logic — the
actual tenant-isolation boundary is therefore enforced entirely at the
service/repository layer this file exercises directly (the same
enforcement point Phase 3's ``test_contract_tenant_isolation.py``
already proved for the Contracts group's ``get``/version-update paths;
this file extends that proof to every remaining group: search/list,
lifecycle (submit/approve/reject/cancel/default/cure/writeoff),
activation, collections, collection reversal, settlement, reschedule,
and schedule retrieval).

Real PostgreSQL throughout (schedule persistence requires it).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from modules.installments.exceptions import (
    InstallmentNotFoundError,
    InstallmentReversalNotAllowedError,
)
from tests.security.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
    build_contract_service,
    build_rescheduling_service,
    build_settlement_service,
)


class TestSearchAndListIsolation:
    def test_list_never_returns_another_companys_contracts(
        self, pg_db_session: Session
    ) -> None:
        ctx_a = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)

        company_b = uuid.uuid4()
        items_b, total_b = svc.list(company_b)
        assert total_b == 0
        assert items_b == []

        items_a, total_a = svc.list(ctx_a["company_id"])
        assert total_a == 1
        assert items_a[0].id == ctx_a["contract"].id


class TestContractByIdIsolation:
    def test_get_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.get(company_b, ctx["contract"].id)


class TestLifecycleActionsIsolation:
    def test_submit_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="DRAFT",
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.submit(company_b, ctx["contract"].id, actor_id=None)

    def test_approve_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="PENDING_APPROVAL",
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.approve(company_b, ctx["contract"].id, approver_id=None)

    def test_reject_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="PENDING_APPROVAL",
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.reject(company_b, ctx["contract"].id, "reason", rejecter_id=None)

    def test_cancel_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="DRAFT",
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.cancel(
                company_b,
                ctx["contract"].id,
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

    def test_default_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.default_command(
                company_b,
                ctx["contract"].id,
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

    def test_cure_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.cure(company_b, ctx["contract"].id, "reason", actor_id=None)

    def test_writeoff_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.writeoff(
                company_b,
                ctx["contract"].id,
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

    def test_activate_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="APPROVED",
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.activate(
                company_b,
                ctx["contract"].id,
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )


class TestScheduleIsolation:
    def test_get_active_schedule_cross_tenant_is_not_found(
        self, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.get_active_schedule(company_b, ctx["contract"].id)

    def test_get_schedule_version_cross_tenant_is_not_found(
        self, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.get_schedule_version(company_b, ctx["contract"].id, 1)


class TestCollectionIsolation:
    def test_record_collection_cross_tenant_is_not_found(
        self, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_collection_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.record_collection(
                company_b,
                ctx["contract"].id,
                amount=Decimal("50.00"),
                payment_method="BANK_TRANSFER",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
                bank_account_id=ctx["bank_account"].id,
            )

    def test_reverse_collection_cross_tenant_is_rejected(
        self, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_collection_service(pg_db_session)
        result = svc.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("50.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        collection_id = uuid.UUID(result["accounting_payment_id"])
        company_b = uuid.uuid4()

        # The allocation-reference lookup is company_id-scoped — a wrong
        # company_id sees zero references, indistinguishable from a
        # never-existed collection_id (BR-INST-015-style).
        with pytest.raises(InstallmentReversalNotAllowedError):
            svc.reverse_collection(
                company_b,
                collection_id,
                reason="cross-tenant reversal attempt",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )


class TestSettlementIsolation:
    def test_generate_quote_cross_tenant_is_not_allowed(
        self, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_settlement_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.generate_quote(
                company_b, ctx["contract"].id, ctx["today"], actor_id=None
            )

    def test_execute_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_settlement_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.execute(
                company_b,
                ctx["contract"].id,
                Decimal("100.00"),
                ctx["today"],
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
                bank_account_id=ctx["bank_account"].id,
            )


class TestRescheduleIsolation:
    def test_reschedule_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        from modules.installments.services.rescheduling_service import (
            RescheduleTerms,
        )

        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_rescheduling_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.reschedule(
                company_b,
                ctx["contract"].id,
                RescheduleTerms(first_due_date=ctx["today"]),
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
                requested_by=None,
            )
