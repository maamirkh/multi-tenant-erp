"""TaxService — Tax Engine configuration and reporting — Phase 11.

Configuration (tax codes, rate history, tax groups) plus the three tax
reports spec.md §23.8 lists: VAT/GST Summary, Tax Detail, and Withholding
Tax Report.

Report correlation design: since no ``tax_code_id`` column exists on the
append-only ``accounting_journal_lines`` table (see models/tax.py's module
docstring for why), every report correlates postings to a ``TaxCode`` via
that code's own ``gl_account_id`` — each tax code owns exactly one
dedicated GL account (data-model.md §2.9), so the account itself is a
sufficient join key, mirroring ``GLReportRepository.account_balance_query()``'s
established pattern.

VAT summary classification: rather than trusting ``TaxCode.applicability``
(SALES/PURCHASES/BOTH) to say which side of the ledger a given posting
belongs to — a BOTH-scoped code's own field can't disambiguate an
individual GL line — this uses the GL entry's own debit/credit direction,
which is always correct regardless of how the code is scoped: a credit to
a tax account is tax collected (output), a debit is tax paid (input).
"Recoverable" input tax (spec.md §23.6) is exactly ``TaxCode.
is_input_tax_recoverable`` — Net Payable = Output Tax − recoverable Input Tax.

WHT report: Phase 10's ``Payment.wht_amount`` already captures WHT
deducted per supplier disbursement (no TaxCode linkage exists for it —
Phase 10 shipped independently of the Tax Engine); this report reads that
field directly via ``PaymentRepository.find_wht_payments()`` rather than
inventing a retroactive TaxCode association Phase 10 never had.

Spec ref: specs/008-accounting-finance/spec.md §23 Tax Management
Tasks ref: specs/008-accounting-finance/tasks.md T232
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.exceptions import (
    AccountingException,
    PostingValidationError,
    TaxCodeNotFoundError,
    TaxGroupNotFoundError,
    TaxRateOverlapError,
)
from modules.accounting.models.tax import TaxCode, TaxGroup, TaxGroupLine, TaxRate
from modules.accounting.repositories.gl import GLReportRepository
from modules.accounting.repositories.payments import PaymentRepository
from modules.accounting.repositories.tax import (
    TaxCodeRepository,
    TaxGroupLineRepository,
    TaxGroupRepository,
    TaxRateRepository,
)


class TaxService:
    """Application service for tax code/group configuration and reporting."""

    def __init__(
        self,
        db: Session,
        tax_code_repo: TaxCodeRepository,
        tax_rate_repo: TaxRateRepository,
        tax_group_repo: TaxGroupRepository,
        tax_group_line_repo: TaxGroupLineRepository,
        payment_repo: PaymentRepository,
    ) -> None:
        self.db = db
        self._tax_codes = tax_code_repo
        self._tax_rates = tax_rate_repo
        self._tax_groups = tax_group_repo
        self._tax_group_lines = tax_group_line_repo
        self._payments = payment_repo
        self._gl_reports = GLReportRepository(db)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def create_tax_code(
        self,
        company_id: UUID,
        tax_code: str,
        tax_name: str,
        tax_type: str,
        applicability: str,
        gl_account_id: UUID,
        is_input_tax_recoverable: bool = False,
        country_code: str | None = None,
        actor_id: UUID | None = None,
    ) -> TaxCode:
        if self._tax_codes.find_by_code(company_id, tax_code) is not None:
            raise AccountingException(
                message=f"Tax code '{tax_code}' already exists for this company.",
                code="DUPLICATE_TAX_CODE",
                details={"tax_code": tax_code},
                http_status=409,
            )
        return self._tax_codes.create(
            TaxCode(
                company_id=company_id,
                tax_code=tax_code,
                tax_name=tax_name,
                tax_type=tax_type,
                applicability=applicability,
                gl_account_id=gl_account_id,
                is_input_tax_recoverable=is_input_tax_recoverable,
                country_code=country_code,
                created_by=actor_id,
            )
        )

    def get_tax_code(self, company_id: UUID, tax_code_id: UUID) -> TaxCode:
        tax_code = self._tax_codes.get_by_id_or_none(
            id=tax_code_id, company_id=company_id
        )
        if tax_code is None:
            raise TaxCodeNotFoundError(tax_code_id=str(tax_code_id))
        return tax_code

    def list_tax_codes(
        self, company_id: UUID, active_only: bool = False
    ) -> list[TaxCode]:
        return self._tax_codes.list_all(company_id, active_only=active_only)

    def update_tax_code(
        self, company_id: UUID, tax_code_id: UUID, **fields: Any
    ) -> TaxCode:
        tax_code = self.get_tax_code(company_id, tax_code_id)
        for key, value in fields.items():
            if value is not None and hasattr(tax_code, key):
                setattr(tax_code, key, value)
        return self._tax_codes.update(tax_code)

    def update_tax_rate(
        self,
        company_id: UUID,
        tax_code_id: UUID,
        effective_from: date,
        rate: Decimal,
        effective_to: date | None = None,
        rounding_rule: str = "HALF_UP",
        actor_id: UUID | None = None,
    ) -> TaxRate:
        """Add a new rate to a tax code's history.

        When ``effective_to`` is omitted (a new ongoing/current rate), any
        existing open-ended rate is automatically closed the day before
        ``effective_from`` — the standard "rate change" workflow. Any
        other overlap against existing history is rejected.
        """
        self.get_tax_code(company_id, tax_code_id)  # existence/tenant check
        if rate < 0:
            raise PostingValidationError("Tax rate cannot be negative.")
        if effective_to is not None and effective_to < effective_from:
            raise PostingValidationError(
                "effective_to cannot be before effective_from."
            )

        existing_rates = self._tax_rates.find_by_tax_code(company_id, tax_code_id)

        open_ended_predecessor = next(
            (
                r
                for r in existing_rates
                if r.effective_to is None and r.effective_from < effective_from
            ),
            None,
        )
        if effective_to is None and open_ended_predecessor is not None:
            open_ended_predecessor.effective_to = effective_from - timedelta(days=1)
            self.db.add(open_ended_predecessor)
            self.db.flush()

        for existing in existing_rates:
            if existing.id == getattr(open_ended_predecessor, "id", None):
                continue  # just closed above — no longer overlaps by construction
            existing_end = existing.effective_to or date.max
            new_end = effective_to or date.max
            if existing.effective_from <= new_end and effective_from <= existing_end:
                raise TaxRateOverlapError(str(tax_code_id))

        new_rate = TaxRate(
            company_id=company_id,
            tax_code_id=tax_code_id,
            effective_from=effective_from,
            effective_to=effective_to,
            rate=rate,
            rounding_rule=rounding_rule,
            created_by=actor_id,
        )
        return self._tax_rates.create(new_rate)

    def list_tax_rates(self, company_id: UUID, tax_code_id: UUID) -> list[TaxRate]:
        self.get_tax_code(company_id, tax_code_id)
        return self._tax_rates.find_by_tax_code(company_id, tax_code_id)

    def create_tax_group(
        self,
        company_id: UUID,
        group_code: str,
        group_name: str,
        applicability: str,
        actor_id: UUID | None = None,
    ) -> TaxGroup:
        if self._tax_groups.find_by_code(company_id, group_code) is not None:
            raise AccountingException(
                message=f"Tax group '{group_code}' already exists for this company.",
                code="DUPLICATE_TAX_GROUP_CODE",
                details={"group_code": group_code},
                http_status=409,
            )
        return self._tax_groups.create(
            TaxGroup(
                company_id=company_id,
                group_code=group_code,
                group_name=group_name,
                applicability=applicability,
                created_by=actor_id,
            )
        )

    def get_tax_group(self, company_id: UUID, tax_group_id: UUID) -> TaxGroup:
        tax_group = self._tax_groups.get_by_id_or_none(
            id=tax_group_id, company_id=company_id
        )
        if tax_group is None:
            raise TaxGroupNotFoundError(tax_group_id=str(tax_group_id))
        return tax_group

    def list_tax_groups(
        self, company_id: UUID, active_only: bool = False
    ) -> list[TaxGroup]:
        return self._tax_groups.list_all(company_id, active_only=active_only)

    def add_group_line(
        self,
        company_id: UUID,
        tax_group_id: UUID,
        tax_code_id: UUID,
        display_order: int = 0,
        actor_id: UUID | None = None,
    ) -> TaxGroupLine:
        self.get_tax_group(company_id, tax_group_id)
        self.get_tax_code(company_id, tax_code_id)
        return self._tax_group_lines.create(
            TaxGroupLine(
                company_id=company_id,
                tax_group_id=tax_group_id,
                tax_code_id=tax_code_id,
                display_order=display_order,
                created_by=actor_id,
            )
        )

    def list_group_lines(
        self, company_id: UUID, tax_group_id: UUID
    ) -> list[TaxGroupLine]:
        self.get_tax_group(company_id, tax_group_id)
        return self._tax_group_lines.find_by_group(company_id, tax_group_id)

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def get_vat_summary_report(
        self, company_id: UUID, period_start: date, period_end: date
    ) -> dict[str, Any]:
        """Output tax, input tax, and net payable — broken down by tax
        code (spec.md §39.4 "Tax Summary Report ... by tax code").
        """
        rows: list[dict[str, Any]] = []
        total_output = Decimal("0")
        total_recoverable_input = Decimal("0")

        for tax_code in self._tax_codes.list_all(company_id):
            balances = self._gl_reports.account_balance_query(
                company_id=company_id,
                account_id=tax_code.gl_account_id,
                start_date=period_start,
                end_date=period_end,
            )
            output_tax = balances["total_credit"]
            input_tax = balances["total_debit"]
            if output_tax == 0 and input_tax == 0:
                continue

            rows.append(
                {
                    "tax_code_id": tax_code.id,
                    "tax_code": tax_code.tax_code,
                    "tax_name": tax_code.tax_name,
                    "output_tax": output_tax,
                    "input_tax": input_tax,
                    "is_input_tax_recoverable": tax_code.is_input_tax_recoverable,
                }
            )
            total_output += output_tax
            if tax_code.is_input_tax_recoverable:
                total_recoverable_input += input_tax

        return {
            "period_start": period_start,
            "period_end": period_end,
            "rows": rows,
            "total_output_tax": total_output,
            "total_input_tax": total_recoverable_input,
            "net_payable": total_output - total_recoverable_input,
        }

    def get_tax_detail_report(
        self,
        company_id: UUID,
        period_start: date | None = None,
        period_end: date | None = None,
        tax_code_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        """Every individual GL line posted to a tax code's account
        (spec.md §39.4 "Detailed Tax Transaction Report").
        """
        codes = (
            [self.get_tax_code(company_id, tax_code_id)]
            if tax_code_id is not None
            else self._tax_codes.list_all(company_id)
        )

        rows: list[dict[str, Any]] = []
        for code in codes:
            items, _total = self._gl_reports.gl_detail_query(
                company_id=company_id,
                account_id=code.gl_account_id,
                start_date=period_start,
                end_date=period_end,
                limit=10_000,
            )
            for item in items:
                rows.append(
                    {
                        **item,
                        "tax_code_id": code.id,
                        "tax_code": code.tax_code,
                        "tax_type": code.tax_type,
                    }
                )
        rows.sort(key=lambda r: r["posting_date"])
        return rows

    def get_wht_report(
        self, company_id: UUID, period_start: date, period_end: date
    ) -> dict[str, Any]:
        """WHT deducted per supplier for the period (spec.md §23.8/§39.4
        "Withholding Tax Report").
        """
        payments = self._payments.find_wht_payments(
            company_id, period_start, period_end
        )

        by_supplier: dict[UUID, dict[str, Any]] = {}
        for payment in payments:
            bucket = by_supplier.setdefault(
                payment.party_id,
                {
                    "supplier_id": payment.party_id,
                    "gross_amount": Decimal("0"),
                    "wht_amount": Decimal("0"),
                    "net_amount": Decimal("0"),
                    "payment_count": 0,
                },
            )
            bucket["gross_amount"] += payment.amount_base
            bucket["wht_amount"] += payment.wht_amount
            bucket["net_amount"] += payment.amount_base - payment.wht_amount
            bucket["payment_count"] += 1

        rows = sorted(by_supplier.values(), key=lambda r: r["supplier_id"].hex)
        return {
            "period_start": period_start,
            "period_end": period_end,
            "rows": rows,
            "total_wht": sum((r["wht_amount"] for r in rows), Decimal("0")),
        }
