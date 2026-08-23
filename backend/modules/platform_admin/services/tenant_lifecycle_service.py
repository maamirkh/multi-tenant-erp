"""TenantLifecycleService — suspend()/reactivate() (T088/T089, ADR-12).

Fail-closed atomicity (ADR-5): each method locks the ``Company`` row
(``SELECT ... FOR UPDATE``, real-PostgreSQL-only semantics), validates the
transition, stages the state change (flush-only,
``CompanyRepository.suspend()``/``reactivate()``), stages an
``OutboxRecord`` (flush-only, ``EventOutboxRepository.create()``), stages
an audit row (flush-only, ``PlatformAuditService.record()``), then
performs a single service-level ``db.commit()``. If any step raises, the
whole transaction is rolled back by the caller — nothing partial
persists.

Reactivation restores the **recorded** ``pre_suspension_status`` — never
a hardcoded ``active`` (ADR-12) — and deliberately leaves
``access_invalidated_at`` untouched, so pre-suspension ``Session`` rows
stay refused for this company even after the status is restored
(FR-9A-018); only a genuine new login can advance past the watermark.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from core.events.outbox import EventOutboxRepository
from core.logging.setup import REQUEST_ID_CONTEXT
from modules.companies.events import CompanySuspendedEvent, CompanySuspensionLiftedEvent
from modules.companies.exceptions import CompanyNotFoundError
from modules.companies.models.company import Company
from modules.companies.models.enums import CompanyStatus
from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.exceptions import TenantLifecycleTransitionError
from modules.platform_admin.services.platform_audit_service import PlatformAuditService

_SUSPENDABLE_STATUSES = frozenset(
    {CompanyStatus.active.value, CompanyStatus.inactive.value}
)

logger = logging.getLogger(__name__)


def _new_correlation_id() -> str:
    return str(uuid.uuid4())


def _lifecycle_snapshot(company: Company) -> dict[str, str | None]:
    return {
        "status": company.status,
        "pre_suspension_status": company.pre_suspension_status,
        "access_invalidated_at": (
            company.access_invalidated_at.isoformat()
            if company.access_invalidated_at
            else None
        ),
    }


class TenantLifecycleService:
    """Domain service for Platform-initiated tenant suspend/reactivate."""

    def __init__(
        self,
        db: Session,
        company_repo: CompanyRepository,
        outbox_repo: EventOutboxRepository,
        audit: PlatformAuditService,
    ) -> None:
        self._db = db
        self._company_repo = company_repo
        self._outbox_repo = outbox_repo
        self._audit = audit

    def suspend(
        self,
        *,
        company_id: UUID,
        actor_platform_administrator_id: UUID,
        reason: str,
    ) -> Company:
        """Suspend a tenant (active/inactive -> suspended).

        Raises:
            CompanyNotFoundError: No company with this id.
            TenantLifecycleTransitionError: Company is not currently
                ``active``/``inactive`` (Edge Case #1 — already suspended,
                or a deleted/pending_setup company).
        """
        company = self._company_repo.get_for_update(company_id)
        if company is None:
            raise CompanyNotFoundError()

        if company.status not in _SUSPENDABLE_STATUSES:
            logger.warning(
                "Platform tenant suspend rejected",
                extra={
                    "request_id": REQUEST_ID_CONTEXT.get("-"),
                    "company_id": str(company_id),
                    "current_status": company.status,
                    "platform_administrator_id": str(actor_platform_administrator_id),
                },
            )
            raise TenantLifecycleTransitionError(
                f"Cannot suspend a company with status '{company.status}'. "
                "Only 'active' or 'inactive' companies may be suspended."
            )

        before_state = _lifecycle_snapshot(company)
        pre_suspension_status = company.status
        now = datetime.now(UTC)

        self._company_repo.suspend(
            company,
            pre_suspension_status=pre_suspension_status,
            access_invalidated_at=now,
        )

        event = CompanySuspendedEvent(
            company_id=company.id, reason=reason, suspended_at=now
        )
        self._outbox_repo.create(
            event.to_outbox_record(
                _new_correlation_id(), actor_platform_administrator_id
            )
        )

        self._audit.record(
            action="tenant_lifecycle.suspend",
            target_type="Company",
            target_id=company.id,
            company_id=company.id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=before_state,
            after_state=_lifecycle_snapshot(company),
        )
        self._db.commit()
        logger.info(
            "Platform tenant suspended",
            extra={
                "request_id": REQUEST_ID_CONTEXT.get("-"),
                "company_id": str(company.id),
                "platform_administrator_id": str(actor_platform_administrator_id),
                "pre_suspension_status": pre_suspension_status,
            },
        )
        return company

    def reactivate(
        self,
        *,
        company_id: UUID,
        actor_platform_administrator_id: UUID,
        reason: str,
    ) -> Company:
        """Reactivate a tenant (suspended -> its recorded pre-suspension
        status).

        Raises:
            CompanyNotFoundError: No company with this id.
            TenantLifecycleTransitionError: Company is not currently
                ``suspended`` (Edge Case #2), or (defensive fallback,
                should be unreachable under the DB CHECK constraint)
                ``pre_suspension_status`` is somehow NULL.
        """
        company = self._company_repo.get_for_update(company_id)
        if company is None:
            raise CompanyNotFoundError()

        if company.status != CompanyStatus.suspended.value:
            logger.warning(
                "Platform tenant reactivate rejected",
                extra={
                    "request_id": REQUEST_ID_CONTEXT.get("-"),
                    "company_id": str(company_id),
                    "current_status": company.status,
                    "platform_administrator_id": str(actor_platform_administrator_id),
                },
            )
            raise TenantLifecycleTransitionError(
                "Company is not currently suspended; nothing to reactivate."
            )

        restored_status = company.pre_suspension_status
        if restored_status is None:
            # Defensive fallback (plan.md §9.3): the DB CHECK constraint
            # makes this unreachable in practice, but reactivation must
            # fail closed rather than ever guess a restore target.
            logger.error(
                "Platform tenant reactivate found no pre_suspension_status",
                extra={
                    "request_id": REQUEST_ID_CONTEXT.get("-"),
                    "company_id": str(company_id),
                    "platform_administrator_id": str(actor_platform_administrator_id),
                },
            )
            raise TenantLifecycleTransitionError(
                "Cannot reactivate: no recorded pre-suspension status for "
                "this company. This indicates data corruption and requires "
                "manual operator investigation."
            )

        before_state = _lifecycle_snapshot(company)

        self._company_repo.reactivate(company, restored_status=restored_status)

        event = CompanySuspensionLiftedEvent(
            company_id=company.id, lifted_at=datetime.now(UTC)
        )
        self._outbox_repo.create(
            event.to_outbox_record(
                _new_correlation_id(), actor_platform_administrator_id
            )
        )

        self._audit.record(
            action="tenant_lifecycle.reactivate",
            target_type="Company",
            target_id=company.id,
            company_id=company.id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=before_state,
            after_state=_lifecycle_snapshot(company),
        )
        self._db.commit()
        logger.info(
            "Platform tenant reactivated",
            extra={
                "request_id": REQUEST_ID_CONTEXT.get("-"),
                "company_id": str(company.id),
                "platform_administrator_id": str(actor_platform_administrator_id),
                "restored_status": restored_status,
            },
        )
        return company
