"""Attribute repositories — AttributeDefinition, AttributeSet, AttributeSetMembership.

Spec ref: specs/005-inventory-management/spec.md §14
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.inventory.models.attribute import (
    AttributeDefinition,
    AttributeSet,
    AttributeSetMembership,
)


class AttributeDefinitionRepository(BaseRepository[AttributeDefinition]):
    """Data-access layer for ``inventory_attribute_definitions`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=AttributeDefinition)

    def get_by_name(self, company_id: UUID, name: str) -> AttributeDefinition | None:
        """Return the attribute definition with this name for the company, or None."""
        stmt = (
            select(AttributeDefinition)
            .where(AttributeDefinition.company_id == company_id)
            .where(AttributeDefinition.name == name)
            .where(AttributeDefinition.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_active(self, company_id: UUID) -> list[AttributeDefinition]:
        """Return all active (non-deleted) attribute definitions for a company."""
        stmt = (
            select(AttributeDefinition)
            .where(AttributeDefinition.company_id == company_id)
            .where(AttributeDefinition.is_deleted == False)  # noqa: E712
            .order_by(AttributeDefinition.name)
        )
        return list(self.db.execute(stmt).scalars().all())


class AttributeSetRepository(BaseRepository[AttributeSet]):
    """Data-access layer for ``inventory_attribute_sets`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=AttributeSet)

    def get_by_name(self, company_id: UUID, name: str) -> AttributeSet | None:
        """Return the attribute set with this name for the company, or None."""
        stmt = (
            select(AttributeSet)
            .where(AttributeSet.company_id == company_id)
            .where(AttributeSet.name == name)
            .where(AttributeSet.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_by_scope(self, company_id: UUID, scope: str) -> list[AttributeSet]:
        """Return all attribute sets matching a given scope."""
        stmt = (
            select(AttributeSet)
            .where(AttributeSet.company_id == company_id)
            .where(AttributeSet.scope == scope)
            .where(AttributeSet.is_deleted == False)  # noqa: E712
            .order_by(AttributeSet.name)
        )
        return list(self.db.execute(stmt).scalars().all())


class AttributeSetMembershipRepository(BaseRepository[AttributeSetMembership]):
    """Data-access layer for ``inventory_attribute_set_memberships`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=AttributeSetMembership)

    def get_by_set_and_definition(
        self,
        company_id: UUID,
        attribute_set_id: UUID,
        attribute_definition_id: UUID,
    ) -> AttributeSetMembership | None:
        """Return the membership record for this set+definition pair, or None."""
        stmt = (
            select(AttributeSetMembership)
            .where(AttributeSetMembership.company_id == company_id)
            .where(AttributeSetMembership.attribute_set_id == str(attribute_set_id))
            .where(
                AttributeSetMembership.attribute_definition_id
                == str(attribute_definition_id)
            )
            .where(AttributeSetMembership.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_for_set(
        self, company_id: UUID, attribute_set_id: UUID
    ) -> list[AttributeSetMembership]:
        """Return all memberships for an attribute set, ordered by sort_order."""
        stmt = (
            select(AttributeSetMembership)
            .where(AttributeSetMembership.company_id == company_id)
            .where(AttributeSetMembership.attribute_set_id == str(attribute_set_id))
            .where(AttributeSetMembership.is_deleted == False)  # noqa: E712
            .order_by(AttributeSetMembership.sort_order)
        )
        return list(self.db.execute(stmt).scalars().all())
