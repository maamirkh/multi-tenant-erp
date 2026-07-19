"""Permission Pydantic schemas — response models for permission endpoints.

Spec reference: tasks T050.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PermissionResponse(BaseModel):
    """Single permission in the catalogue."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    label: str
    module: str
    action: str
    description: str | None = None


class PermissionGroupResponse(BaseModel):
    """Permissions grouped by module."""

    module: str
    permissions: list[PermissionResponse]
