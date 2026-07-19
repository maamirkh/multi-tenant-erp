"""Email verification request schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VerifyEmailRequest(BaseModel):
    """Request body for POST /auth/verify-email."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"token": "<verification-token-from-email>"}]}
    )

    token: str = Field(
        ...,
        min_length=1,
        description="Email verification token received at registration.",
    )
