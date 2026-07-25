"""CustomFieldDefinitionRepository — custom field schema data access.

Spec ref: specs/005-inventory-management/spec.md §14
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.inventory.models.custom_field import CustomFieldDefinition


class CustomFieldDefinitionRepository(BaseRepository[CustomFieldDefinition]):
    """Data-access layer for ``inventory_custom_field_definitions`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CustomFieldDefinition)

    def get_by_field_key(
        self, company_id: UUID, entity_type: str, field_key: str
    ) -> CustomFieldDefinition | None:
        """Return the custom field definition for this company/entity_type/field_key."""
        stmt = (
            select(CustomFieldDefinition)
            .where(CustomFieldDefinition.company_id == company_id)
            .where(CustomFieldDefinition.entity_type == entity_type)
            .where(CustomFieldDefinition.field_key == field_key)
            .where(CustomFieldDefinition.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_entity_type(
        self, company_id: UUID, entity_type: str
    ) -> list[CustomFieldDefinition]:
        """Return all custom fields for a given entity type, ordered by sort_order."""
        stmt = (
            select(CustomFieldDefinition)
            .where(CustomFieldDefinition.company_id == company_id)
            .where(CustomFieldDefinition.entity_type == entity_type)
            .where(CustomFieldDefinition.is_deleted == False)  # noqa: E712
            .order_by(
                CustomFieldDefinition.sort_order, CustomFieldDefinition.field_label
            )
        )
        return list(self.db.execute(stmt).scalars().all())
