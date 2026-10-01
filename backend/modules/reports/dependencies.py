"""FastAPI dependency injection functions for the Reports module.

All DI factories are synchronous, matching the sync ``Session`` / ``get_db``
pattern used throughout the backend. Extended incrementally in every later
phase as new repositories/services are added.

Spec ref: specs/011-reports-analytics/plan.md §12.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends
from sqlalchemy.orm import Session

from core.database.session import get_db
from modules.reports.exceptions import ReportNotEntitledError
from modules.reports.repositories.feature_flag import ReportsFeatureFlagRepository
from modules.reports.repositories.saved_report_view import SavedReportViewRepository
from modules.reports.services.feature_flag_service import ReportsFeatureFlagService

# ---------------------------------------------------------------------------
# Feature flag gate
# ---------------------------------------------------------------------------


def require_reports_enabled(
    company_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    """Raise ``ReportNotEntitledError("reports")`` unless
    ``feature.reports.enabled`` is on for this company. Applied at
    router-include time (T008) alongside ``require_capability_entitled
    ("reports")``, which already resolves the full Plan x Toggle chain and
    is the primary enforcement point reached first — this dependency is a
    defence-in-depth second check, mirroring ``require_crm_enabled``'s
    mount position exactly.
    """
    service = ReportsFeatureFlagService(flag_repo=ReportsFeatureFlagRepository(db))
    if not service.is_enabled(company_id):
        raise ReportNotEntitledError("reports")


# ---------------------------------------------------------------------------
# Repository factories
# ---------------------------------------------------------------------------


def get_saved_report_view_repo(
    db: Session = Depends(get_db),
) -> SavedReportViewRepository:
    return SavedReportViewRepository(db)
