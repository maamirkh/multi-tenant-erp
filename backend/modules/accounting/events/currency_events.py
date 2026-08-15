"""Currency revaluation domain events — Phase 12.

  RevaluationCompletedEvent — ``accounting.revaluation.completed``

Spec ref: specs/008-accounting-finance/contracts/events.md, tasks.md T249
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from modules.accounting.events import AccountingDomainEvent


@dataclass
class RevaluationCompletedEvent(AccountingDomainEvent):
    """``accounting.revaluation.completed`` — published by
    ``CurrencyRevaluationService.run_revaluation()`` on completion.
    """

    fiscal_period_id: UUID | None = None
    revaluation_date: str | None = None
    currencies_revalued: list[str] = field(default_factory=list)
    total_unrealized_gain_base: Decimal | None = None
    total_unrealized_loss_base: Decimal | None = None
    net_gain_loss_base: Decimal | None = None
    journal_entry_id: UUID | None = None


__all__ = ["RevaluationCompletedEvent"]
