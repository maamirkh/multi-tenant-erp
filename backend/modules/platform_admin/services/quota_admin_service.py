"""QuotaAdminService — tenant quota override grant/revoke (T149).

The workflow layer over the Phase-8 `TenantQuotaOverride` model (T107)
and resolver (T108) — no new model, no second resolver.
`QuotaRepository.get_active_override()` is already expiry-at-read-time
aware (never trusts a stale `is_active`, mirroring `EntitlementOverride`).
This service owns the audited, committed side of that same lifecycle:
granting, revoking, and reverting a stale-but-still-`is_active` row the
moment it would otherwise block a new grant (the DB's partial unique
index on `(company_id, quota_key) WHERE is_active = true` would
otherwise reject the new row).

No HTTP DELETE exists for quota overrides in the OpenAPI contract
(`platform-admin-v1.yaml` declares only `POST
/tenants/{companyId}/quota-overrides`) — `revoke()` is a genuine,
audited service capability, reachable only via `grant()`'s own
auto-reversion of a stale row, not via any router-exposed endpoint
(the router lock, plan.md §10, forbids inventing an undeclared DELETE
route here).

Fail-closed atomicity (ADR-5): stage the domain change plus an audit
row (both flush-only), then a single service-level `db.commit()`.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException
from core.logging.setup import REQUEST_ID_CONTEXT
from core.utils.datetime import ensure_utc, utcnow
from modules.platform_admin.exceptions import QuotaOverrideAlreadyActiveError
from modules.platform_admin.models.quota import TenantQuotaOverride
from modules.platform_admin.repositories.quota_repository import QuotaRepository
from modules.platform_admin.services.platform_audit_service import PlatformAuditService

logger = logging.getLogger(__name__)


def _snapshot(override: TenantQuotaOverride) -> dict[str, Any]:
    return {
        "company_id": str(override.company_id),
        "quota_key": override.quota_key,
        "override_limit": (
            str(override.override_limit)
            if override.override_limit is not None
            else None
        ),
        "reason": override.reason,
        "expires_at": override.expires_at.isoformat() if override.expires_at else None,
        "is_active": override.is_active,
    }


class QuotaAdminService:
    """Domain service for granting/revoking `TenantQuotaOverride` rows."""

    def __init__(
        self,
        db: Session,
        repo: QuotaRepository,
        audit: PlatformAuditService,
    ) -> None:
        self._db = db
        self._repo = repo
        self._audit = audit

    def _revoke_stale_row(
        self, override: TenantQuotaOverride, *, actor_platform_administrator_id: UUID
    ) -> None:
        """Audited auto-reversion of a row whose `expires_at` has passed
        but whose `is_active` has not yet been physically flipped —
        mirrors `OverrideService.has_active_override()`'s own
        auto-reversion (T147/T149 parity). Flush-only; the caller's own
        commit finalizes this alongside the new grant."""
        before_state = _snapshot(override)
        self._repo.revoke_override(override, revoked_at=utcnow())
        self._audit.record(
            action="quota_override.auto_revert_expired",
            target_type="TenantQuotaOverride",
            target_id=override.id,
            company_id=override.company_id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason="Automatic reversion: expires_at has passed.",
            before_state=before_state,
            after_state=_snapshot(override),
        )

    def grant(
        self,
        *,
        company_id: UUID,
        quota_key: str,
        override_limit: Decimal | None,
        reason: str,
        actor_platform_administrator_id: UUID,
        expires_at: datetime | None = None,
    ) -> TenantQuotaOverride:
        """Grant a time-boxed (or permanent) quota override.

        Raises:
            QuotaOverrideAlreadyActiveError: a genuinely-active override
                for this (company, quota_key) pair already exists.
        """
        stale = self._repo.get_active_override_ignoring_expiry(company_id, quota_key)
        if stale is not None:
            if (
                stale.expires_at is not None
                and ensure_utc(stale.expires_at) <= utcnow()
            ):
                self._revoke_stale_row(
                    stale,
                    actor_platform_administrator_id=actor_platform_administrator_id,
                )
            else:
                logger.warning(
                    "Platform quota override grant rejected — already active",
                    extra={
                        "request_id": REQUEST_ID_CONTEXT.get("-"),
                        "company_id": str(company_id),
                        "quota_key": quota_key,
                        "platform_administrator_id": str(
                            actor_platform_administrator_id
                        ),
                        "existing_override_id": str(stale.id),
                    },
                )
                raise QuotaOverrideAlreadyActiveError(
                    details={
                        "company_id": str(company_id),
                        "quota_key": quota_key,
                        "existing_override_id": str(stale.id),
                    }
                )

        override = self._repo.create_override(
            company_id=company_id,
            quota_key=quota_key,
            override_limit=override_limit,
            reason=reason,
            actor_id=actor_platform_administrator_id,
            granted_at=utcnow(),
            expires_at=expires_at,
        )
        self._audit.record(
            action="quota_override.grant",
            target_type="TenantQuotaOverride",
            target_id=override.id,
            company_id=company_id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            after_state=_snapshot(override),
        )
        self._db.commit()
        logger.info(
            "Platform quota override granted",
            extra={
                "request_id": REQUEST_ID_CONTEXT.get("-"),
                "company_id": str(company_id),
                "quota_key": quota_key,
                "platform_administrator_id": str(actor_platform_administrator_id),
                "override_id": str(override.id),
            },
        )
        return override

    def revoke(
        self,
        *,
        override_id: UUID,
        actor_platform_administrator_id: UUID,
        reason: str | None = None,
    ) -> TenantQuotaOverride:
        """Revoke an active quota override. Service-level only — no
        router exposes this directly (see module docstring).

        Raises:
            NotFoundException: no override exists with this id, or it is
                already inactive.
        """
        override = self._repo.get_override_by_id(override_id)
        if override is None or not override.is_active:
            raise NotFoundException(
                message="Quota override not found or already inactive."
            )

        before_state = _snapshot(override)
        self._repo.revoke_override(override, revoked_at=utcnow())
        self._audit.record(
            action="quota_override.revoke",
            target_type="TenantQuotaOverride",
            target_id=override.id,
            company_id=override.company_id,
            actor_platform_administrator_id=actor_platform_administrator_id,
            reason=reason,
            before_state=before_state,
            after_state=_snapshot(override),
        )
        self._db.commit()
        return override
