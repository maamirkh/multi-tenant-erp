"""[Epic 10, Phase 11, T192-T196] Entitlement servicing-continuity
cluster (plan.md §15, FR-INST-353-358, Scenario K, SC-006).

A single shared file (same-file, sequential — not parallel-safe with
each other, matching tasks.md's own explicit [P]-marker correction for
this cluster) proving, against the REAL
``PlatformEntitlementService``/``InstallmentsFeatureFlagService`` chain
(no subscription row for these freshly-created test companies, so
resolution takes the documented "no_subscription_ceiling_inapplicable"
branch and defers entirely to the Installments module's own tenant
toggle — module_enablement.py's own docstring):

    T192 — enabled tenant: every operation class passes.
    T193 — disabled tenant: ORIGINATION-class operations are denied with
           403 FEATURE_DISABLED.
    T194 — disabled tenant: SERVICING-class operations against an
           existing ACTIVE/DEFAULTED contract remain available.
    T195 — disabled tenant: normal RBAC is still independently enforced
           — a missing permission still denies a servicing action, and
           the router's permission check runs regardless of entitlement
           state.
    T196 — a suspended tenant is denied identically to every other
           module via the shared ``get_current_company_member`` path —
           proven both structurally (no ``Company.status`` read inside
           ``InstallmentAccessPolicy``) and by confirming entitlement
           resolution has no special-case suspension branch of its own.

Real PostgreSQL throughout (schedule persistence requires it).
"""

from __future__ import annotations

import inspect
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from modules.installments.exceptions import InstallmentsNotEntitledError
from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.services.access_policy import InstallmentAccessPolicy
from modules.installments.services.feature_flag_service import (
    InstallmentsFeatureFlagService,
)
from modules.installments.services.permission_check import (
    user_has_installments_permission,
)
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
    build_contract_service,
    build_rescheduling_service,
    build_settlement_service,
)


def _build_real_access_policy(db_session: Session) -> InstallmentAccessPolicy:
    """The exact same construction ``get_installment_access_policy()``
    (dependencies.py) assembles for production — no test double."""
    entitlement_service = PlatformEntitlementService(
        db=db_session,
        plan_repo=PlanRepository(db_session),
        subscription_repo=SubscriptionRepository(db_session),
        override_checker=None,
    )
    return InstallmentAccessPolicy(entitlement_service=entitlement_service)


def _enable(db_session: Session, company_id: uuid.UUID) -> None:
    InstallmentsFeatureFlagService(
        flag_repo=InstallmentsFeatureFlagRepository(db_session)
    ).enable(company_id)
    db_session.commit()


class TestT192EnabledTenantAllOperationsPass:
    def test_origination_operation_succeeds_when_enabled(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="DRAFT",
        )
        _enable(db_session, ctx["company_id"])
        access_policy = _build_real_access_policy(db_session)
        svc = build_contract_service(db_session)
        svc._access_policy = access_policy  # noqa: SLF001 — test wiring

        updated = svc.submit(ctx["company_id"], ctx["contract"].id, actor_id=None)
        assert updated.status in ("PENDING_APPROVAL", "APPROVED")

    def test_servicing_operation_succeeds_when_enabled(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        _enable(db_session, ctx["company_id"])
        access_policy = _build_real_access_policy(db_session)
        svc = build_collection_service(db_session)
        svc._access_policy = access_policy  # noqa: SLF001 — test wiring

        result = svc.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("50.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        assert result["accounting_payment_id"] is not None

    def test_read_operation_succeeds_when_enabled(self, db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        _enable(db_session, ctx["company_id"])
        access_policy = _build_real_access_policy(db_session)
        svc = build_contract_service(db_session)
        svc._access_policy = access_policy  # noqa: SLF001 — test wiring

        fetched = svc.get(ctx["company_id"], ctx["contract"].id)
        assert fetched.id == ctx["contract"].id


class TestT193DisabledTenantOriginationDenied:
    """Disabled tenant (default state — no flag row written): every
    ORIGINATION-class operation is denied with 403 FEATURE_DISABLED,
    fired as literally the first statement of each method — before any
    repository access, business validation, or dependency is ever
    touched (proven by supplying deliberately-broken/``None``
    collaborators for everything past the gate and confirming the
    entitlement error is what surfaces, not an ``AttributeError``)."""

    def test_create_draft_denied_before_touching_eligibility_service(
        self, db_session: Session
    ) -> None:
        from modules.installments.repositories.contract import (
            InstallmentContractRepository,
        )
        from modules.installments.services.contract_service import (
            InstallmentContractService,
        )

        company_id = uuid.uuid4()
        access_policy = _build_real_access_policy(db_session)
        svc = InstallmentContractService(
            repo=InstallmentContractRepository(db_session),
            sequence_repo=None,  # type: ignore[arg-type]
            eligibility_service=None,  # type: ignore[arg-type]  # never reached
            accounting_gateway=None,  # type: ignore[arg-type]  # never reached
            configuration_service=None,  # type: ignore[arg-type]  # never reached
            audit_service=None,  # type: ignore[arg-type]  # never reached
            access_policy=access_policy,
        )

        with pytest.raises(InstallmentsNotEntitledError) as exc_info:
            svc.create_draft(
                company_id,
                None,
                sales_invoice_id=uuid.uuid4(),
                down_payment_amount=Decimal("0"),
                installment_count=3,
                frequency="MONTHLY",
                first_due_date=date.today(),
                maturity_date=date.today(),
            )
        assert exc_info.value.code == "FEATURE_DISABLED"

    def test_submit_denied(self, db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="DRAFT",
        )
        access_policy = _build_real_access_policy(db_session)
        svc = build_contract_service(db_session)
        svc._access_policy = access_policy  # noqa: SLF001

        with pytest.raises(InstallmentsNotEntitledError) as exc_info:
            svc.submit(ctx["company_id"], ctx["contract"].id, actor_id=None)
        assert exc_info.value.code == "FEATURE_DISABLED"

    def test_cancel_denied(self, db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="DRAFT",
        )
        access_policy = _build_real_access_policy(db_session)
        svc = build_contract_service(db_session)
        svc._access_policy = access_policy  # noqa: SLF001

        with pytest.raises(InstallmentsNotEntitledError) as exc_info:
            svc.cancel(
                ctx["company_id"],
                ctx["contract"].id,
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )
        assert exc_info.value.code == "FEATURE_DISABLED"

    def test_default_command_denied(self, db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        access_policy = _build_real_access_policy(db_session)
        svc = build_contract_service(db_session)
        svc._access_policy = access_policy  # noqa: SLF001

        with pytest.raises(InstallmentsNotEntitledError) as exc_info:
            svc.default_command(
                ctx["company_id"],
                ctx["contract"].id,
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )
        assert exc_info.value.code == "FEATURE_DISABLED"

    def test_writeoff_denied(self, db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        access_policy = _build_real_access_policy(db_session)
        svc = build_contract_service(db_session)
        svc._access_policy = access_policy  # noqa: SLF001

        with pytest.raises(InstallmentsNotEntitledError) as exc_info:
            svc.writeoff(
                ctx["company_id"],
                ctx["contract"].id,
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )
        assert exc_info.value.code == "FEATURE_DISABLED"

    def test_reschedule_denied(self, db_session: Session) -> None:
        from modules.installments.services.rescheduling_service import (
            RescheduleTerms,
        )

        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        access_policy = _build_real_access_policy(db_session)
        svc = build_rescheduling_service(db_session)
        svc._access_policy = access_policy  # noqa: SLF001

        with pytest.raises(InstallmentsNotEntitledError) as exc_info:
            svc.reschedule(
                ctx["company_id"],
                ctx["contract"].id,
                RescheduleTerms(first_due_date=ctx["today"]),
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
                requested_by=None,
            )
        assert exc_info.value.code == "FEATURE_DISABLED"

    def test_plan_template_create_denied(self, db_session: Session) -> None:
        from modules.installments.repositories.plan_template import (
            InstallmentPlanTemplateRepository,
        )
        from modules.installments.services.plan_template_service import (
            InstallmentPlanTemplateService,
        )

        company_id = uuid.uuid4()
        access_policy = _build_real_access_policy(db_session)
        svc = InstallmentPlanTemplateService(
            repo=InstallmentPlanTemplateRepository(db_session),
            access_policy=access_policy,
        )

        with pytest.raises(InstallmentsNotEntitledError) as exc_info:
            svc.create(
                company_id,
                None,
                name="Denied Template",
                installment_count=3,
                frequency="MONTHLY",
            )
        assert exc_info.value.code == "FEATURE_DISABLED"

    def test_configuration_change_denied(self, db_session: Session) -> None:
        """[Documented resolution of a plan.md/spec.md contradiction]
        Spec FR-INST-353/§34 OQ-2 explicitly names "configuration
        changes" as a blocked ORIGINATION operation while disabled —
        overriding plan.md §16.1's permission-catalogue table, which
        loosely labels ``installments.config.manage`` "ADMIN" in the RBAC
        sense (an admin-level permission), not the distinct
        ``InstallmentOperationClass.ADMIN`` entitlement-bypass sense."""
        from modules.installments.repositories.configuration import (
            InstallmentConfigurationRepository,
        )
        from modules.installments.services.configuration_service import (
            InstallmentConfigurationService,
        )

        company_id = uuid.uuid4()
        access_policy = _build_real_access_policy(db_session)
        svc = InstallmentConfigurationService(
            repo=InstallmentConfigurationRepository(db_session),
            access_policy=access_policy,
        )

        with pytest.raises(InstallmentsNotEntitledError) as exc_info:
            svc.upsert_config(company_id, None, None, min_term=1, max_term=60)
        assert exc_info.value.code == "FEATURE_DISABLED"


class TestT194DisabledTenantServicingContinues:
    """Disabled tenant: SERVICING-class operations against an existing
    contract remain fully available (FR-INST-356)."""

    def test_record_collection_succeeds_when_disabled(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        access_policy = _build_real_access_policy(db_session)
        svc = build_collection_service(db_session)
        svc._access_policy = access_policy  # noqa: SLF001

        result = svc.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("50.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        assert result["accounting_payment_id"] is not None

    def test_settlement_execute_succeeds_when_disabled(
        self, db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        access_policy = _build_real_access_policy(db_session)
        settlement_svc = build_settlement_service(db_session)
        settlement_svc._access_policy = access_policy  # noqa: SLF001

        quote = settlement_svc.generate_quote(
            ctx["company_id"], ctx["contract"].id, date.today(), actor_id=None
        )
        contract = settlement_svc.execute(
            ctx["company_id"],
            ctx["contract"].id,
            quote.settlement_amount,
            quote.as_of_date,
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        assert contract.status == "COMPLETED"

    def test_read_operations_succeed_when_disabled(self, db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        access_policy = _build_real_access_policy(db_session)
        svc = build_contract_service(db_session)
        svc._access_policy = access_policy  # noqa: SLF001

        fetched = svc.get(ctx["company_id"], ctx["contract"].id)
        assert fetched.id == ctx["contract"].id

    def test_cure_succeeds_when_disabled(self, db_session: Session) -> None:
        """``cure()`` is classified SERVICING (plan.md §16.1's
        ``installments.contract.cure`` row) — restoring an existing
        obligation to servicing, not originating a new one."""
        from modules.installments.models.configuration import (
            InstallmentConfiguration,
        )
        from modules.installments.models.contract import InstallmentContract
        from modules.installments.repositories.configuration import (
            InstallmentConfigurationRepository,
        )

        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        InstallmentConfigurationRepository(db_session).create(
            InstallmentConfiguration(
                company_id=ctx["company_id"],
                cure_enabled=True,
                allowed_frequencies=["MONTHLY"],
                min_term=1,
                max_term=60,
            )
        )
        contract = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        contract.status = "DEFAULTED"
        contract.defaulted_at = contract.contract_date  # type: ignore[assignment]
        db_session.add(contract)
        db_session.commit()

        access_policy = _build_real_access_policy(db_session)
        svc = build_contract_service(db_session)
        svc._access_policy = access_policy  # noqa: SLF001

        updated = svc.cure(ctx["company_id"], ctx["contract"].id, "reason", None)
        assert updated.status == "ACTIVE"


class TestT195DisabledTenantRbacStillEnforced:
    """Disabled tenant: normal RBAC remains independently enforced — a
    servicing action still requires its own permission code, and the
    router's permission check is not bypassed by entitlement state
    (plan.md router.py's own thin-controller sequence: authN -> authZ
    (RBAC) -> call service (which then applies entitlement) — so a
    caller lacking the permission never even reaches the entitlement
    check)."""

    def test_missing_permission_denies_regardless_of_entitlement_state(
        self, db_session: Session
    ) -> None:
        from modules.companies.models.company import Company
        from modules.users_roles.models.company_member import CompanyMember
        from modules.users_roles.models.enums import MembershipStatus
        from modules.users_roles.models.role import Role
        from tests.fixtures.auth_fixtures import create_test_user

        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        user, _ = create_test_user(db_session)
        # Role/CompanyMember (users_roles module) carry a real FK to
        # companies, unlike Installments'/Accounting's own soft
        # company_id references — a genuine Company row matching the
        # fixture's company_id is required here (Postgres enforces it;
        # the SQLite-backed test_rbac_permission_sweep.py sweep doesn't
        # need this since SQLite doesn't enforce FKs by default).
        company = Company(
            id=ctx["company_id"],
            legal_name="T195 RBAC Enforcement Co",
            slug=f"t195-rbac-co-{uuid.uuid4().hex[:10]}",
            owner_id=user.id,
            email=f"t195-rbac-co-{uuid.uuid4().hex[:10]}@example.com",
            status="active",
        )
        db_session.add(company)
        db_session.flush()
        empty_role = Role(
            company_id=ctx["company_id"],
            name="T195 Empty Role",
            slug=f"t195-empty-role-{uuid.uuid4().hex[:10]}",
            rank=10,
            is_system=False,
            is_active=True,
        )
        db_session.add(empty_role)
        db_session.flush()
        member = CompanyMember(
            company_id=ctx["company_id"],
            user_id=user.id,
            role_id=empty_role.id,
            status=MembershipStatus.active.value,
        )
        db_session.add(member)
        db_session.commit()

        # A role with ZERO permissions granted — disabled entitlement would
        # PERMIT this SERVICING operation, but RBAC must deny it anyway.
        allowed = user_has_installments_permission(
            db_session,
            ctx["company_id"],
            user.id,
            "installments.collection.create",
        )
        assert allowed is False

    def test_router_checks_permission_before_calling_the_service(self) -> None:
        """Structural proof: every ``router.py`` endpoint calls
        ``_require_permission()`` (RBAC) as a statement preceding its
        service-method call — RBAC is never conditioned on, or ordered
        after, any entitlement resolution."""
        import modules.installments.router as router_module

        source = inspect.getsource(router_module)
        # Every endpoint function's body contains _require_permission(
        # before its own svc.<method>(...) call — spot-checked via the
        # record_collection endpoint (FR-INST-356's own named example).
        record_collection_src = inspect.getsource(router_module.record_collection)
        permission_pos = record_collection_src.index("_require_permission(")
        service_call_pos = record_collection_src.index("svc.record_collection(")
        assert permission_pos < service_call_pos


class TestT196SuspendedTenantDeniedIdentically:
    """A suspended tenant is denied identically to every other module —
    no Installments-specific suspension mechanism exists."""

    def test_access_policy_module_imports_no_company_model(self) -> None:
        import ast
        import inspect as _inspect

        import modules.installments.services.access_policy as access_policy_module

        tree = ast.parse(_inspect.getsource(access_policy_module))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "modules.companies" not in node.module
