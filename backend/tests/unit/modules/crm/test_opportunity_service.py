"""Unit tests: OpportunityService lifecycle transitions + weighted_value
calculation — mocked repository/session, no DB (plan.md §27.1/§48.1).

Covers:
  - weighted_value calculation table (OpportunityRead computed_field, BR-010).
  - win()/lose() valid (OPEN -> WON/LOST) and invalid (already terminal)
    transitions, via the row-level ``UPDATE ... WHERE status='OPEN'`` guard.
  - change_stage() INV-004 (stage must belong to the same pipeline) and
    inactive-stage rejection.
  - update() rejected once WON/LOST (BR-003).

Task: T048 (tasks.md Phase 5).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from core.exceptions.base import ValidationException
from modules.crm.exceptions import InvalidOpportunityTransitionError
from modules.crm.models.opportunity import Opportunity
from modules.crm.schemas.opportunity import OpportunityRead, OpportunityUpdate
from modules.crm.services.opportunity_service import OpportunityService


def _service() -> OpportunityService:
    return OpportunityService(
        db=MagicMock(),
        repo=MagicMock(),
        stage_repo=MagicMock(),
        customer_repo=MagicMock(),
        member_repo=MagicMock(),
        quotation_repo=MagicMock(),
        audit_service=MagicMock(),
    )


def _opportunity(status: str = "OPEN", **overrides: object) -> Opportunity:
    opp = Opportunity(
        company_id=uuid4(),
        name="Test Deal",
        customer_id=str(uuid4()),
        owner_id=str(uuid4()),
        pipeline_id=uuid4(),
        stage_id=uuid4(),
        currency_code="USD",
        probability=20,
        status=status,
    )
    for key, value in overrides.items():
        setattr(opp, key, value)
    return opp


def _read(value: Decimal, probability: int) -> OpportunityRead:
    now = datetime.now(UTC)
    return OpportunityRead(
        id=uuid4(),
        company_id=uuid4(),
        name="Test",
        customer_id=uuid4(),
        owner_id=uuid4(),
        pipeline_id=uuid4(),
        stage_id=uuid4(),
        value=value,
        currency_code="USD",
        probability=probability,
        expected_close_date=None,
        source_lead_id=None,
        description=None,
        status="OPEN",
        lost_reason=None,
        won_at=None,
        lost_at=None,
        quotation_id=None,
        created_at=now,
        updated_at=now,
    )


class TestWeightedValueCalculation:
    @pytest.mark.parametrize(
        "value,probability,expected",
        [
            (Decimal("10000"), 20, Decimal("2000.00")),
            (Decimal("5000"), 50, Decimal("2500.00")),
            (Decimal("100"), 0, Decimal("0.00")),
            (Decimal("100"), 100, Decimal("100.00")),
            (Decimal("333.33"), 33, Decimal("110.00")),
            (Decimal("0"), 50, Decimal("0.00")),
        ],
    )
    def test_weighted_value(
        self, value: Decimal, probability: int, expected: Decimal
    ) -> None:
        assert _read(value, probability).weighted_value == expected


class TestWinTransition:
    def test_win_open_opportunity_succeeds(self) -> None:
        service = _service()
        opp = _opportunity("OPEN")
        service._get_or_raise = MagicMock(return_value=opp)  # type: ignore[method-assign]
        service._stage_repo.get_flagged_stage = MagicMock(return_value=None)  # type: ignore[method-assign]
        service.db.execute = MagicMock(return_value=MagicMock(rowcount=1))  # type: ignore[method-assign]

        result = service.win(uuid4(), uuid4())

        assert result is opp
        service.db.commit.assert_called_once()  # type: ignore[attr-defined]

    def test_win_already_won_raises(self) -> None:
        service = _service()
        opp = _opportunity("WON")
        service._get_or_raise = MagicMock(return_value=opp)  # type: ignore[method-assign]
        service._stage_repo.get_flagged_stage = MagicMock(return_value=None)  # type: ignore[method-assign]
        service.db.execute = MagicMock(return_value=MagicMock(rowcount=0))  # type: ignore[method-assign]

        with pytest.raises(InvalidOpportunityTransitionError):
            service.win(uuid4(), uuid4())

    def test_win_already_lost_raises(self) -> None:
        service = _service()
        opp = _opportunity("LOST")
        service._get_or_raise = MagicMock(return_value=opp)  # type: ignore[method-assign]
        service._stage_repo.get_flagged_stage = MagicMock(return_value=None)  # type: ignore[method-assign]
        service.db.execute = MagicMock(return_value=MagicMock(rowcount=0))  # type: ignore[method-assign]

        with pytest.raises(InvalidOpportunityTransitionError):
            service.win(uuid4(), uuid4())

    def test_win_moves_to_flagged_won_stage(self) -> None:
        service = _service()
        opp = _opportunity("OPEN")
        won_stage_id = uuid4()
        won_stage = MagicMock(id=won_stage_id, probability=100)
        service._get_or_raise = MagicMock(return_value=opp)  # type: ignore[method-assign]
        service._stage_repo.get_flagged_stage = MagicMock(return_value=won_stage)  # type: ignore[method-assign]
        service.db.execute = MagicMock(return_value=MagicMock(rowcount=1))  # type: ignore[method-assign]

        service.win(uuid4(), uuid4())

        executed_stmt = service.db.execute.call_args[0][0]  # type: ignore[attr-defined]
        bound_params = executed_stmt.compile().params
        assert bound_params["stage_id"] == won_stage_id
        assert bound_params["probability"] == 100
        assert bound_params["status"] == "WON"


class TestLoseTransition:
    def test_lose_open_opportunity_succeeds(self) -> None:
        service = _service()
        opp = _opportunity("OPEN")
        service._get_or_raise = MagicMock(return_value=opp)  # type: ignore[method-assign]
        service._stage_repo.get_flagged_stage = MagicMock(return_value=None)  # type: ignore[method-assign]
        service.db.execute = MagicMock(return_value=MagicMock(rowcount=1))  # type: ignore[method-assign]

        result = service.lose(uuid4(), uuid4(), "Budget cut")

        assert result is opp
        service.db.commit.assert_called_once()  # type: ignore[attr-defined]

    def test_lose_already_terminal_raises(self) -> None:
        service = _service()
        opp = _opportunity("WON")
        service._get_or_raise = MagicMock(return_value=opp)  # type: ignore[method-assign]
        service._stage_repo.get_flagged_stage = MagicMock(return_value=None)  # type: ignore[method-assign]
        service.db.execute = MagicMock(return_value=MagicMock(rowcount=0))  # type: ignore[method-assign]

        with pytest.raises(InvalidOpportunityTransitionError):
            service.lose(uuid4(), uuid4(), "Too late")


class TestChangeStage:
    def test_change_stage_to_different_pipeline_rejected(self) -> None:
        service = _service()
        opp = _opportunity("OPEN", pipeline_id=uuid4())
        other_pipeline_stage = MagicMock(pipeline_id=uuid4(), is_active=True)
        service._get_or_raise = MagicMock(return_value=opp)  # type: ignore[method-assign]
        service._stage_repo.get_by_id_or_none = MagicMock(  # type: ignore[method-assign]
            return_value=other_pipeline_stage
        )

        with pytest.raises(ValidationException):
            service.change_stage(uuid4(), uuid4(), uuid4())

    def test_change_stage_to_inactive_stage_rejected(self) -> None:
        service = _service()
        opp = _opportunity("OPEN")
        inactive_stage = MagicMock(pipeline_id=opp.pipeline_id, is_active=False)
        service._get_or_raise = MagicMock(return_value=opp)  # type: ignore[method-assign]
        service._stage_repo.get_by_id_or_none = MagicMock(  # type: ignore[method-assign]
            return_value=inactive_stage
        )

        with pytest.raises(ValidationException):
            service.change_stage(uuid4(), uuid4(), uuid4())

    def test_change_stage_valid_succeeds(self) -> None:
        service = _service()
        opp = _opportunity("OPEN")
        target_stage = MagicMock(
            pipeline_id=opp.pipeline_id, is_active=True, probability=75
        )
        service._get_or_raise = MagicMock(return_value=opp)  # type: ignore[method-assign]
        service._stage_repo.get_by_id_or_none = MagicMock(return_value=target_stage)  # type: ignore[method-assign]
        service.db.execute = MagicMock(return_value=MagicMock(rowcount=1))  # type: ignore[method-assign]

        result = service.change_stage(uuid4(), uuid4(), uuid4())

        assert result is opp
        service.db.commit.assert_called_once()  # type: ignore[attr-defined]


class TestUpdateRejectedWhenTerminal:
    @pytest.mark.parametrize("status", ["WON", "LOST"])
    def test_update_terminal_opportunity_raises(self, status: str) -> None:
        service = _service()
        opp = _opportunity(status)
        service._get_or_raise = MagicMock(return_value=opp)  # type: ignore[method-assign]

        with pytest.raises(InvalidOpportunityTransitionError):
            service.update(uuid4(), uuid4(), OpportunityUpdate(description="new"))

    def test_update_open_opportunity_succeeds(self) -> None:
        service = _service()
        opp = _opportunity("OPEN")
        service._get_or_raise = MagicMock(return_value=opp)  # type: ignore[method-assign]
        service._repo.update = MagicMock(side_effect=lambda entity: entity)  # type: ignore[method-assign]

        result = service.update(uuid4(), uuid4(), OpportunityUpdate(description="new"))

        assert result.description == "new"
