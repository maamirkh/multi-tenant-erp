"""User profile response schema."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserProfileResponse(BaseModel):
    """Response body for GET /auth/me.

    Contains only safe identity fields — credential data is never included.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "alice@example.com",
                    "display_name": "Alice Smith",
                    "account_status": "ACTIVE",
                    "is_email_verified": True,
                    "created_at": "2026-01-01T00:00:00+00:00",
                }
            ]
        },
    )

    user_id: UUID = Field(..., description="User's unique identifier.")
    email: str = Field(..., description="User's email address.")
    display_name: str = Field(..., description="Human-readable name.")
    account_status: str = Field(
        ..., description="Account lifecycle status (ACTIVE, INACTIVE, LOCKED, DELETED)."
    )
    is_email_verified: bool = Field(
        ..., description="True once the user has verified their email address."
    )
    created_at: datetime = Field(..., description="UTC timestamp of account creation.")
