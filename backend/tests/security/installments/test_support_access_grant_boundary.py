"""[Epic 10, Phase 11, T199] An active Epic 9A ``SupportAccessGrant``
cannot read Installments business records (Scenario L) — mirrors
``tests/security/modules/platform_admin/test_support_access_boundary.py``
``TestSupportAccessCannotReachBusinessRecords`` exactly, substituting a
genuine ``InstallmentContract`` for that test's ``Product`` row.

Real PostgreSQL (schedule-backed contract fixture).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.platform_admin.models.platform_administrator import (
    PlatformAdministrator,
)
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.support_access_repository import (
    SupportAccessRepository,
)
from modules.platform_admin.services.platform_audit_service import (
    PlatformAuditService,
)
from modules.platform_admin.services.support_access_service import (
    SupportAccessService,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)


def _make_administrator(db: Session, *, label: str) -> PlatformAdministrator:
    user = User(
        email=f"t199-{label}-{uuid.uuid4().hex[:10]}@example.test",
        display_name=f"T199 {label}",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _support_access_service(db: Session) -> SupportAccessService:
    return SupportAccessService(
        db=db,
        repo=SupportAccessRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


def _make_company_with_real_installment_contract(pg_db_session: Session) -> uuid.UUID:
    """A tenant holding at least one genuine, real-Postgres-backed
    ``InstallmentContract`` — mirrors T163's ``Product``-holding
    company, substituting Installments' own aggregate root."""
    ctx = build_active_contract_with_schedule(
        pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
    )
    return ctx["company_id"]


class TestSupportAccessCannotReachInstallmentsBusinessRecords:
    def test_only_the_three_contract_paths_exist(
        self, test_client: TestClient, db_session: Session, pg_db_session: Session
    ) -> None:
        company_id = _make_company_with_real_installment_contract(pg_db_session)
        actor = _make_administrator(db_session, label="grant-actor")
        _support_access_service(db_session).initiate(
            company_id=company_id,
            reason="T199 — proving the boundary against a real InstallmentContract.",
            actor_platform_administrator_id=actor.id,
        )

        app = cast(FastAPI, test_client.app)
        spec = app.openapi()
        support_access_paths = {p for p in spec["paths"] if "support-access" in p}
        assert support_access_paths == {
            "/api/v1/platform/tenants/{companyId}/support-access",
            "/api/v1/platform/support-access/{grantId}",
            "/api/v1/platform/support-access",
        }
        installments_paths = {
            p for p in spec["paths"] if "installments" in p and "support" in p
        }
        assert installments_paths == set()
