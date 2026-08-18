"""FastAPI dependency injection functions for the CRM module.

All DI factories are synchronous, matching the sync ``Session`` / ``get_db``
pattern used throughout the backend. Extended incrementally in every later
phase as new repositories/services are added.

Spec ref: specs/009-crm/plan.md §21.5 (Feature Flag gate wiring).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from core.database.session import get_db
from modules.accounting.dependencies import get_ar_service
from modules.accounting.services.ar_service import AccountsReceivableService
from modules.crm.exceptions import CrmFeatureDisabledError
from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.audit_log import CrmAuditLogRepository
from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.lead_source import LeadSourceRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.repositories.pipeline import PipelineRepository
from modules.crm.repositories.pipeline_stage import PipelineStageRepository
from modules.crm.services.activity_service import ActivityService
from modules.crm.services.audit_service import CrmAuditService
from modules.crm.services.customer_360_service import Customer360Service
from modules.crm.services.feature_flag_service import CrmFeatureFlagService
from modules.crm.services.lead_conversion_service import LeadConversionService
from modules.crm.services.lead_service import LeadService
from modules.crm.services.lead_source_service import LeadSourceService
from modules.crm.services.opportunity_service import OpportunityService
from modules.crm.services.pipeline_service import PipelineService
from modules.crm.services.provisioning_service import CrmProvisioningService
from modules.crm.services.reporting_service import CrmReportingService
from modules.sales.dependencies import (
    get_customer_category_repo,
    get_customer_category_service,
    get_customer_repo,
    get_customer_service,
    get_sales_quotation_repo,
)
from modules.sales.repositories.customer import CustomerRepository
from modules.sales.repositories.master import CustomerCategoryRepository
from modules.sales.repositories.quotation import SalesQuotationRepository
from modules.sales.services.customer_service import CustomerService
from modules.sales.services.master_data_service import CustomerCategoryService
from modules.users_roles.dependencies import get_member_repo
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)

# ---------------------------------------------------------------------------
# Repository factories
# ---------------------------------------------------------------------------


def get_crm_feature_flag_repo(
    db: Session = Depends(get_db),
) -> CrmFeatureFlagRepository:
    return CrmFeatureFlagRepository(db)


def get_lead_source_repository(
    db: Session = Depends(get_db),
) -> LeadSourceRepository:
    return LeadSourceRepository(db)


def get_lead_repository(db: Session = Depends(get_db)) -> LeadRepository:
    return LeadRepository(db)


def get_pipeline_repository(db: Session = Depends(get_db)) -> PipelineRepository:
    return PipelineRepository(db)


def get_pipeline_stage_repository(
    db: Session = Depends(get_db),
) -> PipelineStageRepository:
    return PipelineStageRepository(db)


def get_opportunity_repository(
    db: Session = Depends(get_db),
) -> OpportunityRepository:
    return OpportunityRepository(db)


def get_activity_repository(db: Session = Depends(get_db)) -> ActivityRepository:
    return ActivityRepository(db)


def get_crm_audit_log_repo(db: Session = Depends(get_db)) -> CrmAuditLogRepository:
    return CrmAuditLogRepository(db)


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_crm_audit_service(
    repo: CrmAuditLogRepository = Depends(get_crm_audit_log_repo),
) -> CrmAuditService:
    return CrmAuditService(repo=repo)


def get_pipeline_service(
    db: Session = Depends(get_db),
    repo: PipelineRepository = Depends(get_pipeline_repository),
    stage_repo: PipelineStageRepository = Depends(get_pipeline_stage_repository),
) -> PipelineService:
    return PipelineService(db=db, repo=repo, stage_repo=stage_repo)


def get_crm_provisioning_service(
    db: Session = Depends(get_db),
    pipeline_repo: PipelineRepository = Depends(get_pipeline_repository),
    pipeline_service: PipelineService = Depends(get_pipeline_service),
    category_repo: CustomerCategoryRepository = Depends(get_customer_category_repo),
    category_service: CustomerCategoryService = Depends(get_customer_category_service),
) -> CrmProvisioningService:
    return CrmProvisioningService(
        db=db,
        pipeline_repo=pipeline_repo,
        pipeline_service=pipeline_service,
        category_repo=category_repo,
        category_service=category_service,
    )


def get_crm_feature_flag_service(
    db: Session = Depends(get_db),
    provisioning_service: CrmProvisioningService = Depends(
        get_crm_provisioning_service
    ),
) -> CrmFeatureFlagService:
    return CrmFeatureFlagService(
        db=db,
        flag_repo=CrmFeatureFlagRepository(db),
        provisioning_service=provisioning_service,
    )


def get_lead_source_service(
    db: Session = Depends(get_db),
    repo: LeadSourceRepository = Depends(get_lead_source_repository),
) -> LeadSourceService:
    return LeadSourceService(db=db, repo=repo)


def get_lead_service(
    db: Session = Depends(get_db),
    repo: LeadRepository = Depends(get_lead_repository),
    member_repo: CompanyMemberRepository = Depends(get_member_repo),
    audit_service: CrmAuditService = Depends(get_crm_audit_service),
) -> LeadService:
    return LeadService(
        db=db, repo=repo, member_repo=member_repo, audit_service=audit_service
    )


def get_lead_conversion_service(
    db: Session = Depends(get_db),
    lead_repo: LeadRepository = Depends(get_lead_repository),
    opportunity_repo: OpportunityRepository = Depends(get_opportunity_repository),
    pipeline_repo: PipelineRepository = Depends(get_pipeline_repository),
    pipeline_stage_repo: PipelineStageRepository = Depends(
        get_pipeline_stage_repository
    ),
    provisioning_service: CrmProvisioningService = Depends(
        get_crm_provisioning_service
    ),
    customer_service: CustomerService = Depends(get_customer_service),
    audit_service: CrmAuditService = Depends(get_crm_audit_service),
) -> LeadConversionService:
    return LeadConversionService(
        db=db,
        lead_repo=lead_repo,
        opportunity_repo=opportunity_repo,
        pipeline_repo=pipeline_repo,
        pipeline_stage_repo=pipeline_stage_repo,
        provisioning_service=provisioning_service,
        customer_service=customer_service,
        audit_service=audit_service,
    )


def get_opportunity_service(
    db: Session = Depends(get_db),
    repo: OpportunityRepository = Depends(get_opportunity_repository),
    stage_repo: PipelineStageRepository = Depends(get_pipeline_stage_repository),
    customer_repo: CustomerRepository = Depends(get_customer_repo),
    member_repo: CompanyMemberRepository = Depends(get_member_repo),
    quotation_repo: SalesQuotationRepository = Depends(get_sales_quotation_repo),
    audit_service: CrmAuditService = Depends(get_crm_audit_service),
) -> OpportunityService:
    return OpportunityService(
        db=db,
        repo=repo,
        stage_repo=stage_repo,
        customer_repo=customer_repo,
        member_repo=member_repo,
        quotation_repo=quotation_repo,
        audit_service=audit_service,
    )


def get_activity_service(
    db: Session = Depends(get_db),
    repo: ActivityRepository = Depends(get_activity_repository),
    lead_repo: LeadRepository = Depends(get_lead_repository),
    customer_repo: CustomerRepository = Depends(get_customer_repo),
    opportunity_repo: OpportunityRepository = Depends(get_opportunity_repository),
    member_repo: CompanyMemberRepository = Depends(get_member_repo),
    audit_service: CrmAuditService = Depends(get_crm_audit_service),
) -> ActivityService:
    return ActivityService(
        db=db,
        repo=repo,
        lead_repo=lead_repo,
        customer_repo=customer_repo,
        opportunity_repo=opportunity_repo,
        member_repo=member_repo,
        audit_service=audit_service,
    )


def get_crm_reporting_service(
    opportunity_repo: OpportunityRepository = Depends(get_opportunity_repository),
    lead_repo: LeadRepository = Depends(get_lead_repository),
    activity_repo: ActivityRepository = Depends(get_activity_repository),
) -> CrmReportingService:
    return CrmReportingService(
        opportunity_repo=opportunity_repo,
        lead_repo=lead_repo,
        activity_repo=activity_repo,
    )


def get_customer_360_service(
    db: Session = Depends(get_db),
    customer_repo: CustomerRepository = Depends(get_customer_repo),
    lead_repo: LeadRepository = Depends(get_lead_repository),
    opportunity_repo: OpportunityRepository = Depends(get_opportunity_repository),
    activity_repo: ActivityRepository = Depends(get_activity_repository),
    ar_service: AccountsReceivableService = Depends(get_ar_service),
) -> Customer360Service:
    """Direct, synchronous, in-process read-only composition across CRM +
    Sales + Accounting (plan.md §14, ADR-3, ADR-6) — reuses Accounting's
    own ``get_ar_service`` DI factory unchanged, never a new Accounting
    endpoint or a cached financial value."""
    return Customer360Service(
        db=db,
        customer_repo=customer_repo,
        lead_repo=lead_repo,
        opportunity_repo=opportunity_repo,
        activity_repo=activity_repo,
        ar_service=ar_service,
    )


# ---------------------------------------------------------------------------
# Feature flag gate
# ---------------------------------------------------------------------------


def require_crm_enabled(
    company_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    """Raise ``CrmFeatureDisabledError`` unless ``feature.crm.enabled`` is on
    for this company. Applied at router-include time (Phase 9, T079)
    alongside the existing tenant-membership gate.
    """
    service = CrmFeatureFlagService(db=db, flag_repo=CrmFeatureFlagRepository(db))
    if not service.is_enabled(company_id):
        raise CrmFeatureDisabledError()
