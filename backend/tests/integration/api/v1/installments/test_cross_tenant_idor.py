"""[Epic 10, Phase 7, closure-gap-4] Cross-tenant IDOR tests for the 5
Phase-7 endpoints' underlying service methods.

Each router endpoint is a thin wrapper (auth + permission check, then a
direct call into the service method with ``company_id`` taken from the
authenticated request's path, never from a client-supplied body field)
— the actual tenant-isolation enforcement lives in the service/repository
layer these tests exercise directly, which is exactly what a real HTTP
request would reach after authentication/permission middleware. This
matches the router's own "not yet mounted" state (T190/Phase 11) — the
service layer is the real, present enforcement boundary today.

Distinct underlying service paths covered (one test per path, not per
route — ``get_active_schedule()``/``get_schedule_version()`` share the
identical ``_get_or_404()`` gate, so the second gets a lighter check):

1. ``InstallmentContractService.activate()``
2. ``InstallmentCollectionService.record_collection()``
3. ``InstallmentCollectionService.reverse_collection()``
4. ``InstallmentContractService.get_active_schedule()``
5. ``InstallmentContractService.get_schedule_version()`` (shares #4's gate)
6. ``InstallmentSettlementService.generate_quote()`` (Phase 9, T160-adjacent)
7. ``InstallmentSettlementService.execute()`` (Phase 9, T161-adjacent)
8. ``InstallmentReschedulingService.reschedule()`` (Phase 10)
9. ``InstallmentContractService.cancel()`` (Phase 10)
10. ``InstallmentContractService.default_command()`` (Phase 10)
11. ``InstallmentContractService.cure()`` (Phase 10)
12. ``InstallmentContractService.writeoff()`` (Phase 10)

Real Postgres (schedule tables require it).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from modules.installments.exceptions import (
    InstallmentNotFoundError,
    InstallmentReversalNotAllowedError,
)
from modules.installments.models.configuration import InstallmentConfiguration
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.configuration import (
    InstallmentConfigurationRepository,
)
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.services.rescheduling_service import RescheduleTerms
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
    build_contract_service,
    build_rescheduling_service,
    build_settlement_service,
)
from tests.integration.api.v1.installments.test_activation_service import (
    _build_approved_contract,
    _build_contract_service,
)


class TestCrossTenantIDOR:
    def test_activate_cannot_reach_another_companys_contract(self, db_session) -> None:
        company_a_ctx = _build_approved_contract(
            db_session, installment_count=1, down_payment_amount=Decimal("0")
        )
        service = _build_contract_service(db_session)
        company_b_id = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            service.activate(
                company_b_id,
                company_a_ctx["contract"].id,
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

        # No Company B state was mutated (there is none), and Company
        # A's contract is untouched — still APPROVED, never activated
        # by the cross-tenant attempt.
        untouched = InstallmentContractRepository(db_session).get_by_id_or_none(
            company_a_ctx["contract"].id, company_a_ctx["company_id"]
        )
        assert untouched is not None
        assert untouched.status == "APPROVED"
        assert untouched.activated_at is None

    def test_record_collection_cannot_reach_another_companys_contract(
        self, db_session
    ) -> None:
        company_a_ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        service = build_collection_service(db_session)
        company_b_id = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            service.record_collection(
                company_b_id,
                company_a_ctx["contract"].id,
                amount=Decimal("100.00"),
                payment_method="BANK_TRANSFER",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
                bank_account_id=company_a_ctx["bank_account"].id,
            )

        # No collection was recorded against Company A's contract as a
        # side effect of the cross-tenant attempt.
        refs = InstallmentAllocationReferenceRepository(db_session).list_for_contract(
            company_a_ctx["company_id"], company_a_ctx["contract"].id
        )
        assert refs == []

    def test_reverse_collection_cannot_reach_another_companys_collection(
        self, db_session
    ) -> None:
        company_a_ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        service = build_collection_service(db_session)

        collect_result = service.record_collection(
            company_a_ctx["company_id"],
            company_a_ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=company_a_ctx["bank_account"].id,
        )
        collection_id = uuid.UUID(collect_result["accounting_payment_id"])
        company_b_id = uuid.uuid4()

        # get_by_payment_id() is scoped by company_id, so Company B's
        # lookup finds nothing for Company A's collection_id — the same
        # "No collection found" message a genuinely nonexistent id would
        # produce (never distinguishable from non-existence, matching
        # BR-INST-015's cross-tenant-indistinguishable-from-nonexistent
        # convention elsewhere in this module); this is the approved
        # typed response for this path (409 ConflictException, since
        # reversal failures are modeled as conflicts throughout T123,
        # not a 404 NotFoundException).
        with pytest.raises(InstallmentReversalNotAllowedError):
            service.reverse_collection(
                company_b_id,
                collection_id,
                reason="Cross-tenant reversal attempt",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

        # Company A's original allocation-reference row is untouched —
        # no reversal row was created as a side effect.
        refs = InstallmentAllocationReferenceRepository(db_session).list_for_contract(
            company_a_ctx["company_id"], company_a_ctx["contract"].id
        )
        assert len(refs) == 1
        assert refs[0].is_reversal is False

    def test_get_active_schedule_cannot_reach_another_companys_contract(
        self, db_session
    ) -> None:
        company_a_ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        service = _build_contract_service(db_session)
        company_b_id = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            service.get_active_schedule(company_b_id, company_a_ctx["contract"].id)

    def test_get_schedule_version_cannot_reach_another_companys_contract(
        self, db_session
    ) -> None:
        """Shares get_active_schedule()'s identical ``_get_or_404()``
        gate — a lighter check confirming the same guard applies here
        too, not a full independent re-proof."""
        company_a_ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        service = _build_contract_service(db_session)
        company_b_id = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            service.get_schedule_version(company_b_id, company_a_ctx["contract"].id, 1)

    def test_generate_settlement_quote_cannot_reach_another_companys_contract(
        self, db_session
    ) -> None:
        company_a_ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        service = build_settlement_service(db_session)
        company_b_id = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            service.generate_quote(
                company_b_id, company_a_ctx["contract"].id, date.today()
            )

    def test_execute_settlement_cannot_reach_another_companys_contract(
        self, db_session
    ) -> None:
        company_a_ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        service = build_settlement_service(db_session)
        quote = service.generate_quote(
            company_a_ctx["company_id"], company_a_ctx["contract"].id, date.today()
        )
        company_b_id = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            service.execute(
                company_b_id,
                company_a_ctx["contract"].id,
                quote.settlement_amount,
                quote.as_of_date,
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
                bank_account_id=company_a_ctx["bank_account"].id,
            )

        # Company A's contract is untouched by the cross-tenant attempt.
        untouched = InstallmentContractRepository(db_session).get_by_id_or_none(
            company_a_ctx["contract"].id, company_a_ctx["company_id"]
        )
        assert untouched is not None
        assert untouched.status == "ACTIVE"
        assert untouched.closed_at is None

    def test_reschedule_cannot_reach_another_companys_contract(
        self, db_session
    ) -> None:
        company_a_ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        service = build_rescheduling_service(db_session)
        company_b_id = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            service.reschedule(
                company_b_id,
                company_a_ctx["contract"].id,
                RescheduleTerms(first_due_date=date.today() + timedelta(days=30)),
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=uuid.uuid4(),
                requested_by=uuid.uuid4(),
            )

        untouched = InstallmentContractRepository(db_session).get_by_id_or_none(
            company_a_ctx["contract"].id, company_a_ctx["company_id"]
        )
        assert untouched is not None
        assert (
            untouched.active_schedule_version_id == company_a_ctx["schedule_version"].id
        )

    def test_cancel_cannot_reach_another_companys_contract(self, db_session) -> None:
        company_a_ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        service = build_contract_service(db_session)
        company_b_id = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            service.cancel(
                company_b_id,
                company_a_ctx["contract"].id,
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

        untouched = InstallmentContractRepository(db_session).get_by_id_or_none(
            company_a_ctx["contract"].id, company_a_ctx["company_id"]
        )
        assert untouched is not None
        assert untouched.status == "ACTIVE"

    def test_default_command_cannot_reach_another_companys_contract(
        self, db_session
    ) -> None:
        company_a_ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        service = build_contract_service(db_session)
        company_b_id = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            service.default_command(
                company_b_id,
                company_a_ctx["contract"].id,
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

        untouched = InstallmentContractRepository(db_session).get_by_id_or_none(
            company_a_ctx["contract"].id, company_a_ctx["company_id"]
        )
        assert untouched is not None
        assert untouched.status == "ACTIVE"
        assert untouched.defaulted_at is None

    def test_cure_cannot_reach_another_companys_contract(self, db_session) -> None:
        company_a_ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        contract_repo = InstallmentContractRepository(db_session)
        contract = contract_repo.get_by_id_or_none(
            company_a_ctx["contract"].id, company_a_ctx["company_id"]
        )
        assert contract is not None
        contract.status = "DEFAULTED"
        db_session.add(contract)
        db_session.commit()
        InstallmentConfigurationRepository(db_session).create(
            InstallmentConfiguration(
                company_id=company_a_ctx["company_id"],
                branch_id=None,
                allowed_frequencies=["MONTHLY"],
                min_term=1,
                max_term=60,
                cure_enabled=True,
            )
        )
        db_session.commit()

        service = build_contract_service(db_session)
        company_b_id = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            service.cure(
                company_b_id, company_a_ctx["contract"].id, "Goodwill", actor_id=None
            )

        untouched = contract_repo.get_by_id_or_none(
            company_a_ctx["contract"].id, company_a_ctx["company_id"]
        )
        assert untouched is not None
        assert untouched.status == "DEFAULTED"

    def test_writeoff_cannot_reach_another_companys_contract(self, db_session) -> None:
        company_a_ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        contract_repo = InstallmentContractRepository(db_session)
        contract = contract_repo.get_by_id_or_none(
            company_a_ctx["contract"].id, company_a_ctx["company_id"]
        )
        assert contract is not None
        contract.status = "DEFAULTED"
        db_session.add(contract)
        db_session.commit()

        service = build_contract_service(db_session)
        company_b_id = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            service.writeoff(
                company_b_id,
                company_a_ctx["contract"].id,
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

        untouched = contract_repo.get_by_id_or_none(
            company_a_ctx["contract"].id, company_a_ctx["company_id"]
        )
        assert untouched is not None
        assert untouched.status == "DEFAULTED"
        assert untouched.written_off_at is None
