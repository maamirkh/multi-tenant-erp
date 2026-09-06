"""[T176] ExportService — platform export, permission-scoped, no HTTP
route (FR-9A-120/121) — Epic 9A Phase 13.

Static proof that no `/export` path exists anywhere in the mounted app
(matching the contract's declared 28 paths exactly) lives in
`test_contract_conformance.py` (T177); this file proves the service
layer's own behavior: permission gating and a business-record-import
static check, mirroring Phase 12's established technique.
"""

from __future__ import annotations

import ast
import inspect
import uuid

import pytest
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.companies.repositories.company_repository import CompanyRepository
from modules.platform_admin.exceptions import InsufficientPlatformPermissionError
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.usage_repository import UsageRepository
from modules.platform_admin.services.export_service import ExportService
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.tenant_lifecycle_service import (
    TenantLifecycleService,
)

_BUSINESS_MODULE_PREFIXES = (
    "modules.inventory",
    "modules.purchase",
    "modules.sales",
    "modules.accounting",
    "modules.crm",
)


class TestExportServiceImportsNoBusinessRecordModule:
    def test_export_service_imports_no_business_record_module(self) -> None:
        import modules.platform_admin.services.export_service as mod

        tree = ast.parse(inspect.getsource(mod))
        violations = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module
            and any(node.module.startswith(p) for p in _BUSINESS_MODULE_PREFIXES)
        ]
        assert violations == [], f"forbidden imports found: {violations}"


def _make_company(db: Session, *, label: str) -> Company:
    suffix = uuid.uuid4().hex[:10]
    owner = User(
        email=f"t176-owner-{label}-{suffix}@example.test",
        display_name=f"T176 Owner {label}",
    )
    db.add(owner)
    db.flush()
    company = Company(
        legal_name=f"T176 Export Co {label} {suffix}",
        slug=f"t176-export-co-{label}-{suffix}",
        owner_id=owner.id,
        email=f"t176-export-co-{label}-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _make_actor(db: Session) -> PlatformAdministrator:
    user = User(
        email=f"t176-actor-{uuid.uuid4().hex[:10]}@example.test",
        display_name="T176 Actor",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _export_service(db: Session) -> ExportService:
    return ExportService(
        db=db,
        company_repo=CompanyRepository(db),
        usage_repo=UsageRepository(db),
        audit_repo=PlatformAuditRepository(db),
    )


class TestExportPermissionScoping:
    def test_export_tenant_directory_without_permission_raises(
        self, db_session: Session
    ) -> None:
        service = _export_service(db_session)
        with pytest.raises(InsufficientPlatformPermissionError):
            service.export_tenant_directory(held_permissions=set())

    def test_export_tenant_directory_with_permission_includes_company(
        self, db_session: Session
    ) -> None:
        company = _make_company(db_session, label="directory")
        service = _export_service(db_session)
        rows = service.export_tenant_directory(
            held_permissions={"platform.tenants.read"}
        )
        assert any(r["id"] == str(company.id) for r in rows)

    def test_export_audit_data_without_permission_raises(
        self, db_session: Session
    ) -> None:
        service = _export_service(db_session)
        with pytest.raises(InsufficientPlatformPermissionError):
            service.export_audit_data(held_permissions=set())

    def test_export_audit_data_with_permission_includes_recorded_event(
        self, db_session: Session
    ) -> None:
        actor = _make_actor(db_session)
        company = _make_company(db_session, label="audit")
        from core.events.outbox import EventOutboxRepository

        TenantLifecycleService(
            db=db_session,
            company_repo=CompanyRepository(db_session),
            outbox_repo=EventOutboxRepository(db_session),
            audit=PlatformAuditService(db_session, PlatformAuditRepository(db_session)),
        ).suspend(
            company_id=company.id,
            actor_platform_administrator_id=actor.id,
            reason="T176 export test.",
        )

        service = _export_service(db_session)
        rows = service.export_audit_data(held_permissions={"platform.audit.read"})
        assert any(
            r["action"] == "tenant_lifecycle.suspend"
            and r["company_id"] == str(company.id)
            for r in rows
        )

    def test_export_usage_summary_without_permission_raises(
        self, db_session: Session
    ) -> None:
        service = _export_service(db_session)
        with pytest.raises(InsufficientPlatformPermissionError):
            service.export_usage_summary(held_permissions=set())

    def test_export_subscription_summary_without_permission_raises(
        self, db_session: Session
    ) -> None:
        service = _export_service(db_session)
        with pytest.raises(InsufficientPlatformPermissionError):
            service.export_subscription_summary(held_permissions=set())
