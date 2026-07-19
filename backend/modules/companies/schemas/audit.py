"""Audit log schemas for the companies module."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from core.schemas.pagination import PaginatedResponse


class AuditLogEntryResponse(BaseModel):
    """Single audit log record returned in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Audit log entry identifier.")
    company_id: UUID = Field(..., description="Company this event belongs to.")
    actor_user_id: UUID | None = Field(
        None, description="User who triggered the event; null for system events."
    )
    action: str = Field(..., description="Event type label (e.g. COMPANY_CREATED).")
    before_state: dict[str, Any] | None = Field(
        None, description="Company snapshot before the change."
    )
    after_state: dict[str, Any] | None = Field(
        None, description="Company snapshot after the change."
    )
    ip_address: str | None = Field(
        None, description="Requester IP address (IPv4 or IPv6)."
    )
    user_agent: str | None = Field(None, description="Requester User-Agent header.")
    request_id: UUID | None = Field(
        None, description="Correlation ID from the originating HTTP request."
    )
    created_at: datetime = Field(..., description="UTC timestamp of the event.")


AuditLogListResponse = PaginatedResponse[AuditLogEntryResponse]
