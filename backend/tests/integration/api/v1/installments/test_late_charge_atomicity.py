"""[Epic 10, Phase 8, T152 — Correction 4, Layer B] Real-Postgres
forced-failure test: full cross-module late-charge atomicity.

Fails *after* ``stage_adjustment()`` flushes the GL entry/``ARTransaction``/
``CustomerLedger`` recompute and *after* ``InstallmentLateCharge``/
``InstallmentAuditLog``/outbox are staged, but *before*
``finalize_adjustment()`` — asserts **all** of ``JournalEntry``,
``ARTransaction``, the ``CustomerLedger`` balance change,
``InstallmentLateCharge``, ``InstallmentAuditLog``, and the outbox event
are simultaneously absent post-rollback (plan.md §12.1/§12.2's
staging-order discipline; mirrors T136's identical proof for collection).

Replicates ``InstallmentDelinquencyService.apply_late_charge()``'s exact
staged sequence directly (mirroring T114/T136's established pattern) so
the injected failure point is precise and verifiable via a second,
independent connection.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from core.events.outbox import EventOutboxRepository, OutboxRecord
from modules.accounting.dependencies import build_ar_service
from modules.accounting.models.ar import ARTransaction, CustomerLedger
from modules.accounting.models.gl import JournalEntry
from modules.installments.models.audit import InstallmentAuditLog
from modules.installments.models.late_charge import InstallmentLateCharge
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.late_charge import (
    InstallmentLateChargeRepository,
)
from modules.installments.services.audit_service import InstallmentAuditService
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_delinquency_service,
)

_POLICY = {"enabled": True, "charge_type": "FIXED", "amount": "25.00"}


class TestLateChargeAtomicityLayerB:
    def test_forced_failure_before_finalize_leaves_nothing_committed(
        self, db_session, pg_engine
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            late_charge_policy=_POLICY,
        )
        line = ctx["schedule_lines"][0]

        ar_service = build_ar_service(db_session, with_sales_sync=False)
        late_charge_repo = InstallmentLateChargeRepository(db_session)
        audit_service = InstallmentAuditService(
            db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
        )
        outbox_repo = EventOutboxRepository(db_session)

        ledger_before = db_session.execute(
            select(CustomerLedger).where(
                CustomerLedger.company_id == ctx["company_id"],
                CustomerLedger.customer_id == ctx["customer_id"],
            )
        ).scalar_one()
        outstanding_before = ledger_before.total_outstanding_base

        # Replicates apply_late_charge()'s exact sequence up to (but not
        # including) finalize_adjustment().
        late_charge_id = uuid.uuid4()
        staged = ar_service.stage_adjustment(
            company_id=ctx["company_id"],
            customer_id=ctx["customer_id"],
            amount=Decimal("25.00"),
            contra_account_id=ctx["late_fee_account"].id,
            reason="Late charge for installment due (T152 test)",
            posting_date=ctx["today"],
            actor_id=None,
            transaction_type="DEBIT_NOTE",
            source_document_type="InstallmentLateCharge",
            source_document_id=late_charge_id,
        )

        late_charge = InstallmentLateCharge(
            id=late_charge_id,
            company_id=ctx["company_id"],
            contract_id=ctx["contract"].id,
            schedule_line_id=line.id,
            charge_amount=Decimal("25.00"),
            overdue_occurrence_date=line.due_date,
            accounting_journal_entry_id=staged.journal_entry.id,
            accounting_ar_transaction_id=staged.ar_transaction.id,
        )
        late_charge_repo.create(late_charge)

        audit_row = audit_service.record(
            ctx["company_id"],
            "InstallmentLateCharge",
            late_charge.id,
            action="LATE_CHARGE_APPLIED",
            actor_id=None,
            after={"charge_amount": "25.00"},
        )
        audit_row_id = audit_row.id

        outbox_repo.create(
            OutboxRecord(
                event_type="installment.late_charge_applied",
                aggregate_id=str(ctx["contract"].id),
                aggregate_type="InstallmentContract",
                payload={"contract_id": str(ctx["contract"].id)},
            )
        )

        journal_entry_id = staged.journal_entry.id
        ar_transaction_id = staged.ar_transaction.id

        class _InjectedFailure(Exception):
            pass

        try:
            raise _InjectedFailure("simulated failure before finalize_adjustment()")
        except _InjectedFailure:
            db_session.rollback()

        verify_session_factory = sessionmaker(bind=pg_engine)
        verify_session = verify_session_factory()
        try:
            assert verify_session.get(JournalEntry, journal_entry_id) is None
            assert verify_session.get(ARTransaction, ar_transaction_id) is None
            assert verify_session.get(InstallmentLateCharge, late_charge_id) is None
            assert verify_session.get(InstallmentAuditLog, audit_row_id) is None

            refreshed_ledger = verify_session.execute(
                select(CustomerLedger).where(
                    CustomerLedger.company_id == ctx["company_id"],
                    CustomerLedger.customer_id == ctx["customer_id"],
                )
            ).scalar_one()
            assert refreshed_ledger.total_outstanding_base == outstanding_before

            outbox_rows = (
                verify_session.query(OutboxRecord)
                .filter_by(aggregate_id=str(ctx["contract"].id))
                .all()
            )
            assert outbox_rows == []
        finally:
            verify_session.close()

    def test_normal_path_commits_everything_together(
        self, db_session, pg_engine
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            late_charge_policy=_POLICY,
        )
        line = ctx["schedule_lines"][0]
        service = build_delinquency_service(db_session)

        late_charge = service.apply_late_charge(
            ctx["company_id"], ctx["contract"].id, line.id, actor_id=None
        )
        db_session.commit()

        verify_session_factory = sessionmaker(bind=pg_engine)
        verify_session = verify_session_factory()
        try:
            assert (
                verify_session.get(
                    JournalEntry, late_charge.accounting_journal_entry_id
                )
                is not None
            )
            assert (
                verify_session.get(
                    ARTransaction, late_charge.accounting_ar_transaction_id
                )
                is not None
            )
            assert verify_session.get(InstallmentLateCharge, late_charge.id) is not None

            audit_rows = (
                verify_session.query(InstallmentAuditLog)
                .filter_by(entity_id=late_charge.id, action="LATE_CHARGE_APPLIED")
                .all()
            )
            assert len(audit_rows) == 1
        finally:
            verify_session.close()
