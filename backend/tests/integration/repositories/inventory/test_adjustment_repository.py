"""Integration tests for AdjustmentRepository.

Tests:
  - Create adjustment
  - get_by_id_or_none (company isolation)
  - list_for_company with status / product / warehouse filters
  - update_status with correct version (succeeds)
  - update_status with wrong version (optimistic lock conflict raises)
  - Soft-delete isolation

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-012
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from modules.inventory.exceptions import InvalidAdjustmentStateTransitionError
from modules.inventory.models.adjustment import InventoryAdjustment
from modules.inventory.repositories.adjustment_repository import AdjustmentRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adj(db: Session, company_id: uuid.UUID, **kwargs) -> InventoryAdjustment:
    defaults = {
        "id": uuid.uuid4(),
        "company_id": company_id,
        "product_id": str(uuid.uuid4()),
        "warehouse_id": str(uuid.uuid4()),
        "movement_type": "ADJUSTMENT_IN",
        "quantity": Decimal("10"),
        "status": "DRAFT",
        "version": 1,
    }
    defaults.update(kwargs)
    adj = InventoryAdjustment(**defaults)
    db.add(adj)
    db.flush()
    return adj


# ---------------------------------------------------------------------------
# Create & get
# ---------------------------------------------------------------------------


class TestAdjustmentRepositoryCreate:
    def test_create_and_get_by_id(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        adj = _make_adj(db_session, cid, movement_type="ADJUSTMENT_OUT")

        found = repo.get_by_id_or_none(company_id=cid, id=adj.id)
        assert found is not None
        assert found.movement_type == "ADJUSTMENT_OUT"
        assert found.status == "DRAFT"
        assert found.version == 1

    def test_get_by_id_wrong_company_returns_none(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        adj = _make_adj(db_session, cid)

        other_company = uuid.uuid4()
        found = repo.get_by_id_or_none(company_id=other_company, id=adj.id)
        assert found is None

    def test_create_stores_all_fields(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        pid = str(uuid.uuid4())
        wid = str(uuid.uuid4())
        adj = _make_adj(
            db_session,
            cid,
            product_id=pid,
            warehouse_id=wid,
            quantity=Decimal("33.5"),
            notes="test note",
            status="DRAFT",
        )

        found = repo.get_by_id_or_none(company_id=cid, id=adj.id)
        assert found is not None
        assert float(found.quantity) == pytest.approx(33.5)
        assert found.notes == "test note"
        assert found.product_id == pid
        assert found.warehouse_id == wid


# ---------------------------------------------------------------------------
# List with filters
# ---------------------------------------------------------------------------


class TestAdjustmentRepositoryList:
    def test_list_for_company_returns_all(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        _make_adj(db_session, cid)
        _make_adj(db_session, cid)
        _make_adj(db_session, cid)

        results = repo.list_for_company(company_id=cid)
        assert len(results) == 3

    def test_list_excludes_other_companies(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid1 = uuid.uuid4()
        cid2 = uuid.uuid4()
        _make_adj(db_session, cid1)
        _make_adj(db_session, cid2)
        _make_adj(db_session, cid2)

        results = repo.list_for_company(company_id=cid1)
        assert len(results) == 1

    def test_list_filter_by_status(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        _make_adj(db_session, cid, status="DRAFT")
        _make_adj(db_session, cid, status="PENDING_APPROVAL")
        _make_adj(db_session, cid, status="APPROVED")

        drafts = repo.list_for_company(company_id=cid, status="DRAFT")
        assert len(drafts) == 1
        assert drafts[0].status == "DRAFT"

        pending = repo.list_for_company(company_id=cid, status="PENDING_APPROVAL")
        assert len(pending) == 1

    def test_list_filter_by_product(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        pid = uuid.uuid4()
        _make_adj(db_session, cid, product_id=str(pid))
        _make_adj(db_session, cid, product_id=str(uuid.uuid4()))

        results = repo.list_for_company(company_id=cid, product_id=pid)
        assert len(results) == 1
        assert results[0].product_id == str(pid)

    def test_list_filter_by_warehouse(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        wid = uuid.uuid4()
        _make_adj(db_session, cid, warehouse_id=str(wid))
        _make_adj(db_session, cid, warehouse_id=str(uuid.uuid4()))
        _make_adj(db_session, cid, warehouse_id=str(uuid.uuid4()))

        results = repo.list_for_company(company_id=cid, warehouse_id=wid)
        assert len(results) == 1
        assert results[0].warehouse_id == str(wid)

    def test_list_respects_pagination(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        for _ in range(5):
            _make_adj(db_session, cid)

        page1 = repo.list_for_company(company_id=cid, limit=3, offset=0)
        page2 = repo.list_for_company(company_id=cid, limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 2


# ---------------------------------------------------------------------------
# update_status (optimistic lock)
# ---------------------------------------------------------------------------


class TestAdjustmentRepositoryUpdateStatus:
    def test_update_status_success(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        adj = _make_adj(db_session, cid, status="DRAFT", version=1)

        updated = repo.update_status(
            adjustment_id=adj.id,
            company_id=cid,
            expected_version=1,
            new_status="PENDING_APPROVAL",
            submitted_by=str(uuid.uuid4()),
        )
        assert updated.status == "PENDING_APPROVAL"
        assert updated.version == 2

    def test_update_status_increments_version(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        adj = _make_adj(db_session, cid, status="DRAFT", version=1)

        updated = repo.update_status(
            adjustment_id=adj.id,
            company_id=cid,
            expected_version=1,
            new_status="PENDING_APPROVAL",
        )
        assert updated.version == 2

    def test_update_status_wrong_version_raises(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        adj = _make_adj(db_session, cid, status="DRAFT", version=1)

        with pytest.raises(InvalidAdjustmentStateTransitionError):
            repo.update_status(
                adjustment_id=adj.id,
                company_id=cid,
                expected_version=99,  # wrong version
                new_status="PENDING_APPROVAL",
            )

    def test_update_status_wrong_company_raises(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        adj = _make_adj(db_session, cid, status="DRAFT", version=1)

        with pytest.raises(InvalidAdjustmentStateTransitionError):
            repo.update_status(
                adjustment_id=adj.id,
                company_id=uuid.uuid4(),  # wrong company
                expected_version=1,
                new_status="PENDING_APPROVAL",
            )

    def test_concurrent_double_approve_second_fails(self, db_session: Session):
        """Simulate optimistic lock: both tries use version=1; only first wins."""
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        actor_a = str(uuid.uuid4())
        adj = _make_adj(db_session, cid, status="PENDING_APPROVAL", version=2)

        # First approve succeeds
        repo.update_status(
            adjustment_id=adj.id,
            company_id=cid,
            expected_version=2,
            new_status="APPROVED",
            approved_by=actor_a,
        )

        # Second approve (same original version) must fail
        with pytest.raises(InvalidAdjustmentStateTransitionError):
            repo.update_status(
                adjustment_id=adj.id,
                company_id=cid,
                expected_version=2,  # stale version
                new_status="APPROVED",
                approved_by=str(uuid.uuid4()),
            )

    def test_extra_fields_stored(self, db_session: Session):
        repo = AdjustmentRepository(db_session)
        cid = uuid.uuid4()
        adj = _make_adj(db_session, cid, status="PENDING_APPROVAL", version=2)
        approver = str(uuid.uuid4())
        ref_id = str(uuid.uuid4())

        updated = repo.update_status(
            adjustment_id=adj.id,
            company_id=cid,
            expected_version=2,
            new_status="APPROVED",
            approved_by=approver,
            new_quantity=Decimal("85"),
            reference_movement_id=ref_id,
        )
        assert updated.approved_by == approver
        assert float(updated.new_quantity) == pytest.approx(85.0)
        assert updated.reference_movement_id == ref_id
