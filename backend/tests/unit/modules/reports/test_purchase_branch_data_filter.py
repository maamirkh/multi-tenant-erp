"""T083 — Branch-filter-is-not-authorization test (Scenario G): an
ordinary filtered result, explicitly documenting no authorization
narrowing occurs (FR-RPT-160/161/163 — branch is a plain data filter,
never an access-control boundary, since no per-user branch ACL exists
anywhere in the repository, spec §25)."""

from __future__ import annotations

from uuid import uuid4

from modules.reports.schemas.purchase import (
    OpenCommitmentsFilter,
    PendingDeliveriesFilter,
    PurchaseSummaryFilter,
)


def test_open_commitments_accepts_branch_id_as_plain_filter() -> None:
    branch_id = uuid4()
    filters = OpenCommitmentsFilter(branch_id=branch_id)
    assert filters.branch_id == branch_id


def test_pending_deliveries_accepts_branch_id_as_plain_filter() -> None:
    branch_id = uuid4()
    filters = PendingDeliveriesFilter(branch_id=branch_id)
    assert filters.branch_id == branch_id


def test_purchase_summary_has_no_branch_filter_field() -> None:
    """Only OpenCommitmentsFilter/PendingDeliveriesFilter carry
    branch_id (FR-RPT-062) — purchase.summary does not."""
    assert "branch_id" not in PurchaseSummaryFilter.model_fields
