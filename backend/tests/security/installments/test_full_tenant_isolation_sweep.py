"""[Epic 10, Phase 11, T197] Full tenant-isolation sweep — Company A
cannot reach Company B's installment resources by ID, by search, by
collection, or by settlement, across every endpoint group.

``router.py`` endpoints are deliberately thin controllers (module
docstring: "validate -> authN -> authZ -> call service -> return
schema") that pass the URL's ``company_id`` straight into the
corresponding service method with no additional business logic — the
actual tenant-isolation boundary is therefore enforced entirely at the
service/repository layer this file exercises directly (the same
enforcement point Phase 3's ``test_contract_tenant_isolation.py``
already proved for the Contracts group's ``get``/version-update paths;
this file extends that proof to every remaining group: search/list,
lifecycle (submit/approve/reject/cancel/default/cure/writeoff),
activation, collections, collection reversal, settlement, reschedule,
and schedule retrieval).

Real PostgreSQL throughout (schedule persistence requires it).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.models.payments import Payment
from modules.installments.exceptions import (
    InstallmentNotFoundError,
    InstallmentReversalNotAllowedError,
)
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.plan_template import InstallmentPlanTemplate
from modules.installments.repositories.configuration import (
    InstallmentConfigurationRepository,
)
from modules.installments.repositories.plan_template import (
    InstallmentPlanTemplateRepository,
)
from modules.installments.services.configuration_service import (
    InstallmentConfigurationService,
)
from modules.installments.services.plan_template_service import (
    InstallmentPlanTemplateService,
)
from tests.security.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
    build_contract_service,
    build_rescheduling_service,
    build_settlement_service,
)


class TestSearchAndListIsolation:
    def test_list_never_returns_another_companys_contracts(
        self, pg_db_session: Session
    ) -> None:
        ctx_a = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)

        company_b = uuid.uuid4()
        items_b, total_b = svc.list(company_b)
        assert total_b == 0
        assert items_b == []

        items_a, total_a = svc.list(ctx_a["company_id"])
        assert total_a == 1
        assert items_a[0].id == ctx_a["contract"].id


class TestContractByIdIsolation:
    def test_get_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.get(company_b, ctx["contract"].id)


class TestLifecycleActionsIsolation:
    def test_submit_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="DRAFT",
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.submit(company_b, ctx["contract"].id, actor_id=None)

    def test_approve_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="PENDING_APPROVAL",
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.approve(company_b, ctx["contract"].id, approver_id=None)

    def test_reject_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="PENDING_APPROVAL",
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.reject(company_b, ctx["contract"].id, "reason", rejecter_id=None)

    def test_cancel_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="DRAFT",
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()
        before = (
            pg_db_session.query(InstallmentContract)
            .filter_by(id=ctx["contract"].id)
            .one()
        )
        before_status, before_version = before.status, before.version

        with pytest.raises(InstallmentNotFoundError):
            svc.cancel(
                company_b,
                ctx["contract"].id,
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

        # Every protected field on the target (owning tenant's) record
        # is re-read and confirmed unchanged after the attempt.
        after = (
            pg_db_session.query(InstallmentContract)
            .filter_by(id=ctx["contract"].id)
            .one()
        )
        assert after.status == before_status == "DRAFT"
        assert after.version == before_version
        assert after.cancelled_at is None
        assert after.company_id == ctx["company_id"]

    def test_default_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.default_command(
                company_b,
                ctx["contract"].id,
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

    def test_cure_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.cure(company_b, ctx["contract"].id, "reason", actor_id=None)

    def test_writeoff_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.writeoff(
                company_b,
                ctx["contract"].id,
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )

    def test_activate_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="APPROVED",
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.activate(
                company_b,
                ctx["contract"].id,
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )


class TestScheduleIsolation:
    def test_get_active_schedule_cross_tenant_is_not_found(
        self, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.get_active_schedule(company_b, ctx["contract"].id)

    def test_get_schedule_version_cross_tenant_is_not_found(
        self, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_contract_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.get_schedule_version(company_b, ctx["contract"].id, 1)


class TestCollectionIsolation:
    def test_record_collection_cross_tenant_is_not_found(
        self, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_collection_service(pg_db_session)
        company_b = uuid.uuid4()
        before = (
            pg_db_session.query(InstallmentContract)
            .filter_by(id=ctx["contract"].id)
            .one()
        )
        before_status = before.status
        payments_before = (
            pg_db_session.execute(
                select(Payment).where(Payment.company_id == ctx["company_id"])
            )
            .scalars()
            .all()
        )
        assert payments_before == []

        with pytest.raises(InstallmentNotFoundError):
            svc.record_collection(
                company_b,
                ctx["contract"].id,
                amount=Decimal("50.00"),
                payment_method="BANK_TRANSFER",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
                bank_account_id=ctx["bank_account"].id,
            )

        # No financial mutation reached Accounting, and the contract's
        # own protected state is unchanged.
        after = (
            pg_db_session.query(InstallmentContract)
            .filter_by(id=ctx["contract"].id)
            .one()
        )
        assert after.status == before_status
        payments_after = (
            pg_db_session.execute(
                select(Payment).where(Payment.company_id == ctx["company_id"])
            )
            .scalars()
            .all()
        )
        assert payments_after == [], "cross-tenant attempt must create ZERO payments"

    def test_reverse_collection_cross_tenant_is_rejected(
        self, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_collection_service(pg_db_session)
        result = svc.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("50.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        collection_id = uuid.UUID(result["accounting_payment_id"])
        company_b = uuid.uuid4()

        # The allocation-reference lookup is company_id-scoped — a wrong
        # company_id sees zero references, indistinguishable from a
        # never-existed collection_id (BR-INST-015-style).
        with pytest.raises(InstallmentReversalNotAllowedError):
            svc.reverse_collection(
                company_b,
                collection_id,
                reason="cross-tenant reversal attempt",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
            )


class TestSettlementIsolation:
    def test_generate_quote_cross_tenant_is_not_allowed(
        self, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_settlement_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.generate_quote(
                company_b, ctx["contract"].id, ctx["today"], actor_id=None
            )

    def test_execute_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_settlement_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.execute(
                company_b,
                ctx["contract"].id,
                Decimal("100.00"),
                ctx["today"],
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
                bank_account_id=ctx["bank_account"].id,
            )


class TestRescheduleIsolation:
    def test_reschedule_cross_tenant_is_not_found(self, pg_db_session: Session) -> None:
        from modules.installments.services.rescheduling_service import (
            RescheduleTerms,
        )

        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        svc = build_rescheduling_service(pg_db_session)
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.reschedule(
                company_b,
                ctx["contract"].id,
                RescheduleTerms(first_due_date=ctx["today"]),
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=None,
                requested_by=None,
            )


class TestConfigurationAndPlanTemplateIsolation:
    """[Strengthening — HTTP Security Evidence Closure item 8] The
    configuration/template group T197 did not originally cover."""

    def test_plan_template_update_cross_tenant_is_not_found_and_unchanged(
        self, pg_db_session: Session
    ) -> None:
        company_a = uuid.uuid4()
        repo = InstallmentPlanTemplateRepository(pg_db_session)
        svc = InstallmentPlanTemplateService(repo=repo)
        template = svc.create(
            company_a,
            None,
            name="Tenant A's Template",
            installment_count=6,
            frequency="MONTHLY",
            down_payment_rule={"type": "FIXED", "amount": "0"},
        )
        before_name, before_updated_at = template.name, template.updated_at
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.update(company_b, template.id, name="Hijacked By Tenant B")

        after = (
            pg_db_session.execute(
                select(InstallmentPlanTemplate).where(
                    InstallmentPlanTemplate.id == template.id
                )
            )
            .scalars()
            .one()
        )
        assert after.name == before_name == "Tenant A's Template"
        assert after.updated_at == before_updated_at
        assert after.company_id == company_a

    def test_plan_template_deactivate_cross_tenant_is_not_found_and_unchanged(
        self, pg_db_session: Session
    ) -> None:
        company_a = uuid.uuid4()
        repo = InstallmentPlanTemplateRepository(pg_db_session)
        svc = InstallmentPlanTemplateService(repo=repo)
        template = svc.create(
            company_a,
            None,
            name="Tenant A's Deactivation Target",
            installment_count=3,
            frequency="MONTHLY",
            down_payment_rule={"type": "FIXED", "amount": "0"},
        )
        assert template.is_active is True
        company_b = uuid.uuid4()

        with pytest.raises(InstallmentNotFoundError):
            svc.deactivate(company_b, template.id)

        after = (
            pg_db_session.execute(
                select(InstallmentPlanTemplate).where(
                    InstallmentPlanTemplate.id == template.id
                )
            )
            .scalars()
            .one()
        )
        assert after.is_active is True, "cross-tenant attempt must not deactivate it"

    def test_configuration_never_reveals_another_companys_policy(
        self, pg_db_session: Session
    ) -> None:
        company_a = uuid.uuid4()
        repo = InstallmentConfigurationRepository(pg_db_session)
        svc = InstallmentConfigurationService(repo=repo)
        svc.upsert_config(
            company_a,
            None,
            None,
            allowed_frequencies=["MONTHLY"],
            min_term=1,
            max_term=60,
            cure_enabled=True,
        )
        company_b = uuid.uuid4()

        # Company B's own effective config is genuinely unconfigured —
        # never company A's policy, structurally impossible to leak
        # since the lookup is scoped by company_id at the query level.
        config_for_b = svc.get_effective_config(company_b, None)
        assert config_for_b is None

        config_for_a = svc.get_effective_config(company_a, None)
        assert config_for_a is not None
        assert config_for_a.cure_enabled is True
