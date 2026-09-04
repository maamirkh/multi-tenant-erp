"""InstallmentReportingService — the 8 report types plus dashboard KPI
aggregation (tasks.md T204/T205, plan.md §25's truth-source table).

Every report/KPI figure traces to exactly one authoritative source,
never re-derived independently and never re-invented as a competing
value:

- Contract register, settlement, default/write-off, plan/template
  performance: Installments-owned (``InstallmentContract`` +
  ``InstallmentAuditLog``).
- Collection report: Accounting's own ``Payment``/``PaymentAllocationLine``
  (live gateway reads), filtered via ``InstallmentAllocationReference``.
- Due/overdue/aging: Installments schedule lines (authoritative — no
  Accounting equivalent exists) + Accounting allocation sums, computed
  at read time via the same ``DueStateCalculator``/
  ``InstallmentAgingCalculator`` every other phase already uses — no
  materialized "status" column to drift from truth.
- Dashboard KPIs: a mix per FR-INST-080, each individual figure sourced
  exactly as its own dedicated report would source it, combined here
  with a single non-double-counting derivation (FR-INST-081): an amount
  that has crossed into OVERDUE is excluded from "due this month," never
  counted in both buckets.

All list methods return ``(items, total)`` for ``PaginatedResponse``,
company_id-scoped throughout, and batch-load (never per-row/per-contract
query the allocation-reference or Accounting layers, tasks.md T213).

Spec ref: specs/010-installments/plan.md §25; specs/010-installments/
spec.md FR-INST-080/081/360-362.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.late_charge import (
    InstallmentLateChargeRepository,
)
from modules.installments.repositories.plan_template import (
    InstallmentPlanTemplateRepository,
)
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.access_policy import (
    InstallmentAccessPolicy,
    InstallmentOperationClass,
)
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.aging_calculator import InstallmentAgingCalculator
from modules.installments.services.business_date import get_business_date
from modules.installments.services.due_state import DueStateCalculator

_ACTIVE_TERMINAL = ("COMPLETED", "CANCELLED", "WRITTEN_OFF")


def _grace_period_days(contract: Any) -> int:
    snapshot = contract.terms_snapshot or {}
    return int(snapshot.get("grace_period_days") or 0)


@dataclass(frozen=True)
class InstallmentDashboardData:
    """The full dashboard payload — one non-double-counting derivation,
    never a per-KPI competing computation (FR-INST-080/081)."""

    active_contract_count: int
    outstanding_amount: Decimal
    due_today_amount: Decimal
    due_this_month_amount: Decimal
    collected_today_amount: Decimal
    collected_this_month_amount: Decimal
    overdue_amount: Decimal
    overdue_count: int
    collection_rate: Decimal
    aging_distribution: dict[str, Decimal]
    defaulted_balance: Decimal
    written_off_balance: Decimal
    upcoming_receivables_amount: Decimal


class InstallmentReportingService:
    """Read-only — no service method here ever calls a repository write
    method or an Accounting mutation."""

    def __init__(
        self,
        contract_repo: InstallmentContractRepository,
        schedule_repo: InstallmentScheduleRepository,
        allocation_ref_repo: InstallmentAllocationReferenceRepository,
        late_charge_repo: InstallmentLateChargeRepository,
        audit_repo: InstallmentAuditLogRepository,
        plan_template_repo: InstallmentPlanTemplateRepository,
        accounting_gateway: AccountingIntegrationGateway,
        access_policy: InstallmentAccessPolicy | None = None,
    ) -> None:
        self._contracts = contract_repo
        self._schedule = schedule_repo
        self._allocation_refs = allocation_ref_repo
        self._late_charges = late_charge_repo
        self._audit = audit_repo
        self._plan_templates = plan_template_repo
        self._accounting = accounting_gateway
        self._access_policy = access_policy

    def _authorize_read(self, company_id: UUID) -> None:
        if self._access_policy is not None:
            self._access_policy.authorize(
                company_id=company_id, operation=InstallmentOperationClass.READ
            )

    # ------------------------------------------------------------------
    # Contract register
    # ------------------------------------------------------------------

    def get_contract_register(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        self._authorize_read(company_id)
        contracts, total = self._contracts.list_filtered(
            company_id, status=status, skip=skip, limit=limit
        )
        rows = [
            {
                "report_type": "contract-register",
                "contract_id": str(c.id),
                "contract_number": c.contract_number,
                "customer_id": str(c.customer_id),
                "status": c.status,
                "contract_date": c.contract_date.isoformat(),
                "contractual_total": str(c.contractual_total),
                "installment_count": c.installment_count,
                "frequency": c.frequency,
                "plan_template_id": (
                    str(c.plan_template_id) if c.plan_template_id else None
                ),
            }
            for c in contracts
        ]
        return rows, total

    # ------------------------------------------------------------------
    # Collection report — Accounting-sourced (plan.md §25)
    # ------------------------------------------------------------------

    def get_collection_report(
        self,
        company_id: UUID,
        *,
        since: date | None = None,
        until: date | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        self._authorize_read(company_id)
        # `include_reversals=True`: this report is the sole read path the
        # frontend contract-detail page's "Payments" section uses
        # (`useCollections`, see its own docstring) — the default-False
        # base query exists for callers that want net-collections-only
        # (e.g. a "collected today" KPI sum), but a report showing
        # collection *history* must include reversal rows or a reversed
        # collection appears to stay active forever, with its "Reverse"
        # action still offered on an already-reversed row (Phase-13
        # verification finding).
        references, total = self._allocation_refs.list_for_company(
            company_id,
            since=since,
            until=until,
            include_reversals=True,
            skip=skip,
            limit=limit,
        )

        # Batch-load the authoritative Accounting payment/line data for
        # this page only — one gateway round trip per UNIQUE payment on
        # the page, never per reference row (T213).
        payment_cache: dict[UUID, Any] = {}
        rows: list[dict[str, Any]] = []
        for ref in references:
            payment = payment_cache.get(ref.accounting_payment_id)
            if payment is None and ref.accounting_payment_id not in payment_cache:
                payment = self._accounting.get_payment(
                    company_id, ref.accounting_payment_id
                )
                payment_cache[ref.accounting_payment_id] = payment
            rows.append(
                {
                    "report_type": "collection",
                    "contract_id": str(ref.contract_id),
                    "schedule_line_id": str(ref.schedule_line_id),
                    "accounting_payment_id": str(ref.accounting_payment_id),
                    "allocated_amount": str(ref.allocated_amount),
                    "allocated_at": ref.allocated_at.isoformat(),
                    "is_reversal": ref.is_reversal,
                    "payment_method": (
                        payment.payment_method if payment is not None else None
                    ),
                    "payment_date": (
                        payment.payment_date.isoformat()
                        if payment is not None and payment.payment_date
                        else None
                    ),
                }
            )
        return rows, total

    # ------------------------------------------------------------------
    # Due / Overdue — schedule lines + live allocation sums
    # ------------------------------------------------------------------

    #: No materialized due-state column exists (plan.md §28) — due-state
    #: is a computed classification, not a stored/filterable SQL column,
    #: so it cannot be pushed into the database's own WHERE/LIMIT clause.
    #: This bound is the population every due/overdue report classifies
    #: in one bulk read (still O(1) SQL statements, T213) before
    #: filtering-then-paginating in Python — large enough for any
    #: realistic tenant's live (non-terminal) obligation count.
    _DUE_STATE_POPULATION_BOUND = 50_000

    def _classified_lines_for_company(
        self, company_id: UUID, *, business_date: date
    ) -> list[tuple[Any, Any, Any]]:
        """Every active line's ``(line, contract, due_state)`` triple,
        company-wide — one bulk query + one batch net-allocated lookup
        (never per-line/per-contract, T213), classified in pure Python.
        Callers filter by ``due_state.state`` and paginate the FILTERED
        result themselves — pagination cannot happen before filtering
        when the filter key isn't a stored column."""
        pairs, _total = self._schedule.list_active_lines_for_company(
            company_id, skip=0, limit=self._DUE_STATE_POPULATION_BOUND
        )
        line_ids = [line.id for line, _contract in pairs]
        net_allocated = self._allocation_refs.get_net_allocated_by_line(
            company_id, line_ids
        )
        results = []
        for line, contract in pairs:
            paid = net_allocated.get(line.id, Decimal("0"))
            due_state = DueStateCalculator.calculate(
                scheduled_amount=line.scheduled_amount,
                paid_amount=paid,
                due_date=line.due_date,
                business_date=business_date,
                grace_period_days=_grace_period_days(contract),
                waived_at=line.waived_at,
                voided_at=line.voided_at,
            )
            results.append((line, contract, due_state))
        return results

    def get_due_report(
        self, company_id: UUID, *, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        self._authorize_read(company_id)
        business_date = get_business_date()
        triples = self._classified_lines_for_company(
            company_id, business_date=business_date
        )
        matching = [
            self._due_row("due", line, contract, due_state)
            for line, contract, due_state in triples
            if due_state.state in ("DUE", "PARTIALLY_PAID")
        ]
        return matching[skip : skip + limit], len(matching)

    def get_overdue_report(
        self, company_id: UUID, *, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        self._authorize_read(company_id)
        business_date = get_business_date()
        triples = self._classified_lines_for_company(
            company_id, business_date=business_date
        )
        matching = [
            self._due_row("overdue", line, contract, due_state)
            for line, contract, due_state in triples
            if due_state.state == "OVERDUE"
        ]
        return matching[skip : skip + limit], len(matching)

    @staticmethod
    def _due_row(
        report_type: str, line: Any, contract: Any, due_state: Any
    ) -> dict[str, Any]:
        return {
            "report_type": report_type,
            "contract_id": str(contract.id),
            "contract_number": contract.contract_number,
            "customer_id": str(contract.customer_id),
            "schedule_line_id": str(line.id),
            "due_date": line.due_date.isoformat(),
            "scheduled_amount": str(line.scheduled_amount),
            "outstanding_amount": str(due_state.outstanding_amount),
            "state": due_state.state,
            "days_overdue": due_state.days_overdue,
        }

    # ------------------------------------------------------------------
    # Aging — replicates Accounting's exact bucket boundaries
    # ------------------------------------------------------------------

    def get_aging_report(
        self,
        company_id: UUID,
        *,
        as_of_date: date | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        self._authorize_read(company_id)
        as_of = as_of_date or get_business_date()
        # Same reasoning as due/overdue: "has positive outstanding" is a
        # computed filter, not a stored column — fetch the bounded
        # population once, filter, THEN paginate in Python, never push
        # skip/limit ahead of the filter (that would silently mis-total
        # and mis-page, the exact bug T211/T204's own review caught here).
        pairs, _total = self._schedule.list_active_lines_for_company(
            company_id, skip=0, limit=self._DUE_STATE_POPULATION_BOUND
        )
        line_ids = [line.id for line, _contract in pairs]
        net_allocated = self._allocation_refs.get_net_allocated_by_line(
            company_id, line_ids
        )
        matching = []
        for line, contract in pairs:
            outstanding = line.scheduled_amount - net_allocated.get(
                line.id, Decimal("0")
            )
            if outstanding <= Decimal("0"):
                continue
            bucket = InstallmentAgingCalculator.bucket_for(line.due_date, as_of)
            matching.append(
                {
                    "report_type": "aging",
                    "contract_id": str(contract.id),
                    "contract_number": contract.contract_number,
                    "customer_id": str(contract.customer_id),
                    "schedule_line_id": str(line.id),
                    "due_date": line.due_date.isoformat(),
                    "outstanding_amount": str(outstanding),
                    "bucket": bucket,
                }
            )
        return matching[skip : skip + limit], len(matching)

    # ------------------------------------------------------------------
    # Settlement report — SETTLED audit events
    # ------------------------------------------------------------------

    def get_settlement_report(
        self, company_id: UUID, *, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        self._authorize_read(company_id)
        entries, total = self._audit.list_by_action_for_company(
            company_id,
            entity_type="InstallmentContract",
            action="SETTLED",
            skip=skip,
            limit=limit,
        )
        rows = [
            {
                "report_type": "settlement",
                "contract_id": str(entry.entity_id),
                "occurred_at": entry.occurred_at.isoformat(),
                "actor_user_id": (
                    str(entry.actor_user_id) if entry.actor_user_id else None
                ),
            }
            for entry in entries
        ]
        return rows, total

    # ------------------------------------------------------------------
    # Default / write-off report
    # ------------------------------------------------------------------

    def get_default_writeoff_report(
        self, company_id: UUID, *, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        self._authorize_read(company_id)
        contracts, total = self._contracts.list_filtered(
            company_id, status="WRITTEN_OFF", skip=skip, limit=limit
        )
        rows = []
        for contract in contracts:
            # Write-off amount: the schedule-outstanding balance at the
            # moment of write-off — mathematically exact for a WRITTEN_OFF
            # (terminal) contract, since no further schedule/allocation
            # activity is legally possible after this status is reached.
            # Cross-checked (not sourced) against Accounting's own
            # ARTransaction.status == WRITTEN_OFF, per plan.md §25.
            #
            # `list_active_lines_for_company()` deliberately excludes
            # WRITTEN_OFF contracts (it's the due/overdue/aging
            # population, ACTIVE/DEFAULTED only) — this report's own
            # page is already bounded (<= `limit` contracts), so a
            # direct per-contract lookup here is O(page_size), never
            # O(every schedule line in the company), the N+1 T213
            # actually forbids.
            version = self._schedule.get_active_version(company_id, contract.id)
            own_lines = (
                self._schedule.get_lines(company_id, version.id)
                if version is not None
                else []
            )
            line_ids = [line.id for line in own_lines]
            net_allocated = self._allocation_refs.get_net_allocated_by_line(
                company_id, line_ids
            )
            written_off_amount = sum(
                (
                    line.scheduled_amount - net_allocated.get(line.id, Decimal("0"))
                    for line in own_lines
                    if line.waived_at is None and line.voided_at is None
                ),
                Decimal("0"),
            )
            rows.append(
                {
                    "report_type": "default-writeoff",
                    "contract_id": str(contract.id),
                    "contract_number": contract.contract_number,
                    "customer_id": str(contract.customer_id),
                    "defaulted_at": (
                        contract.defaulted_at.isoformat()
                        if contract.defaulted_at
                        else None
                    ),
                    "written_off_at": (
                        contract.written_off_at.isoformat()
                        if contract.written_off_at
                        else None
                    ),
                    "written_off_amount": str(written_off_amount),
                }
            )
        return rows, total

    # ------------------------------------------------------------------
    # Plan / template performance
    # ------------------------------------------------------------------

    def get_plan_performance_report(
        self, company_id: UUID
    ) -> tuple[list[dict[str, Any]], int]:
        self._authorize_read(company_id)
        aggregates = self._contracts.aggregate_by_plan_template(company_id)
        rows = [
            {
                "report_type": "plan-performance",
                "plan_template_id": (
                    str(plan_template_id) if plan_template_id else None
                ),
                "contract_count": count,
                "total_contractual_amount": str(total_amount),
            }
            for plan_template_id, count, total_amount in aggregates
        ]
        return rows, len(rows)

    # ------------------------------------------------------------------
    # Dashboard KPIs (T205) — non-double-counting derivation
    # ------------------------------------------------------------------

    def get_dashboard(
        self, company_id: UUID, *, as_of_date: date | None = None
    ) -> InstallmentDashboardData:
        self._authorize_read(company_id)
        business_date = as_of_date or get_business_date()
        month_start = business_date.replace(day=1)

        status_counts = self._contracts.count_by_status(company_id)
        active_contract_count = status_counts.get("ACTIVE", 0)

        schedule_outstanding = self._schedule.sum_schedule_outstanding_for_company(
            company_id
        )
        late_charge_outstanding = self._sum_late_charge_outstanding(company_id)
        outstanding_amount = schedule_outstanding + late_charge_outstanding

        collected_today = self._allocation_refs.sum_allocated_between(
            company_id, since=business_date, until=business_date
        )
        collected_this_month = self._allocation_refs.sum_allocated_between(
            company_id, since=month_start, until=business_date
        )

        pairs, _total = self._schedule.list_active_lines_for_company(
            company_id, skip=0, limit=self._DUE_STATE_POPULATION_BOUND
        )
        line_ids = [line.id for line, _c in pairs]
        net_allocated = self._allocation_refs.get_net_allocated_by_line(
            company_id, line_ids
        )

        due_today = Decimal("0")
        due_this_month = Decimal("0")
        overdue_amount = Decimal("0")
        overdue_count = 0
        upcoming_amount = Decimal("0")
        aging_distribution: dict[str, Decimal] = {
            "current": Decimal("0"),
            "days_1_30": Decimal("0"),
            "days_31_60": Decimal("0"),
            "days_61_90": Decimal("0"),
            "days_91_120": Decimal("0"),
            "days_120_plus": Decimal("0"),
        }
        month_end = _month_end(business_date)

        for line, contract in pairs:
            paid = net_allocated.get(line.id, Decimal("0"))
            due_state = DueStateCalculator.calculate(
                scheduled_amount=line.scheduled_amount,
                paid_amount=paid,
                due_date=line.due_date,
                business_date=business_date,
                grace_period_days=_grace_period_days(contract),
                waived_at=line.waived_at,
                voided_at=line.voided_at,
            )
            if due_state.state == "OVERDUE":
                overdue_amount += due_state.outstanding_amount
                overdue_count += 1
                bucket = InstallmentAgingCalculator.bucket_for(
                    line.due_date, business_date
                )
                aging_distribution[bucket] += due_state.outstanding_amount
                # FR-INST-081: already counted as overdue — never also
                # counted in "due today"/"due this month".
                continue
            if due_state.state in ("DUE", "PARTIALLY_PAID"):
                if line.due_date == business_date:
                    due_today += due_state.outstanding_amount
                if month_start <= line.due_date <= month_end:
                    due_this_month += due_state.outstanding_amount
            elif due_state.state == "UPCOMING":
                upcoming_amount += due_state.outstanding_amount

        collection_rate = _collection_rate(
            collected_this_month, collected_this_month + due_this_month
        )

        defaulted_balance = self._sum_outstanding_for_statuses(
            company_id, statuses=("DEFAULTED",)
        )
        written_off_balance = self._sum_written_off_balance(company_id)

        return InstallmentDashboardData(
            active_contract_count=active_contract_count,
            outstanding_amount=outstanding_amount,
            due_today_amount=due_today,
            due_this_month_amount=due_this_month,
            collected_today_amount=collected_today,
            collected_this_month_amount=collected_this_month,
            overdue_amount=overdue_amount,
            overdue_count=overdue_count,
            collection_rate=collection_rate,
            aging_distribution=aging_distribution,
            defaulted_balance=defaulted_balance,
            written_off_balance=written_off_balance,
            upcoming_receivables_amount=upcoming_amount,
        )

    def _sum_late_charge_outstanding(self, company_id: UUID) -> Decimal:
        """Bounded — one Installments query plus one Accounting aggregate
        query, never one Accounting round-trip per late charge (tasks.md
        T213)."""
        ar_transaction_ids = [
            charge.accounting_ar_transaction_id
            for charge in self._late_charges.list_for_company(company_id)
            if charge.accounting_ar_transaction_id is not None
        ]
        return self._accounting.sum_ar_transactions_outstanding(
            company_id, ar_transaction_ids
        )

    def _sum_outstanding_for_statuses(
        self, company_id: UUID, *, statuses: tuple[str, ...]
    ) -> Decimal:
        pairs, _total = self._schedule.list_active_lines_for_company(
            company_id, skip=0, limit=self._DUE_STATE_POPULATION_BOUND
        )
        relevant = [(line, c) for line, c in pairs if c.status in statuses]
        line_ids = [line.id for line, _c in relevant]
        net_allocated = self._allocation_refs.get_net_allocated_by_line(
            company_id, line_ids
        )
        return sum(
            (
                line.scheduled_amount - net_allocated.get(line.id, Decimal("0"))
                for line, _c in relevant
            ),
            Decimal("0"),
        )

    def _sum_written_off_balance(self, company_id: UUID) -> Decimal:
        """One aggregate query, never a loop over every WRITTEN_OFF
        contract (that would be the exact N+1 pattern T213 forbids —
        ``get_default_writeoff_report`` is fine on its own since the
        router page-bounds it, but the dashboard must not call it with
        an inflated ``limit`` to approximate a company-wide total)."""
        return self._schedule.sum_schedule_outstanding_for_statuses(
            company_id, statuses=("WRITTEN_OFF",)
        )


def _month_end(business_date: date) -> date:
    if business_date.month == 12:
        next_month_start = date(business_date.year + 1, 1, 1)
    else:
        next_month_start = date(business_date.year, business_date.month + 1, 1)
    return next_month_start - timedelta(days=1)


def _collection_rate(collected: Decimal, expected: Decimal) -> Decimal:
    if expected <= Decimal("0"):
        return Decimal("0")
    return (collected / expected).quantize(Decimal("0.0001"))
