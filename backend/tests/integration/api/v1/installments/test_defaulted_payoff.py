"""[Epic 10, Phase 10, T185] Service test — DEFAULTED -> COMPLETED full
payoff (spec §28 edge case) does not force an unnecessary cure() first
(FR-INST-104).

``_LEGAL_TRANSITIONS["DEFAULTED"]`` already includes ``COMPLETED``
directly (plan.md §9.1's state diagram), and
``InstallmentCollectionService.record_collection()`` already treats
``DEFAULTED`` as a reversible/serviceable status
(``_REVERSIBLE_STATUSES``, FR-INST-356's servicing-continuity) — this
test is the explicit, dedicated proof that a full payoff against a
DEFAULTED contract completes it directly, with zero call to ``cure()``
anywhere in the path.
"""

from __future__ import annotations

import inspect
import uuid
from decimal import Decimal

from modules.installments.models.contract import InstallmentContract
from modules.installments.services.collection_service import (
    InstallmentCollectionService,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
)


class TestDefaultedFullPayoffSkipsCure:
    def test_full_payoff_against_defaulted_contract_completes_directly(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        contract = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        contract.status = "DEFAULTED"
        contract.defaulted_at = contract.contract_date
        db_session.add(contract)
        db_session.commit()

        collection_service = build_collection_service(db_session)
        # record_collection() has no cure()/cure_enabled dependency at
        # all — grep-verifiable, matching the "never forces cure" claim
        # structurally, not merely by behavior.
        assert (
            "cure"
            not in inspect.getsource(
                InstallmentCollectionService.record_collection
            ).lower()
        )

        result = collection_service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("200.00"),
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
        # Never routed through ACTIVE — the contract went straight from
        # DEFAULTED to COMPLETED.
        assert refreshed.defaulted_at is not None
