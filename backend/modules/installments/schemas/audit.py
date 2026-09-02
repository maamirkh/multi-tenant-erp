"""Pydantic schema for Installments audit-history read.

Backs ``GET /contracts/{contractId}/audit`` — a thin read wrapper around
the already-existing, tenant-scoped
``InstallmentAuditService.list_for_entity()`` (Phase 13 gap discovered
and closed by the same "smallest safe fix" precedent as
``GET /my-permissions``: the service method already existed, only the
HTTP surface was missing).

Spec ref: specs/010-installments/plan.md §17.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from modules.installments.schemas.base import InstallmentsBaseSchema


class InstallmentAuditLogRead(InstallmentsBaseSchema):
    id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    actor_user_id: UUID | None
    occurred_at: datetime
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    reason: str | None
