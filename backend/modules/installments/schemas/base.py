"""Shared base schema for the Installments module.

Provides ``InstallmentsBaseSchema`` — base config with ORM mode enabled,
mirroring ``modules/accounting/schemas/base.py``'s ``AccountingBaseSchema``
convention.

Spec ref: specs/010-installments/plan.md §23.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class InstallmentsBaseSchema(BaseModel):
    """Base schema for all Installments module request/response models.

    Enables ORM mode (``from_attributes=True``) so SQLAlchemy models
    can be serialised directly into response schemas.
    """

    model_config = ConfigDict(from_attributes=True)


class InstallmentsStatusRead(InstallmentsBaseSchema):
    """Whether the Installments module is currently enabled for a
    company. Mirrors ``CrmStatusRead`` exactly."""

    enabled: bool


class InstallmentsMyPermissions(InstallmentsBaseSchema):
    """The requesting user's granted ``installments.*`` permission codes
    in this company — lets the frontend hide (not just disable) actions
    the user cannot perform, instead of relying solely on the 403 the
    backend already returns after the fact. Mirrors ``CrmMyPermissions``
    exactly."""

    permissions: list[str]
