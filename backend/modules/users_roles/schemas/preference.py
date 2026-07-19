"""Preference Pydantic schemas — request/response models for preference endpoints.

Spec reference: contracts/profile-api.yaml, tasks T061.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UpdatePreferenceRequest(BaseModel):
    """Request body for PUT /api/v1/preferences."""

    language: str | None = Field(
        default=None,
        min_length=2,
        max_length=10,
        description="BCP-47 language tag (e.g. 'en', 'fr', 'pt-BR').",
    )
    timezone: str | None = Field(
        default=None,
        max_length=50,
        description="IANA timezone identifier (e.g. 'UTC', 'Europe/London').",
    )
    date_format: (
        Literal["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY", "DD-MM-YYYY"] | None
    ) = Field(
        default=None,
        description="Date display format.",
    )
    number_format: str | None = Field(
        default=None,
        max_length=20,
        description="Number formatting locale (e.g. 'en-US', 'fr-FR').",
    )
    theme: Literal["light", "dark", "system"] | None = Field(
        default=None,
        description="UI colour theme.",
    )


class PreferenceResponse(BaseModel):
    """Response payload for GET/PUT /api/v1/preferences."""

    model_config = ConfigDict(from_attributes=True)

    language: str
    timezone: str
    date_format: str
    number_format: str
    theme: str
    notification_preferences: dict[str, Any]
