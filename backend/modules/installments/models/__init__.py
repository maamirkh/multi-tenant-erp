"""Installments module ORM models.

All models are imported here to ensure Alembic autogenerate and the test
suite's ``Base.metadata.create_all()`` can resolve every Installments
table — mirrors ``modules/crm/models/__init__.py``'s exact convention.

Import order follows dependency order (parent before child tables).
"""

from modules.installments.models.audit import InstallmentAuditLog
from modules.installments.models.configuration import InstallmentConfiguration
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.feature_flag import InstallmentsFeatureFlag
from modules.installments.models.plan_template import InstallmentPlanTemplate
from modules.installments.models.sequence import InstallmentSequence

__all__ = [
    "InstallmentAuditLog",
    "InstallmentConfiguration",
    "InstallmentContract",
    "InstallmentPlanTemplate",
    "InstallmentSequence",
    "InstallmentsFeatureFlag",
]
