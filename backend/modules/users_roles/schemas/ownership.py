"""Ownership transfer Pydantic schemas.

Validates the request body for the POST /companies/{company_id}/transfer-ownership
endpoint per contracts/members-api.yaml.

Spec reference: Epic 4, Phase 15 (T127).
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class TransferOwnershipRequest(BaseModel):
    """Request body for transferring company ownership to an active member.

    Attributes:
        target_member_id: UUID of the CompanyMember record that will become
            the new Owner.  Must reference an active member in the same
            company as the requesting Owner.
    """

    target_member_id: UUID = Field(
        ...,
        description="UUID of the active company member who will become the new Owner.",
    )
