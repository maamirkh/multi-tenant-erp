"""T073 — Structural test (FR-RPT-162): a ``branch_id`` filter param is
rejected by ``extra="forbid"`` at the schema layer for every Sales
filter schema (Sales carries no ``branch_id`` column on any model)."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from modules.reports.schemas.sales import (
    QuotationPipelineFilter,
    SalesByCustomerFilter,
    SalesByProductFilter,
    SalesKpiFilter,
    SalesReturnsFilter,
    SalesSummaryFilter,
    SalesTrendFilter,
    TopCustomersFilter,
)

ALL_SALES_FILTERS = (
    SalesSummaryFilter,
    SalesByCustomerFilter,
    SalesByProductFilter,
    TopCustomersFilter,
    SalesTrendFilter,
    QuotationPipelineFilter,
    SalesReturnsFilter,
    SalesKpiFilter,
)


@pytest.mark.parametrize("filter_cls", ALL_SALES_FILTERS)
def test_branch_id_is_rejected(filter_cls: type) -> None:
    with pytest.raises(ValidationError):
        filter_cls(branch_id="00000000-0000-0000-0000-000000000000")


def test_date_range_filters_still_accept_their_own_fields() -> None:
    # Sanity check the rejection above isn't masking an overly-strict schema.
    SalesSummaryFilter(date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
