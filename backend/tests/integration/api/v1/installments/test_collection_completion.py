"""[Epic 10, Phase 7, T134] Service test: ``record_collection()`` reaching
zero outstanding auto-transitions the contract to ``COMPLETED``
(FR-INST-104). Real Postgres (schedule tables require it).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.installments.models.contract import InstallmentContract
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)


class TestCollectionAutoCompletion:
    def test_full_payoff_in_one_collection_completes_contract(
        self, db_session: Session
    ) -> None:
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

        assert result["contract_status"] == "COMPLETED"

        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.status == "COMPLETED"
        assert refreshed.closed_at is not None

    def test_full_payoff_across_multiple_collections_completes_on_last(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        service = build_collection_service(db_session)

        first = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        assert first["contract_status"] == "ACTIVE"

        second = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        assert second["contract_status"] == "COMPLETED"

    def test_partial_payment_never_completes_contract(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        service = build_collection_service(db_session)

        result = service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("499.99"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        assert result["contract_status"] == "ACTIVE"
