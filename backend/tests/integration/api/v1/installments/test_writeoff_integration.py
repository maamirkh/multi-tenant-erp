"""[Epic 10, Phase 10, T183] Accounting integration test — write-off
confirms ``stage_write_off()``/``finalize_write_off()`` each called
exactly once, no direct Installments->Accounting table write.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from core.events.outbox import EventOutboxRepository, OutboxRecord
from modules.accounting.dependencies import build_ar_service
from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.gl import JournalEntry
from modules.installments.exceptions import InstallmentIdempotencyConflictError
from modules.installments.models.audit import InstallmentAuditLog
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.idempotency import InstallmentIdempotencyKey
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.configuration import (
    InstallmentConfigurationRepository,
)
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.contract_service import InstallmentContractService
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)


def _default_the_contract(db_session, contract_id: uuid.UUID) -> None:
    contract = db_session.query(InstallmentContract).filter_by(id=contract_id).one()
    contract.status = "DEFAULTED"
    contract.defaulted_at = contract.contract_date
    db_session.add(contract)
    db_session.commit()


class _CountingAccountsReceivableService:
    """Wraps a real ``AccountsReceivableService``, counting
    ``stage_write_off()``/``finalize_write_off()`` calls without
    altering their behavior — proves each is called exactly once per
    ``writeoff()`` invocation, never a direct Installments->Accounting
    table write."""

    def __init__(self, real_service) -> None:
        self._real = real_service
        self.stage_write_off_calls = 0
        self.finalize_write_off_calls = 0

    def stage_write_off(self, *args, **kwargs):
        self.stage_write_off_calls += 1
        return self._real.stage_write_off(*args, **kwargs)

    def finalize_write_off(self, *args, **kwargs):
        self.finalize_write_off_calls += 1
        return self._real.finalize_write_off(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._real, name)


class TestWriteoffAccountingIntegration:
    def test_stage_and_finalize_write_off_each_called_exactly_once(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        _default_the_contract(db_session, ctx["contract"].id)

        real_ar_service = build_ar_service(db_session, with_sales_sync=False)
        counting_ar_service = _CountingAccountsReceivableService(real_ar_service)
        gateway = AccountingIntegrationGateway(
            ar_service=counting_ar_service,
            payment_service=None,
            allocation_engine=None,
        )
        svc = InstallmentContractService(
            repo=InstallmentContractRepository(db_session),
            sequence_repo=None,  # type: ignore[arg-type]
            eligibility_service=None,  # type: ignore[arg-type]
            accounting_gateway=gateway,
            configuration_service=InstallmentConfigurationService(
                repo=InstallmentConfigurationRepository(db_session)
            ),
            audit_service=InstallmentAuditService(
                db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
            ),
            schedule_repo=InstallmentScheduleRepository(db_session),
            idempotency_service=InstallmentIdempotencyService(db_session),
            outbox_repo=EventOutboxRepository(db_session),
            allocation_ref_repo=InstallmentAllocationReferenceRepository(db_session),
        )

        updated = svc.writeoff(
            ctx["company_id"],
            ctx["contract"].id,
            "Uncollectible balance",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
        )

        assert updated.status == "WRITTEN_OFF"
        assert counting_ar_service.stage_write_off_calls == 1
        assert counting_ar_service.finalize_write_off_calls == 1

    def test_writeoff_no_direct_installments_module_import_of_accounting_models(
        self,
    ) -> None:
        """Structural guard: InstallmentContractService.writeoff() must
        reach Accounting exclusively through AccountingIntegrationGateway
        — never import modules.accounting.models directly."""
        import inspect

        source = inspect.getsource(InstallmentContractService)
        assert "from modules.accounting.models" not in source
        assert "import modules.accounting.models" not in source


def _build_counting_contract_service(
    db_session,
) -> tuple[InstallmentContractService, _CountingAccountsReceivableService]:
    real_ar_service = build_ar_service(db_session, with_sales_sync=False)
    counting_ar_service = _CountingAccountsReceivableService(real_ar_service)
    gateway = AccountingIntegrationGateway(
        ar_service=counting_ar_service, payment_service=None, allocation_engine=None
    )
    svc = InstallmentContractService(
        repo=InstallmentContractRepository(db_session),
        sequence_repo=None,  # type: ignore[arg-type]
        eligibility_service=None,  # type: ignore[arg-type]
        accounting_gateway=gateway,
        configuration_service=InstallmentConfigurationService(
            repo=InstallmentConfigurationRepository(db_session)
        ),
        audit_service=InstallmentAuditService(
            db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
        ),
        schedule_repo=InstallmentScheduleRepository(db_session),
        idempotency_service=InstallmentIdempotencyService(db_session),
        outbox_repo=EventOutboxRepository(db_session),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(db_session),
    )
    return svc, counting_ar_service


class TestWriteoffIdempotency:
    """[Phase-10 closure evidence] Direct proof of replay/conflict
    behavior for ``contract.writeoff`` — the REAL ``writeoff()`` command,
    using call-counts on the real ``AccountsReceivableService`` (the
    strongest possible proof that no second Accounting interaction
    occurred at all, not merely that its net effect looks unchanged)
    plus company-wide ``JournalEntry``/``ARTransaction`` row counts."""

    def test_replay_with_same_key_makes_zero_additional_accounting_calls(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        _default_the_contract(db_session, ctx["contract"].id)
        svc, counting_ar_service = _build_counting_contract_service(db_session)
        idem_key = str(uuid.uuid4())

        first = svc.writeoff(
            ctx["company_id"],
            ctx["contract"].id,
            "Uncollectible balance",
            idempotency_key=idem_key,
            actor_id=None,
        )
        assert first.status == "WRITTEN_OFF"
        assert counting_ar_service.stage_write_off_calls == 1
        assert counting_ar_service.finalize_write_off_calls == 1

        journal_entries_after_first = len(
            db_session.execute(
                select(JournalEntry).where(JournalEntry.company_id == ctx["company_id"])
            )
            .scalars()
            .all()
        )
        ar_transactions_after_first = len(
            db_session.execute(
                select(ARTransaction).where(
                    ARTransaction.company_id == ctx["company_id"]
                )
            )
            .scalars()
            .all()
        )
        audit_after_first = (
            db_session.execute(
                select(InstallmentAuditLog).where(
                    InstallmentAuditLog.entity_id == ctx["contract"].id,
                    InstallmentAuditLog.action == "WRITTEN_OFF",
                )
            )
            .scalars()
            .all()
        )
        assert len(audit_after_first) == 1
        outbox_after_first = (
            db_session.query(OutboxRecord)
            .filter_by(aggregate_id=str(ctx["contract"].id))
            .all()
        )
        assert len(outbox_after_first) == 1

        # Replay — same key. writeoff()'s REPLAY branch returns before
        # ever reaching self._accounting.writeoff() at all, so the
        # counting wrapper's own call counters must NOT increment.
        second = svc.writeoff(
            ctx["company_id"],
            ctx["contract"].id,
            "Uncollectible balance",
            idempotency_key=idem_key,
            actor_id=None,
        )
        assert second.id == first.id
        assert second.status == "WRITTEN_OFF"
        assert counting_ar_service.stage_write_off_calls == 1, (
            "replay must make ZERO additional stage_write_off() calls"
        )
        assert counting_ar_service.finalize_write_off_calls == 1, (
            "replay must make ZERO additional finalize_write_off() calls"
        )

        assert (
            len(
                db_session.execute(
                    select(JournalEntry).where(
                        JournalEntry.company_id == ctx["company_id"]
                    )
                )
                .scalars()
                .all()
            )
            == journal_entries_after_first
        ), "replay must create ZERO additional JournalEntry rows"
        assert (
            len(
                db_session.execute(
                    select(ARTransaction).where(
                        ARTransaction.company_id == ctx["company_id"]
                    )
                )
                .scalars()
                .all()
            )
            == ar_transactions_after_first
        ), "replay must create ZERO additional ARTransaction rows"

        audit_after_replay = (
            db_session.execute(
                select(InstallmentAuditLog).where(
                    InstallmentAuditLog.entity_id == ctx["contract"].id,
                    InstallmentAuditLog.action == "WRITTEN_OFF",
                )
            )
            .scalars()
            .all()
        )
        assert len(audit_after_replay) == 1, "replay must create ZERO new audit rows"
        outbox_after_replay = (
            db_session.query(OutboxRecord)
            .filter_by(aggregate_id=str(ctx["contract"].id))
            .all()
        )
        assert len(outbox_after_replay) == 1, "replay must create ZERO new outbox rows"

        reservations = (
            db_session.execute(
                select(InstallmentIdempotencyKey)
                .where(InstallmentIdempotencyKey.company_id == ctx["company_id"])
                .where(InstallmentIdempotencyKey.operation == "contract.writeoff")
            )
            .scalars()
            .all()
        )
        assert len(reservations) == 1
        assert reservations[0].status == "COMPLETED"

    def test_conflict_with_different_reason_makes_zero_accounting_calls(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        _default_the_contract(db_session, ctx["contract"].id)
        svc, counting_ar_service = _build_counting_contract_service(db_session)
        idem_key = str(uuid.uuid4())

        svc.writeoff(
            ctx["company_id"],
            ctx["contract"].id,
            "Reason A",
            idempotency_key=idem_key,
            actor_id=None,
        )
        assert counting_ar_service.stage_write_off_calls == 1

        with pytest.raises(InstallmentIdempotencyConflictError):
            svc.writeoff(
                ctx["company_id"],
                ctx["contract"].id,
                "Reason B — a different request",
                idempotency_key=idem_key,
                actor_id=None,
            )

        assert counting_ar_service.stage_write_off_calls == 1, (
            "a rejected conflicting request must make ZERO Accounting calls"
        )
        assert counting_ar_service.finalize_write_off_calls == 1

        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.status == "WRITTEN_OFF"  # unchanged from the first call
