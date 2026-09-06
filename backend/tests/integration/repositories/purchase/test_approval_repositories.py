"""Integration tests for Phase 3 Approval Engine repositories — T095.

Tests:
  - ApprovalMatrixRepository: CRUD, active-matrix lookup, company isolation
  - MatrixRuleRepository: CRUD, list_for_matrix
  - ApprovalLevelRepository: CRUD, list_for_rule
  - ApprovalRecordRepository: append-only invariant, list/get helpers
  - ApprovalDelegateRepository: CRUD, active-delegation lookup

All tests run against SQLite in-memory DB.

Task: T095
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from modules.purchase.models.approval import (
    ApprovalDelegate,
    ApprovalLevel,
    ApprovalMatrix,
    ApprovalRecord,
    MatrixRule,
)
from modules.purchase.repositories.approval import (
    ApprovalDelegateRepository,
    ApprovalLevelRepository,
    ApprovalMatrixRepository,
    ApprovalRecordRepository,
    MatrixRuleRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def _add_matrix(
    db: Session,
    company_id: UUID,
    document_type: str = "PURCHASE_REQUEST",
    name: str = "Test Matrix",
    is_active: bool = True,
) -> ApprovalMatrix:
    m = ApprovalMatrix(
        company_id=company_id,
        document_type=document_type,
        name=name,
        is_active=is_active,
    )
    db.add(m)
    db.flush()
    return m


def _add_rule(
    db: Session,
    company_id: UUID,
    matrix_id: UUID,
    condition_type: str = "ALWAYS",
) -> MatrixRule:
    r = MatrixRule(
        company_id=company_id,
        matrix_id=str(matrix_id),
        condition_type=condition_type,
        approval_level=1,
        approval_mode="SEQUENTIAL",
    )
    db.add(r)
    db.flush()
    return r


def _add_level(
    db: Session,
    company_id: UUID,
    rule_id: UUID,
    level_number: int = 1,
    approver_type: str = "ROLE",
    approver_role: str = "PURCHASE_MANAGER",
) -> ApprovalLevel:
    lv = ApprovalLevel(
        company_id=company_id,
        rule_id=str(rule_id),
        level_number=level_number,
        approver_type=approver_type,
        approver_role=approver_role,
        escalation_days=3,
    )
    db.add(lv)
    db.flush()
    return lv


def _add_record(
    db: Session,
    company_id: UUID,
    document_type: str = "PURCHASE_REQUEST",
    document_id: UUID | None = None,
    level_number: int = 1,
    action: str = "APPROVED",
) -> ApprovalRecord:
    rec = ApprovalRecord(
        company_id=company_id,
        document_type=document_type,
        document_id=str(document_id or uuid4()),
        level_number=level_number,
        approver_id=str(uuid4()),
        action=action,
        is_emergency_bypass=False,
        actioned_at=_now(),
    )
    db.add(rec)
    db.flush()
    return rec


def _add_delegate(
    db: Session,
    company_id: UUID,
    delegator_id: UUID,
    delegate_id: UUID,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
    document_type: str | None = None,
    is_active: bool = True,
) -> ApprovalDelegate:
    now = _now()
    d = ApprovalDelegate(
        company_id=company_id,
        delegator_id=str(delegator_id),
        delegate_id=str(delegate_id),
        valid_from=valid_from or (now - timedelta(days=1)),
        valid_until=valid_until or (now + timedelta(days=7)),
        document_type=document_type,
        is_active=is_active,
    )
    db.add(d)
    db.flush()
    return d


# ===========================================================================
# ApprovalMatrixRepository
# ===========================================================================


class TestApprovalMatrixRepository:
    def test_create_and_get(self, db_session: Session):
        cid = uuid4()
        m = _add_matrix(db_session, cid)
        repo = ApprovalMatrixRepository(db_session)
        fetched = repo.get_by_id_or_none(id=m.id, company_id=cid)
        assert fetched is not None
        assert fetched.document_type == "PURCHASE_REQUEST"

    def test_get_active_for_document_type(self, db_session: Session):
        cid = uuid4()
        _add_matrix(db_session, cid, document_type="PURCHASE_ORDER", is_active=False)
        active = _add_matrix(
            db_session, cid, document_type="PURCHASE_REQUEST", is_active=True
        )
        repo = ApprovalMatrixRepository(db_session)
        result = repo.get_active_for_document_type(
            company_id=cid, document_type="PURCHASE_REQUEST"
        )
        assert result is not None
        assert result.id == active.id

    def test_get_active_returns_none_when_inactive(self, db_session: Session):
        cid = uuid4()
        _add_matrix(db_session, cid, is_active=False)
        repo = ApprovalMatrixRepository(db_session)
        result = repo.get_active_for_document_type(
            company_id=cid, document_type="PURCHASE_REQUEST"
        )
        assert result is None

    def test_list_for_company(self, db_session: Session):
        cid = uuid4()
        _add_matrix(db_session, cid, document_type="PURCHASE_REQUEST")
        _add_matrix(db_session, cid, document_type="PURCHASE_ORDER")
        other_cid = uuid4()
        _add_matrix(db_session, other_cid, document_type="PURCHASE_REQUEST")

        repo = ApprovalMatrixRepository(db_session)
        results = repo.list_for_company(company_id=cid)
        assert len(results) == 2

    def test_soft_delete(self, db_session: Session):
        cid = uuid4()
        m = _add_matrix(db_session, cid)
        repo = ApprovalMatrixRepository(db_session)
        repo.soft_delete(id=m.id, company_id=cid)
        fetched = repo.get_by_id_or_none(id=m.id, company_id=cid)
        assert fetched is None  # get_by_id_or_none filters is_deleted


# ===========================================================================
# MatrixRuleRepository
# ===========================================================================


class TestMatrixRuleRepository:
    def test_create_and_list_for_matrix(self, db_session: Session):
        cid = uuid4()
        matrix = _add_matrix(db_session, cid)
        _add_rule(db_session, cid, matrix.id, condition_type="ALWAYS")
        _add_rule(db_session, cid, matrix.id, condition_type="AMOUNT_RANGE")

        repo = MatrixRuleRepository(db_session)
        rules = repo.list_for_matrix(company_id=cid, matrix_id=matrix.id)
        assert len(rules) == 2

    def test_company_isolation(self, db_session: Session):
        cid1 = uuid4()
        cid2 = uuid4()
        matrix1 = _add_matrix(db_session, cid1)
        matrix2 = _add_matrix(db_session, cid2)
        _add_rule(db_session, cid1, matrix1.id)
        _add_rule(db_session, cid2, matrix2.id)

        repo = MatrixRuleRepository(db_session)
        rules = repo.list_for_matrix(company_id=cid1, matrix_id=matrix1.id)
        assert len(rules) == 1


# ===========================================================================
# ApprovalLevelRepository
# ===========================================================================


class TestApprovalLevelRepository:
    def test_create_and_list_for_rule(self, db_session: Session):
        cid = uuid4()
        matrix = _add_matrix(db_session, cid)
        rule = _add_rule(db_session, cid, matrix.id)
        _add_level(db_session, cid, rule.id, level_number=1)
        _add_level(db_session, cid, rule.id, level_number=2)

        repo = ApprovalLevelRepository(db_session)
        levels = repo.list_for_rule(company_id=cid, rule_id=rule.id)
        assert len(levels) == 2
        assert levels[0].level_number == 1
        assert levels[1].level_number == 2

    def test_company_isolation(self, db_session: Session):
        cid1 = uuid4()
        cid2 = uuid4()
        matrix1 = _add_matrix(db_session, cid1)
        matrix2 = _add_matrix(db_session, cid2)
        rule1 = _add_rule(db_session, cid1, matrix1.id)
        rule2 = _add_rule(db_session, cid2, matrix2.id)
        _add_level(db_session, cid1, rule1.id)
        _add_level(db_session, cid2, rule2.id)

        repo = ApprovalLevelRepository(db_session)
        levels = repo.list_for_rule(company_id=cid1, rule_id=rule1.id)
        assert len(levels) == 1


# ===========================================================================
# ApprovalRecordRepository
# ===========================================================================


class TestApprovalRecordRepository:
    def test_create_and_list_for_document(self, db_session: Session):
        cid = uuid4()
        doc_id = uuid4()
        _add_record(db_session, cid, document_id=doc_id, level_number=1)
        _add_record(db_session, cid, document_id=doc_id, level_number=2)

        repo = ApprovalRecordRepository(db_session)
        records = repo.list_for_document(
            company_id=cid, document_type="PURCHASE_REQUEST", document_id=doc_id
        )
        assert len(records) == 2

    def test_get_for_document_level(self, db_session: Session):
        cid = uuid4()
        doc_id = uuid4()
        _add_record(
            db_session, cid, document_id=doc_id, level_number=1, action="APPROVED"
        )
        _add_record(
            db_session, cid, document_id=doc_id, level_number=2, action="APPROVED"
        )

        repo = ApprovalRecordRepository(db_session)
        records = repo.get_for_document_level(
            company_id=cid,
            document_type="PURCHASE_REQUEST",
            document_id=doc_id,
            level_number=1,
        )
        assert len(records) == 1
        assert records[0].action == "APPROVED"

    def test_update_raises(self, db_session: Session):
        repo = ApprovalRecordRepository(db_session)
        with pytest.raises(NotImplementedError):
            repo.update(ApprovalRecord())

    def test_soft_delete_raises(self, db_session: Session):
        cid = uuid4()
        repo = ApprovalRecordRepository(db_session)
        with pytest.raises(NotImplementedError):
            repo.soft_delete(id=uuid4(), company_id=cid)

    def test_company_isolation(self, db_session: Session):
        cid1 = uuid4()
        cid2 = uuid4()
        doc_id = uuid4()
        _add_record(db_session, cid1, document_id=doc_id)
        _add_record(db_session, cid2, document_id=doc_id)

        repo = ApprovalRecordRepository(db_session)
        records = repo.list_for_document(
            company_id=cid1, document_type="PURCHASE_REQUEST", document_id=doc_id
        )
        assert len(records) == 1


# ===========================================================================
# ApprovalDelegateRepository
# ===========================================================================


class TestApprovalDelegateRepository:
    def test_create_and_list_for_delegator(self, db_session: Session):
        cid = uuid4()
        delegator_id = uuid4()
        delegate_id = uuid4()
        _add_delegate(db_session, cid, delegator_id, delegate_id)

        repo = ApprovalDelegateRepository(db_session)
        delegations = repo.list_for_delegator(company_id=cid, delegator_id=delegator_id)
        assert len(delegations) == 1

    def test_get_active_delegation_success(self, db_session: Session):
        cid = uuid4()
        delegator_id = uuid4()
        delegate_id = uuid4()
        _add_delegate(db_session, cid, delegator_id, delegate_id)

        repo = ApprovalDelegateRepository(db_session)
        result = repo.get_active_delegation(
            company_id=cid,
            delegator_id=delegator_id,
            document_type="PURCHASE_REQUEST",
            as_of=_now(),
        )
        assert result is not None
        assert result.delegate_id == str(delegate_id)

    def test_get_active_delegation_expired(self, db_session: Session):
        """No delegation returned when window has expired."""
        cid = uuid4()
        delegator_id = uuid4()
        delegate_id = uuid4()
        past_from = _now() - timedelta(days=10)
        past_until = _now() - timedelta(days=5)
        _add_delegate(
            db_session,
            cid,
            delegator_id,
            delegate_id,
            valid_from=past_from,
            valid_until=past_until,
        )

        repo = ApprovalDelegateRepository(db_session)
        result = repo.get_active_delegation(
            company_id=cid,
            delegator_id=delegator_id,
            document_type="PURCHASE_REQUEST",
            as_of=_now(),
        )
        assert result is None

    def test_get_active_delegation_inactive(self, db_session: Session):
        """No delegation returned when is_active=False."""
        cid = uuid4()
        delegator_id = uuid4()
        delegate_id = uuid4()
        _add_delegate(db_session, cid, delegator_id, delegate_id, is_active=False)

        repo = ApprovalDelegateRepository(db_session)
        result = repo.get_active_delegation(
            company_id=cid,
            delegator_id=delegator_id,
            document_type="PURCHASE_REQUEST",
            as_of=_now(),
        )
        assert result is None

    def test_universal_delegation_matches_any_document_type(self, db_session: Session):
        """Universal delegation (document_type=None) matches any document type."""
        cid = uuid4()
        delegator_id = uuid4()
        delegate_id = uuid4()
        _add_delegate(db_session, cid, delegator_id, delegate_id, document_type=None)

        repo = ApprovalDelegateRepository(db_session)
        result = repo.get_active_delegation(
            company_id=cid,
            delegator_id=delegator_id,
            document_type="PURCHASE_ORDER",
            as_of=_now(),
        )
        assert result is not None

    def test_company_isolation(self, db_session: Session):
        cid1 = uuid4()
        cid2 = uuid4()
        delegator_id = uuid4()
        _add_delegate(db_session, cid1, delegator_id, uuid4())
        _add_delegate(db_session, cid2, delegator_id, uuid4())

        repo = ApprovalDelegateRepository(db_session)
        delegations = repo.list_for_delegator(
            company_id=cid1, delegator_id=delegator_id
        )
        assert len(delegations) == 1
