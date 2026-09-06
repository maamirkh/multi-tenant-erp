"""AiCreditService — manual AI credit adjustment (T155, BR-9A-026/027).

Provider-neutral: this phase (and the whole of Epic 9A) integrates no AI
provider (plan.md Architecture Freeze) — every manually-adjusted entry
carries `provider`/`model`/token/cost fields as NULL; those columns exist
only for a future automatic usage-debit path this phase does not build.

Fail-closed atomicity (ADR-5): stage the ledger entry plus an audit row
(both flush-only), link the entry back to its own audit event
(`platform_audit_event_id`, BR-9A-027), then a single service-level
`db.commit()`.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import ValidationException
from core.utils.datetime import utcnow
from modules.platform_admin.models.ai_credit_ledger import AiCreditLedgerEntry
from modules.platform_admin.repositories.ai_credit_repository import AiCreditRepository
from modules.platform_admin.services.platform_audit_service import PlatformAuditService


def _snapshot(entry: AiCreditLedgerEntry) -> dict[str, object]:
    return {
        "company_id": str(entry.company_id),
        "delta": str(entry.delta),
        "reason": entry.reason,
    }


class AiCreditService:
    """Domain service for manual AI credit ledger adjustments."""

    def __init__(
        self,
        db: Session,
        repo: AiCreditRepository,
        audit: PlatformAuditService,
    ) -> None:
        self._db = db
        self._repo = repo
        self._audit = audit

    def adjust(
        self,
        *,
        company_id: UUID,
        delta: Decimal,
        reason: str,
        actor_platform_administrator_id: UUID,
    ) -> AiCreditLedgerEntry:
        """Manually adjust a tenant's AI credit balance by *delta*
        (positive = grant, negative = debit). *reason* is mandatory for
        every manual adjustment (BR-9A-026).

        Raises:
            ValidationException: *reason* is empty/blank.
        """
        if not reason or not reason.strip():
            raise ValidationException(
                "reason is required for a manual AI credit adjustment."
            )

        entry = self._repo.create_entry(
            company_id=company_id,
            delta=delta,
            occurred_at=utcnow(),
            reason=reason,
            actor_platform_administrator_id=actor_platform_administrator_id,
        )
        audit_event = self._audit.record(
            action="ai_credit.adjust",
            target_type="AiCreditLedgerEntry",
            target_id=entry.id,
            company_id=company_id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            after_state=_snapshot(entry),
        )
        entry.platform_audit_event_id = audit_event.id
        self._db.flush()
        self._db.commit()
        return entry

    def get_balance(self, company_id: UUID) -> Decimal:
        return self._repo.get_balance(company_id)

    def list_ledger(self, company_id: UUID) -> list[AiCreditLedgerEntry]:
        return self._repo.list_for_company(company_id)
