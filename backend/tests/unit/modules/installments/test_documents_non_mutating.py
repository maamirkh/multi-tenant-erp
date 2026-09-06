"""[Epic 10, Phase 12, T212] Service test — every
``InstallmentDocumentService`` method makes zero repository write calls
(read-only proof, plan.md §27: "read-only with respect to contract/
financial state").

Wraps the real repositories with call-counting proxies on their own
write methods (``create``/``update``/``soft_delete``) — the strongest
possible proof that a write method was never invoked, not merely that
the database state happened not to change.

Real PostgreSQL (schedule persistence requires it).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.document_service import InstallmentDocumentService
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)


class _WriteCountingProxy:
    """Wraps any repository, counting calls to its own
    ``create``/``update``/``soft_delete``/``mark_waived`` methods
    without altering behaviour — every other attribute (including
    read methods) passes straight through."""

    _WRITE_METHOD_NAMES = ("create", "update", "soft_delete", "mark_waived")

    def __init__(self, real_repo: Any) -> None:
        self._real = real_repo
        self.write_calls: dict[str, int] = dict.fromkeys(self._WRITE_METHOD_NAMES, 0)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._real, name)
        if name in self._WRITE_METHOD_NAMES and callable(attr):

            def _counted(*args: Any, **kwargs: Any) -> Any:
                self.write_calls[name] += 1
                return attr(*args, **kwargs)

            return _counted
        return attr

    @property
    def total_write_calls(self) -> int:
        return sum(self.write_calls.values())


def _build_service_with_spies(
    pg_db_session: Session,
) -> tuple[InstallmentDocumentService, _WriteCountingProxy, _WriteCountingProxy]:
    contract_repo = _WriteCountingProxy(InstallmentContractRepository(pg_db_session))
    schedule_repo = _WriteCountingProxy(InstallmentScheduleRepository(pg_db_session))
    allocation_ref_repo = InstallmentAllocationReferenceRepository(pg_db_session)
    svc = InstallmentDocumentService(
        contract_repo=contract_repo,  # type: ignore[arg-type]
        schedule_repo=schedule_repo,  # type: ignore[arg-type]
        allocation_ref_repo=allocation_ref_repo,
    )
    return svc, contract_repo, schedule_repo


class TestDocumentsAreNonMutating:
    def test_get_agreement_makes_zero_write_calls(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc, contract_repo, schedule_repo = _build_service_with_spies(pg_db_session)

        result = svc.get_agreement(ctx["company_id"], ctx["contract"].id)

        assert result["document_type"] == "agreement"
        assert contract_repo.total_write_calls == 0
        assert schedule_repo.total_write_calls == 0

    def test_get_schedule_document_makes_zero_write_calls(
        self, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        svc, contract_repo, schedule_repo = _build_service_with_spies(pg_db_session)

        result = svc.get_schedule_document(ctx["company_id"], ctx["contract"].id)

        assert result["document_type"] == "schedule"
        assert len(result["lines"]) == 2
        assert contract_repo.total_write_calls == 0
        assert schedule_repo.total_write_calls == 0

    def test_get_customer_statement_makes_zero_write_calls(
        self, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc, contract_repo, schedule_repo = _build_service_with_spies(pg_db_session)

        result = svc.get_customer_statement(ctx["company_id"], ctx["customer_id"])

        assert result["document_type"] == "customer_statement"
        assert len(result["contracts"]) == 1
        assert contract_repo.total_write_calls == 0
        assert schedule_repo.total_write_calls == 0

    def test_all_three_document_methods_in_sequence_make_zero_write_calls(
        self, pg_db_session: Session
    ) -> None:
        """A stronger, combined proof: even across three consecutive
        calls on the SAME service instance, the running write-call
        count never increments."""
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc, contract_repo, schedule_repo = _build_service_with_spies(pg_db_session)

        svc.get_agreement(ctx["company_id"], ctx["contract"].id)
        svc.get_schedule_document(ctx["company_id"], ctx["contract"].id)
        svc.get_customer_statement(ctx["company_id"], ctx["customer_id"])

        assert contract_repo.total_write_calls == 0
        assert schedule_repo.total_write_calls == 0
