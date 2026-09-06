"""Unit test: Opportunity.weighted_value is computed at read time, never
stored, never accepted as input (BR-010).

The actual `value * probability / 100` computation is tested at the
schema/service layer in Phase 5 (plan.md §6.5) — this test only proves the
ORM model itself carries no such column, so a future change can't silently
reintroduce a denormalized, driftable field.

Task: T022 (tasks.md Phase 2).
"""

from __future__ import annotations

from modules.crm.models.opportunity import Opportunity


def test_opportunity_model_has_no_weighted_value_column() -> None:
    column_names = {column.name for column in Opportunity.__table__.columns}
    assert "weighted_value" not in column_names


def test_opportunity_model_has_no_weighted_value_attribute() -> None:
    assert not hasattr(Opportunity, "weighted_value")
