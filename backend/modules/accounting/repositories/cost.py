"""Repositories for Cost Accounting entities — Phase 11.

  DepartmentRepository  — department CRUD + hierarchy queries
  CostCenterRepository  — cost center CRUD + hierarchy/department queries
  ProjectRepository     — project CRUD

Spec ref: specs/008-accounting-finance/tasks.md T228-T230
Data model: specs/008-accounting-finance/data-model.md line 514 (CostCenterRepository)
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.models.cost import CostCenter, Department, Project
from modules.accounting.repositories import BaseAccountingRepository


class DepartmentRepository(BaseAccountingRepository[Department]):
    """Data-access layer for the ``accounting_departments`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Department)

    def find_by_code(self, company_id: UUID, dept_code: str) -> Department | None:
        stmt = (
            select(Department)
            .where(Department.company_id == company_id)
            .where(Department.dept_code == dept_code)
            .where(Department.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_all(self, company_id: UUID, active_only: bool = False) -> list[Department]:
        stmt = (
            select(Department)
            .where(Department.company_id == company_id)
            .where(Department.is_deleted == False)  # noqa: E712
            .order_by(Department.dept_code)
        )
        if active_only:
            stmt = stmt.where(Department.is_active == True)  # noqa: E712
        return list(self.db.execute(stmt).scalars().all())

    def get_hierarchy(self, company_id: UUID) -> list[Department]:
        """All departments for a company, ordered so a parent always
        precedes its children — sufficient for callers to build a tree by
        a single pass keyed on ``parent_dept_id``.
        """
        stmt = (
            select(Department)
            .where(Department.company_id == company_id)
            .where(Department.is_deleted == False)  # noqa: E712
            .order_by(Department.parent_dept_id.is_(None).desc(), Department.dept_code)
        )
        return list(self.db.execute(stmt).scalars().all())


class CostCenterRepository(BaseAccountingRepository[CostCenter]):
    """Data-access layer for the ``accounting_cost_centers`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CostCenter)

    def find_by_code(self, company_id: UUID, center_code: str) -> CostCenter | None:
        stmt = (
            select(CostCenter)
            .where(CostCenter.company_id == company_id)
            .where(CostCenter.center_code == center_code)
            .where(CostCenter.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def find_by_company(
        self, company_id: UUID, active_only: bool = False
    ) -> list[CostCenter]:
        stmt = (
            select(CostCenter)
            .where(CostCenter.company_id == company_id)
            .where(CostCenter.is_deleted == False)  # noqa: E712
            .order_by(CostCenter.center_code)
        )
        if active_only:
            stmt = stmt.where(CostCenter.is_active == True)  # noqa: E712
        return list(self.db.execute(stmt).scalars().all())

    def find_by_department(
        self, company_id: UUID, department_id: UUID
    ) -> list[CostCenter]:
        stmt = (
            select(CostCenter)
            .where(CostCenter.company_id == company_id)
            .where(CostCenter.department_id == department_id)
            .where(CostCenter.is_deleted == False)  # noqa: E712
            .order_by(CostCenter.center_code)
        )
        return list(self.db.execute(stmt).scalars().all())


class ProjectRepository(BaseAccountingRepository[Project]):
    """Data-access layer for the ``accounting_projects`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Project)

    def find_by_code(self, company_id: UUID, project_code: str) -> Project | None:
        stmt = (
            select(Project)
            .where(Project.company_id == company_id)
            .where(Project.project_code == project_code)
            .where(Project.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_all(self, company_id: UUID, active_only: bool = False) -> list[Project]:
        stmt = (
            select(Project)
            .where(Project.company_id == company_id)
            .where(Project.is_deleted == False)  # noqa: E712
            .order_by(Project.project_code)
        )
        if active_only:
            stmt = stmt.where(Project.is_active == True)  # noqa: E712
        return list(self.db.execute(stmt).scalars().all())
