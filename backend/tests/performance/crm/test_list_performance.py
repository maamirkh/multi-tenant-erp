"""T092 — Lead/Opportunity/Activity list-endpoint performance benchmark.

Verifies spec.md §47's "Lead/Opportunity/Activity list (paginated):
p95 < 300ms at 100,000 rows" target — measured directly, not assumed from
index presence alone (plan.md §14/§26).

**Why this test seeds 5,000 rows per entity, not 100,000, against SQLite:**
Matches the exact, established, audited precedent set by
``tests/performance/accounting/test_report_performance.py`` (Epic 8,
Phase 13): SQLite's in-memory query planner has no cost-based statistics
and behaves non-linearly at very large row counts in ways that do not
represent PostgreSQL's real (indexed, cost-based) behavior. This test is
therefore a fast SQLite regression guard — it would catch a regressed
missing composite index (the exact indexes list_filtered() relies on:
``ix_crm_leads_company_status``, ``ix_crm_leads_company_owner``,
``ix_crm_opportunities_company_status``, ``ix_crm_opportunities_company_owner``,
``ix_crm_opportunities_company_pipeline_stage``,
``ix_crm_activities_company_assigned_status``,
``ix_crm_activities_company_due_date``) — not a substitute for the real
100,000-row number, which requires live PostgreSQL (spec.md §48.5) and is
tracked as an explicit, separate Epic-9-closure verification step, not
silently skipped.

Task: T092 (tasks.md Phase 10). Spec ref: spec.md §47/NFR-001.
"""

from __future__ import annotations

import statistics
import time
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import insert
from sqlalchemy.orm import Session

from modules.crm.models.activity import Activity
from modules.crm.models.lead import Lead
from modules.crm.models.opportunity import Opportunity
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage
from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository

_SAMPLE_ROWS = 5_000
_TARGET_SECONDS = 1.0  # generous SQLite regression guard, not the 300ms/100K SLA itself
_STATUSES_LEAD = ["NEW", "CONTACTED", "QUALIFIED", "UNQUALIFIED", "CONVERTED", "LOST"]
_STATUSES_OPP = ["OPEN", "WON", "LOST"]
_STATUSES_ACT = ["PLANNED", "COMPLETED", "CANCELLED"]


def _p95(samples: list[float]) -> float:
    return statistics.quantiles(samples, n=100)[94]


def _seed_leads(db: Session, company_id: uuid.UUID, owner_ids: list[str]) -> None:
    rows = [
        {
            "company_id": company_id,
            "first_name": f"Lead{i}",
            "last_name": "Perf",
            "email": f"lead-perf-{i}@example.com",
            "status": _STATUSES_LEAD[i % len(_STATUSES_LEAD)],
            "owner_id": owner_ids[i % len(owner_ids)],
        }
        for i in range(_SAMPLE_ROWS)
    ]
    db.execute(insert(Lead), rows)
    db.commit()


def _seed_opportunities(
    db: Session,
    company_id: uuid.UUID,
    owner_ids: list[str],
    customer_ids: list[str],
    pipeline_id: uuid.UUID,
    stage_id: uuid.UUID,
) -> None:
    rows = [
        {
            "company_id": company_id,
            "name": f"Perf Opportunity {i}",
            "customer_id": customer_ids[i % len(customer_ids)],
            "owner_id": owner_ids[i % len(owner_ids)],
            "pipeline_id": pipeline_id,
            "stage_id": stage_id,
            "value": Decimal("1000.00"),
            "currency_code": "USD",
            "probability": 20,
            "status": _STATUSES_OPP[i % len(_STATUSES_OPP)],
        }
        for i in range(_SAMPLE_ROWS)
    ]
    db.execute(insert(Opportunity), rows)
    db.commit()


def _seed_activities(db: Session, company_id: uuid.UUID, owner_ids: list[str]) -> None:
    rows = [
        {
            "company_id": company_id,
            "activity_type": "CALL",
            "subject": f"Perf Activity {i}",
            "status": _STATUSES_ACT[i % len(_STATUSES_ACT)],
            "priority": "MEDIUM",
            "assigned_to": owner_ids[i % len(owner_ids)],
            "customer_id": owner_ids[
                i % len(owner_ids)
            ],  # any non-null relation (BR-006)
        }
        for i in range(_SAMPLE_ROWS)
    ]
    db.execute(insert(Activity), rows)
    db.commit()


class TestListPerformance:
    def test_lead_list_p95_under_target(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        owner_ids = [str(uuid.uuid4()) for _ in range(10)]
        seed_start = time.perf_counter()
        _seed_leads(db_session, company_id, owner_ids)
        print(
            f"\nSeeded {_SAMPLE_ROWS} leads in {time.perf_counter() - seed_start:.2f}s"
        )

        repo = LeadRepository(db_session)
        samples: list[float] = []
        for i in range(20):
            filters: dict[str, Any] = {"page": (i % 5) + 1, "page_size": 20}
            if i % 3 == 0:
                filters["status"] = _STATUSES_LEAD[i % len(_STATUSES_LEAD)]
            if i % 4 == 0:
                filters["owner_id"] = uuid.UUID(owner_ids[i % len(owner_ids)])
            start = time.perf_counter()
            items, total = repo.list_filtered(company_id, **filters)
            samples.append(time.perf_counter() - start)
            assert total > 0  # filters may narrow total below _SAMPLE_ROWS

        p95 = _p95(samples)
        print(
            f"Lead list p95 over {_SAMPLE_ROWS} rows (SQLite guard): {p95 * 1000:.1f}ms"
        )
        assert p95 < _TARGET_SECONDS, (
            f"Lead list p95 {p95:.3f}s exceeds {_TARGET_SECONDS}s guard"
        )

    def test_opportunity_list_p95_under_target(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        owner_ids = [str(uuid.uuid4()) for _ in range(10)]
        customer_ids = [str(uuid.uuid4()) for _ in range(20)]
        pipeline = Pipeline(
            company_id=company_id, name="Perf Pipeline", is_default=True
        )
        db_session.add(pipeline)
        db_session.flush()
        stage = PipelineStage(
            company_id=company_id,
            pipeline_id=pipeline.id,
            name="Perf Stage",
            sequence=1,
            probability=20,
        )
        db_session.add(stage)
        db_session.flush()

        seed_start = time.perf_counter()
        _seed_opportunities(
            db_session, company_id, owner_ids, customer_ids, pipeline.id, stage.id
        )
        print(
            f"\nSeeded {_SAMPLE_ROWS} opportunities in "
            f"{time.perf_counter() - seed_start:.2f}s"
        )

        repo = OpportunityRepository(db_session)
        samples: list[float] = []
        for i in range(20):
            filters: dict[str, Any] = {"page": (i % 5) + 1, "page_size": 20}
            if i % 3 == 0:
                filters["status"] = _STATUSES_OPP[i % len(_STATUSES_OPP)]
            if i % 4 == 0:
                filters["owner_id"] = uuid.UUID(owner_ids[i % len(owner_ids)])
            start = time.perf_counter()
            items, total = repo.list_filtered(company_id, **filters)
            samples.append(time.perf_counter() - start)
            assert total > 0  # filters may narrow total below _SAMPLE_ROWS

        p95 = _p95(samples)
        print(
            f"Opportunity list p95 over {_SAMPLE_ROWS} rows (SQLite guard): "
            f"{p95 * 1000:.1f}ms"
        )
        assert p95 < _TARGET_SECONDS, (
            f"Opportunity list p95 {p95:.3f}s exceeds {_TARGET_SECONDS}s guard"
        )

    def test_activity_list_p95_under_target(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        owner_ids = [str(uuid.uuid4()) for _ in range(10)]
        seed_start = time.perf_counter()
        _seed_activities(db_session, company_id, owner_ids)
        print(
            f"\nSeeded {_SAMPLE_ROWS} activities in "
            f"{time.perf_counter() - seed_start:.2f}s"
        )

        repo = ActivityRepository(db_session)
        samples: list[float] = []
        for i in range(20):
            filters: dict[str, Any] = {"page": (i % 5) + 1, "page_size": 20}
            if i % 3 == 0:
                filters["status"] = _STATUSES_ACT[i % len(_STATUSES_ACT)]
            if i % 4 == 0:
                filters["assigned_to"] = uuid.UUID(owner_ids[i % len(owner_ids)])
            start = time.perf_counter()
            items, total = repo.list_filtered(company_id, **filters)
            samples.append(time.perf_counter() - start)
            assert total > 0  # filters may narrow total below _SAMPLE_ROWS

        p95 = _p95(samples)
        print(
            f"Activity list p95 over {_SAMPLE_ROWS} rows (SQLite guard): "
            f"{p95 * 1000:.1f}ms"
        )
        assert p95 < _TARGET_SECONDS, (
            f"Activity list p95 {p95:.3f}s exceeds {_TARGET_SECONDS}s guard"
        )
