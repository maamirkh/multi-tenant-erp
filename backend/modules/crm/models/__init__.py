"""CRM module ORM models.

All models are imported here to ensure Alembic autogenerate and the test
suite's ``Base.metadata.create_all()`` can resolve every CRM table.

Import order follows dependency order (parent before child tables).
"""

from modules.crm.models.activity import Activity
from modules.crm.models.audit import CrmAuditLog
from modules.crm.models.feature_flag import CrmFeatureFlag
from modules.crm.models.lead import Lead
from modules.crm.models.lead_source import LeadSource
from modules.crm.models.opportunity import Opportunity
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage

__all__ = [
    "Activity",
    "CrmAuditLog",
    "CrmFeatureFlag",
    "Lead",
    "LeadSource",
    "Opportunity",
    "Pipeline",
    "PipelineStage",
]
