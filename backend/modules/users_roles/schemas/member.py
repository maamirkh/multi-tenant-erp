"""Member Pydantic schemas — request/response models for member endpoints.

Matches the contracts defined in contracts/members-api.yaml.

Spec reference: tasks T030, T042.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AddMemberRequest(BaseModel):
    """Request body for POST /companies/{company_id}/members."""

    email: EmailStr = Field(..., description="Email of the user to add.")
    role_id: UUID = Field(..., description="Role to assign to the new member.")
    employee_id: str | None = Field(
        None, max_length=50, description="Company-assigned employee ID."
    )
    job_title: str | None = Field(None, max_length=100, description="Position title.")
    department: str | None = Field(None, max_length=100, description="Department name.")
    work_phone: str | None = Field(
        None, max_length=20, description="Work phone number."
    )
    hire_date: date | None = Field(None, description="Employment start date.")
    notes: str | None = Field(None, max_length=2000, description="Internal notes.")


class UpdateMemberRequest(BaseModel):
    """Request body for PATCH /companies/{company_id}/members/{member_id}."""

    model_config = ConfigDict()

    role_id: UUID | None = Field(None, description="New role to assign to the member.")
    employee_id: str | None = Field(
        None, max_length=50, description="Company-assigned employee ID."
    )
    job_title: str | None = Field(None, max_length=100, description="Position title.")
    department: str | None = Field(None, max_length=100, description="Department name.")
    work_phone: str | None = Field(
        None, max_length=20, description="Work phone number."
    )
    hire_date: date | None = Field(None, description="Employment start date.")
    notes: str | None = Field(None, max_length=2000, description="Internal notes.")


class RoleSummary(BaseModel):
    """Embedded role info in member responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    rank: int


class MemberResponse(BaseModel):
    """Response body for newly created member (POST /members 201)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    role: RoleSummary
    status: str
    created_at: datetime


class MemberListItem(BaseModel):
    """Item in paginated member list response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    display_name: str
    email: str
    avatar_url: str | None = None
    role: RoleSummary
    status: str
    department: str | None = None
    job_title: str | None = None
    created_at: datetime


class MemberDetailResponse(BaseModel):
    """Full member detail response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    company_id: UUID
    display_name: str
    email: str
    avatar_url: str | None = None
    role: RoleSummary
    status: str
    employee_id: str | None = None
    job_title: str | None = None
    department: str | None = None
    work_phone: str | None = None
    hire_date: date | None = None
    notes: str | None = None
    invited_by: UUID | None = None
    invitation_accepted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
