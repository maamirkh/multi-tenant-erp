"""Platform RBAC Pydantic schemas — request/response models for the Role
and role-assignment routes (T069).

Explicit field allow-lists on every request schema (mass-assignment
protection, plan.md §28), mirroring ``schemas/platform_administrator.py``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateOrUpdateRoleRequest(BaseModel):
    """Request body for ``POST /roles`` — creates a role, or updates an
    existing one (keyed by ``code``) name/description/permission bundle.

    Deliberately excludes ``id`` — roles are addressed by their stable
    ``code``, never a client-supplied identifier.
    """

    model_config = ConfigDict()

    code: str = Field(
        ...,
        max_length=100,
        description="Stable role code, e.g. 'platform_operations_admin'.",
    )
    name: str = Field(..., max_length=150, description="Display name.")
    description: str | None = Field(None, max_length=1000)
    permission_codes: list[str] = Field(
        default_factory=list,
        description="Complete replacement permission bundle for this role "
        "— every code must exist in the seeded Platform permission "
        "catalogue.",
    )
    reason: str | None = Field(
        None, max_length=1000, description="Reason for this change."
    )


class RoleResponse(BaseModel):
    """Response body for a single Platform Role, including its resolved
    permission bundle."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    permission_codes: list[str]
    created_at: datetime
    updated_at: datetime


class AssignRoleRequest(BaseModel):
    """Request body for ``POST /administrators/{adminId}/roles``."""

    model_config = ConfigDict()

    role_id: UUID = Field(..., description="Platform Role to assign.")
    reason: str | None = Field(
        None, max_length=1000, description="Reason for this assignment."
    )


class RoleAssignmentResponse(BaseModel):
    """Response body confirming a role assignment."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform_administrator_id: UUID
    role_id: UUID
    assigned_by: UUID | None
    assigned_at: datetime
