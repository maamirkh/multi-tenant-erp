"""Repositories for the Phase 3 Approval Engine entities.

Covers:
  ApprovalMatrixRepository  — CRUD + active-matrix lookup
  MatrixRuleRepository      — CRUD + rules-for-matrix lookup
  ApprovalLevelRepository   — CRUD + levels-for-rule lookup
  ApprovalRecordRepository  — INSERT only (append-only audit trail)
  ApprovalDelegateRepository — CRUD + active-delegation lookup

All repositories enforce company_id isolation via BasePurchaseRepository.
ApprovalRecordRepository intentionally omits update/delete — records are immutable.

Spec ref: specs/006-purchase-management/data-model.md §Approval Aggregate
Task: T086
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from modules.purchase.models.approval import (
    ApprovalDelegate,
    ApprovalLevel,
    ApprovalMatrix,
    ApprovalRecord,
    MatrixRule,
)
from modules.purchase.repositories import BasePurchaseRepository

# ---------------------------------------------------------------------------
# ApprovalMatrixRepository
# ---------------------------------------------------------------------------


class ApprovalMatrixRepository(BasePurchaseRepository[ApprovalMatrix]):
    """Data-access layer for the ``approval_matrices`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ApprovalMatrix)

    def get_active_for_document_type(
        self, company_id: UUID, document_type: str
    ) -> ApprovalMatrix | None:
        """Return the active matrix for a company+document_type pair, or None."""
        stmt = (
            select(ApprovalMatrix)
            .where(ApprovalMatrix.company_id == company_id)
            .where(ApprovalMatrix.document_type == document_type)
            .where(ApprovalMatrix.is_active == True)  # noqa: E712
            .where(ApprovalMatrix.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_company(self, company_id: UUID) -> list[ApprovalMatrix]:
        """Return all non-deleted matrices for a company."""
        stmt = (
            select(ApprovalMatrix)
            .where(ApprovalMatrix.company_id == company_id)
            .where(ApprovalMatrix.is_deleted == False)  # noqa: E712
            .order_by(ApprovalMatrix.document_type, ApprovalMatrix.name)
        )
        return list(self.db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# MatrixRuleRepository
# ---------------------------------------------------------------------------


class MatrixRuleRepository(BasePurchaseRepository[MatrixRule]):
    """Data-access layer for the ``matrix_rules`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=MatrixRule)

    def list_for_matrix(self, company_id: UUID, matrix_id: UUID) -> list[MatrixRule]:
        """Return all non-deleted rules for a matrix, ordered by approval_level."""
        stmt = (
            select(MatrixRule)
            .where(MatrixRule.company_id == company_id)
            .where(MatrixRule.matrix_id == str(matrix_id))
            .where(MatrixRule.is_deleted == False)  # noqa: E712
            .order_by(MatrixRule.approval_level, MatrixRule.created_at)
        )
        return list(self.db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# ApprovalLevelRepository
# ---------------------------------------------------------------------------


class ApprovalLevelRepository(BasePurchaseRepository[ApprovalLevel]):
    """Data-access layer for the ``approval_levels`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ApprovalLevel)

    def list_for_rule(self, company_id: UUID, rule_id: UUID) -> list[ApprovalLevel]:
        """Return all non-deleted approval levels for a rule, ordered by level_number."""
        stmt = (
            select(ApprovalLevel)
            .where(ApprovalLevel.company_id == company_id)
            .where(ApprovalLevel.rule_id == str(rule_id))
            .where(ApprovalLevel.is_deleted == False)  # noqa: E712
            .order_by(ApprovalLevel.level_number)
        )
        return list(self.db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# ApprovalRecordRepository  — append-only (no update / no delete)
# ---------------------------------------------------------------------------


class ApprovalRecordRepository(BasePurchaseRepository[ApprovalRecord]):
    """Append-only data-access layer for the ``approval_records`` table.

    This repository intentionally OMITS ``update`` and soft-delete operations.
    Once an ApprovalRecord is written it is immutable.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ApprovalRecord)

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def list_for_document(
        self,
        company_id: UUID,
        document_type: str,
        document_id: UUID,
    ) -> list[ApprovalRecord]:
        """Return all approval records for a specific document, ordered by time."""
        stmt = (
            select(ApprovalRecord)
            .where(ApprovalRecord.company_id == company_id)
            .where(ApprovalRecord.document_type == document_type)
            .where(ApprovalRecord.document_id == str(document_id))
            .order_by(ApprovalRecord.actioned_at, ApprovalRecord.level_number)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_for_document_level(
        self,
        company_id: UUID,
        document_type: str,
        document_id: UUID,
        level_number: int,
    ) -> list[ApprovalRecord]:
        """Return approval records for a specific document+level combination."""
        stmt = (
            select(ApprovalRecord)
            .where(ApprovalRecord.company_id == company_id)
            .where(ApprovalRecord.document_type == document_type)
            .where(ApprovalRecord.document_id == str(document_id))
            .where(ApprovalRecord.level_number == level_number)
            .order_by(ApprovalRecord.actioned_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Immutability guard — override mutating base methods to raise
    # ------------------------------------------------------------------

    def update(self, entity: ApprovalRecord) -> ApprovalRecord:
        raise NotImplementedError(
            "ApprovalRecord is immutable — updates are forbidden."
        )

    def soft_delete(self, id: UUID, company_id: UUID) -> None:
        raise NotImplementedError(
            "ApprovalRecord is immutable — deletes are forbidden."
        )


# ---------------------------------------------------------------------------
# ApprovalDelegateRepository
# ---------------------------------------------------------------------------


class ApprovalDelegateRepository(BasePurchaseRepository[ApprovalDelegate]):
    """Data-access layer for the ``approval_delegates`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ApprovalDelegate)

    def get_active_delegation(
        self,
        company_id: UUID,
        delegator_id: UUID,
        document_type: str | None,
        as_of: datetime,
    ) -> ApprovalDelegate | None:
        """Return an active delegation for a delegator that covers the given document_type.

        Checks:
          - is_active = True
          - is_deleted = False
          - valid_from <= as_of <= valid_until
          - document_type matches OR delegation applies to all (document_type IS NULL)
        """
        stmt = (
            select(ApprovalDelegate)
            .where(ApprovalDelegate.company_id == company_id)
            .where(ApprovalDelegate.delegator_id == str(delegator_id))
            .where(ApprovalDelegate.is_active == True)  # noqa: E712
            .where(ApprovalDelegate.is_deleted == False)  # noqa: E712
            .where(ApprovalDelegate.valid_from <= as_of)
            .where(ApprovalDelegate.valid_until >= as_of)
            .where(
                and_(
                    ApprovalDelegate.document_type.is_(None)
                    | (ApprovalDelegate.document_type == document_type)
                )
            )
            .order_by(ApprovalDelegate.document_type.desc().nulls_last())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_delegator(
        self, company_id: UUID, delegator_id: UUID
    ) -> list[ApprovalDelegate]:
        """Return all non-deleted delegations for a delegator."""
        stmt = (
            select(ApprovalDelegate)
            .where(ApprovalDelegate.company_id == company_id)
            .where(ApprovalDelegate.delegator_id == str(delegator_id))
            .where(ApprovalDelegate.is_deleted == False)  # noqa: E712
            .order_by(ApprovalDelegate.valid_from.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_for_delegate(
        self, company_id: UUID, delegate_id: UUID
    ) -> list[ApprovalDelegate]:
        """Return all non-deleted delegations granted to a delegate."""
        stmt = (
            select(ApprovalDelegate)
            .where(ApprovalDelegate.company_id == company_id)
            .where(ApprovalDelegate.delegate_id == str(delegate_id))
            .where(ApprovalDelegate.is_deleted == False)  # noqa: E712
            .order_by(ApprovalDelegate.valid_from.desc())
        )
        return list(self.db.execute(stmt).scalars().all())
