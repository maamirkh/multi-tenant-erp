"""Password-related request schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ForgotPasswordRequest(BaseModel):
    """Request body for POST /auth/forgot-password."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={"examples": [{"email": "alice@example.com"}]},
    )

    email: EmailStr = Field(
        ...,
        description="Email address associated with the account.",
        examples=["user@example.com"],
    )


class ResetPasswordRequest(BaseModel):
    """Request body for POST /auth/reset-password."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "token": "<reset-token-from-email>",
                    "new_password": "N3wS3cur3P@ss!",
                    "confirm_password": "N3wS3cur3P@ss!",
                }
            ]
        }
    )

    token: str = Field(
        ...,
        min_length=1,
        description="Password reset token received in the reset email.",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=1024,
        description="New password to set. Must meet the configured complexity requirements.",
    )
    confirm_password: str = Field(
        ...,
        min_length=1,
        description="Must exactly match new_password.",
    )

    @model_validator(mode="after")
    def passwords_must_match(self) -> ResetPasswordRequest:
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password do not match.")
        return self


class ChangePasswordRequest(BaseModel):
    """Request body for POST /auth/change-password."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "current_password": "OldP@ssword123",
                    "new_password": "N3wS3cur3P@ss!",
                    "confirm_password": "N3wS3cur3P@ss!",
                }
            ]
        }
    )

    current_password: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        description="The user's current password for verification.",
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=1024,
        description="New password. Must meet complexity requirements and not be recently used.",
    )
    confirm_password: str = Field(
        ...,
        min_length=1,
        description="Must exactly match new_password.",
    )

    @model_validator(mode="after")
    def passwords_must_match(self) -> ChangePasswordRequest:
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password do not match.")
        return self
