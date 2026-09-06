"""Platform health Pydantic schemas — response model for the Phase 13
health route (T174).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PlatformHealthResponse(BaseModel):
    status: str
    checks: dict[str, str]
    outbox_pending: int
    outbox_published: int
    relay: dict[str, Any]
