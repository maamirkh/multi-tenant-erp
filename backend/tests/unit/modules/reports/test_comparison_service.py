"""T025 — ``comparison_service.compute_comparison()``'s three branches
(spec §23, FR-RPT-141)."""

from __future__ import annotations

from decimal import Decimal

from modules.reports.schemas.common import Comparability
from modules.reports.services.comparison_service import compute_comparison


def test_normal_comparison_computes_absolute_and_percentage_change() -> None:
    result = compute_comparison(current=Decimal("150"), prior=Decimal("100"))
    assert result.absolute_change == "50"
    assert result.percentage_change == "50.00"
    assert result.comparability is Comparability.FULL


def test_zero_prior_nonzero_current_is_not_comparable() -> None:
    result = compute_comparison(current=Decimal("10"), prior=Decimal("0"))
    assert result.percentage_change is None
    assert result.comparability is Comparability.NOT_COMPARABLE


def test_zero_prior_and_zero_current_is_zero_percent() -> None:
    result = compute_comparison(current=Decimal("0"), prior=Decimal("0"))
    assert result.absolute_change == "0"
    assert result.percentage_change == "0"
    assert result.comparability is Comparability.FULL


def test_partial_current_period_is_labeled() -> None:
    result = compute_comparison(
        current=Decimal("40"),
        prior=Decimal("100"),
        is_current_period_partial=True,
    )
    assert result.comparability is Comparability.PARTIAL_CURRENT_PERIOD


def test_not_comparable_is_never_downgraded_to_partial() -> None:
    result = compute_comparison(
        current=Decimal("10"),
        prior=Decimal("0"),
        is_current_period_partial=True,
    )
    assert result.comparability is Comparability.NOT_COMPARABLE
