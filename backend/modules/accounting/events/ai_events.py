"""AI ERP readiness domain events — Phase 17.

  AnomalyDetectedEvent — ``accounting.anomaly.detected``

Spec ref: specs/008-accounting-finance/contracts/events.md, tasks.md T307
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from modules.accounting.events import AccountingDomainEvent


@dataclass
class AnomalyDetectedEvent(AccountingDomainEvent):
    """``accounting.anomaly.detected`` — published by
    ``AIReadinessService.record_anomaly_report()`` for each journal entry
    flagged via ``POST /accounting/ai/anomaly-report``.
    """

    journal_entry_id: UUID | None = None
    anomaly_flag_id: UUID | None = None
    reason: str | None = None


__all__ = ["AnomalyDetectedEvent"]
