"""Settings schemas for the companies module."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UpdateSettingsRequest(BaseModel):
    """Request body for PATCH /companies/{id}/settings."""

    model_config = ConfigDict(from_attributes=True)

    settings: dict[str, Any] = Field(
        ...,
        description="Key-value map of settings to update. Unknown keys are rejected by the service layer.",
    )


class CompanySettingsResponse(BaseModel):
    """Response body for settings update."""

    model_config = ConfigDict(from_attributes=True)

    company_id: UUID = Field(..., description="Company identifier.")
    settings: dict[str, Any] = Field(
        ..., description="Current settings map after the update."
    )
    updated_at: datetime = Field(
        ..., description="UTC timestamp of last settings update."
    )
