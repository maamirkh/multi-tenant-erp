"""LeadSourceService — thin application service over LeadSourceRepository.

``create``/``update`` delegate to ``BaseRepository.create``/``update``,
which already commit correctly (plan.md §8) — no extra transaction
handling is needed at this layer.

Spec ref: specs/009-crm/spec.md §38.2; plan.md §9.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from modules.crm.exceptions import LeadSourceNotFoundError
from modules.crm.models.lead_source import LeadSource
from modules.crm.repositories.lead_source import LeadSourceRepository


class LeadSourceService:
    """Application service for LeadSource CRUD."""

    def __init__(self, db: Session, repo: LeadSourceRepository) -> None:
        self.db = db
        self._repo = repo

    def list(
        self, company_id: UUID, *, is_active: bool | None = None
    ) -> list[LeadSource]:
        return self._repo.list_for_company(company_id, is_active=is_active)

    def create(
        self,
        company_id: UUID,
        *,
        code: str,
        name: str,
        is_active: bool = True,
        created_by: UUID | None = None,
    ) -> LeadSource:
        source = LeadSource(
            company_id=company_id,
            code=code,
            name=name,
            is_active=is_active,
            created_by=created_by,
        )
        return self._repo.create(source)

    def update(
        self,
        source_id: UUID,
        company_id: UUID,
        *,
        code: str | None = None,
        name: str | None = None,
        is_active: bool | None = None,
    ) -> LeadSource:
        source = self._get_or_raise(source_id, company_id)
        if code is not None:
            source.code = code
        if name is not None:
            source.name = name
        if is_active is not None:
            source.is_active = is_active
        return self._repo.update(source)

    def _get_or_raise(self, source_id: UUID, company_id: UUID) -> LeadSource:
        source = self._repo.get_by_id_or_none(id=source_id, company_id=company_id)
        if source is None:
            raise LeadSourceNotFoundError(str(source_id))
        return source
