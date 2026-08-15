"""FiscalCalendarService — Fiscal Calendar application service — Phase 3.

Responsibilities:
  - Create fiscal years with auto-generated monthly periods
  - Lock/unlock periods (Controller authority; mandatory reason on unlock)
  - Enforce ``FiscalPeriodStateMachine`` transition rules
  - Validate and persist opening balances (sum debit == sum credit)
  - Execute year-end close (all periods -> CLOSED, fiscal year -> CLOSED)
  - ``get_open_period_for_posting()`` — the exact check Phase 4's
    PostingEngine (spec.md §14 Step 3) will call before allowing a post

NOTE on ``execute_year_end_close()``: computing and posting the actual
P&L-to-retained-earnings closing JOURNAL ENTRY requires the PostingEngine
and JournalEntry aggregate (Phase 4), neither of which exists yet. This
method performs everything that IS possible with Phase 3 data (validating
all periods are LOCKED, transitioning periods/year to CLOSED, publishing
``accounting.fiscalyear.closed`` with ``closing_journal_entry_id=None``)
and documents the closing-entry gap explicitly — the same pattern used in
Phase 2 for the GL-activity-on-deactivation check. Must be wired in when
Phase 4 ships.

Spec ref: specs/008-accounting-finance/tasks.md T073, T074
"""

from __future__ import annotations

import calendar
import logging
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.accounting.constants import FiscalPeriodStatus, FiscalYearStatus
from modules.accounting.events import get_event_bus
from modules.accounting.events.fiscal_events import (
    FiscalYearClosedEvent,
    PeriodClosedEvent,
    PeriodLockedEvent,
    PeriodUnlockedEvent,
)
from modules.accounting.exceptions import (
    DuplicateFiscalYearError,
    FiscalPeriodNotFoundError,
    FiscalYearNotFoundError,
    InvalidFiscalPeriodTransitionError,
    OpeningBalanceImbalancedError,
    PeriodLockedError,
    YearEndCloseBlockedError,
)
from modules.accounting.models.fiscal import FiscalPeriod, FiscalYear, OpeningBalance
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.services.audit_service import AuditLogService

logger = logging.getLogger(__name__)


class FiscalPeriodStateMachine:
    """Enforces valid ``FiscalPeriod`` status transitions.

    Valid transitions (spec.md §16.2, data-model.md §2.2):
      OPEN -> LOCKED
      LOCKED -> OPEN     (unlock; Controller authority + audit record)
      LOCKED -> CLOSED   (year-end close workflow ONLY — see ``close_period``)
    CLOSED is terminal: no outgoing transition is ever valid.
    """

    _VALID_TRANSITIONS: dict[FiscalPeriodStatus, frozenset[FiscalPeriodStatus]] = {
        FiscalPeriodStatus.OPEN: frozenset({FiscalPeriodStatus.LOCKED}),
        FiscalPeriodStatus.LOCKED: frozenset(
            {FiscalPeriodStatus.OPEN, FiscalPeriodStatus.CLOSED}
        ),
        FiscalPeriodStatus.CLOSED: frozenset(),
    }

    @classmethod
    def validate_transition(cls, current_status: str, target_status: str) -> None:
        """Raise ``InvalidFiscalPeriodTransitionError`` if not allowed."""
        current = FiscalPeriodStatus(current_status)
        target = FiscalPeriodStatus(target_status)
        if target not in cls._VALID_TRANSITIONS[current]:
            raise InvalidFiscalPeriodTransitionError(current.value, target.value)


class FiscalCalendarService:
    """Application service for fiscal year and period management."""

    def __init__(
        self,
        db: Session,
        year_repo: FiscalYearRepository,
        period_repo: FiscalPeriodRepository,
        opening_balance_repo: OpeningBalanceRepository,
        audit_service: AuditLogService,
    ) -> None:
        self.db = db
        self._years = year_repo
        self._periods = period_repo
        self._opening_balances = opening_balance_repo
        self._audit = audit_service

    @staticmethod
    def _period_snapshot(period: FiscalPeriod) -> dict[str, Any]:
        return {
            "status": period.status,
            "period_name": period.period_name,
            "period_number": period.period_number,
        }

    @staticmethod
    def _year_snapshot(year: FiscalYear) -> dict[str, Any]:
        return {
            "status": year.status,
            "fiscal_year_name": year.fiscal_year_name,
            "is_current": year.is_current,
        }

    # ------------------------------------------------------------------
    # Fiscal Year
    # ------------------------------------------------------------------

    def create_fiscal_year(
        self,
        company_id: UUID,
        fiscal_year_name: str,
        start_date: date,
        end_date: date,
        base_currency_code: str,
        is_current: bool = False,
        created_by: UUID | None = None,
    ) -> FiscalYear:
        """Create a fiscal year and auto-generate its monthly periods.

        The year and all its periods are created directly usable (status
        OPEN) — tasks.md does not define a separate "activate" step, and
        the Independent Test for this phase (lock a period, verify posting
        rejection) requires periods to be postable immediately upon
        creation.

        Raises:
            DuplicateFiscalYearError: A fiscal year with this name already
                exists for the company.
            ValueError: ``end_date`` does not fall after ``start_date``.
        """
        if self._years.find_by_year(company_id, fiscal_year_name) is not None:
            raise DuplicateFiscalYearError(fiscal_year_name)
        if end_date <= start_date:
            raise ValueError("end_date must fall after start_date.")

        year = FiscalYear(
            company_id=company_id,
            fiscal_year_name=fiscal_year_name,
            start_date=start_date,
            end_date=end_date,
            status=FiscalYearStatus.OPEN.value,
            base_currency_code=base_currency_code,
            is_current=is_current,
            created_by=created_by,
        )
        self.db.add(year)
        self.db.flush()
        self._audit.record(
            company_id=company_id,
            entity_type="FiscalYear",
            entity_id=year.id,
            action="CREATED",
            actor_id=created_by,
            after=self._year_snapshot(year),
        )
        year = self._years.create(year)

        for period_number, (p_start, p_end) in enumerate(
            self._split_into_monthly_periods(start_date, end_date), start=1
        ):
            period = FiscalPeriod(
                company_id=company_id,
                fiscal_year_id=year.id,
                period_number=period_number,
                period_name=p_start.strftime("%B %Y"),
                start_date=p_start,
                end_date=p_end,
                status=FiscalPeriodStatus.OPEN.value,
                created_by=created_by,
            )
            self._periods.create(period)

        return year

    @staticmethod
    def _split_into_monthly_periods(
        start_date: date, end_date: date
    ) -> list[tuple[date, date]]:
        """Split ``[start_date, end_date]`` into contiguous monthly periods.

        The final period's end date is clamped to the fiscal year's own
        ``end_date`` so the generated periods always sum exactly to the
        fiscal year span, even when it does not divide evenly into
        calendar months (e.g. a fiscal year starting on the 15th).
        """
        periods: list[tuple[date, date]] = []
        cursor = start_date
        while cursor <= end_date:
            year, month = cursor.year, cursor.month
            days_in_month = calendar.monthrange(year, month)[1]
            period_end = date(year, month, days_in_month)
            if period_end > end_date:
                period_end = end_date
            periods.append((cursor, period_end))
            if period_end >= end_date:
                break
            next_month = month + 1
            next_year = year
            if next_month > 12:
                next_month = 1
                next_year += 1
            cursor = date(next_year, next_month, 1)
        return periods

    def get_fiscal_year(self, company_id: UUID, fiscal_year_id: UUID) -> FiscalYear:
        year = self._years.get_by_id_or_none(id=fiscal_year_id, company_id=company_id)
        if year is None:
            raise FiscalYearNotFoundError(fiscal_year_id=str(fiscal_year_id))
        return year

    def list_fiscal_years(self, company_id: UUID) -> list[FiscalYear]:
        return self._years.list_all(company_id=company_id)

    def update_fiscal_year(
        self, company_id: UUID, fiscal_year_id: UUID, **updates: object
    ) -> FiscalYear:
        """Update mutable fields on a fiscal year (name, is_current).

        Dates and status are intentionally excluded — see
        ``FiscalYearUpdateRequest`` docstring.
        """
        year = self.get_fiscal_year(company_id, fiscal_year_id)
        before = self._year_snapshot(year)
        mutable_fields = {"fiscal_year_name", "is_current"}
        for key, value in updates.items():
            if key in mutable_fields and value is not None:
                setattr(year, key, value)
        self._audit.record(
            company_id=company_id,
            entity_type="FiscalYear",
            entity_id=year.id,
            action="UPDATED",
            actor_id=None,
            before=before,
            after=self._year_snapshot(year),
        )
        return self._years.update(year)

    def list_periods(
        self, company_id: UUID, fiscal_year_id: UUID
    ) -> list[FiscalPeriod]:
        return self._periods.list_periods(
            company_id=company_id, fiscal_year_id=fiscal_year_id
        )

    # ------------------------------------------------------------------
    # Period lock / unlock
    # ------------------------------------------------------------------

    def get_period(self, company_id: UUID, period_id: UUID) -> FiscalPeriod:
        period = self._periods.find_by_id(company_id=company_id, period_id=period_id)
        if period is None:
            raise FiscalPeriodNotFoundError(fiscal_period_id=str(period_id))
        return period

    def open_period(self, company_id: UUID, period_id: UUID) -> FiscalPeriod:
        """Set a LOCKED period back to OPEN with no reason/audit record.

        Distinct from ``unlock_period``: this is the structural transition
        primitive with no mandatory-reason business rule attached. Exposed
        per tasks.md T073; ``unlock_period`` is the audited, Controller-
        authority-checked path used by the API and should be preferred by
        callers that need the audit trail.
        """
        period = self.get_period(company_id, period_id)
        if period.status != FiscalPeriodStatus.OPEN.value:
            FiscalPeriodStateMachine.validate_transition(
                period.status, FiscalPeriodStatus.OPEN.value
            )
            period.status = FiscalPeriodStatus.OPEN.value
            period.locked_at = None
            period.locked_by_user_id = None
            period.lock_reason = None
            period = self._periods.update(period)
        return period

    def lock_period(
        self,
        company_id: UUID,
        period_id: UUID,
        locked_by_user_id: UUID | None,
        lock_reason: str,
    ) -> FiscalPeriod:
        """Lock an OPEN period, publishing ``accounting.period.locked``.

        Raises:
            FiscalPeriodNotFoundError
            InvalidFiscalPeriodTransitionError: The period is not OPEN.
        """
        period = self.get_period(company_id, period_id)
        FiscalPeriodStateMachine.validate_transition(
            period.status, FiscalPeriodStatus.LOCKED.value
        )

        before = self._period_snapshot(period)
        period.status = FiscalPeriodStatus.LOCKED.value
        period.locked_at = utcnow()
        period.locked_by_user_id = locked_by_user_id
        period.lock_reason = lock_reason
        self._audit.record(
            company_id=company_id,
            entity_type="FiscalPeriod",
            entity_id=period.id,
            action="LOCKED",
            actor_id=locked_by_user_id,
            before=before,
            after=self._period_snapshot(period),
            reason=lock_reason,
        )
        period = self._periods.update(period)

        get_event_bus().publish(
            PeriodLockedEvent(
                event_type="accounting.period.locked",
                aggregate_type="FiscalPeriod",
                aggregate_id=period.id,
                company_id=company_id,
                actor_id=locked_by_user_id,
                fiscal_year_id=period.fiscal_year_id,
                fiscal_period_id=period.id,
                period_number=period.period_number,
                period_name=period.period_name,
                period_start_date=period.start_date,
                period_end_date=period.end_date,
                locked_by_user_id=locked_by_user_id,
                lock_reason=lock_reason,
            )
        )
        return period

    def unlock_period(
        self,
        company_id: UUID,
        period_id: UUID,
        unlocked_by_user_id: UUID | None,
        reason: str,
    ) -> FiscalPeriod:
        """Unlock a LOCKED period back to OPEN. Mandatory reason; audited.

        RBAC (Controller-or-above authority, spec.md BR-014/BR-016) is
        enforced at the router layer (Phase 14, T276) via the
        ``accounting.period.lock`` permission — see
        ``modules.accounting.router.unlock_fiscal_period``.

        Raises:
            ValueError: ``reason`` is empty/blank.
            InvalidFiscalPeriodTransitionError: The period is not LOCKED.
        """
        if not reason or not reason.strip():
            raise ValueError("A reason is mandatory to unlock a fiscal period.")
        period = self.get_period(company_id, period_id)
        FiscalPeriodStateMachine.validate_transition(
            period.status, FiscalPeriodStatus.OPEN.value
        )

        before = self._period_snapshot(period)
        period.status = FiscalPeriodStatus.OPEN.value
        period.locked_at = None
        period.locked_by_user_id = None
        period.lock_reason = None
        self._audit.record(
            company_id=company_id,
            entity_type="FiscalPeriod",
            entity_id=period.id,
            action="UNLOCKED",
            actor_id=unlocked_by_user_id,
            before=before,
            after=self._period_snapshot(period),
            reason=reason,
        )
        period = self._periods.update(period)

        get_event_bus().publish(
            PeriodUnlockedEvent(
                event_type="accounting.period.unlocked",
                aggregate_type="FiscalPeriod",
                aggregate_id=period.id,
                company_id=company_id,
                actor_id=unlocked_by_user_id,
                fiscal_period_id=period.id,
                period_name=period.period_name,
                unlocked_by_user_id=unlocked_by_user_id,
                reason=reason,
            )
        )
        return period

    def close_period(
        self,
        company_id: UUID,
        period_id: UUID,
        closed_by_user_id: UUID | None = None,
        _year_end_close_in_progress: bool = False,
    ) -> FiscalPeriod:
        """Permanently close a LOCKED period. Terminal — no reversal.

        Only reachable via ``execute_year_end_close`` (data-model.md §2.2
        invariant; tasks.md T074: "reject LOCKED -> CLOSED without
        year-end close completion"). Direct calls outside that workflow
        raise ``InvalidFiscalPeriodTransitionError``.
        """
        if not _year_end_close_in_progress:
            raise InvalidFiscalPeriodTransitionError(
                FiscalPeriodStatus.LOCKED.value, FiscalPeriodStatus.CLOSED.value
            )
        period = self.get_period(company_id, period_id)
        FiscalPeriodStateMachine.validate_transition(
            period.status, FiscalPeriodStatus.CLOSED.value
        )

        before = self._period_snapshot(period)
        period.status = FiscalPeriodStatus.CLOSED.value
        period.closed_at = utcnow()
        period.closed_by_user_id = closed_by_user_id
        self._audit.record(
            company_id=company_id,
            entity_type="FiscalPeriod",
            entity_id=period.id,
            action="CLOSED",
            actor_id=closed_by_user_id,
            before=before,
            after=self._period_snapshot(period),
        )
        period = self._periods.update(period)

        get_event_bus().publish(
            PeriodClosedEvent(
                event_type="accounting.period.closed",
                aggregate_type="FiscalPeriod",
                aggregate_id=period.id,
                company_id=company_id,
                actor_id=closed_by_user_id,
                fiscal_period_id=period.id,
                period_name=period.period_name,
                closed_at=period.closed_at,
            )
        )
        return period

    # ------------------------------------------------------------------
    # Posting-date validation — the exact check Phase 4's PostingEngine
    # Step 3 will call (spec.md §14)
    # ------------------------------------------------------------------

    def get_open_period_for_posting(
        self, company_id: UUID, posting_date: date
    ) -> FiscalPeriod:
        """Return the OPEN fiscal period covering ``posting_date``.

        Raises:
            PeriodLockedError: No period is defined for this date, or the
                covering period is LOCKED/CLOSED.
        """
        period = self._periods.find_open_period_for_date(company_id, posting_date)
        if period is None:
            raise PeriodLockedError(posting_date=posting_date.isoformat())
        if period.status != FiscalPeriodStatus.OPEN.value:
            raise PeriodLockedError(
                posting_date=posting_date.isoformat(), period_status=period.status
            )
        return period

    # ------------------------------------------------------------------
    # Opening balances
    # ------------------------------------------------------------------

    def setup_opening_balances(
        self,
        company_id: UUID,
        fiscal_year_id: UUID,
        lines: list[dict[str, object]],
        created_by: UUID | None = None,
    ) -> list[OpeningBalance]:
        """Validate and persist a batch of opening balances.

        NOTE on plan.md Phase 3 scope ("Opening balance service: batch-
        validates and posts OPENING_BALANCE journal"): this persists rows
        directly to ``accounting_opening_balances`` (data-model.md §2.2's
        ``OpeningBalance`` entity, and the exact method this task set —
        T070/T073 — asks for) rather than posting an actual
        ``JournalType.OPENING_BALANCE`` ``JournalEntry`` through the
        PostingEngine, since neither exists until Phase 4. Same documented-
        gap pattern as ``execute_year_end_close``'s closing entry — must be
        wired to call the PostingEngine once Phase 4 ships.

        Args:
            lines: dicts with keys ``account_id``, ``debit_amount``,
                ``credit_amount``, and optionally ``currency_code``,
                ``notes``.

        Raises:
            FiscalYearNotFoundError
            OpeningBalanceImbalancedError: Total debit != total credit.
        """
        self.get_fiscal_year(company_id, fiscal_year_id)  # existence check

        total_debit = sum(
            (Decimal(str(line.get("debit_amount", 0))) for line in lines), Decimal("0")
        )
        total_credit = sum(
            (Decimal(str(line.get("credit_amount", 0))) for line in lines), Decimal("0")
        )
        if total_debit != total_credit:
            raise OpeningBalanceImbalancedError(
                total_debit=str(total_debit), total_credit=str(total_credit)
            )

        self._audit.record(
            company_id=company_id,
            entity_type="FiscalYear",
            entity_id=fiscal_year_id,
            action="OPENING_BALANCES_SET",
            actor_id=created_by,
            after={
                "total_debit": str(total_debit),
                "total_credit": str(total_credit),
                "line_count": len(lines),
            },
        )

        created: list[OpeningBalance] = []
        for line in lines:
            balance = OpeningBalance(
                company_id=company_id,
                fiscal_year_id=fiscal_year_id,
                account_id=line["account_id"],
                debit_amount=Decimal(str(line.get("debit_amount", 0))),
                credit_amount=Decimal(str(line.get("credit_amount", 0))),
                currency_code=line.get("currency_code"),
                notes=line.get("notes"),
                created_by=created_by,
            )
            created.append(self._opening_balances.create(balance))
        return created

    def list_opening_balances(
        self, company_id: UUID, fiscal_year_id: UUID
    ) -> list[OpeningBalance]:
        return self._opening_balances.list_for_fiscal_year(company_id, fiscal_year_id)

    # ------------------------------------------------------------------
    # Year-end close
    # ------------------------------------------------------------------

    def execute_year_end_close(
        self,
        company_id: UUID,
        fiscal_year_id: UUID,
        closed_by_user_id: UUID | None = None,
    ) -> FiscalYear:
        """Execute the year-end close workflow for a fiscal year.

        Steps performed (spec.md §16.5):
          1. Validate every period in the year is LOCKED.
          2. Transition every period LOCKED -> CLOSED.
          3. Transition the fiscal year to CLOSED.
          4. Publish ``accounting.fiscalyear.closed``.

        NOT performed (documented gap — see module docstring): computing
        and posting the actual P&L-to-retained-earnings closing journal
        entry, which requires the PostingEngine and GL (Phase 4).
        ``closing_journal_entry_id``/``net_income_transferred`` publish as
        ``None`` until then.

        Raises:
            FiscalYearNotFoundError
            YearEndCloseBlockedError: Any period is not LOCKED.
        """
        year = self.get_fiscal_year(company_id, fiscal_year_id)
        periods = self.list_periods(company_id, fiscal_year_id)

        not_locked = [p for p in periods if p.status != FiscalPeriodStatus.LOCKED.value]
        if not_locked:
            raise YearEndCloseBlockedError(
                fiscal_year_name=year.fiscal_year_name,
                open_period_names=[p.period_name for p in not_locked],
            )

        for period in periods:
            self.close_period(
                company_id=company_id,
                period_id=period.id,
                closed_by_user_id=closed_by_user_id,
                _year_end_close_in_progress=True,
            )

        before = self._year_snapshot(year)
        year.status = FiscalYearStatus.CLOSED.value
        self._audit.record(
            company_id=company_id,
            entity_type="FiscalYear",
            entity_id=year.id,
            action="CLOSED",
            actor_id=closed_by_user_id,
            before=before,
            after=self._year_snapshot(year),
        )
        year = self._years.update(year)

        get_event_bus().publish(
            FiscalYearClosedEvent(
                event_type="accounting.fiscalyear.closed",
                aggregate_type="FiscalYear",
                aggregate_id=year.id,
                company_id=company_id,
                actor_id=closed_by_user_id,
                fiscal_year_id=year.id,
                fiscal_year_name=year.fiscal_year_name,
                closing_journal_entry_id=None,
                net_income_transferred=None,
                retained_earnings_account_id=None,
                closed_at=utcnow(),
            )
        )
        return year
