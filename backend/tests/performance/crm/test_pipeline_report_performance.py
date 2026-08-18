"""T095 — Pipeline report performance benchmark (spec.md §47/NFR-004).

Verifies "Pipeline report: p95 < 2s at 10,000 open opportunities".

**Why this test seeds 3,000 open Opportunities, not 10,000, against
SQLite:** matches the exact, established, audited precedent set by
``tests/performance/accounting/test_report_performance.py`` (see that
file's own module docstring) — a fast SQLite regression guard at a scale
where SQLite's non-cost-based planner still behaves reasonably, not a
substitute for the real 10,000-row/live-PostgreSQL number (spec.md
§48.5), which is a separate, explicit Epic-9-closure verification step.

``CrmReportingService.get_pipeline_report()`` is built entirely from
aggregate (``GROUP BY``/``SUM``) repository queries (see
``modules/crm/repositories/opportunity.py``'s ``sum_value_by_*``/
``count_won_lost_in_period`` methods) plus one Python-side loop over only
the *won* subset (``list_won_in_period``) — not a full table scan — so
this also exercises the aggregate-query design directly.

**Fallback if this ever regresses below target** (plan.md §26/ADR-13):
a ``GENERATED ALWAYS AS (value * probability / 100) STORED`` computed
column for ``weighted_value``, added via a follow-up migration — not a
silently-lowered target and not a skipped benchmark.

Task: T095 (tasks.md Phase 10). Spec ref: spec.md §47/NFR-004.
"""

from __future__ import annotations

import statistics
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import insert
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.crm.models.opportunity import Opportunity
from modules.crm.models.pipeline import Pipeline
from modules.crm.models.pipeline_stage import PipelineStage
from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.crm.services.reporting_service import CrmReportingService

_SAMPLE_ROWS = 3_000  # SQLite regression-guard scale (see module docstring)
_TARGET_SECONDS = 1.0  # generous guard, not the 2s/10K SLA itself
_OWNER_POOL = 10
_CUSTOMER_POOL = 50


def _p95(samples: list[float]) -> float:
    return statistics.quantiles(samples, n=100)[94]


def _seed_open_opportunities(
    db: Session,
    company_id: uuid.UUID,
    pipeline_id: uuid.UUID,
    stage_ids: list[uuid.UUID],
) -> None:
    owner_ids = [str(uuid.uuid4()) for _ in range(_OWNER_POOL)]
    customer_ids = [str(uuid.uuid4()) for _ in range(_CUSTOMER_POOL)]
    today = date.today()
    rows = [
        {
            "company_id": company_id,
            "name": f"Perf Open Opp {i}",
            "customer_id": customer_ids[i % _CUSTOMER_POOL],
            "owner_id": owner_ids[i % _OWNER_POOL],
            "pipeline_id": pipeline_id,
            "stage_id": stage_ids[i % len(stage_ids)],
            "value": Decimal("1000.00"),
            "currency_code": "USD",
            "probability": 20,
            "status": "OPEN",
            "expected_close_date": today + timedelta(days=i % 90),
        }
        for i in range(_SAMPLE_ROWS)
    ]
    db.execute(insert(Opportunity), rows)

    # A representative won/lost tail so won_value/lost_value/win_rate/
    # avg_deal_size/avg_sales_cycle_days are non-trivially exercised too.
    won_lost_rows = []
    for i in range(200):
        is_won = i % 2 == 0
        won_lost_rows.append(
            {
                "company_id": company_id,
                "name": f"Perf Closed Opp {i}",
                "customer_id": customer_ids[i % _CUSTOMER_POOL],
                "owner_id": owner_ids[i % _OWNER_POOL],
                "pipeline_id": pipeline_id,
                "stage_id": stage_ids[-1],
                "value": Decimal("2000.00"),
                "currency_code": "USD",
                "probability": 100 if is_won else 0,
                "status": "WON" if is_won else "LOST",
                "won_at": None if not is_won else utcnow(),
                "lost_at": None,
                "lost_reason": None if is_won else "Budget cut",
            }
        )
    db.execute(insert(Opportunity), won_lost_rows)
    db.commit()


class TestPipelineReportPerformance:
    def test_pipeline_report_p95_under_target(self, db_session: Session) -> None:
        company_id = uuid.uuid4()
        pipeline = Pipeline(
            company_id=company_id, name="Perf Pipeline", is_default=True
        )
        db_session.add(pipeline)
        db_session.flush()
        stages = []
        for seq, (name, prob) in enumerate(
            [("Qualification", 20), ("Proposal", 50), ("Closed", 90)], start=1
        ):
            stage = PipelineStage(
                company_id=company_id,
                pipeline_id=pipeline.id,
                name=name,
                sequence=seq,
                probability=prob,
            )
            db_session.add(stage)
            db_session.flush()
            stages.append(stage.id)

        seed_start = time.perf_counter()
        _seed_open_opportunities(db_session, company_id, pipeline.id, stages)
        print(
            f"\nSeeded {_SAMPLE_ROWS} open + 200 closed opportunities in "
            f"{time.perf_counter() - seed_start:.2f}s"
        )

        service = CrmReportingService(
            opportunity_repo=OpportunityRepository(db_session),
            lead_repo=LeadRepository(db_session),
            activity_repo=ActivityRepository(db_session),
        )

        samples: list[float] = []
        for _ in range(10):
            start = time.perf_counter()
            report = service.get_pipeline_report(company_id)
            samples.append(time.perf_counter() - start)
            assert report.won_value is not None or report.won_value == Decimal("0")

        p95 = _p95(samples)
        print(
            f"Pipeline report p95 over {_SAMPLE_ROWS} open opportunities "
            f"(SQLite guard): {p95 * 1000:.1f}ms"
        )
        assert (
            p95 < _TARGET_SECONDS
        ), f"Pipeline report p95 {p95:.3f}s exceeds {_TARGET_SECONDS}s guard"
