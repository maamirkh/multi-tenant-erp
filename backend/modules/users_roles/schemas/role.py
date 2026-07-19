"""Role Pydantic schemas — request/response models for role endpoints.

Spec reference: tasks T041, T084.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateRoleRequest(BaseModel):
    """Request body for POST /companies/{company_id}/roles."""

    model_config = ConfigDict()

    name: str = Field(
        ..., min_length=2, max_length=50, description="Role display name."
    )
    description: str | None = Field(
        None, max_length=500, description="Role purpose description."
    )
    rank: int = Field(
        ..., ge=1, le=99, description="Numeric hierarchy value (1-99 for custom roles)."
    )
    permission_codes: list[str] = Field(
        default_factory=list,
        description="Permission codes to assign to this role.",
    )


class UpdateRoleRequest(BaseModel):
    """Request body for PATCH /companies/{company_id}/roles/{role_id}."""

    model_config = ConfigDict()

    name: str | None = Field(
        None, min_length=2, max_length=50, description="New role display name."
    )
    description: str | None = Field(
        None, max_length=500, description="New role description."
    )
    rank: int | None = Field(None, ge=1, le=99, description="New rank value (1-99).")
    permission_codes: list[str] | None = Field(
        None, description="Updated permission codes (replaces existing)."
    )


class RoleResponse(BaseModel):
    """Minimal role response (list items, embedded refs)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    rank: int
    is_system: bool
    is_active: bool
    created_at: datetime


class RoleListItem(BaseModel):
    """Item in paginated role list response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    rank: int
    is_system: bool
    is_active: bool
    description: str | None = None
    member_count: int = 0
    created_at: datetime


class PermissionResponse(BaseModel):
    """Full permission detail — embedded in RoleDetailResponse.

    Matches PermissionResponse in contracts/roles-api.yaml.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    label: str
    module: str
    action: str
    description: str | None = None


class RoleDetailResponse(BaseModel):
    """Full role detail response per contracts/roles-api.yaml RoleDetailResponse.

    Replaces legacy ``permission_codes`` field with full ``PermissionResponse``
    objects; adds ``member_count`` (T084).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    name: str
    slug: str
    rank: int
    description: str | None = None
    is_system: bool
    is_active: bool
    member_count: int = 0
    permissions: list[PermissionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
