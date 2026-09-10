"""[Phase 3] InstallmentContract tenant isolation and IDOR.

Covers tasks.md T054: cross-tenant ``get_by_id_or_none`` returns ``None``
(structurally impossible to leak a row across tenants — ``BaseRepository``
always filters by ``company_id``), and the service layer maps that
``None`` to a 404 (``InstallmentNotFoundError``) indistinguishable from
genuine non-existence (BR-INST-015, FR-INST-372).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from modules.installments.exceptions import InstallmentNotFoundError
from modules.installments.models.contract import InstallmentContract
from modules.installments.repositories.contract import InstallmentContractRepository


def _create_contract(
    repo: InstallmentContractRepository, company_id: uuid.UUID
) -> InstallmentContract:
    contract = InstallmentContract(
        company_id=company_id,
        contract_number=f"IC-2026-{uuid.uuid4().hex[:6]}",
        customer_id=uuid.uuid4(),
        sales_invoice_id=uuid.uuid4(),
        contract_date=date(2026, 1, 1),
        principal_amount=Decimal("1000.00"),
        down_payment_amount=Decimal("100.00"),
        markup_amount=Decimal("0"),
        contractual_total=Decimal("1000.00"),
        installment_count=12,
        frequency="MONTHLY",
        first_due_date=date(2026, 2, 1),
        maturity_date=date(2027, 1, 1),
        currency_code="USD",
        status="DRAFT",
        terms_snapshot={"note": "tenant-isolation fixture"},
    )
    return repo.create(contract)


class TestInstallmentContractRepositoryTenantIsolation:
    def test_cross_tenant_get_by_id_returns_none(self, db_session: Session) -> None:
        repo = InstallmentContractRepository(db_session)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        contract = _create_contract(repo, company_a)

        # Company A can see its own contract.
        assert repo.get_by_id_or_none(contract.id, company_a) is not None
        # Company B cannot — structurally impossible cross-tenant read.
        assert repo.get_by_id_or_none(contract.id, company_b) is None

    def test_cross_tenant_get_by_id_locked_returns_none(
        self, db_session: Session
    ) -> None:
        repo = InstallmentContractRepository(db_session)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        contract = _create_contract(repo, company_a)

        assert repo.get_by_id_locked(contract.id, company_b) is None

    def test_cross_tenant_find_active_by_sales_invoice_returns_none(
        self, db_session: Session
    ) -> None:
        repo = InstallmentContractRepository(db_session)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        contract = _create_contract(repo, company_a)

        assert (
            repo.find_active_by_sales_invoice(company_a, contract.sales_invoice_id)
            is not None
        )
        assert (
            repo.find_active_by_sales_invoice(company_b, contract.sales_invoice_id)
            is None
        )

    def test_cross_tenant_version_update_affects_zero_rows(
        self, db_session: Session
    ) -> None:
        """The optimistic-lock conditional UPDATE must not be exploitable
        as a cross-tenant write primitive — a wrong company_id must never
        match any row, ever."""
        from modules.installments.exceptions import (
            InstallmentConcurrentModificationError,
        )

        repo = InstallmentContractRepository(db_session)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        contract = _create_contract(repo, company_a)

        with pytest.raises(InstallmentConcurrentModificationError):
            repo.update_with_version_check(
                contract_id=contract.id,
                company_id=company_b,
                expected_version=contract.version,
                status="CANCELLED",
            )

        # Confirm the row was NOT mutated by the cross-tenant attempt.
        db_session.refresh(contract)
        assert contract.status == "DRAFT"


class TestInstallmentContractServiceIDOR:
    def test_get_maps_missing_or_cross_tenant_to_not_found(
        self, db_session: Session
    ) -> None:
        """A non-existent contract and a genuinely cross-tenant contract
        must be indistinguishable — both raise the identical
        InstallmentNotFoundError (BR-INST-015)."""
        from modules.installments.services.contract_service import (
            InstallmentContractService,
        )

        repo = InstallmentContractRepository(db_session)
        company_a, company_b = uuid.uuid4(), uuid.uuid4()
        contract = _create_contract(repo, company_a)

        service = InstallmentContractService(
            repo=repo,
            sequence_repo=None,  # type: ignore[arg-type]  # not exercised by get()
            eligibility_service=None,  # type: ignore[arg-type]  # not exercised by get()
            accounting_gateway=None,  # type: ignore[arg-type]  # not exercised by get()
            configuration_service=None,  # type: ignore[arg-type]  # not exercised by get()
            audit_service=None,  # type: ignore[arg-type]  # not exercised by get()
        )

        # Genuinely non-existent id.
        with pytest.raises(InstallmentNotFoundError) as exc_never_existed:
            service.get(company_a, uuid.uuid4())

        # Cross-tenant reference to a contract that DOES exist for company A.
        with pytest.raises(InstallmentNotFoundError) as exc_cross_tenant:
            service.get(company_b, contract.id)

        # Identical exception type/code/http_status — indistinguishable.
        assert type(exc_never_existed.value) is type(exc_cross_tenant.value)
        assert exc_never_existed.value.code == exc_cross_tenant.value.code
        assert exc_never_existed.value.http_status == exc_cross_tenant.value.http_status
