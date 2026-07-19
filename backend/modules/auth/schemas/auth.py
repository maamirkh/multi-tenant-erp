"""Authentication request and response schemas.

All schemas use Pydantic v2 with strict validation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "email": "alice@example.com",
                    "password": "S3cur3P@ssw0rd!",
                    "remember_me": False,
                }
            ]
        },
    )

    email: EmailStr = Field(
        ...,
        description="User's registered email address.",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="Account password.",
    )
    remember_me: bool = Field(
        default=False,
        description=(
            "When True, issues a long-lived refresh token "
            "(JWT_REMEMBER_ME_EXPIRE_DAYS days instead of JWT_REFRESH_TOKEN_EXPIRE_DAYS)."
        ),
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        import unicodedata

        return unicodedata.normalize("NFKC", str(v)).lower().strip()


class RefreshTokenRequest(BaseModel):
    """Request body for POST /auth/refresh."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"refresh_token": "<opaque-refresh-token-from-login>"}]
        }
    )

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Opaque refresh token previously issued by POST /auth/login or POST /auth/refresh.",
        examples=["<raw-refresh-token>"],
    )


class LoginResponse(BaseModel):
    """Response body for POST /auth/login."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "access_token": "<jwt-access-token>",
                    "refresh_token": "<opaque-refresh-token>",
                    "token_type": "bearer",
                    "expires_in": 900,
                }
            ]
        },
    )

    access_token: str = Field(..., description="Short-lived JWT access token.")
    refresh_token: str = Field(..., description="Opaque refresh token for rotation.")
    token_type: str = Field(
        default="bearer", description="Token type; always 'bearer'."
    )
    expires_in: int = Field(..., description="Access token lifetime in seconds.")


class RefreshTokenResponse(BaseModel):
    """Response body for POST /auth/refresh."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "access_token": "<new-jwt-access-token>",
                    "refresh_token": "<new-opaque-refresh-token>",
                    "expires_in": 900,
                }
            ]
        },
    )

    access_token: str = Field(..., description="New JWT access token.")
    refresh_token: str = Field(
        ..., description="New opaque refresh token (old one is revoked)."
    )
    expires_in: int = Field(..., description="Access token lifetime in seconds.")


class LogoutResponse(BaseModel):
    """Response body for POST /auth/logout."""

    message: str = Field(default="Successfully logged out.")
