"""AIReadinessService — AI ERP Readiness — Phase 17.

Provides three read-only projections structured for external ML consumption
(GL event stream, P&L history, cash flow history) plus a minimal
anomaly-flag capture stub, all gated by the ``accounting.ai.enabled``
feature flag at the router layer (T309) — this service itself is
flag-agnostic and only implements the data shaping.

Spec ref: specs/008-accounting-finance/spec.md §54 AI Readiness
Tasks ref: specs/008-accounting-finance/tasks.md T304-T307
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.events import get_event_bus
from modules.accounting.events.ai_events import AnomalyDetectedEvent
from modules.accounting.exceptions import JournalEntryNotFoundForAnomalyFlagError
from modules.accounting.models.ai import AccountingAnomalyFlag
from modules.accounting.models.gl import JournalEntry
from modules.accounting.repositories.ai import AccountingAnomalyFlagRepository
from modules.accounting.repositories.fiscal import FiscalPeriodRepository
from modules.accounting.repositories.gl import JournalEntryRepository
from modules.accounting.services.financial_statements import FinancialStatementService


class AIReadinessService:
    """Application service backing the AI ERP readiness endpoints."""

    def __init__(
        self,
        db: Session,
        journal_entry_repo: JournalEntryRepository,
        fiscal_period_repo: FiscalPeriodRepository,
        financial_statement_service: FinancialStatementService,
        anomaly_flag_repo: AccountingAnomalyFlagRepository,
    ) -> None:
        self.db = db
        self._journal_entries = journal_entry_repo
        self._fiscal_periods = fiscal_period_repo
        self._statements = financial_statement_service
        self._anomaly_flags = anomaly_flag_repo

    # ------------------------------------------------------------------
    # GL event stream (T304)
    # ------------------------------------------------------------------

    def get_event_stream(
        self, company_id: UUID, from_date: date | None, skip: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        """Paginated POSTED journal entry history — the same fields
        ``accounting.journal.posted`` publishes (plus ``reference``, per
        T303's documented gap), structured for ML training-data export.
        """
        filters: dict[str, Any] = {"status": "POSTED"}
        if from_date is not None:
            filters["start_date"] = from_date
        entries, total = self._journal_entries.search(
            company_id=company_id, filters=filters, skip=skip, limit=limit
        )
        return [self._to_event_stream_row(e) for e in entries], total

    @staticmethod
    def _to_event_stream_row(entry: JournalEntry) -> dict[str, Any]:
        return {
            "journal_entry_id": entry.id,
            "journal_number": entry.journal_number,
            "journal_type": entry.journal_type,
            "posting_source": entry.posting_source,
            "posting_date": entry.posting_date,
            "reference": entry.reference,
            "total_debit_base": entry.total_debit_base,
            "total_credit_base": entry.total_credit_base,
            "posted_at": entry.posted_at,
            "actor_id": entry.posted_by_user_id,
        }

    # ------------------------------------------------------------------
    # P&L / cash flow history (T305, T306)
    # ------------------------------------------------------------------

    def get_pl_history(self, company_id: UUID, periods: int) -> list[dict[str, Any]]:
        """Last ``periods`` fiscal periods' P&L, oldest first — structured
        for revenue/expense forecasting models (spec.md §54.3).
        """
        recent_periods = self._fiscal_periods.list_recent(company_id, periods)
        results = []
        for period in recent_periods:
            pl = self._statements.get_pl(company_id, period.start_date, period.end_date)
            results.append(
                {
                    "fiscal_period_id": period.id,
                    "period_name": period.period_name,
                    "start_date": period.start_date,
                    "end_date": period.end_date,
                    "total_revenue": pl["total_revenue"],
                    "total_expense": pl["total_expense"],
                    "net_income": pl["net_income"],
                }
            )
        return results

    def get_cashflow_history(
        self, company_id: UUID, periods: int
    ) -> list[dict[str, Any]]:
        """Last ``periods`` fiscal periods' indirect-method cash flow, oldest
        first — structured for cash flow forecasting models (spec.md §54.2).
        """
        recent_periods = self._fiscal_periods.list_recent(company_id, periods)
        results = []
        for period in recent_periods:
            cf = self._statements.get_cash_flow(
                company_id, period.start_date, period.end_date
            )
            results.append(
                {
                    "fiscal_period_id": period.id,
                    "period_name": period.period_name,
                    "start_date": period.start_date,
                    "end_date": period.end_date,
                    "net_income": cf["net_income"],
                    "net_cash_from_operating_activities": cf[
                        "net_cash_from_operating_activities"
                    ],
                    "opening_cash_balance": cf["opening_cash_balance"],
                    "closing_cash_balance": cf["closing_cash_balance"],
                    "net_change_in_cash": cf["net_change_in_cash"],
                }
            )
        return results

    # ------------------------------------------------------------------
    # Anomaly detection stub (T307)
    # ------------------------------------------------------------------

    def record_anomaly_report(
        self,
        company_id: UUID,
        journal_entry_ids: list[UUID],
        reason: str | None,
        actor_id: UUID | None,
    ) -> list[AccountingAnomalyFlag]:
        """Store an anomaly flag for each referenced (existing, POSTED)
        journal entry and publish ``accounting.anomaly.detected`` per flag.

        Raises:
            JournalEntryNotFoundForAnomalyFlagError: A referenced journal
                entry does not exist, or is not POSTED, for this company.
        """
        for journal_entry_id in journal_entry_ids:
            entry = self._journal_entries.get_by_id_or_none(
                id=journal_entry_id, company_id=company_id
            )
            if entry is None or entry.status != "POSTED":
                raise JournalEntryNotFoundForAnomalyFlagError(str(journal_entry_id))

        flags: list[AccountingAnomalyFlag] = []
        bus = get_event_bus()
        for journal_entry_id in journal_entry_ids:
            flag = self._anomaly_flags.create(
                AccountingAnomalyFlag(
                    company_id=company_id,
                    journal_entry_id=journal_entry_id,
                    reason=reason,
                    created_by=actor_id,
                )
            )
            flags.append(flag)
            bus.publish(
                AnomalyDetectedEvent(
                    event_type="accounting.anomaly.detected",
                    aggregate_type="JournalEntry",
                    aggregate_id=journal_entry_id,
                    company_id=company_id,
                    actor_id=actor_id,
                    journal_entry_id=journal_entry_id,
                    anomaly_flag_id=flag.id,
                    reason=reason,
                )
            )
        return flags
