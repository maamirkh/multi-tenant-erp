"""Unit tests for the full reachable _LEGAL_TRANSITIONS matrix (tasks.md
T081) — every legal transition Phase 5's named methods (``submit()``,
``approve()``, ``reject()``, ``mark_defaulted()``) can reach succeeds; a
representative sample of illegal transitions raises
``InstallmentIllegalTransitionError``.

``cancel()`` is intentionally NOT tested here as of Phase 10: it became
idempotency-protected (T169), which requires PostgreSQL's
``ON CONFLICT DO NOTHING`` — incompatible with this file's SQLite
in-memory ``db_session`` fixture. Its transition-matrix and commit-
durability coverage now lives in
``tests/integration/api/v1/installments/test_cancellation_service.py``
(real Postgres), alongside its financial-activity-branch tests.

``activate()``/``complete()``/``cure()``/``writeoff()`` don't exist as
service methods until Phase 7/10 — those _LEGAL_TRANSITIONS edges are
untestable here by construction and are not exercised (no future-phase
leakage; ``cure()``/``writeoff()`` are also tested in dedicated
Postgres-backed files, since ``writeoff()`` needs Accounting integration
and ``cure()`` needs policy-configuration fixtures). Contracts start in
a non-DRAFT status by direct ORM construction where needed (there is no
other way to reach e.g. ACTIVE before Phase 7's ``activate()`` exists)
— this is arranging state for an isolated unit test, not bypassing any
guard under test.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from modules.installments.exceptions import InstallmentIllegalTransitionError
from modules.installments.models.contract import InstallmentContract
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.contract_service import InstallmentContractService


@dataclass
class _FakeConfig:
    approval_threshold_amount: Decimal | None = None


class _FakeConfigurationService:
    def __init__(self, threshold: Decimal | None = None) -> None:
        self._config = _FakeConfig(approval_threshold_amount=threshold)

    def get_effective_config(self, company_id, branch_id=None):
        return self._config


def _make_service(
    db_session: Session, threshold: Decimal | None = None
) -> InstallmentContractService:
    return InstallmentContractService(
        repo=InstallmentContractRepository(db_session),
        sequence_repo=None,  # not exercised by lifecycle methods
        eligibility_service=None,  # not exercised by lifecycle methods
        accounting_gateway=None,  # not exercised by lifecycle methods
        configuration_service=_FakeConfigurationService(threshold),
        audit_service=InstallmentAuditService(
            db=db_session, audit_repo=InstallmentAuditLogRepository(db_session)
        ),
    )


def _persist_contract(
    db_session: Session, company_id: uuid.UUID, *, status: str, **overrides
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
        contractual_total=overrides.pop("contractual_total", Decimal("900.00")),
        installment_count=12,
        frequency="MONTHLY",
        first_due_date=date(2026, 2, 1),
        maturity_date=date(2027, 1, 1),
        currency_code="USD",
        status=status,
        terms_snapshot={"note": "lifecycle-matrix fixture"},
        **overrides,
    )
    db_session.add(contract)
    db_session.commit()
    return contract


class TestSubmitTransitions:
    def test_draft_to_approved_when_no_threshold_configured(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(db_session, company_id, status="DRAFT")
        svc = _make_service(db_session, threshold=None)

        updated = svc.submit(company_id, contract.id, uuid.uuid4())
        assert updated.status == "APPROVED"
        assert updated.submitted_at is not None
        assert updated.approved_at is not None

    def test_draft_to_pending_approval_when_above_threshold(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(
            db_session, company_id, status="DRAFT", contractual_total=Decimal("900")
        )
        svc = _make_service(db_session, threshold=Decimal("500"))

        updated = svc.submit(company_id, contract.id, uuid.uuid4())
        assert updated.status == "PENDING_APPROVAL"
        assert updated.approved_at is None

    def test_draft_to_approved_when_below_threshold(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(
            db_session, company_id, status="DRAFT", contractual_total=Decimal("100")
        )
        svc = _make_service(db_session, threshold=Decimal("500"))

        updated = svc.submit(company_id, contract.id, uuid.uuid4())
        assert updated.status == "APPROVED"

    @pytest.mark.parametrize(
        "starting_status",
        ["PENDING_APPROVAL", "APPROVED", "CANCELLED", "COMPLETED", "WRITTEN_OFF"],
    )
    def test_submit_rejected_from_non_draft_status(
        self, db_session: Session, starting_status: str
    ) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(db_session, company_id, status=starting_status)
        svc = _make_service(db_session)

        with pytest.raises(InstallmentIllegalTransitionError):
            svc.submit(company_id, contract.id, uuid.uuid4())


class TestApproveTransitions:
    def test_pending_approval_to_approved(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        submitter_id = uuid.uuid4()
        contract = _persist_contract(
            db_session,
            company_id,
            status="PENDING_APPROVAL",
            submitted_by=submitter_id,
        )
        svc = _make_service(db_session)

        updated = svc.approve(company_id, contract.id, uuid.uuid4())
        assert updated.status == "APPROVED"
        assert updated.approved_at is not None

    @pytest.mark.parametrize(
        "starting_status", ["DRAFT", "APPROVED", "CANCELLED", "ACTIVE"]
    )
    def test_approve_rejected_from_non_pending_approval_status(
        self, db_session: Session, starting_status: str
    ) -> None:
        """Critical regression guard: "APPROVED" is ALSO reachable from
        "DRAFT" in the raw _LEGAL_TRANSITIONS graph (submit()'s own
        no-threshold fast path) — approve() must still reject a DRAFT
        contract, not silently succeed via bare graph-reachability."""
        company_id = uuid.uuid4()
        contract = _persist_contract(db_session, company_id, status=starting_status)
        svc = _make_service(db_session)

        with pytest.raises(InstallmentIllegalTransitionError):
            svc.approve(company_id, contract.id, uuid.uuid4())


class TestRejectTransitions:
    def test_pending_approval_to_draft(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        submitter_id = uuid.uuid4()
        contract = _persist_contract(
            db_session,
            company_id,
            status="PENDING_APPROVAL",
            submitted_by=submitter_id,
        )
        svc = _make_service(db_session)

        updated = svc.reject(company_id, contract.id, "Missing documents", uuid.uuid4())
        assert updated.status == "DRAFT"

    @pytest.mark.parametrize("starting_status", ["DRAFT", "APPROVED", "CANCELLED"])
    def test_reject_rejected_from_non_pending_approval_status(
        self, db_session: Session, starting_status: str
    ) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(db_session, company_id, status=starting_status)
        svc = _make_service(db_session)

        with pytest.raises(InstallmentIllegalTransitionError):
            svc.reject(company_id, contract.id, "reason", uuid.uuid4())


class TestLifecycleMethodsCommitDurably:
    """Every lifecycle method must actually commit — a returned in-memory
    object alone proves nothing about durability. Re-fetch through a
    brand-new repository/session-independent query to prove the mutation
    survived, guarding against the exact "missing commit" defect class
    already documented once elsewhere in this codebase (inventory
    module's adjustment_service.py history)."""

    def test_submit_commits(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(db_session, company_id, status="DRAFT")
        svc = _make_service(db_session)
        svc.submit(company_id, contract.id, uuid.uuid4())

        db_session.expire_all()
        refetched = InstallmentContractRepository(db_session).get_by_id_or_none(
            contract.id, company_id
        )
        assert refetched.status == "APPROVED"

    def test_approve_commits(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(
            db_session, company_id, status="PENDING_APPROVAL", submitted_by=uuid.uuid4()
        )
        svc = _make_service(db_session)
        svc.approve(company_id, contract.id, uuid.uuid4())

        db_session.expire_all()
        refetched = InstallmentContractRepository(db_session).get_by_id_or_none(
            contract.id, company_id
        )
        assert refetched.status == "APPROVED"

    def test_reject_commits(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(
            db_session, company_id, status="PENDING_APPROVAL", submitted_by=uuid.uuid4()
        )
        svc = _make_service(db_session)
        svc.reject(company_id, contract.id, "reason", uuid.uuid4())

        db_session.expire_all()
        refetched = InstallmentContractRepository(db_session).get_by_id_or_none(
            contract.id, company_id
        )
        assert refetched.status == "DRAFT"

    def test_mark_defaulted_does_not_commit_by_itself(
        self, db_session: Session
    ) -> None:
        """Internal-primitive guard: mark_defaulted() stages the
        transition but must NOT commit — it is the caller's (Phase 10's
        default_command()) job to commit as its own final step."""
        company_id = uuid.uuid4()
        contract = _persist_contract(db_session, company_id, status="ACTIVE")
        svc = _make_service(db_session)
        svc.mark_defaulted(company_id, contract.id, "reason", uuid.uuid4())

        db_session.rollback()
        refetched = InstallmentContractRepository(db_session).get_by_id_or_none(
            contract.id, company_id
        )
        assert refetched.status == "ACTIVE"  # rolled back — never committed


class TestMarkDefaultedTransitions:
    def test_active_to_defaulted(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(db_session, company_id, status="ACTIVE")
        svc = _make_service(db_session)

        updated = svc.mark_defaulted(
            company_id, contract.id, "Missed 3 installments", uuid.uuid4()
        )
        assert updated.status == "DEFAULTED"
        assert updated.defaulted_at is not None

    @pytest.mark.parametrize(
        "starting_status", ["DRAFT", "PENDING_APPROVAL", "APPROVED", "COMPLETED"]
    )
    def test_mark_defaulted_rejected_from_non_active_status(
        self, db_session: Session, starting_status: str
    ) -> None:
        company_id = uuid.uuid4()
        contract = _persist_contract(db_session, company_id, status=starting_status)
        svc = _make_service(db_session)

        with pytest.raises(InstallmentIllegalTransitionError):
            svc.mark_defaulted(company_id, contract.id, "reason", uuid.uuid4())
