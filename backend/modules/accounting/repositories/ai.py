"""Repository for AI readiness entities — Phase 17.

Spec ref: specs/008-accounting-finance/tasks.md T307
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from modules.accounting.models.ai import AccountingAnomalyFlag
from modules.accounting.repositories import BaseAccountingRepository


class AccountingAnomalyFlagRepository(BaseAccountingRepository[AccountingAnomalyFlag]):
    """Data-access layer for the ``accounting_anomaly_flags`` table.

    Only ``create()`` (inherited from ``BaseAccountingRepository``) is used
    by this phase's stub — no listing/review endpoint exists yet (out of
    T307's scope), so no additional query methods are added speculatively.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=AccountingAnomalyFlag)
