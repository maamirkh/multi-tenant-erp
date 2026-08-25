"""FastAPI dependency injection functions for the Installments module.

All DI factories are synchronous, matching the sync ``Session`` /
``get_db`` pattern used throughout the backend. Extended incrementally in
every later phase as new repositories/services are added, mirroring
``modules/crm/dependencies.py``'s own incremental-growth convention.

Spec ref: specs/010-installments/plan.md §2, §12.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from core.database.session import get_db
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.configuration import (
    InstallmentConfigurationRepository,
)
from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.repositories.plan_template import (
    InstallmentPlanTemplateRepository,
)
from modules.installments.services.audit_service import InstallmentAuditService
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.feature_flag_service import (
    InstallmentsFeatureFlagService,
)
from modules.installments.services.plan_template_service import (
    InstallmentPlanTemplateService,
)

# ---------------------------------------------------------------------------
# Repository factories
# ---------------------------------------------------------------------------


def get_installment_configuration_repo(
    db: Session = Depends(get_db),
) -> InstallmentConfigurationRepository:
    return InstallmentConfigurationRepository(db)


def get_installment_plan_template_repo(
    db: Session = Depends(get_db),
) -> InstallmentPlanTemplateRepository:
    return InstallmentPlanTemplateRepository(db)


def get_installments_feature_flag_repo(
    db: Session = Depends(get_db),
) -> InstallmentsFeatureFlagRepository:
    return InstallmentsFeatureFlagRepository(db)


def get_installment_audit_log_repo(
    db: Session = Depends(get_db),
) -> InstallmentAuditLogRepository:
    return InstallmentAuditLogRepository(db)


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def get_installment_configuration_service(
    repo: InstallmentConfigurationRepository = Depends(
        get_installment_configuration_repo
    ),
) -> InstallmentConfigurationService:
    return InstallmentConfigurationService(repo=repo)


def get_installment_plan_template_service(
    repo: InstallmentPlanTemplateRepository = Depends(
        get_installment_plan_template_repo
    ),
) -> InstallmentPlanTemplateService:
    return InstallmentPlanTemplateService(repo=repo)


def get_installments_feature_flag_service(
    repo: InstallmentsFeatureFlagRepository = Depends(
        get_installments_feature_flag_repo
    ),
) -> InstallmentsFeatureFlagService:
    return InstallmentsFeatureFlagService(flag_repo=repo)


def get_installment_audit_service(
    db: Session = Depends(get_db),
    repo: InstallmentAuditLogRepository = Depends(get_installment_audit_log_repo),
) -> InstallmentAuditService:
    return InstallmentAuditService(db=db, audit_repo=repo)
