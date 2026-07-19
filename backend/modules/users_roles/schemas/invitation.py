"""Invitation Pydantic schemas — request/response models for invitation endpoints.

Matches the contracts defined in contracts/members-api.yaml.

Spec reference: tasks T031.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InvitationResponse(BaseModel):
    """Response for invitation-related operations."""

    model_config = ConfigDict(from_attributes=True)

    member_id: UUID
    user_id: UUID
    company_id: UUID
    status: str
    invited_by: UUID | None = None
    invitation_accepted_at: datetime | None = None
    created_at: datetime
