"""Concurrency test: optimistic-lock race handling in Lead conversion
(tasks.md T039).

**Scope note**: tasks.md's original acceptance for T039 calls for two
genuinely simultaneous DB sessions "against real Postgres, not SQLite,
since SQLite's locking semantics differ" — no Docker/Postgres engine is
available in this environment (consistent with every earlier phase's
verification notes), so true simultaneous-transaction lock-contention
behavior is deferred to Epic 9's comprehensive live-Postgres pass.

What *is* tested here, deterministically and dialect-agnostically: the
race-detection LOGIC itself in
``LeadConversionService._apply_conversion_with_optimistic_lock()`` — the
``UPDATE ... WHERE version = :expected_version`` / rowcount-check /
idempotent-recovery branch is pure SQL-level behavior identical on SQLite
and Postgres; only genuine simultaneous blocking differs between the two.
A "loser" request is simulated by constructing a transient ``Lead`` object
holding the pre-conversion version (exactly what a concurrent request that
read the Lead before the winner committed would hold in memory) and
feeding it directly into that method after a real winning conversion has
already committed.

Task: T039 (tasks.md Phase 4).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException
from modules.crm.models.lead import Lead
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.sales.repositories.customer import CustomerRepository
from tests.integration.repositories.crm.test_lead_conversion import (
    _build_conversion_service,
    _qualified_lead,
)


class TestOptimisticLockRaceDetection:
    def test_loser_receives_winners_result_idempotently(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        service = _build_conversion_service(db_session)
        lead = _qualified_lead(db_session, company_id)
        pre_conversion_version = lead.version

        winner_result = service.convert(lead.id, company_id, actor_id=uuid4())

        # The "loser" is a concurrent request that read the Lead before the
        # winner's commit — it still holds the pre-conversion version.
        stale_lead = Lead(
            id=lead.id, company_id=company_id, version=pre_conversion_version
        )
        loser_result = service._apply_conversion_with_optimistic_lock(
            stale_lead, company_id, uuid4(), uuid4()
        )

        assert loser_result is not None
        assert loser_result.customer_id == winner_result.customer_id
        assert loser_result.opportunity_id == winner_result.opportunity_id
        assert loser_result.customer_matched is True

        # The loser's attempted write never actually happened.
        _, customer_total = CustomerRepository(db_session).list(company_id=company_id)
        _, opp_total = OpportunityRepository(db_session).list(company_id=company_id)
        assert customer_total == 1
        assert opp_total == 1

    def test_genuine_conflict_raises_when_lead_still_qualified(
        self, db_session: Session
    ) -> None:
        """A rowcount=0 update whose fresh re-read shows the Lead is still
        QUALIFIED (not CONVERTED by a concurrent winner) is a genuinely
        unexplained conflict, not a race to recover from."""
        company_id = uuid4()
        service = _build_conversion_service(db_session)
        lead = _qualified_lead(db_session, company_id)
        stale_version = lead.version

        # Bump the version without changing status — simulates some other
        # unrelated update touching this row's optimistic-lock counter.
        db_session.execute(
            update(Lead).where(Lead.id == lead.id).values(version=Lead.version + 1)
        )
        db_session.commit()

        stale_lead = Lead(id=lead.id, company_id=company_id, version=stale_version)
        with pytest.raises(ConflictException):
            service._apply_conversion_with_optimistic_lock(
                stale_lead, company_id, uuid4(), uuid4()
            )

        fresh_lead = LeadRepository(db_session).get_by_id_or_none(
            id=lead.id, company_id=company_id
        )
        assert fresh_lead is not None
        assert fresh_lead.status == "QUALIFIED"
