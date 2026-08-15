"""Pydantic v2 schemas for Cost Accounting — Phase 11.

  DepartmentCreateRequest / DepartmentResponse
  CostCenterCreateRequest / CostCenterResponse
  ProjectCreateRequest / ProjectResponse
  CostCenterPLReport / PLReportLine

Spec ref: specs/008-accounting-finance/tasks.md T235
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from modules.accounting.schemas.base import AccountingBaseSchema

# ---------------------------------------------------------------------------
# Departments
# ---------------------------------------------------------------------------


class DepartmentCreateRequest(AccountingBaseSchema):
    dept_code: str = Field(..., min_length=1, max_length=20)
    dept_name: str = Field(..., min_length=1, max_length=200)
    parent_dept_id: UUID | None = None


class DepartmentResponse(AccountingBaseSchema):
    id: UUID
    dept_code: str
    dept_name: str
    parent_dept_id: UUID | None = None
    is_active: bool


# ---------------------------------------------------------------------------
# Cost centers
# ---------------------------------------------------------------------------


class CostCenterCreateRequest(AccountingBaseSchema):
    center_code: str = Field(..., min_length=1, max_length=20)
    center_name: str = Field(..., min_length=1, max_length=200)
    department_id: UUID | None = None
    responsible_user_id: UUID | None = None


class CostCenterResponse(AccountingBaseSchema):
    id: UUID
    center_code: str
    center_name: str
    department_id: UUID | None = None
    responsible_user_id: UUID | None = None
    is_active: bool


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class ProjectCreateRequest(AccountingBaseSchema):
    project_code: str = Field(..., min_length=1, max_length=20)
    project_name: str = Field(..., min_length=1, max_length=200)
    start_date: date | None = None
    end_date: date | None = None
    budget_amount: Decimal | None = None
    responsible_user_id: UUID | None = None


class ProjectResponse(AccountingBaseSchema):
    id: UUID
    project_code: str
    project_name: str
    start_date: date | None = None
    end_date: date | None = None
    budget_amount: Decimal | None = None
    responsible_user_id: UUID | None = None
    is_active: bool


# ---------------------------------------------------------------------------
# P&L reports (shared shape for Cost Center P&L and Project P&L)
# ---------------------------------------------------------------------------


class PLReportLine(AccountingBaseSchema):
    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    amount: Decimal


class CostCenterPLReport(AccountingBaseSchema):
    id: UUID
    name: str
    period_start: date | None = None
    period_end: date | None = None
    revenue_lines: list[PLReportLine]
    expense_lines: list[PLReportLine]
    total_revenue: Decimal
    total_expense: Decimal
    net_income: Decimal


__all__ = [
    "CostCenterCreateRequest",
    "CostCenterPLReport",
    "CostCenterResponse",
    "DepartmentCreateRequest",
    "DepartmentResponse",
    "PLReportLine",
    "ProjectCreateRequest",
    "ProjectResponse",
]
