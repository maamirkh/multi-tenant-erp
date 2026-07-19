"""Status-transition request/response schemas for the companies module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DeactivateRequest(BaseModel):
    """Request body for POST /companies/{id}/deactivate."""

    model_config = ConfigDict(from_attributes=True)

    reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Reason for deactivating the company.",
    )


class DeleteCompanyRequest(BaseModel):
    """Request body for DELETE /companies/{id}.

    ``confirm_delete`` must be ``True`` — callers must explicitly acknowledge
    the deletion to prevent accidental data loss.
    """

    model_config = ConfigDict(from_attributes=True)

    reason: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Reason for deleting the company.",
    )
    force_delete: bool = Field(
        False,
        description="Set to true to delete even when active transactions exist.",
    )
    confirm_delete: bool = Field(
        ...,
        description="Must be set to true to confirm the deletion.",
    )

    @model_validator(mode="after")
    def require_confirm(self) -> DeleteCompanyRequest:
        if not self.confirm_delete:
            raise ValueError("confirm_delete must be true to proceed with deletion.")
        return self


class ActivateResponse(BaseModel):
    """Response body for POST /companies/{id}/activate."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Company identifier.")
    status: str = Field(..., description="New status after activation (active).")
    updated_at: datetime = Field(..., description="UTC timestamp of the status change.")
    message: str = Field(..., description="Human-readable confirmation message.")


class DeactivateResponse(BaseModel):
    """Response body for POST /companies/{id}/deactivate."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Company identifier.")
    status: str = Field(..., description="New status after deactivation (inactive).")
    updated_at: datetime = Field(..., description="UTC timestamp of the status change.")
    message: str = Field(..., description="Human-readable confirmation message.")


class DeleteCompanyResponse(BaseModel):
    """Response body for DELETE /companies/{id}."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Company identifier.")
    status: str = Field(..., description="Status after deletion (deleted).")
    deleted_at: datetime = Field(..., description="UTC timestamp of the soft deletion.")
    message: str = Field(..., description="Human-readable confirmation message.")


class RestoreResponse(BaseModel):
    """Response body for POST /companies/{id}/restore."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Company identifier.")
    status: str = Field(..., description="New status after restore (inactive).")
    updated_at: datetime = Field(..., description="UTC timestamp of the restore.")
    message: str = Field(..., description="Human-readable confirmation message.")
