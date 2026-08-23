"""Platform Dashboard Pydantic schemas — response model for the Phase 13
dashboard route (T171/T172/T173).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class DashboardWidgetResponse(BaseModel):
    state: str
    data: Any


class DashboardResponse(BaseModel):
    widgets: dict[str, DashboardWidgetResponse]
