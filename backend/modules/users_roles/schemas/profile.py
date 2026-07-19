"""Profile Pydantic schemas — request/response models for profile endpoints.

Spec reference: contracts/profile-api.yaml, tasks T060.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UpdateProfileRequest(BaseModel):
    """Request body for PATCH /api/v1/profile."""

    display_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Human-readable display name.",
    )
    phone: str | None = Field(
        default=None,
        max_length=20,
        description="Personal phone number. Pass null to clear.",
    )


class ProfileResponse(BaseModel):
    """Response payload for GET/PATCH /api/v1/profile."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    phone: str | None
    avatar_url: str | None
    created_at: datetime
    updated_at: datetime


class AvatarUploadResponse(BaseModel):
    """Response payload for POST /api/v1/profile/avatar."""

    avatar_url: str = Field(description="Public URL of the newly uploaded avatar.")
