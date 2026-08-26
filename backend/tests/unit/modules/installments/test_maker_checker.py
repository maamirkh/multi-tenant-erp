"""Unit tests: self-approval denied symmetrically on both approve() and
reject() (tasks.md T082, FR-INST-102, plan.md §16.2) — an explicit
regression guard against the documented Accounting/Payment historical
gap of only guarding one of the two mirror actions.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from modules.installments.exceptions import InstallmentSelfApprovalNotAllowedError
from modules.installments.models.contract import InstallmentContract
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.contract_service import InstallmentContractService


class _FakeConfigurationService:
    def get_effective_config(self, company_id, branch_id=None):
        return None


def _make_service(db_session: Session) -> InstallmentContractService:
    return InstallmentContractService(
        repo=InstallmentContractRepository(db_session),
        sequence_repo=None,
        eligibility_service=None,
        accounting_gateway=None,
        configuration_service=_FakeConfigurationService(),
        audit_service=InstallmentAuditService(
            db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
        ),
    )


def _persist_pending_approval_contract(
    db_session: Session, company_id: uuid.UUID, submitted_by: uuid.UUID
) -> InstallmentContract:
    contract = InstallmentContract(
        company_id=company_id,
        contract_number=f"IC-2026-{uuid.uuid4().hex[:6]}",
        customer_id=uuid.uuid4(),
        sales_invoice_id=uuid.uuid4(),
        contract_date=date(2026, 1, 1),
        principal_amount=Decimal("900.00"),
        down_payment_amount=Decimal("100.00"),
        markup_amount=Decimal("0"),
        contractual_total=Decimal("900.00"),
        installment_count=12,
        frequency="MONTHLY",
        first_due_date=date(2026, 2, 1),
        maturity_date=date(2027, 1, 1),
        currency_code="USD",
        status="PENDING_APPROVAL",
        submitted_by=submitted_by,
        terms_snapshot={"note": "maker-checker fixture"},
    )
    db_session.add(contract)
    db_session.commit()
    return contract


class TestSelfApprovalDenied:
    def test_approve_denies_the_submitter_approving_their_own_contract(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        submitter_id = uuid.uuid4()
        contract = _persist_pending_approval_contract(
            db_session, company_id, submitter_id
        )
        svc = _make_service(db_session)

        with pytest.raises(InstallmentSelfApprovalNotAllowedError):
            svc.approve(company_id, contract.id, submitter_id)

    def test_approve_succeeds_for_a_distinct_approver(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        submitter_id = uuid.uuid4()
        contract = _persist_pending_approval_contract(
            db_session, company_id, submitter_id
        )
        svc = _make_service(db_session)

        updated = svc.approve(company_id, contract.id, uuid.uuid4())
        assert updated.status == "APPROVED"

    def test_reject_denies_the_submitter_rejecting_their_own_contract(
        self, db_session: Session
    ) -> None:
        """The same distinct-approver check applies to reject(), applied
        symmetrically from day one — never fixed only on approve()."""
        company_id = uuid.uuid4()
        submitter_id = uuid.uuid4()
        contract = _persist_pending_approval_contract(
            db_session, company_id, submitter_id
        )
        svc = _make_service(db_session)

        with pytest.raises(InstallmentSelfApprovalNotAllowedError):
            svc.reject(company_id, contract.id, "Not viable", submitter_id)

    def test_reject_succeeds_for_a_distinct_rejecter(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        submitter_id = uuid.uuid4()
        contract = _persist_pending_approval_contract(
            db_session, company_id, submitter_id
        )
        svc = _make_service(db_session)

        updated = svc.reject(company_id, contract.id, "Not viable", uuid.uuid4())
        assert updated.status == "DRAFT"
