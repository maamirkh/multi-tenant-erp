"""Platform Administrator Pydantic schemas — request/response models.

Explicit field allow-lists on every request schema (mass-assignment
protection, plan.md §28) — ``CreatePlatformAdministratorRequest`` carries
only ``user_id``, never ``is_active`` or a role field (Phase 5's T068
consumes this exact constraint). No password or token field is ever
echoed in any response schema.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreatePlatformAdministratorRequest(BaseModel):
    """Request body for creating a Platform Administrator account.

    Deliberately excludes ``is_active``/role fields — an administrator is
    always created active, and role assignment is a separate,
    ``platform.rbac.manage``-gated operation (Phase 5).
    """

    model_config = ConfigDict()

    user_id: UUID = Field(
        ...,
        description="Existing User to grant Platform authority to — reuses "
        "credentials, never a second password system.",
    )


class UpdatePlatformAdministratorRequest(BaseModel):
    """Request body for activating/deactivating a Platform Administrator.

    Activate/deactivate only — no other field of the account may be
    mutated through this endpoint.
    """

    model_config = ConfigDict()

    is_active: bool = Field(
        ..., description="Target active state for this administrator."
    )
    reason: str | None = Field(
        None,
        max_length=1000,
        description="Reason for this change; required for deactivation.",
    )


class PlatformAdministratorResponse(BaseModel):
    """Response body for a single Platform Administrator account."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    is_active: bool
    last_login_at: datetime | None
    deactivated_at: datetime | None
    deactivated_by: UUID | None
    created_at: datetime
    updated_at: datetime
