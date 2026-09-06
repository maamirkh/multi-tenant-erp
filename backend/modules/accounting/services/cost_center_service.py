"""CostCenterService — Cost Accounting — Phase 11.

Cost center / department / project configuration, plus the Cost Center
P&L and Project P&L reports (spec.md §39.6).

Both reports read ``JournalLine.cost_center_id``/``project_id`` — plain
UUID columns with no FK, populated by ``PostingEngine`` whenever a caller
supplies them on a posting line (research.md Decision 14; already live
since Phase 4). Revenue accounts run credit-normal (revenue = credit −
debit); expense accounts run debit-normal (expense = debit − credit);
Net Income = total revenue − total expense — the standard P&L sign
convention already used implicitly throughout this module's GL reporting.

Spec ref: specs/008-accounting-finance/spec.md §25 Cost Accounting
Tasks ref: specs/008-accounting-finance/tasks.md T233
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.exceptions import (
    CostCenterNotFoundError,
    DepartmentNotFoundError,
    ProjectNotFoundError,
)
from modules.accounting.models.cost import CostCenter, Department, Project
from modules.accounting.repositories.cost import (
    CostCenterRepository,
    DepartmentRepository,
    ProjectRepository,
)
from modules.accounting.repositories.gl import GLReportRepository


class CostCenterService:
    """Application service for cost centers, departments, projects, and their P&L reports."""

    def __init__(
        self,
        db: Session,
        cost_center_repo: CostCenterRepository,
        department_repo: DepartmentRepository,
        project_repo: ProjectRepository,
    ) -> None:
        self.db = db
        self._cost_centers = cost_center_repo
        self._departments = department_repo
        self._projects = project_repo
        self._gl_reports = GLReportRepository(db)

    # ------------------------------------------------------------------
    # Departments
    # ------------------------------------------------------------------

    def create_department(
        self,
        company_id: UUID,
        dept_code: str,
        dept_name: str,
        parent_dept_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> Department:
        return self._departments.create(
            Department(
                company_id=company_id,
                dept_code=dept_code,
                dept_name=dept_name,
                parent_dept_id=parent_dept_id,
                created_by=actor_id,
            )
        )

    def get_department(self, company_id: UUID, department_id: UUID) -> Department:
        department = self._departments.get_by_id_or_none(
            id=department_id, company_id=company_id
        )
        if department is None:
            raise DepartmentNotFoundError(department_id=str(department_id))
        return department

    def list_departments(
        self, company_id: UUID, active_only: bool = False
    ) -> list[Department]:
        return self._departments.list_all(company_id, active_only=active_only)

    # ------------------------------------------------------------------
    # Cost centers
    # ------------------------------------------------------------------

    def create_cost_center(
        self,
        company_id: UUID,
        center_code: str,
        center_name: str,
        department_id: UUID | None = None,
        responsible_user_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> CostCenter:
        if department_id is not None:
            self.get_department(company_id, department_id)  # existence/tenant check
        return self._cost_centers.create(
            CostCenter(
                company_id=company_id,
                center_code=center_code,
                center_name=center_name,
                department_id=department_id,
                responsible_user_id=responsible_user_id,
                created_by=actor_id,
            )
        )

    def get_cost_center(self, company_id: UUID, cost_center_id: UUID) -> CostCenter:
        cost_center = self._cost_centers.get_by_id_or_none(
            id=cost_center_id, company_id=company_id
        )
        if cost_center is None:
            raise CostCenterNotFoundError(cost_center_id=str(cost_center_id))
        return cost_center

    def list_cost_centers(
        self, company_id: UUID, active_only: bool = False
    ) -> list[CostCenter]:
        return self._cost_centers.find_by_company(company_id, active_only=active_only)

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def create_project(
        self,
        company_id: UUID,
        project_code: str,
        project_name: str,
        start_date: date | None = None,
        end_date: date | None = None,
        budget_amount: Decimal | None = None,
        responsible_user_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> Project:
        return self._projects.create(
            Project(
                company_id=company_id,
                project_code=project_code,
                project_name=project_name,
                start_date=start_date,
                end_date=end_date,
                budget_amount=budget_amount,
                responsible_user_id=responsible_user_id,
                created_by=actor_id,
            )
        )

    def get_project(self, company_id: UUID, project_id: UUID) -> Project:
        project = self._projects.get_by_id_or_none(id=project_id, company_id=company_id)
        if project is None:
            raise ProjectNotFoundError(project_id=str(project_id))
        return project

    def list_projects(
        self, company_id: UUID, active_only: bool = False
    ) -> list[Project]:
        return self._projects.list_all(company_id, active_only=active_only)

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def get_cost_center_pl_report(
        self,
        company_id: UUID,
        cost_center_id: UUID,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> dict[str, Any]:
        cost_center = self.get_cost_center(company_id, cost_center_id)
        rows = self._gl_reports.cost_center_pl_query(
            company_id=company_id,
            cost_center_id=cost_center_id,
            start_date=period_start,
            end_date=period_end,
        )
        return self._build_pl_result(
            cost_center_id, cost_center.center_name, rows, period_start, period_end
        )

    def get_project_report(
        self,
        company_id: UUID,
        project_id: UUID,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> dict[str, Any]:
        project = self.get_project(company_id, project_id)
        rows = self._gl_reports.project_pl_query(
            company_id=company_id,
            project_id=project_id,
            start_date=period_start,
            end_date=period_end,
        )
        return self._build_pl_result(
            project_id, project.project_name, rows, period_start, period_end
        )

    @staticmethod
    def _build_pl_result(
        entity_id: UUID,
        entity_name: str,
        rows: list[dict[str, Any]],
        period_start: date | None,
        period_end: date | None,
    ) -> dict[str, Any]:
        revenue_lines = []
        expense_lines = []
        total_revenue = Decimal("0")
        total_expense = Decimal("0")

        for row in rows:
            if row["account_type"] == "REVENUE":
                amount = row["total_credit"] - row["total_debit"]
                revenue_lines.append({**row, "amount": amount})
                total_revenue += amount
            else:
                amount = row["total_debit"] - row["total_credit"]
                expense_lines.append({**row, "amount": amount})
                total_expense += amount

        return {
            "id": entity_id,
            "name": entity_name,
            "period_start": period_start,
            "period_end": period_end,
            "revenue_lines": revenue_lines,
            "expense_lines": expense_lines,
            "total_revenue": total_revenue,
            "total_expense": total_expense,
            "net_income": total_revenue - total_expense,
        }
