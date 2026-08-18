"""Shared base schema for the CRM module.

Mirrors ``modules/sales/schemas/base.py::SalesBaseSchema`` exactly — enables
ORM mode (``from_attributes=True``) so SQLAlchemy models can be serialised
directly into response schemas, per the established per-module convention
(no shared cross-module base schema exists today).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CrmBaseSchema(BaseModel):
    """Base schema for all CRM module request/response models."""

    model_config = ConfigDict(from_attributes=True)


class CrmStatusRead(CrmBaseSchema):
    """Whether the CRM module is currently enabled for a company."""

    enabled: bool


class CrmMyPermissions(CrmBaseSchema):
    """The requesting user's granted ``crm.*`` permission codes in this
    company — lets the frontend hide (not just disable) actions the user
    cannot perform, instead of relying solely on the 403 the backend
    already returns after the fact."""

    permissions: list[str]
