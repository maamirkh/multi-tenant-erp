"""Repositories for General Ledger entities — Phase 4 (CRITICAL).

  JournalEntryRepository     — the aggregate root (soft-delete capable via
                                ``BaseAccountingRepository``, though nothing
                                in this phase deletes a journal entry)
  JournalLineRepository      — append-only: ``create`` + read only, no
                                ``update``/``delete`` path exists (mirrors
                                ``CompanyAuditLogRepository``'s pattern)
  JournalApprovalRepository  — one row per approve/reject decision
  AccountingAuditLogRepository — append-only immutable audit trail
  GLReportRepository         — read-optimized GL/trial-balance queries
                                (only ``JournalEntry.status == 'POSTED'``
                                rows ever count towards a balance)

Write methods on the append-only repositories use ``flush()`` (not
``commit()``) so ``PostingEngine`` can compose entry + lines + audit log
into a single atomic transaction (research.md Decision 11 — the audit
write and the action it records must commit together or not at all).

Spec ref: specs/008-accounting-finance/tasks.md T096, T097
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import false, func, select, true, tuple_
from sqlalchemy.orm import Session

from modules.accounting.models.coa import Account, AccountGroup
from modules.accounting.models.gl import (
    AccountingAuditLog,
    JournalApproval,
    JournalEntry,
    JournalLine,
)
from modules.accounting.repositories import BaseAccountingRepository


class JournalEntryRepository(BaseAccountingRepository[JournalEntry]):
    """Data-access layer for the ``accounting_journal_entries`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=JournalEntry)

    def find_by_number(
        self, company_id: UUID, journal_number: str
    ) -> JournalEntry | None:
        stmt = (
            select(JournalEntry)
            .where(JournalEntry.company_id == company_id)
            .where(JournalEntry.journal_number == journal_number)
            .where(JournalEntry.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def find_by_source_document(
        self, company_id: UUID, source_document_type: str, source_document_id: UUID
    ) -> list[JournalEntry]:
        stmt = (
            select(JournalEntry)
            .where(JournalEntry.company_id == company_id)
            .where(JournalEntry.source_document_type == source_document_type)
            .where(JournalEntry.source_document_id == source_document_id)
            .where(JournalEntry.is_deleted == False)  # noqa: E712
            .order_by(JournalEntry.posting_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_by_status(self, company_id: UUID, status: str) -> list[JournalEntry]:
        stmt = (
            select(JournalEntry)
            .where(JournalEntry.company_id == company_id)
            .where(JournalEntry.status == status)
            .where(JournalEntry.is_deleted == False)  # noqa: E712
            .order_by(JournalEntry.posting_date.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def search(
        self,
        company_id: UUID,
        filters: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[JournalEntry], int]:
        """Filter by date range/account (via line join)/period/source/reference/status.

        Supported filter keys: ``start_date``, ``end_date``, ``account_id``,
        ``fiscal_period_id``, ``posting_source``, ``reference``, ``status``,
        ``cost_center_id``.
        """
        filters = filters or {}
        stmt = (
            select(JournalEntry)
            .where(JournalEntry.company_id == company_id)
            .where(JournalEntry.is_deleted == False)  # noqa: E712
        )

        if start_date := filters.get("start_date"):
            stmt = stmt.where(JournalEntry.posting_date >= start_date)
        if end_date := filters.get("end_date"):
            stmt = stmt.where(JournalEntry.posting_date <= end_date)
        if fiscal_period_id := filters.get("fiscal_period_id"):
            stmt = stmt.where(JournalEntry.fiscal_period_id == fiscal_period_id)
        if posting_source := filters.get("posting_source"):
            stmt = stmt.where(JournalEntry.posting_source == posting_source)
        if reference := filters.get("reference"):
            stmt = stmt.where(JournalEntry.reference.ilike(f"%{reference}%"))
        if status := filters.get("status"):
            stmt = stmt.where(JournalEntry.status == status)

        account_id = filters.get("account_id")
        cost_center_id = filters.get("cost_center_id")
        if account_id or cost_center_id:
            line_stmt = select(JournalLine.journal_entry_id).where(
                JournalLine.company_id == company_id
            )
            if account_id:
                line_stmt = line_stmt.where(JournalLine.account_id == account_id)
            if cost_center_id:
                line_stmt = line_stmt.where(
                    JournalLine.cost_center_id == cost_center_id
                )
            stmt = stmt.where(JournalEntry.id.in_(line_stmt))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = self.db.execute(count_stmt).scalar_one()

        rows_stmt = (
            stmt.order_by(JournalEntry.posting_date.desc()).offset(skip).limit(limit)
        )
        items = list(self.db.execute(rows_stmt).scalars().all())
        return items, total


class JournalLineRepository:
    """Append-only data access for the ``accounting_journal_lines`` table.

    NO ``update``/``delete`` methods exist — see models/gl.py docstring.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, line: JournalLine) -> JournalLine:
        """Stage a new line for insert. Caller commits (see module docstring)."""
        self.db.add(line)
        self.db.flush()
        return line

    def find_by_journal_entry(self, journal_entry_id: UUID) -> list[JournalLine]:
        stmt = (
            select(JournalLine)
            .where(JournalLine.journal_entry_id == journal_entry_id)
            .order_by(JournalLine.line_number)
        )
        return list(self.db.execute(stmt).scalars().all())


class JournalApprovalRepository(BaseAccountingRepository[JournalApproval]):
    """Data-access layer for the ``accounting_journal_approvals`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=JournalApproval)

    def find_by_journal_entry(self, journal_entry_id: UUID) -> list[JournalApproval]:
        stmt = (
            select(JournalApproval)
            .where(JournalApproval.journal_entry_id == journal_entry_id)
            .where(JournalApproval.is_deleted == False)  # noqa: E712
            .order_by(JournalApproval.created_at)
        )
        return list(self.db.execute(stmt).scalars().all())


class AccountingAuditLogRepository:
    """Append-only data access for the ``accounting_audit_log`` table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, log: AccountingAuditLog) -> AccountingAuditLog:
        """Stage a new audit record for insert. Caller commits."""
        self.db.add(log)
        self.db.flush()
        return log

    def list_for_entity(
        self, company_id: UUID, entity_type: str, entity_id: UUID
    ) -> list[AccountingAuditLog]:
        stmt = (
            select(AccountingAuditLog)
            .where(AccountingAuditLog.company_id == company_id)
            .where(AccountingAuditLog.entity_type == entity_type)
            .where(AccountingAuditLog.entity_id == entity_id)
            .order_by(AccountingAuditLog.occurred_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_filtered(
        self,
        company_id: UUID,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        actor_user_id: UUID | None = None,
        action: str | None = None,
        date_from: Any | None = None,
        date_to: Any | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AccountingAuditLog], int]:
        """Filtered, paginated audit-log query (T279) — newest first.

        Returns ``(rows, total_count)`` so the API layer can expose
        pagination metadata without a second round trip from the caller.
        """
        conditions = [AccountingAuditLog.company_id == company_id]
        if entity_type is not None:
            conditions.append(AccountingAuditLog.entity_type == entity_type)
        if entity_id is not None:
            conditions.append(AccountingAuditLog.entity_id == entity_id)
        if actor_user_id is not None:
            conditions.append(AccountingAuditLog.actor_user_id == actor_user_id)
        if action is not None:
            conditions.append(AccountingAuditLog.action == action)
        if date_from is not None:
            conditions.append(AccountingAuditLog.occurred_at >= date_from)
        if date_to is not None:
            conditions.append(AccountingAuditLog.occurred_at <= date_to)

        count_stmt = (
            select(func.count()).select_from(AccountingAuditLog).where(*conditions)
        )
        total = self.db.execute(count_stmt).scalar_one()

        stmt = (
            select(AccountingAuditLog)
            .where(*conditions)
            .order_by(AccountingAuditLog.occurred_at.desc())
            .offset(skip)
            .limit(limit)
        )
        rows = list(self.db.execute(stmt).scalars().all())
        return rows, total


class GLReportRepository:
    """Read-optimized queries over posted GL lines (data-model.md §11).

    Every method restricts to ``JournalEntry.status == 'POSTED'`` — only
    posted entries are part of the General Ledger; drafts, submitted, and
    rejected entries never contribute to a balance.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def trial_balance_query(
        self, company_id: UUID, fiscal_period_id: UUID
    ) -> list[dict[str, Any]]:
        """Return SUM(debit)/SUM(credit) per account for a fiscal period."""
        stmt = (
            select(
                JournalLine.account_id,
                JournalLine.account_code,
                func.sum(JournalLine.debit_amount_base).label("total_debit"),
                func.sum(JournalLine.credit_amount_base).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .where(JournalEntry.company_id == company_id)
            .where(JournalEntry.fiscal_period_id == fiscal_period_id)
            .where(JournalEntry.status == "POSTED")
            .group_by(JournalLine.account_id, JournalLine.account_code)
            .order_by(JournalLine.account_code)
        )
        rows = self.db.execute(stmt).all()
        return [
            {
                "account_id": r.account_id,
                "account_code": r.account_code,
                "total_debit": r.total_debit or Decimal("0"),
                "total_credit": r.total_credit or Decimal("0"),
            }
            for r in rows
        ]

    def gl_detail_query(
        self,
        company_id: UUID,
        account_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        cost_center_id: UUID | None = None,
        fiscal_period_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return posted GL lines with parent-entry context, filtered/paginated."""
        base = (
            select(JournalLine, JournalEntry)
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .where(JournalEntry.company_id == company_id)
            .where(JournalEntry.status == "POSTED")
        )
        if account_id is not None:
            base = base.where(JournalLine.account_id == account_id)
        if cost_center_id is not None:
            base = base.where(JournalLine.cost_center_id == cost_center_id)
        if fiscal_period_id is not None:
            base = base.where(JournalEntry.fiscal_period_id == fiscal_period_id)
        if start_date is not None:
            base = base.where(JournalEntry.posting_date >= start_date)
        if end_date is not None:
            base = base.where(JournalEntry.posting_date <= end_date)

        count_stmt = select(func.count()).select_from(base.subquery())
        total: int = self.db.execute(count_stmt).scalar_one()

        rows_stmt = (
            base.order_by(JournalEntry.posting_date.desc(), JournalLine.line_number)
            .offset(skip)
            .limit(limit)
        )
        rows = self.db.execute(rows_stmt).all()
        items = [
            {
                "journal_entry_id": entry.id,
                "journal_number": entry.journal_number,
                "posting_date": entry.posting_date,
                "account_id": line.account_id,
                "account_code": line.account_code,
                "line_number": line.line_number,
                "debit_amount": line.debit_amount_base,
                "credit_amount": line.credit_amount_base,
                "description": line.description,
                "reference": line.reference,
                "source_document_type": entry.source_document_type,
                "source_document_id": entry.source_document_id,
                "cost_center_id": line.cost_center_id,
            }
            for line, entry in rows
        ]
        return items, total

    def gl_detail_cursor_query(
        self,
        company_id: UUID,
        account_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        cost_center_id: UUID | None = None,
        fiscal_period_id: UUID | None = None,
        cursor: tuple[date, UUID, int] | None = None,
        limit: int = 100,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Keyset (cursor) paginated GL detail query — Phase 13, T256.

        Unlike ``gl_detail_query()`` (Phase 4, ``OFFSET``-based — fine for
        small interactive pages but O(N) per page at scale), this walks the
        ledger chronologically forward using a composite keyset cursor of
        ``(posting_date, journal_entry_id, line_number)`` — the same triplet
        ``gl_detail_query`` already sorts by, so results are consistent
        between the two. Chosen (ascending, oldest-first) for bulk/audit
        export use cases distinct from the offset endpoint's
        recent-first interactive default; see report_service.py.

        Returns ``(rows, has_more)`` — the caller derives the next cursor
        from the last row's own ``(posting_date, journal_entry_id,
        line_number)`` rather than a server-generated opaque token, keeping
        the row shape identical to ``gl_detail_query()``'s.
        """
        base = (
            select(JournalLine, JournalEntry)
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .where(JournalEntry.company_id == company_id)
            .where(JournalEntry.status == "POSTED")
        )
        if account_id is not None:
            base = base.where(JournalLine.account_id == account_id)
        if cost_center_id is not None:
            base = base.where(JournalLine.cost_center_id == cost_center_id)
        if fiscal_period_id is not None:
            base = base.where(JournalEntry.fiscal_period_id == fiscal_period_id)
        if start_date is not None:
            base = base.where(JournalEntry.posting_date >= start_date)
        if end_date is not None:
            base = base.where(JournalEntry.posting_date <= end_date)
        if cursor is not None:
            cursor_date, cursor_entry_id, cursor_line_number = cursor
            base = base.where(
                tuple_(
                    JournalEntry.posting_date,
                    JournalLine.journal_entry_id,
                    JournalLine.line_number,
                )
                > (cursor_date, cursor_entry_id, cursor_line_number)
            )

        rows_stmt = base.order_by(
            JournalEntry.posting_date,
            JournalLine.journal_entry_id,
            JournalLine.line_number,
        ).limit(limit + 1)
        rows = self.db.execute(rows_stmt).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [
            {
                "journal_entry_id": entry.id,
                "journal_number": entry.journal_number,
                "posting_date": entry.posting_date,
                "account_id": line.account_id,
                "account_code": line.account_code,
                "line_number": line.line_number,
                "debit_amount": line.debit_amount_base,
                "credit_amount": line.credit_amount_base,
                "description": line.description,
                "reference": line.reference,
                "source_document_type": entry.source_document_type,
                "source_document_id": entry.source_document_id,
                "cost_center_id": line.cost_center_id,
            }
            for line, entry in rows
        ]
        return items, has_more

    def working_capital_query(
        self, company_id: UUID, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Per-account debit/credit MOVEMENT (not cumulative balance) within
        a date range, for ASSET/LIABILITY/EQUITY accounts — the raw material
        for the indirect-method Cash Flow statement's working-capital
        adjustment (Phase 13, T255). Excludes cash/bank accounts (their
        movement IS the cash flow being explained, not an adjustment to it).
        """
        stmt = (
            select(
                Account.id.label("account_id"),
                Account.account_code.label("account_code"),
                Account.account_type.label("account_type"),
                func.sum(JournalLine.debit_amount_base).label("total_debit"),
                func.sum(JournalLine.credit_amount_base).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .join(Account, Account.id == JournalLine.account_id)
            .where(JournalEntry.company_id == company_id)
            .where(JournalEntry.status.in_(["POSTED", "REVERSED"]))
            .where(JournalEntry.posting_date >= start_date)
            .where(JournalEntry.posting_date <= end_date)
            .where(Account.account_type.in_(["ASSET", "LIABILITY", "EQUITY"]))
            .where(Account.is_cash_account == false())
            .where(Account.is_bank_account == false())
            .group_by(Account.id, Account.account_code, Account.account_type)
        )
        rows = self.db.execute(stmt).all()
        return [
            {
                "account_id": r.account_id,
                "account_code": r.account_code,
                "account_type": r.account_type,
                "total_debit": r.total_debit or Decimal("0"),
                "total_credit": r.total_credit or Decimal("0"),
            }
            for r in rows
        ]

    def cash_balance_query(self, company_id: UUID, as_of_date: date) -> Decimal:
        """Cumulative balance of every cash/bank account as of ``as_of_date``
        (Phase 13, T255) — the direct-from-GL truth the indirect Cash Flow
        method's derived total must reconcile to (plan.md acceptance
        criterion: "Cash Flow closing balance matches GL cash and bank
        account balances").
        """
        stmt = (
            select(
                func.sum(JournalLine.debit_amount_base).label("total_debit"),
                func.sum(JournalLine.credit_amount_base).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .join(Account, Account.id == JournalLine.account_id)
            .where(JournalEntry.company_id == company_id)
            .where(JournalEntry.status.in_(["POSTED", "REVERSED"]))
            .where(JournalEntry.posting_date <= as_of_date)
            .where(
                (Account.is_cash_account == true())
                | (Account.is_bank_account == true())
            )
        )
        row = self.db.execute(stmt).one()
        total_debit = row.total_debit or Decimal("0")
        total_credit = row.total_credit or Decimal("0")
        return total_debit - total_credit

    def cash_and_bank_account_balances_query(
        self, company_id: UUID, as_of_date: date
    ) -> list[dict[str, Any]]:
        """Per-account cumulative balance for every cash/bank account as of
        ``as_of_date`` (Phase 15, T288 — the Cash Position dashboard
        widget's per-account breakdown). Same account filter as
        ``cash_balance_query()``, grouped by account instead of aggregated
        into one total.
        """
        stmt = (
            select(
                Account.id.label("account_id"),
                Account.account_code.label("account_code"),
                Account.account_name.label("account_name"),
                Account.is_bank_account.label("is_bank_account"),
                Account.is_cash_account.label("is_cash_account"),
                func.sum(JournalLine.debit_amount_base).label("total_debit"),
                func.sum(JournalLine.credit_amount_base).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .join(Account, Account.id == JournalLine.account_id)
            .where(JournalEntry.company_id == company_id)
            .where(JournalEntry.status.in_(["POSTED", "REVERSED"]))
            .where(JournalEntry.posting_date <= as_of_date)
            .where(
                (Account.is_cash_account == true())
                | (Account.is_bank_account == true())
            )
            .group_by(
                Account.id,
                Account.account_code,
                Account.account_name,
                Account.is_bank_account,
                Account.is_cash_account,
            )
            .order_by(Account.account_code)
        )
        rows = self.db.execute(stmt).all()
        return [
            {
                "account_id": r.account_id,
                "account_code": r.account_code,
                "account_name": r.account_name,
                "is_bank_account": r.is_bank_account,
                "is_cash_account": r.is_cash_account,
                "balance": (r.total_debit or Decimal("0"))
                - (r.total_credit or Decimal("0")),
            }
            for r in rows
        ]

    def account_balance_query(
        self,
        company_id: UUID,
        account_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Decimal]:
        """Return SUM(debit)/SUM(credit) for one account over an optional date range.

        Includes REVERSED entries, not just POSTED ones: a reversed entry's
        original effect is real, immutable history (Constitution — "Immutable
        Ledger") — it is only netted out by its separate reversal entry
        (also counted here), never by hiding the original. Excluding
        REVERSED entries would silently drop one leg of every reversal,
        corrupting the balance by the full reversed amount.
        """
        stmt = (
            select(
                func.sum(JournalLine.debit_amount_base).label("total_debit"),
                func.sum(JournalLine.credit_amount_base).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .where(JournalEntry.company_id == company_id)
            .where(JournalLine.account_id == account_id)
            .where(JournalEntry.status.in_(["POSTED", "REVERSED"]))
        )
        if start_date is not None:
            stmt = stmt.where(JournalEntry.posting_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(JournalEntry.posting_date <= end_date)
        row = self.db.execute(stmt).one()
        return {
            "total_debit": row.total_debit or Decimal("0"),
            "total_credit": row.total_credit or Decimal("0"),
        }

    def cost_center_pl_query(
        self,
        company_id: UUID,
        cost_center_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Per-account SUM(debit)/SUM(credit) for REVENUE/EXPENSE accounts
        posted against one cost center (Phase 11 — CostCenterService's
        Cost Center P&L report). Same REVERSED-inclusion rule as
        ``account_balance_query()``.
        """
        stmt = (
            select(
                Account.id.label("account_id"),
                Account.account_code.label("account_code"),
                Account.account_name.label("account_name"),
                Account.account_type.label("account_type"),
                func.sum(JournalLine.debit_amount_base).label("total_debit"),
                func.sum(JournalLine.credit_amount_base).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .join(Account, Account.id == JournalLine.account_id)
            .where(JournalEntry.company_id == company_id)
            .where(JournalLine.cost_center_id == cost_center_id)
            .where(JournalEntry.status.in_(["POSTED", "REVERSED"]))
            .where(Account.account_type.in_(["REVENUE", "EXPENSE"]))
            .group_by(
                Account.id,
                Account.account_code,
                Account.account_name,
                Account.account_type,
            )
        )
        if start_date is not None:
            stmt = stmt.where(JournalEntry.posting_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(JournalEntry.posting_date <= end_date)
        rows = self.db.execute(stmt).all()
        return [
            {
                "account_id": r.account_id,
                "account_code": r.account_code,
                "account_name": r.account_name,
                "account_type": r.account_type,
                "total_debit": r.total_debit or Decimal("0"),
                "total_credit": r.total_credit or Decimal("0"),
            }
            for r in rows
        ]

    def balance_sheet_query(
        self, company_id: UUID, as_of_date: date
    ) -> list[dict[str, Any]]:
        """Per-account cumulative SUM(debit)/SUM(credit) for ASSET/LIABILITY/
        EQUITY accounts, from inception through ``as_of_date`` (Phase 12 —
        ``FinancialStatementService.get_balance_sheet()``). Same
        REVERSED-inclusion rule as ``account_balance_query()``.
        """
        stmt = (
            select(
                Account.id.label("account_id"),
                Account.account_code.label("account_code"),
                Account.account_name.label("account_name"),
                Account.account_type.label("account_type"),
                func.sum(JournalLine.debit_amount_base).label("total_debit"),
                func.sum(JournalLine.credit_amount_base).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .join(Account, Account.id == JournalLine.account_id)
            .where(JournalEntry.company_id == company_id)
            .where(JournalEntry.status.in_(["POSTED", "REVERSED"]))
            .where(JournalEntry.posting_date <= as_of_date)
            .where(Account.account_type.in_(["ASSET", "LIABILITY", "EQUITY"]))
            .group_by(
                Account.id,
                Account.account_code,
                Account.account_name,
                Account.account_type,
            )
            .order_by(Account.account_code)
        )
        rows = self.db.execute(stmt).all()
        return [
            {
                "account_id": r.account_id,
                "account_code": r.account_code,
                "account_name": r.account_name,
                "account_type": r.account_type,
                "total_debit": r.total_debit or Decimal("0"),
                "total_credit": r.total_credit or Decimal("0"),
            }
            for r in rows
        ]

    def pl_query(
        self,
        company_id: UUID,
        start_date: date,
        end_date: date,
        cost_center_id: UUID | None = None,
        group_code: str | None = None,
    ) -> list[dict[str, Any]]:
        """Per-account SUM(debit)/SUM(credit) for REVENUE/EXPENSE accounts
        within a date range (Phase 12/13 — ``FinancialStatementService.get_pl()``).
        Mirrors ``cost_center_pl_query()``, with an optional cost-center filter
        (Phase 13, T255) rather than that method's mandatory one.

        ``group_code`` (Phase 15, T286) restricts to accounts whose
        ``AccountGroup.group_code`` matches exactly — e.g. ``"COGS"`` for
        ``FinancialKPIService``'s Gross Profit Margin. Keyword-only, default
        ``None``, so existing positional call sites are unaffected.
        """
        stmt = (
            select(
                Account.id.label("account_id"),
                Account.account_code.label("account_code"),
                Account.account_name.label("account_name"),
                Account.account_type.label("account_type"),
                func.sum(JournalLine.debit_amount_base).label("total_debit"),
                func.sum(JournalLine.credit_amount_base).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .join(Account, Account.id == JournalLine.account_id)
            .where(JournalEntry.company_id == company_id)
            .where(JournalEntry.status.in_(["POSTED", "REVERSED"]))
            .where(JournalEntry.posting_date >= start_date)
            .where(JournalEntry.posting_date <= end_date)
            .where(Account.account_type.in_(["REVENUE", "EXPENSE"]))
        )
        if cost_center_id is not None:
            stmt = stmt.where(JournalLine.cost_center_id == cost_center_id)
        if group_code is not None:
            stmt = stmt.join(
                AccountGroup, AccountGroup.id == Account.account_group_id
            ).where(AccountGroup.group_code == group_code)
        stmt = stmt.group_by(
            Account.id, Account.account_code, Account.account_name, Account.account_type
        ).order_by(Account.account_code)
        rows = self.db.execute(stmt).all()
        return [
            {
                "account_id": r.account_id,
                "account_code": r.account_code,
                "account_name": r.account_name,
                "account_type": r.account_type,
                "total_debit": r.total_debit or Decimal("0"),
                "total_credit": r.total_credit or Decimal("0"),
            }
            for r in rows
        ]

    def project_pl_query(
        self,
        company_id: UUID,
        project_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Per-account SUM(debit)/SUM(credit) for REVENUE/EXPENSE accounts
        posted against one project (Phase 11 — CostCenterService's Project
        P&L report). Mirrors ``cost_center_pl_query()`` exactly, filtered
        by ``JournalLine.project_id`` instead.
        """
        stmt = (
            select(
                Account.id.label("account_id"),
                Account.account_code.label("account_code"),
                Account.account_name.label("account_name"),
                Account.account_type.label("account_type"),
                func.sum(JournalLine.debit_amount_base).label("total_debit"),
                func.sum(JournalLine.credit_amount_base).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .join(Account, Account.id == JournalLine.account_id)
            .where(JournalEntry.company_id == company_id)
            .where(JournalLine.project_id == project_id)
            .where(JournalEntry.status.in_(["POSTED", "REVERSED"]))
            .where(Account.account_type.in_(["REVENUE", "EXPENSE"]))
            .group_by(
                Account.id,
                Account.account_code,
                Account.account_name,
                Account.account_type,
            )
        )
        if start_date is not None:
            stmt = stmt.where(JournalEntry.posting_date >= start_date)
        if end_date is not None:
            stmt = stmt.where(JournalEntry.posting_date <= end_date)
        rows = self.db.execute(stmt).all()
        return [
            {
                "account_id": r.account_id,
                "account_code": r.account_code,
                "account_name": r.account_name,
                "account_type": r.account_type,
                "total_debit": r.total_debit or Decimal("0"),
                "total_credit": r.total_credit or Decimal("0"),
            }
            for r in rows
        ]

    def current_position_query(
        self, company_id: UUID, as_of_date: date
    ) -> list[dict[str, Any]]:
        """Per-account cumulative balance for accounts classified under the
        ``CUR-AST`` (Current Assets) / ``CUR-LIA`` (Current Liabilities)
        account groups, as of ``as_of_date`` (Phase 15 —
        ``FinancialKPIService``'s Current Ratio / Quick Ratio).

        These two group codes are seeded identically by every industry COA
        template (``services/coa_templates.py``'s shared ``_BASE_GROUPS``)
        and are the platform's only structural signal for "current" vs.
        "fixed/long-term" — there is no ``is_current`` flag on ``Account``
        itself, so this joins through ``account_group_id`` rather than
        inventing one. ``account_name`` is included because there is
        likewise no ``is_inventory_account`` flag; the service identifies
        Inventory accounts (for Quick Ratio's Current Assets − Inventory)
        by name within this same result set rather than a second query.

        Same REVERSED-inclusion rule as ``account_balance_query()``.
        """
        stmt = (
            select(
                Account.id.label("account_id"),
                Account.account_code.label("account_code"),
                Account.account_name.label("account_name"),
                Account.account_type.label("account_type"),
                AccountGroup.group_code.label("group_code"),
                func.sum(JournalLine.debit_amount_base).label("total_debit"),
                func.sum(JournalLine.credit_amount_base).label("total_credit"),
            )
            .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
            .join(Account, Account.id == JournalLine.account_id)
            .join(AccountGroup, AccountGroup.id == Account.account_group_id)
            .where(JournalEntry.company_id == company_id)
            .where(JournalEntry.status.in_(["POSTED", "REVERSED"]))
            .where(JournalEntry.posting_date <= as_of_date)
            .where(AccountGroup.group_code.in_(["CUR-AST", "CUR-LIA"]))
            .group_by(
                Account.id,
                Account.account_code,
                Account.account_name,
                Account.account_type,
                AccountGroup.group_code,
            )
        )
        rows = self.db.execute(stmt).all()
        return [
            {
                "account_id": r.account_id,
                "account_code": r.account_code,
                "account_name": r.account_name,
                "account_type": r.account_type,
                "group_code": r.group_code,
                "total_debit": r.total_debit or Decimal("0"),
                "total_credit": r.total_credit or Decimal("0"),
            }
            for r in rows
        ]
