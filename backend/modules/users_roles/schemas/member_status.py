"""Member lifecycle status Pydantic schemas — request models for lifecycle endpoints.

Spec reference: BR-022, BR-023, tasks T071.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SuspendRequest(BaseModel):
    """Request body for POST /members/{member_id}/suspend.

    Suspension reason is mandatory per BR-022.
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Mandatory reason for suspension (BR-022). Max 500 characters.",
    )


class ArchiveRequest(BaseModel):
    """Request body for POST /members/{member_id}/archive.

    Archival reason is mandatory per BR-023.
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Mandatory reason for archival/soft-delete (BR-023). Max 500 characters.",
    )
