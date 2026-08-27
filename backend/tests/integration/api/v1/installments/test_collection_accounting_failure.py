"""[Epic 10, Phase 7, closure-gap-3] Real Accounting failure rollback for
``InstallmentCollectionService.record_collection()`` — a genuine
``PostingValidationError`` (locked fiscal period, Accounting's own
canonical mechanism — the same one Phase 6's T117 uses), not a generic
injected exception.

Proves: collection/allocation changes do not commit; the Payment does
not survive; no new ARTransaction/JournalEntry survives; the idempotency
key is not stranded as a completed success (retry remains valid per the
Phase 5.5 primitive).

Real Postgres (schedule tables require it).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.accounting.models.ar import ARTransaction
from modules.accounting.models.gl import JournalEntry
from modules.accounting.models.payments import Payment
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.installments.exceptions import InstallmentFiscalPeriodLockedError
from modules.installments.models.idempotency import InstallmentIdempotencyKey
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.services.idempotency_service import (
    InstallmentIdempotencyService,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)


def _lock_todays_period(db_session, company_id) -> None:
    fiscal_service = FiscalCalendarService(
        db=db_session,
        year_repo=FiscalYearRepository(db_session),
        period_repo=FiscalPeriodRepository(db_session),
        opening_balance_repo=OpeningBalanceRepository(db_session),
        audit_service=AuditLogService(
            db=db_session, audit_repo=AccountingAuditLogRepository(db_session)
        ),
    )
    period = FiscalPeriodRepository(db_session).find_open_period_for_date(
        company_id, date.today()
    )
    fiscal_service.lock_period(
        company_id, period.id, locked_by_user_id=None, lock_reason="Gap-3 test fixture"
    )
    db_session.commit()


class TestRecordCollectionAccountingFailureRollback:
    def test_locked_fiscal_period_rolls_back_everything_and_key_is_retryable(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("400.00")
        )
        service = build_collection_service(db_session)

        payments_before = len(
            db_session.execute(
                select(Payment).where(Payment.company_id == ctx["company_id"])
            )
            .scalars()
            .all()
        )
        ar_transactions_before = len(
            db_session.execute(
                select(ARTransaction).where(
                    ARTransaction.company_id == ctx["company_id"]
                )
            )
            .scalars()
            .all()
        )
        journal_entries_before = len(
            db_session.execute(
                select(JournalEntry).where(JournalEntry.company_id == ctx["company_id"])
            )
            .scalars()
            .all()
        )
        refs_before = InstallmentAllocationReferenceRepository(
            db_session
        ).list_for_contract(ctx["company_id"], ctx["contract"].id)
        assert refs_before == []

        # Lock the period the collection would post into — Accounting's
        # own canonical PostingValidationError mechanism (identical to
        # Phase 6 T117's fiscal-period propagation test), not a generic
        # injected failure.
        _lock_todays_period(db_session, ctx["company_id"])

        idempotency_key = str(uuid.uuid4())
        with pytest.raises(InstallmentFiscalPeriodLockedError):
            service.record_collection(
                ctx["company_id"],
                ctx["contract"].id,
                amount=Decimal("400.00"),
                payment_method="BANK_TRANSFER",
                idempotency_key=idempotency_key,
                actor_id=None,
                bank_account_id=ctx["bank_account"].id,
            )
        db_session.rollback()

        payments_after = len(
            db_session.execute(
                select(Payment).where(Payment.company_id == ctx["company_id"])
            )
            .scalars()
            .all()
        )
        ar_transactions_after = len(
            db_session.execute(
                select(ARTransaction).where(
                    ARTransaction.company_id == ctx["company_id"]
                )
            )
            .scalars()
            .all()
        )
        journal_entries_after = len(
            db_session.execute(
                select(JournalEntry).where(JournalEntry.company_id == ctx["company_id"])
            )
            .scalars()
            .all()
        )
        refs_after = InstallmentAllocationReferenceRepository(
            db_session
        ).list_for_contract(ctx["company_id"], ctx["contract"].id)

        assert payments_after == payments_before
        assert ar_transactions_after == ar_transactions_before
        assert journal_entries_after == journal_entries_before
        assert refs_after == []

        # The idempotency key is not stranded as a completed success —
        # it does not exist as a COMPLETED row (the whole transaction,
        # including the IN_PROGRESS reservation, rolled back), so a
        # retry genuinely reserves fresh rather than replaying a
        # phantom result (plan.md §20.3).
        key_row = (
            db_session.query(InstallmentIdempotencyKey)
            .filter_by(
                company_id=ctx["company_id"],
                operation="collection.create",
                idempotency_key=idempotency_key,
            )
            .one_or_none()
        )
        assert key_row is None

        idempotency_service = InstallmentIdempotencyService(db_session)
        fingerprint = hashlib.sha256(
            f"collection.create:{ctx['contract'].id}:400.00:BANK_TRANSFER".encode()
        ).hexdigest()
        retry_reservation = idempotency_service.reserve(
            ctx["company_id"],
            "collection.create",
            idempotency_key,
            fingerprint,
            contract_id=ctx["contract"].id,
        )
        assert retry_reservation.outcome == "RESERVED"
        db_session.rollback()
