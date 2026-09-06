"""[Epic 10, Phase 8, T147] Unit test — due-state derivation for all 5
derivable states (FR-INST-120) + the 2 controlled-workflow states
(WAIVED, VOIDED).

Pure function, zero I/O — proves BR-INST-019's determinism (same inputs
always produce the same state) is structurally guaranteed, not merely
observed.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from modules.installments.services.due_state import DueStateCalculator

_DUE = date(2026, 6, 1)
_SCHEDULED = Decimal("100.00")


def _calc(
    *,
    paid_amount: Decimal = Decimal("0"),
    business_date: date,
    grace_period_days: int = 0,
    waived_at: datetime | None = None,
    voided_at: datetime | None = None,
):
    return DueStateCalculator.calculate(
        scheduled_amount=_SCHEDULED,
        paid_amount=paid_amount,
        due_date=_DUE,
        business_date=business_date,
        grace_period_days=grace_period_days,
        waived_at=waived_at,
        voided_at=voided_at,
    )


def test_upcoming_before_due_date_no_payment() -> None:
    result = _calc(business_date=_DUE - timedelta(days=5))
    assert result.state == "UPCOMING"
    assert result.outstanding_amount == _SCHEDULED


def test_due_on_due_date_no_payment() -> None:
    result = _calc(business_date=_DUE)
    assert result.state == "DUE"


def test_due_within_grace_period_no_payment() -> None:
    result = _calc(business_date=_DUE + timedelta(days=3), grace_period_days=5)
    assert result.state == "DUE"


def test_overdue_past_grace_period_no_payment() -> None:
    result = _calc(business_date=_DUE + timedelta(days=6), grace_period_days=5)
    assert result.state == "OVERDUE"
    assert result.days_overdue == 6


def test_overdue_with_zero_grace_the_day_after_due_date() -> None:
    result = _calc(business_date=_DUE + timedelta(days=1), grace_period_days=0)
    assert result.state == "OVERDUE"


def test_paid_when_outstanding_is_exactly_zero() -> None:
    result = _calc(paid_amount=_SCHEDULED, business_date=_DUE + timedelta(days=90))
    assert result.state == "PAID"
    assert result.outstanding_amount == Decimal("0")
    assert result.days_overdue == 0


def test_paid_when_overpaid() -> None:
    result = _calc(
        paid_amount=Decimal("150.00"), business_date=_DUE + timedelta(days=1)
    )
    assert result.state == "PAID"


def test_partially_paid_takes_priority_over_overdue() -> None:
    # A partial payment recorded, then the line falls past grace without
    # the remainder being paid — PARTIALLY_PAID, not OVERDUE (FR-INST-120
    # lists them as distinct buckets; Scenario E's "without payment"
    # phrasing implies OVERDUE presumes zero payment).
    result = _calc(
        paid_amount=Decimal("40.00"), business_date=_DUE + timedelta(days=60)
    )
    assert result.state == "PARTIALLY_PAID"
    assert result.outstanding_amount == Decimal("60.00")


def test_partially_paid_before_due_date() -> None:
    result = _calc(paid_amount=Decimal("40.00"), business_date=_DUE - timedelta(days=2))
    assert result.state == "PARTIALLY_PAID"


def test_waived_overrides_everything_else() -> None:
    result = _calc(
        business_date=_DUE + timedelta(days=200),
        waived_at=datetime(2026, 6, 5, tzinfo=None),
    )
    assert result.state == "WAIVED"


def test_voided_takes_precedence_over_waived() -> None:
    result = _calc(
        business_date=_DUE + timedelta(days=200),
        waived_at=datetime(2026, 6, 5, tzinfo=None),
        voided_at=datetime(2026, 6, 6, tzinfo=None),
    )
    assert result.state == "VOIDED"


def test_determinism_same_inputs_always_produce_same_state() -> None:
    first = _calc(business_date=_DUE + timedelta(days=10), grace_period_days=5)
    second = _calc(business_date=_DUE + timedelta(days=10), grace_period_days=5)
    assert first == second
