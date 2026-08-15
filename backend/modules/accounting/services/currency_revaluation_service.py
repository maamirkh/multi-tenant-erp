"""CurrencyRevaluationService — Multi-Currency & Exchange Rates — Phase 12.

Executes period-end revaluation of open foreign-currency AR/AP exposure:
compares each open transaction's booking rate to the current rate (as of
the revaluation date) and posts the aggregate unrealized gain/loss as ONE
journal entry via ``PostingEngine`` (research.md Decision 2 — PostingEngine
is the single GL posting gate).

Sign convention mirrors ``AllocationEngine``'s realized gain/loss exactly
(module docstring there, and the module PHR for this phase):
  AR (asset, debit-normal):  diff = outstanding_foreign * (current_rate - booking_rate)
  AP (liability, credit-normal): diff = outstanding_foreign * (booking_rate - current_rate)
A positive diff is always a DEBIT to the transaction's control account and
a CREDIT to the gain account; a negative diff is always the reverse. Gain
and loss are posted at their GROSS totals (not netted against each other)
so both are visible in the ledger, while each control account (AR/AP) is
posted at its NET total — this still balances because, by construction,
every individual diff's control-account leg equals its gain/loss leg in
magnitude (see the module PHR for the derivation).

"Reversible" (tasks.md T247) is satisfied by posting as a normal ADJUSTING
journal entry, which — like any other POSTED entry in this module — can be
reversed via the existing ``PostingEngine.reverse()`` / ``POST
/accounting/journals/{id}/reverse`` at the start of the next period; this
phase does not add new scheduling infrastructure to automate that reversal
(no such task exists in tasks.md T247-T254).

Spec ref: specs/008-accounting-finance/spec.md §24 Multi-Currency
Tasks ref: specs/008-accounting-finance/tasks.md T247, T249
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.accounting.events import get_event_bus
from modules.accounting.events.currency_events import RevaluationCompletedEvent
from modules.accounting.exceptions import (
    CurrencyRevaluationRunNotFoundError,
    FiscalPeriodNotFoundError,
    PostingValidationError,
)
from modules.accounting.models.currency import CurrencyRevaluationRun
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.ap import SupplierLedgerRepository
from modules.accounting.repositories.ar import CustomerLedgerRepository
from modules.accounting.repositories.currency import CurrencyRevaluationRunRepository
from modules.accounting.repositories.fiscal import FiscalPeriodRepository
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.services.currency_service import CurrencyService
from modules.accounting.services.posting_engine import PostingEngine

logger = logging.getLogger(__name__)


_AMOUNT_QUANT = Decimal("0.000001")
_RATE_QUANT = Decimal("0.0000000001")


def _fmt(value: Decimal, quant: Decimal) -> str:
    """Render a Decimal as fixed-point (never scientific notation).

    Plain ``str(Decimal(...))`` can normalize an exact quotient into
    scientific notation (e.g. ``Decimal("1100") / Decimal("1.1")`` ->
    ``Decimal("1E+3")``) — this showed up verbatim in the live API response
    for ``outstanding_foreign`` before this fix. Quantizing to the field's
    natural DB precision before using the ``f`` format spec guarantees a
    fixed-point string every time.
    """
    return format(value.quantize(quant), "f")


@dataclass
class _RevalLine:
    transaction_type: str
    transaction_id: UUID
    currency_code: str
    booking_rate: Decimal
    current_rate: Decimal
    outstanding_foreign: Decimal
    outstanding_base_before: Decimal
    gain_loss_amount: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "transaction_type": self.transaction_type,
            "transaction_id": str(self.transaction_id),
            "currency_code": self.currency_code,
            "booking_rate": _fmt(self.booking_rate, _RATE_QUANT),
            "current_rate": _fmt(self.current_rate, _RATE_QUANT),
            "outstanding_foreign": _fmt(self.outstanding_foreign, _AMOUNT_QUANT),
            "outstanding_base_before": _fmt(
                self.outstanding_base_before, _AMOUNT_QUANT
            ),
            "gain_loss_amount": _fmt(self.gain_loss_amount, _AMOUNT_QUANT),
        }


class CurrencyRevaluationService:
    """Executes period-end unrealized FX gain/loss revaluation."""

    def __init__(
        self,
        db: Session,
        customer_ledger_repo: CustomerLedgerRepository,
        supplier_ledger_repo: SupplierLedgerRepository,
        config_repo: AccountingConfigurationRepository,
        fiscal_period_repo: FiscalPeriodRepository,
        run_repo: CurrencyRevaluationRunRepository,
        currency_service: CurrencyService,
        posting_engine: PostingEngine,
    ) -> None:
        self.db = db
        self._customer_ledgers = customer_ledger_repo
        self._supplier_ledgers = supplier_ledger_repo
        self._config_repo = config_repo
        self._periods = fiscal_period_repo
        self._runs = run_repo
        self._currency = currency_service
        self._engine = posting_engine

    def run_revaluation(
        self,
        company_id: UUID,
        period_id: UUID,
        revaluation_date: date,
        actor_id: UUID | None = None,
    ) -> CurrencyRevaluationRun:
        """Revalue every open foreign-currency AR/AP transaction as of
        ``revaluation_date`` and post the aggregate unrealized gain/loss.

        Raises:
            FiscalPeriodNotFoundError: ``period_id`` does not exist for this company.
            PostingValidationError: Accounting configuration or the required
                gain/loss/control accounts are not set up for this company.
        """
        period = self._periods.get_by_id_or_none(id=period_id, company_id=company_id)
        if period is None:
            raise FiscalPeriodNotFoundError(fiscal_period_id=str(period_id))

        config = self._config_repo.get_for_company(company_id=company_id)
        if config is None:
            raise PostingValidationError(
                "Cannot run currency revaluation: accounting configuration is "
                "not set up for this company."
            )
        base_currency = config.base_currency_code

        ar_open = self._customer_ledgers.get_aging_data(company_id, revaluation_date)
        ap_open = self._supplier_ledgers.get_aging_data(company_id, revaluation_date)

        lines: list[_RevalLine] = []
        ar_diff_total = Decimal("0")
        ap_diff_total = Decimal("0")
        currencies: set[str] = set()

        for txn in ar_open:
            if txn.currency_code == base_currency or txn.outstanding_amount == 0:
                continue
            current_rate = self._currency.get_rate(
                company_id, txn.currency_code, base_currency, revaluation_date
            )
            outstanding_foreign = txn.outstanding_amount / txn.exchange_rate
            diff = outstanding_foreign * (current_rate - txn.exchange_rate)
            if diff == 0:
                continue
            ar_diff_total += diff
            currencies.add(txn.currency_code)
            lines.append(
                _RevalLine(
                    transaction_type="AR",
                    transaction_id=txn.id,
                    currency_code=txn.currency_code,
                    booking_rate=txn.exchange_rate,
                    current_rate=current_rate,
                    outstanding_foreign=outstanding_foreign,
                    outstanding_base_before=txn.outstanding_amount,
                    gain_loss_amount=diff,
                )
            )

        for ap_txn in ap_open:
            if ap_txn.currency_code == base_currency or ap_txn.outstanding_amount == 0:
                continue
            current_rate = self._currency.get_rate(
                company_id, ap_txn.currency_code, base_currency, revaluation_date
            )
            outstanding_foreign = ap_txn.outstanding_amount / ap_txn.exchange_rate
            diff = outstanding_foreign * (ap_txn.exchange_rate - current_rate)
            if diff == 0:
                continue
            ap_diff_total += diff
            currencies.add(ap_txn.currency_code)
            lines.append(
                _RevalLine(
                    transaction_type="AP",
                    transaction_id=ap_txn.id,
                    currency_code=ap_txn.currency_code,
                    booking_rate=ap_txn.exchange_rate,
                    current_rate=current_rate,
                    outstanding_foreign=outstanding_foreign,
                    outstanding_base_before=ap_txn.outstanding_amount,
                    gain_loss_amount=diff,
                )
            )

        total_gain = sum(
            (line.gain_loss_amount for line in lines if line.gain_loss_amount > 0),
            Decimal("0"),
        )
        total_loss = sum(
            (-line.gain_loss_amount for line in lines if line.gain_loss_amount < 0),
            Decimal("0"),
        )
        net_gain_loss = total_gain - total_loss

        run_id = uuid4()
        journal_entry_id: UUID | None = None

        if lines:
            journal_entry_id = self._post_revaluation_entry(
                company_id=company_id,
                config=config,
                ar_diff_total=ar_diff_total,
                ap_diff_total=ap_diff_total,
                total_gain=total_gain,
                total_loss=total_loss,
                revaluation_date=revaluation_date,
                run_id=run_id,
                actor_id=actor_id,
            )

        run = CurrencyRevaluationRun(
            id=run_id,
            company_id=company_id,
            fiscal_period_id=period_id,
            revaluation_date=revaluation_date,
            currencies_revalued=sorted(currencies),
            total_unrealized_gain_base=total_gain,
            total_unrealized_loss_base=total_loss,
            net_gain_loss_base=net_gain_loss,
            journal_entry_id=journal_entry_id,
            lines=[line.to_dict() for line in lines],
            created_by=actor_id,
        )
        self._runs.create(run)

        get_event_bus().publish(
            RevaluationCompletedEvent(
                event_type="accounting.revaluation.completed",
                aggregate_type="CurrencyRevaluationRun",
                aggregate_id=run.id,
                company_id=company_id,
                actor_id=actor_id,
                fiscal_period_id=period_id,
                revaluation_date=revaluation_date.isoformat(),
                currencies_revalued=sorted(currencies),
                total_unrealized_gain_base=total_gain,
                total_unrealized_loss_base=total_loss,
                net_gain_loss_base=net_gain_loss,
                journal_entry_id=journal_entry_id,
            )
        )
        return run

    def _post_revaluation_entry(
        self,
        company_id: UUID,
        config: AccountingConfiguration,
        ar_diff_total: Decimal,
        ap_diff_total: Decimal,
        total_gain: Decimal,
        total_loss: Decimal,
        revaluation_date: date,
        run_id: UUID,
        actor_id: UUID | None,
    ) -> UUID:
        if (total_gain > 0 or total_loss > 0) and (
            config.default_exchange_gain_account_id is None
            or config.default_exchange_loss_account_id is None
        ):
            raise PostingValidationError(
                "Cannot post currency revaluation: default exchange gain/loss "
                "accounts are not configured for this company."
            )
        if ar_diff_total != 0 and config.default_ar_account_id is None:
            raise PostingValidationError(
                "Cannot post currency revaluation: default AR control account "
                "is not configured for this company."
            )
        if ap_diff_total != 0 and config.default_ap_account_id is None:
            raise PostingValidationError(
                "Cannot post currency revaluation: default AP control account "
                "is not configured for this company."
            )

        lines: list[dict[str, object]] = []
        if ar_diff_total > 0:
            lines.append(
                {
                    "account_id": config.default_ar_account_id,
                    "debit_amount": ar_diff_total,
                    "credit_amount": Decimal("0"),
                }
            )
        elif ar_diff_total < 0:
            lines.append(
                {
                    "account_id": config.default_ar_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": -ar_diff_total,
                }
            )

        if ap_diff_total > 0:
            lines.append(
                {
                    "account_id": config.default_ap_account_id,
                    "debit_amount": ap_diff_total,
                    "credit_amount": Decimal("0"),
                }
            )
        elif ap_diff_total < 0:
            lines.append(
                {
                    "account_id": config.default_ap_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": -ap_diff_total,
                }
            )

        if total_gain > 0:
            lines.append(
                {
                    "account_id": config.default_exchange_gain_account_id,
                    "debit_amount": Decimal("0"),
                    "credit_amount": total_gain,
                }
            )
        if total_loss > 0:
            lines.append(
                {
                    "account_id": config.default_exchange_loss_account_id,
                    "debit_amount": total_loss,
                    "credit_amount": Decimal("0"),
                }
            )

        result = self._engine.post_direct(
            company_id=company_id,
            journal_type="ADJUSTING",
            posting_source="SYSTEM",
            posting_date=revaluation_date,
            lines=lines,
            currency_code=config.base_currency_code,
            description=f"Currency revaluation as of {revaluation_date.isoformat()}",
            source_document_type="CurrencyRevaluation",
            source_document_id=run_id,
            actor_id=actor_id,
        )
        return result.journal_entry_id

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_revaluation(self, company_id: UUID, run_id: UUID) -> CurrencyRevaluationRun:
        run = self._runs.get_by_id_or_none(id=run_id, company_id=company_id)
        if run is None:
            raise CurrencyRevaluationRunNotFoundError(run_id=str(run_id))
        return run

    def list_revaluation_history(
        self, company_id: UUID
    ) -> list[CurrencyRevaluationRun]:
        return self._runs.list_all(company_id)
