"""[Epic 10, Phase 10, T180/T181] Service tests — InstallmentContractService.
cure().

T180: cure — policy-disabled tenant never sees the action succeed even
with the permission (true kill switch, ADR-INST-12).

T181 [CORRECTED — Correction 6: removed incorrect [P] marker, same
implied file as T180]: cure preserves the historical DEFAULTED event and
all delinquency history, never rewrites original terms, never touches
Accounting — NOT parallel-safe with T180 (same file).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from modules.accounting.models.ar import ARTransaction
from modules.installments.exceptions import InstallmentCureNotAllowedError
from modules.installments.models.audit import InstallmentAuditLog
from modules.installments.models.configuration import InstallmentConfiguration
from modules.installments.models.contract import InstallmentContract
from modules.installments.repositories.configuration import (
    InstallmentConfigurationRepository,
)
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_contract_service,
    build_delinquency_service,
)

_LATE_CHARGE_POLICY = {"enabled": True, "charge_type": "FIXED", "amount": "25.00"}


def _persist_configuration(db_session, company_id, *, cure_enabled: bool) -> None:
    InstallmentConfigurationRepository(db_session).create(
        InstallmentConfiguration(
            company_id=company_id,
            branch_id=None,
            allowed_frequencies=["MONTHLY"],
            min_term=1,
            max_term=60,
            cure_enabled=cure_enabled,
        )
    )
    db_session.commit()


def _default_contract(db_session, **kwargs) -> dict:
    ctx = build_active_contract_with_schedule(db_session, **kwargs)
    contract = (
        db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
    )
    contract.status = "DEFAULTED"
    contract.defaulted_at = contract.contract_date  # any non-null sentinel
    db_session.add(contract)
    db_session.commit()
    ctx["contract"] = contract
    return ctx


class TestCurePolicyKillSwitch:
    def test_cure_rejected_when_policy_disabled(self, db_session) -> None:
        ctx = _default_contract(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        _persist_configuration(db_session, ctx["company_id"], cure_enabled=False)
        svc = build_contract_service(db_session)

        with pytest.raises(InstallmentCureNotAllowedError):
            svc.cure(ctx["company_id"], ctx["contract"].id, "Goodwill", actor_id=None)

        db_session.rollback()
        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.status == "DEFAULTED"

    def test_cure_rejected_when_no_configuration_row_exists(self, db_session) -> None:
        """No InstallmentConfiguration row at all -> cure_enabled defaults
        to unset/false (fail-closed, never fail-open)."""
        ctx = _default_contract(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        svc = build_contract_service(db_session)

        with pytest.raises(InstallmentCureNotAllowedError):
            svc.cure(ctx["company_id"], ctx["contract"].id, "Goodwill", actor_id=None)

    def test_cure_succeeds_when_policy_enabled(self, db_session) -> None:
        ctx = _default_contract(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        _persist_configuration(db_session, ctx["company_id"], cure_enabled=True)
        svc = build_contract_service(db_session)

        updated = svc.cure(
            ctx["company_id"], ctx["contract"].id, "Goodwill", actor_id=None
        )
        assert updated.status == "ACTIVE"


class TestCurePreservesHistory:
    def test_cure_preserves_defaulted_audit_and_late_charge_history(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session,
            installment_count=1,
            installment_amount=Decimal("500.00"),
            late_charge_policy=_LATE_CHARGE_POLICY,
        )
        line = ctx["schedule_lines"][0]
        delinquency_service = build_delinquency_service(db_session)
        late_charge = delinquency_service.apply_late_charge(
            ctx["company_id"], ctx["contract"].id, line.id, actor_id=None
        )
        db_session.commit()
        db_session.refresh(late_charge)

        contract = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        original_principal = contract.principal_amount
        original_markup = contract.markup_amount
        original_terms_snapshot = dict(contract.terms_snapshot)
        contract.status = "DEFAULTED"
        contract.defaulted_at = contract.contract_date
        db_session.add(contract)
        db_session.commit()

        _persist_configuration(db_session, ctx["company_id"], cure_enabled=True)
        svc = build_contract_service(db_session)

        before_audit_count = len(
            db_session.execute(
                select(InstallmentAuditLog).where(
                    InstallmentAuditLog.entity_id == contract.id
                )
            )
            .scalars()
            .all()
        )

        updated = svc.cure(ctx["company_id"], contract.id, "Goodwill", actor_id=None)

        assert updated.status == "ACTIVE"
        # Original terms untouched.
        assert updated.principal_amount == original_principal
        assert updated.markup_amount == original_markup
        assert dict(updated.terms_snapshot) == original_terms_snapshot

        # A new CURED audit row was added — nothing removed.
        audit_rows = (
            db_session.execute(
                select(InstallmentAuditLog).where(
                    InstallmentAuditLog.entity_id == contract.id
                )
            )
            .scalars()
            .all()
        )
        assert len(audit_rows) == before_audit_count + 1
        assert any(row.action == "CURED" for row in audit_rows)

        # The late charge and its Accounting ARTransaction still exist,
        # untouched — cure() never touches Accounting.
        refreshed_charge = db_session.get(type(late_charge), late_charge.id)
        assert refreshed_charge is not None
        assert refreshed_charge.waived_at is None
        ar_transaction = (
            db_session.execute(
                select(ARTransaction).where(
                    ARTransaction.id == late_charge.accounting_ar_transaction_id
                )
            )
            .scalars()
            .one()
        )
        assert ar_transaction.outstanding_amount == Decimal("25.00")

    def test_cure_never_creates_a_new_contract(self, db_session) -> None:
        ctx = _default_contract(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        _persist_configuration(db_session, ctx["company_id"], cure_enabled=True)
        svc = build_contract_service(db_session)

        updated = svc.cure(
            ctx["company_id"], ctx["contract"].id, "Goodwill", actor_id=None
        )
        assert updated.id == ctx["contract"].id

        all_contracts = (
            db_session.query(InstallmentContract)
            .filter_by(company_id=ctx["company_id"])
            .all()
        )
        assert len(all_contracts) == 1
