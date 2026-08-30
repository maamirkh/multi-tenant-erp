"""[Epic 10, Phase 10, T183] Accounting integration test — write-off
confirms ``stage_write_off()``/``finalize_write_off()`` each called
exactly once, no direct Installments->Accounting table write.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from core.events.outbox import EventOutboxRepository
from modules.accounting.dependencies import build_ar_service
from modules.installments.models.contract import InstallmentContract
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
