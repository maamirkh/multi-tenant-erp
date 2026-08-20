"""Platform authentication request and response schemas.

Mirrors `modules.auth.schemas.auth`'s shape exactly. Created as part of
T049's scope (the login route needs Pydantic request/response models; no
separate task names this file).
"""

from __future__ import annotations

import unicodedata

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class PlatformLoginRequest(BaseModel):
    """Request body for POST /platform/auth/login."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr = Field(..., description="Registered email address.")
    password: str = Field(
        ..., min_length=1, max_length=1024, description="Account password."
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return unicodedata.normalize("NFKC", str(v)).lower().strip()


class PlatformRefreshTokenRequest(BaseModel):
    """Request body for POST /platform/auth/refresh."""

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Platform refresh token previously issued by login or refresh.",
    )


class PlatformLoginResponse(BaseModel):
    """Response body for POST /platform/auth/login."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str = Field(..., description="Short-lived Platform JWT access token.")
    refresh_token: str = Field(..., description="Platform refresh token.")
    token_type: str = Field(
        default="bearer", description="Token type; always 'bearer'."
    )
    expires_in: int = Field(..., description="Access token lifetime in seconds.")


class PlatformRefreshTokenResponse(BaseModel):
    """Response body for POST /platform/auth/refresh."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str = Field(..., description="New Platform JWT access token.")
    refresh_token: str = Field(
        ..., description="New Platform refresh token (old one is revoked)."
    )
    expires_in: int = Field(..., description="Access token lifetime in seconds.")
