"""CompanyService — orchestrates all company lifecycle business logic.

Business rules BR-001 through BR-029 (spec.md §5) are enforced here.
The service delegates persistence to repositories and cross-cutting concerns
(audit logging, domain events) to dedicated sub-services.

Each method is a complete unit of work: it validates preconditions, applies
the state change via the repository, appends an audit log entry, and writes
a domain event to the transactional outbox — all within the same session.

Session / transaction contract
───────────────────────────────
The ``CompanyRepository`` and ``CompanyAuditLogRepository`` call
``db.commit()`` after each write.  The ``EventOutboxRepository`` only does
``db.add()``.  The service therefore calls ``db.commit()`` once more at the
end of each method to flush the outbox record.  This results in sequential
commits rather than a single atomic transaction; the operational trade-off is
acceptable in Phase 7 because the outbox relay is a stub.

Spec reference: §4 User Stories, §5 Business Rules, §5.6 Status Transitions.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.events.outbox import EventOutboxRepository
from modules.companies.events import (
    CompanyActivatedEvent,
    CompanyCreatedEvent,
    CompanyDeactivatedEvent,
    CompanyDeletedEvent,
    CompanyRestoredEvent,
    CompanyUpdatedEvent,
)
from modules.companies.exceptions import (
    CompanyIncompleteError,
    CompanyNameConflictError,
    CompanyNotFoundError,
    CompanyPurgedError,
    CurrencyChangeWarningError,
    InvalidStatusTransitionError,
    SlugConflictError,
    SlugImmutableError,
)
from modules.companies.models.company import Company
from modules.companies.models.enums import CompanyStatus
from modules.companies.repositories.company_address_repository import (
    CompanyAddressRepository,
)
from modules.companies.repositories.company_audit_log_repository import (
    CompanyAuditLogRepository,
)
from modules.companies.repositories.company_repository import CompanyRepository
from modules.companies.services.company_audit_service import CompanyAuditService
from modules.companies.services.company_settings_service import CompanySettingsService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status transition table — spec.md §5.6
# ---------------------------------------------------------------------------

# Maps current_status → set of statuses reachable by the *owner*.
_OWNER_TRANSITIONS: dict[str, set[str]] = {
    CompanyStatus.pending_setup.value: {CompanyStatus.active.value},
    CompanyStatus.active.value: {
        CompanyStatus.inactive.value,
        CompanyStatus.deleted.value,
    },
    CompanyStatus.inactive.value: {
        CompanyStatus.active.value,
        CompanyStatus.deleted.value,
    },
    CompanyStatus.deleted.value: {CompanyStatus.inactive.value},
    CompanyStatus.suspended.value: set(),  # owner cannot change a suspended company
}

# Required company fields before activation is allowed — spec.md §5.4.
_ACTIVATION_REQUIRED_FIELDS: list[str] = [
    "email",
    "country",
    "default_currency",
]

# Window in days within which a soft-deleted company may be restored.
_RESTORE_WINDOW_DAYS: int = 90


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_slug(legal_name: str) -> str:
    """Convert a legal name into a URL-safe lowercase hyphenated slug."""
    slug = legal_name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def _model_snapshot(company: Company) -> dict[str, Any]:
    """Return a JSON-serialisable snapshot dict of key company fields."""
    return {
        "legal_name": company.legal_name,
        "trade_name": company.trade_name,
        "slug": company.slug,
        "status": company.status,
        "email": company.email,
        "country": company.country,
        "default_currency": company.default_currency,
        "default_language": company.default_language,
        "default_timezone": company.default_timezone,
        "updated_at": company.updated_at.isoformat() if company.updated_at else None,
    }


def _new_correlation_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class CompanyService:
    """Orchestrates all company CRUD and lifecycle operations.

    Args:
        db: SQLAlchemy ``Session`` shared by all repositories in this request.
        company_repo: Injected ``CompanyRepository``.
        address_repo: Injected ``CompanyAddressRepository``.
        audit_log_repo: Injected ``CompanyAuditLogRepository``.
        outbox_repo: Injected ``EventOutboxRepository``.
        audit_service: Injected ``CompanyAuditService``.
        settings_service: Injected ``CompanySettingsService``.
    """

    def __init__(
        self,
        db: Session,
        company_repo: CompanyRepository,
        address_repo: CompanyAddressRepository,
        audit_log_repo: CompanyAuditLogRepository,
        outbox_repo: EventOutboxRepository,
        audit_service: CompanyAuditService,
        settings_service: CompanySettingsService,
    ) -> None:
        self._db = db
        self._company_repo = company_repo
        self._address_repo = address_repo
        self._audit_log_repo = audit_log_repo
        self._outbox_repo = outbox_repo
        self._audit_service = audit_service
        self._settings_service = settings_service

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create_company(
        self,
        actor_id: UUID,
        data: dict[str, Any],
        request_context: dict[str, Any] | None = None,
    ) -> Company:
        """Create a new company in ``pending_setup`` status.

        Validates legal name uniqueness (case-insensitive) and derives or
        validates a URL slug.  Appends an audit entry and publishes a
        ``CompanyCreatedEvent`` to the outbox.

        Args:
            actor_id: UUID of the owner/creator user.
            data: Validated field dict (from ``CreateCompanyRequest``).
            request_context: Optional dict with ``ip_address``, ``user_agent``,
                ``request_id`` for audit enrichment.

        Returns:
            Newly persisted :class:`~modules.companies.models.company.Company`.

        Raises:
            CompanyNameConflictError: Legal name already exists.
            SlugConflictError: Explicitly supplied slug is already taken.
        """
        ctx = request_context or {}
        legal_name: str = data["legal_name"]

        # BR-001 — global legal name uniqueness (case-insensitive)
        if self._company_repo.exists_by_name(legal_name):
            raise CompanyNameConflictError(details={"legal_name": legal_name})

        # Derive or validate slug
        explicit_slug = bool(data.get("slug"))
        slug = data.get("slug") or _derive_slug(legal_name)
        if self._company_repo.exists_by_slug(slug):
            if explicit_slug:
                # Caller supplied an explicit slug that is already taken
                raise SlugConflictError(details={"slug": slug})
            # Auto-derive with numeric suffix until unique
            base_slug = slug
            counter = 1
            slug = f"{base_slug}-{counter}"
            while self._company_repo.exists_by_slug(slug):
                counter += 1
                slug = f"{base_slug}-{counter}"

        company_data = {
            **data,
            "slug": slug,
            "owner_id": actor_id,
            "status": CompanyStatus.pending_setup.value,
        }
        company_data.pop("slug", None)
        company_data["slug"] = slug

        company = self._company_repo.create(company_data)

        # Audit log
        self._audit_service.record(
            company_id=company.id,
            actor_user_id=actor_id,
            action="COMPANY_CREATED",
            after_state=_model_snapshot(company),
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        # Domain event → outbox
        event = CompanyCreatedEvent(
            company_id=company.id,
            legal_name=company.legal_name,
            slug=company.slug,
            owner_id=company.owner_id,
            status=company.status,
            created_at=company.created_at,
        )
        self._outbox_repo.create(
            event.to_outbox_record(_new_correlation_id(), actor_id)
        )
        self._db.commit()

        logger.info("Company created", extra={"company_id": str(company.id)})
        return company

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_company(
        self,
        company_id: UUID,
        actor_id: UUID,
        data: dict[str, Any],
        request_context: dict[str, Any] | None = None,
    ) -> Company:
        """Partially update a company's profile fields.

        Enforces:
        - Slug immutability after the company has been activated (BR-005).
        - Currency-change warning when existing transactions may exist (BR-006).

        Args:
            company_id: Target company UUID.
            actor_id: UUID of the requesting user.
            data: Partial field dict (only fields being changed).
            request_context: Optional audit context.

        Returns:
            Updated :class:`Company`.

        Raises:
            CompanyNotFoundError: Company does not exist or is deleted.
            SlugImmutableError: Slug cannot be changed after first activation.
            CurrencyChangeWarningError: Currency changed without explicit confirmation.
        """
        ctx = request_context or {}
        company = self._get_active_company(company_id)
        before = _model_snapshot(company)

        # BR-001 — legal name must remain globally unique on update
        if "legal_name" in data and data["legal_name"] != company.legal_name:
            if self._company_repo.exists_by_name(
                data["legal_name"], exclude_id=company_id
            ):
                raise CompanyNameConflictError(
                    details={"legal_name": data["legal_name"]}
                )

        # BR-005 — slug is immutable after the company has ever been active
        if "slug" in data and data["slug"] != company.slug:
            if company.status != CompanyStatus.pending_setup.value:
                raise SlugImmutableError()

        # BR-006 — warn on currency change (caller must pass confirm_currency_change=True)
        confirm_currency = data.pop("confirm_currency_change", False)
        if (
            "default_currency" in data
            and data["default_currency"] != company.default_currency
            and not confirm_currency
        ):
            raise CurrencyChangeWarningError()

        changed_fields = [k for k in data if k in _model_snapshot(company)]
        company = self._company_repo.update(company, data)

        self._audit_service.record(
            company_id=company.id,
            actor_user_id=actor_id,
            action="COMPANY_UPDATED",
            before_state=before,
            after_state=_model_snapshot(company),
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        event = CompanyUpdatedEvent(
            company_id=company.id,
            changed_fields=changed_fields,
            updated_at=company.updated_at,
        )
        self._outbox_repo.create(
            event.to_outbox_record(_new_correlation_id(), actor_id)
        )
        self._db.commit()

        return company

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------

    def activate_company(
        self,
        company_id: UUID,
        actor_id: UUID,
        request_context: dict[str, Any] | None = None,
    ) -> Company:
        """Transition a company from ``pending_setup`` or ``inactive`` to ``active``.

        Validates that all required setup fields are populated before allowing
        activation (BR-008).

        Raises:
            CompanyNotFoundError: Company does not exist or is deleted.
            InvalidStatusTransitionError: Current status does not permit activation.
            CompanyIncompleteError: Required setup fields are missing.
        """
        ctx = request_context or {}
        company = self._get_active_company(company_id)
        self._assert_owner_transition(company, CompanyStatus.active.value)

        # BR-008 — validate required fields
        missing = [
            f for f in _ACTIVATION_REQUIRED_FIELDS if not getattr(company, f, None)
        ]
        if missing:
            raise CompanyIncompleteError(missing_fields=missing)

        before = _model_snapshot(company)
        company = self._company_repo.update(
            company, {"status": CompanyStatus.active.value}
        )

        self._audit_service.record(
            company_id=company.id,
            actor_user_id=actor_id,
            action="COMPANY_ACTIVATED",
            before_state=before,
            after_state=_model_snapshot(company),
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        event = CompanyActivatedEvent(
            company_id=company.id,
            activated_at=company.updated_at,
        )
        self._outbox_repo.create(
            event.to_outbox_record(_new_correlation_id(), actor_id)
        )
        self._db.commit()

        return company

    def deactivate_company(
        self,
        company_id: UUID,
        actor_id: UUID,
        reason: str,
        request_context: dict[str, Any] | None = None,
    ) -> Company:
        """Transition a company from ``active`` to ``inactive``.

        Raises:
            CompanyNotFoundError: Company does not exist or is deleted.
            InvalidStatusTransitionError: Current status is not ``active``.
        """
        ctx = request_context or {}
        company = self._get_active_company(company_id)
        self._assert_owner_transition(company, CompanyStatus.inactive.value)

        before = _model_snapshot(company)
        company = self._company_repo.update(
            company, {"status": CompanyStatus.inactive.value}
        )

        self._audit_service.record(
            company_id=company.id,
            actor_user_id=actor_id,
            action="COMPANY_DEACTIVATED",
            before_state=before,
            after_state=_model_snapshot(company),
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        event = CompanyDeactivatedEvent(
            company_id=company.id,
            reason=reason,
            deactivated_at=company.updated_at,
        )
        self._outbox_repo.create(
            event.to_outbox_record(_new_correlation_id(), actor_id)
        )
        self._db.commit()

        return company

    def soft_delete_company(
        self,
        company_id: UUID,
        actor_id: UUID,
        reason: str,
        force_delete: bool = False,
        request_context: dict[str, Any] | None = None,
    ) -> Company:
        """Transition a company from ``active`` or ``inactive`` to ``deleted``.

        The company is soft-deleted by setting status to ``deleted`` and
        recording ``deleted_at``.  The company record is retained for the
        configured restoration window (90 days) before permanent purge.

        Args:
            force_delete: When ``True``, skips the active-transaction check.
                Pass ``False`` (default) to receive a ``ForceDeleteRequiredError``
                when active transactions exist (stub — actual check is Phase 8).

        Raises:
            CompanyNotFoundError: Company does not exist or is already deleted.
            InvalidStatusTransitionError: Status is not ``active`` or ``inactive``.
        """
        ctx = request_context or {}
        company = self._get_active_company(company_id)
        self._assert_owner_transition(company, CompanyStatus.deleted.value)

        before = _model_snapshot(company)
        deleted_at = datetime.now(UTC)
        company = self._company_repo.soft_delete(
            company, deleted_at=deleted_at, reason=reason
        )

        self._audit_service.record(
            company_id=company.id,
            actor_user_id=actor_id,
            action="COMPANY_DELETED",
            before_state=before,
            after_state=_model_snapshot(company),
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        event = CompanyDeletedEvent(
            company_id=company.id,
            reason=reason,
            deleted_at=deleted_at,
        )
        self._outbox_repo.create(
            event.to_outbox_record(_new_correlation_id(), actor_id)
        )
        self._db.commit()

        return company

    def restore_company(
        self,
        company_id: UUID,
        actor_id: UUID,
        request_context: dict[str, Any] | None = None,
    ) -> Company:
        """Restore a soft-deleted company back to ``inactive`` status.

        Only allowed within the 90-day restoration window after soft deletion.

        Raises:
            CompanyNotFoundError: Company does not exist.
            CompanyPurgedError: Restoration window has expired (> 90 days).
            InvalidStatusTransitionError: Company is not in ``deleted`` status.
        """
        ctx = request_context or {}
        company = self._company_repo.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError()

        if company.status != CompanyStatus.deleted.value:
            raise InvalidStatusTransitionError(
                details={
                    "current_status": company.status,
                    "target_status": CompanyStatus.inactive.value,
                }
            )

        # BR-023 — enforce restoration window
        if company.deleted_at is not None:
            deleted_at = company.deleted_at
            # SQLite returns naive datetimes; normalise to UTC for comparison.
            if deleted_at.tzinfo is None:
                deleted_at = deleted_at.replace(tzinfo=UTC)
            age = datetime.now(UTC) - deleted_at
            if age > timedelta(days=_RESTORE_WINDOW_DAYS):
                raise CompanyPurgedError()

        before = _model_snapshot(company)
        company = self._company_repo.restore(company)

        self._audit_service.record(
            company_id=company.id,
            actor_user_id=actor_id,
            action="COMPANY_RESTORED",
            before_state=before,
            after_state=_model_snapshot(company),
            ip_address=ctx.get("ip_address"),
            request_id=ctx.get("request_id"),
            user_agent=ctx.get("user_agent"),
        )

        event = CompanyRestoredEvent(
            company_id=company.id,
            restored_at=company.updated_at,
        )
        self._outbox_repo.create(
            event.to_outbox_record(_new_correlation_id(), actor_id)
        )
        self._db.commit()

        return company

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_company(self, company_id: UUID, requester_id: UUID) -> Company:
        """Return a company by ID.

        Args:
            company_id: Target company UUID.
            requester_id: UUID of the requesting user (for future ACL checks).

        Raises:
            CompanyNotFoundError: Company does not exist or is deleted/suspended
                for this requester.
        """
        company = self._company_repo.get_by_id_active(company_id)
        if company is None:
            raise CompanyNotFoundError()
        return company

    def list_user_companies(self, owner_id: UUID) -> list[Company]:
        """Return all non-deleted companies owned by ``owner_id``."""
        return self._company_repo.list_by_owner(owner_id)

    def list_all_companies(
        self,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[Company], int]:
        """Return a paginated list of all companies (SuperAdmin endpoint).

        Args:
            filters: Optional filter keys: ``status``, ``country``, ``search``,
                ``include_deleted`` (bool, default ``False``).
            page: 1-based page number.
            page_size: Records per page.

        Returns:
            Tuple of (company list, total count).
        """
        return self._company_repo.list_all(
            filters=filters or {},
            page=page,
            page_size=page_size,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_active_company(self, company_id: UUID) -> Company:
        """Return a non-deleted company or raise :exc:`CompanyNotFoundError`."""
        company = self._company_repo.get_by_id_active(company_id)
        if company is None:
            raise CompanyNotFoundError()
        return company

    def _assert_owner_transition(self, company: Company, target_status: str) -> None:
        """Raise :exc:`InvalidStatusTransitionError` if the transition is invalid."""
        allowed = _OWNER_TRANSITIONS.get(company.status, set())
        if target_status not in allowed:
            raise InvalidStatusTransitionError(
                details={
                    "current_status": company.status,
                    "target_status": target_status,
                }
            )
