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
