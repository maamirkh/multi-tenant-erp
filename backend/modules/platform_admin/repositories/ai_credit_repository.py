"""AiCreditRepository — data access for `AiCreditLedgerEntry` (T154).

Write paths `flush()` only, never `commit()` (ADR-5) — the calling
service owns the transaction boundary.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.platform_admin.models.ai_credit_ledger import AiCreditLedgerEntry


class AiCreditRepository:
    """Data access for `ai_credit_ledger_entries`."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_company(self, company_id: UUID) -> list[AiCreditLedgerEntry]:
        stmt = (
            select(AiCreditLedgerEntry)
            .where(AiCreditLedgerEntry.company_id == company_id)
            .order_by(AiCreditLedgerEntry.occurred_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_balance(self, company_id: UUID) -> Decimal:
        """Current balance = SUM(delta) — zero (not None/unavailable)
        when no ledger rows exist yet, since an empty ledger genuinely
        means a zero balance, not an unmeasured quantity."""
        stmt = select(func.coalesce(func.sum(AiCreditLedgerEntry.delta), 0)).where(
            AiCreditLedgerEntry.company_id == company_id
        )
        return Decimal(self.db.execute(stmt).scalar_one())

    def create_entry(
        self,
        *,
        company_id: UUID,
        delta: Decimal,
        occurred_at: datetime,
        reason: str | None = None,
        actor_platform_administrator_id: UUID | None = None,
        platform_audit_event_id: UUID | None = None,
        provider: str | None = None,
        model: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        estimated_cost: Decimal | None = None,
        billable_cost: Decimal | None = None,
    ) -> AiCreditLedgerEntry:
        """Stage a new ledger entry. Caller commits."""
        entry = AiCreditLedgerEntry(
            company_id=company_id,
            delta=delta,
            occurred_at=occurred_at,
            reason=reason,
            actor_platform_administrator_id=actor_platform_administrator_id,
            platform_audit_event_id=platform_audit_event_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            billable_cost=billable_cost,
        )
        self.db.add(entry)
        self.db.flush()
        return entry
