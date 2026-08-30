"""[Epic 10, Phase 10, T177/T178/T179] Service tests —
InstallmentReschedulingService.reschedule().

T177: reschedule creates a new schedule version; the prior version's
lines and any linked InstallmentAllocationReference rows remain valid
pointers into history (BR-INST-017).

T178 [CORRECTED — Correction 6: removed incorrect [P] marker, same
implied file as T177]: maker-checker — requester != approver enforced
identically to contract approval — NOT parallel-safe with T177 (same
file).

T179 [CORRECTED — Correction 6: removed incorrect [P] marker, same
implied file as T177/T178]: rejects any attempt to change principal/
markup/installment_count (restructuring), only due-date changes
accepted (FR-INST-202) — NOT parallel-safe with T177/T178.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from modules.installments.exceptions import (
    InstallmentRescheduleRestructuringNotAllowedError,
    InstallmentRescheduleSelfApprovalNotAllowedError,
)
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.schedule import InstallmentScheduleVersion
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.rescheduling_service import RescheduleTerms
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
    build_collection_service,
    build_rescheduling_service,
)


class TestRescheduleCreatesNewVersion:
    def test_reschedule_supersedes_prior_version_and_preserves_history(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        # Pay the first line so a real InstallmentAllocationReference row
        # exists, pointing at v1's own line — this must remain a valid
        # pointer after rescheduling (BR-INST-017), never rewritten.
        collection_service = build_collection_service(db_session)
        collection_service.record_collection(
            ctx["company_id"],
            ctx["contract"].id,
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            idempotency_key=str(uuid.uuid4()),
            actor_id=None,
            bank_account_id=ctx["bank_account"].id,
        )
        original_version_id = ctx["schedule_version"].id
        original_line_ids = {line.id for line in ctx["schedule_lines"]}
        refs_before = InstallmentAllocationReferenceRepository(
            db_session
        ).list_for_contract(ctx["company_id"], ctx["contract"].id)
        assert len(refs_before) == 1
        paid_ref_id = refs_before[0].id
        paid_line_id = refs_before[0].schedule_line_id

        svc = build_rescheduling_service(db_session)
        requester_id = uuid.uuid4()
        approver_id = uuid.uuid4()
        new_first_due = date.today() + timedelta(days=45)

        updated = svc.reschedule(
            ctx["company_id"],
            ctx["contract"].id,
            RescheduleTerms(first_due_date=new_first_due),
            "Customer requested a later due date",
            idempotency_key=str(uuid.uuid4()),
            actor_id=approver_id,
            requested_by=requester_id,
        )

        assert updated.active_schedule_version_id != original_version_id

        # Prior version — superseded, its lines untouched.
        prior_version = (
            db_session.query(InstallmentScheduleVersion)
            .filter_by(id=original_version_id)
            .one()
        )
        assert prior_version.status == "SUPERSEDED"
        schedule_repo = InstallmentScheduleRepository(db_session)
        prior_lines = schedule_repo.get_lines(ctx["company_id"], original_version_id)
        assert {line.id for line in prior_lines} == original_line_ids

        # The already-paid allocation reference still points at the SAME
        # (now-superseded) line id — never rewritten to point at the new
        # version.
        refs_after = InstallmentAllocationReferenceRepository(
            db_session
        ).list_for_contract(ctx["company_id"], ctx["contract"].id)
        matching = [r for r in refs_after if r.id == paid_ref_id]
        assert len(matching) == 1
        assert matching[0].schedule_line_id == paid_line_id

        # New version — only the remaining (unpaid) obligation, over the
        # new due date.
        new_version = schedule_repo.get_active_version(
            ctx["company_id"], ctx["contract"].id
        )
        assert new_version.id == updated.active_schedule_version_id
        assert new_version.version_number == prior_version.version_number + 1
        new_lines = schedule_repo.get_lines(ctx["company_id"], new_version.id)
        assert len(new_lines) == 1
        assert new_lines[0].due_date == new_first_due
        assert new_lines[0].scheduled_amount == Decimal("100.00")

    def test_reschedule_commits_durably(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        svc = build_rescheduling_service(db_session)
        new_first_due = date.today() + timedelta(days=60)

        svc.reschedule(
            ctx["company_id"],
            ctx["contract"].id,
            RescheduleTerms(first_due_date=new_first_due),
            "reason",
            idempotency_key=str(uuid.uuid4()),
            actor_id=uuid.uuid4(),
            requested_by=uuid.uuid4(),
        )

        db_session.expire_all()
        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.active_schedule_version_id is not None
        schedule_repo = InstallmentScheduleRepository(db_session)
        active_version = schedule_repo.get_active_version(
            ctx["company_id"], ctx["contract"].id
        )
        assert active_version.id == refreshed.active_schedule_version_id
        lines = schedule_repo.get_lines(ctx["company_id"], active_version.id)
        assert lines[0].due_date == new_first_due


class TestRescheduleMakerChecker:
    def test_reschedule_rejects_same_requester_and_approver(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        svc = build_rescheduling_service(db_session)
        same_actor = uuid.uuid4()

        with pytest.raises(InstallmentRescheduleSelfApprovalNotAllowedError):
            svc.reschedule(
                ctx["company_id"],
                ctx["contract"].id,
                RescheduleTerms(first_due_date=date.today() + timedelta(days=30)),
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=same_actor,
                requested_by=same_actor,
            )

        db_session.rollback()
        refreshed = (
            db_session.query(InstallmentContract).filter_by(id=ctx["contract"].id).one()
        )
        assert refreshed.active_schedule_version_id == ctx["schedule_version"].id

    def test_reschedule_succeeds_with_distinct_requester_and_approver(
        self, db_session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        svc = build_rescheduling_service(db_session)

        updated = svc.reschedule(
            ctx["company_id"],
            ctx["contract"].id,
            RescheduleTerms(first_due_date=date.today() + timedelta(days=30)),
            "reason",
            idempotency_key=str(uuid.uuid4()),
            actor_id=uuid.uuid4(),
            requested_by=uuid.uuid4(),
        )
        assert updated.active_schedule_version_id != ctx["schedule_version"].id


class TestRescheduleRejectsRestructuring:
    def test_reschedule_rejects_principal_change(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        svc = build_rescheduling_service(db_session)

        with pytest.raises(InstallmentRescheduleRestructuringNotAllowedError) as exc:
            svc.reschedule(
                ctx["company_id"],
                ctx["contract"].id,
                RescheduleTerms(
                    first_due_date=date.today() + timedelta(days=30),
                    principal_amount=Decimal("999999.00"),
                ),
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=uuid.uuid4(),
                requested_by=uuid.uuid4(),
            )
        assert "principal_amount" in exc.value.details["violations"]

    def test_reschedule_rejects_markup_change(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        svc = build_rescheduling_service(db_session)

        with pytest.raises(InstallmentRescheduleRestructuringNotAllowedError) as exc:
            svc.reschedule(
                ctx["company_id"],
                ctx["contract"].id,
                RescheduleTerms(
                    first_due_date=date.today() + timedelta(days=30),
                    markup_amount=Decimal("50.00"),
                ),
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=uuid.uuid4(),
                requested_by=uuid.uuid4(),
            )
        assert "markup_amount" in exc.value.details["violations"]

    def test_reschedule_rejects_installment_count_change(self, db_session) -> None:
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=2, installment_amount=Decimal("100.00")
        )
        svc = build_rescheduling_service(db_session)

        with pytest.raises(InstallmentRescheduleRestructuringNotAllowedError) as exc:
            svc.reschedule(
                ctx["company_id"],
                ctx["contract"].id,
                RescheduleTerms(
                    first_due_date=date.today() + timedelta(days=30),
                    installment_count=5,
                ),
                "reason",
                idempotency_key=str(uuid.uuid4()),
                actor_id=uuid.uuid4(),
                requested_by=uuid.uuid4(),
            )
        assert "installment_count" in exc.value.details["violations"]

    def test_reschedule_accepts_due_date_only_change(self, db_session) -> None:
        """Positive control: a due-date-only change (matching contract-
        level principal/markup/count exactly) is NOT restructuring."""
        ctx = build_active_contract_with_schedule(
            db_session, installment_count=1, installment_amount=Decimal("500.00")
        )
        svc = build_rescheduling_service(db_session)

        updated = svc.reschedule(
            ctx["company_id"],
            ctx["contract"].id,
            RescheduleTerms(
                first_due_date=date.today() + timedelta(days=30),
                principal_amount=ctx["contract"].principal_amount,
                markup_amount=ctx["contract"].markup_amount,
                installment_count=ctx["contract"].installment_count,
            ),
            "reason",
            idempotency_key=str(uuid.uuid4()),
            actor_id=uuid.uuid4(),
            requested_by=uuid.uuid4(),
        )
        assert updated.active_schedule_version_id != ctx["schedule_version"].id
