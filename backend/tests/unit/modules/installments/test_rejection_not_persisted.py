"""Unit tests (tasks.md T083): rejection returns the contract to DRAFT,
never persists a REJECTED status, and the rejection event remains
permanently visible in InstallmentAuditLog even after resubmission
(FR-INST-102, ADR-INST-11)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy.orm import Session

from modules.installments.constants import InstallmentContractStatus
from modules.installments.models.contract import InstallmentContract
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.contract_service import InstallmentContractService


class _FakeConfig:
    def __init__(self, approval_threshold_amount=None) -> None:
        self.approval_threshold_amount = approval_threshold_amount


class _FakeConfigurationService:
    def __init__(self, threshold=None) -> None:
        self._config = _FakeConfig(threshold) if threshold is not None else None

    def get_effective_config(self, company_id, branch_id=None):
        return self._config


def _make_service(
    db_session: Session, threshold: Decimal | None = None
) -> InstallmentContractService:
    return InstallmentContractService(
        repo=InstallmentContractRepository(db_session),
        sequence_repo=None,  # type: ignore[arg-type]  # not exercised
        eligibility_service=None,  # type: ignore[arg-type]  # not exercised
        accounting_gateway=None,  # type: ignore[arg-type]  # not exercised
        configuration_service=cast(
            InstallmentConfigurationService, _FakeConfigurationService(threshold)
        ),
        audit_service=InstallmentAuditService(
            db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
        ),
    )


def _persist_draft_contract(
    db_session: Session, company_id: uuid.UUID
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
        status="DRAFT",
        terms_snapshot={"note": "rejection fixture"},
    )
    db_session.add(contract)
    db_session.commit()
    return contract


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
        terms_snapshot={"note": "rejection fixture"},
    )
    db_session.add(contract)
    db_session.commit()
    return contract


class TestRejectionNotPersisted:
    def test_reject_transitions_to_draft_not_rejected(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        submitter_id = uuid.uuid4()
        contract = _persist_pending_approval_contract(
            db_session, company_id, submitter_id
        )
        svc = _make_service(db_session)

        updated = svc.reject(company_id, contract.id, "Incomplete terms", uuid.uuid4())
        assert updated.status == "DRAFT"

    def test_rejected_is_not_a_member_of_the_status_enum(self) -> None:
        """Structural guard: there is no ``REJECTED`` value in
        ``InstallmentContractStatus`` at all — it cannot be persisted
        even by accident."""
        assert "REJECTED" not in {s.value for s in InstallmentContractStatus}

    def test_rejection_audit_entry_survives_resubmission(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        original_submitter_id = uuid.uuid4()
        rejecter_id = uuid.uuid4()
        contract = _persist_draft_contract(db_session, company_id)
        # A configured threshold keeps submit() landing on
        # PENDING_APPROVAL (never auto-approved), so reject() applies.
        svc = _make_service(db_session, threshold=Decimal("0"))

        svc.submit(company_id, contract.id, original_submitter_id)
        db_session.refresh(contract)
        svc.reject(company_id, contract.id, "Incomplete terms", rejecter_id)

        # Resubmit — a fresh actor submits the now-DRAFT contract again.
        db_session.refresh(contract)
        second_submitter_id = uuid.uuid4()
        svc.submit(company_id, contract.id, second_submitter_id)

        audit_repo = InstallmentAuditLogRepository(db_session)
        entries = audit_repo.list_for_entity(
            company_id, "InstallmentContract", contract.id
        )
        actions = [entry.action for entry in entries]

        assert "REJECTED" in actions
        assert "SUBMITTED" in actions
        assert actions.count("SUBMITTED") == 2  # original + resubmission

        rejection_entry = next(e for e in entries if e.action == "REJECTED")
        assert rejection_entry.reason == "Incomplete terms"
        assert rejection_entry.actor_user_id == rejecter_id

    def test_rejection_audit_entry_is_never_overwritten_or_deleted(
        self, db_session: Session
    ) -> None:
        """Two full reject-then-resubmit cycles must leave BOTH rejection
        events permanently visible — neither is overwritten by the other."""
        company_id = uuid.uuid4()
        submitter_id = uuid.uuid4()
        contract = _persist_pending_approval_contract(
            db_session, company_id, submitter_id
        )
        # A configured threshold keeps every submit() landing on
        # PENDING_APPROVAL (never auto-approved) so reject() can be
        # exercised a second time.
        svc = _make_service(db_session, threshold=Decimal("0"))

        svc.reject(company_id, contract.id, "First pass", uuid.uuid4())
        db_session.refresh(contract)
        svc.submit(company_id, contract.id, uuid.uuid4())
        db_session.refresh(contract)
        svc.reject(company_id, contract.id, "Second pass", uuid.uuid4())

        audit_repo = InstallmentAuditLogRepository(db_session)
        entries = audit_repo.list_for_entity(
            company_id, "InstallmentContract", contract.id
        )
        rejection_reasons = [e.reason for e in entries if e.action == "REJECTED"]
        assert rejection_reasons == ["First pass", "Second pass"]
