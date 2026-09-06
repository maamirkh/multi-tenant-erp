"""Unit tests: ActivityCreate schema validation (BR-006, due_date-for-TASK/
FOLLOW_UP) + ActivityService.complete()/create() logic — mocked
repository/session, no DB (plan.md §27.1/§48.1).

Task: T053 (tasks.md Phase 6).
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from core.exceptions.base import ValidationException
from modules.crm.models.activity import Activity
from modules.crm.schemas.activity import ActivityCreate
from modules.crm.services.activity_service import ActivityService


def _service() -> ActivityService:
    return ActivityService(
        db=MagicMock(),
        repo=MagicMock(),
        lead_repo=MagicMock(),
        customer_repo=MagicMock(),
        opportunity_repo=MagicMock(),
        member_repo=MagicMock(),
        audit_service=MagicMock(),
    )


def _activity(status: str = "PLANNED", **overrides: object) -> Activity:
    activity = Activity(
        company_id=uuid4(),
        activity_type="CALL",
        subject="Intro call",
        assigned_to=str(uuid4()),
        customer_id=str(uuid4()),
        status=status,
    )
    for key, value in overrides.items():
        setattr(activity, key, value)
    return activity


class TestActivityCreateValidation:
    def test_no_relation_fk_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ActivityCreate(activity_type="NOTE", subject="Orphan", assigned_to=uuid4())

    def test_customer_relation_accepted(self) -> None:
        ActivityCreate(
            activity_type="NOTE",
            subject="Linked",
            assigned_to=uuid4(),
            customer_id=uuid4(),
        )

    def test_lead_relation_accepted(self) -> None:
        ActivityCreate(
            activity_type="NOTE", subject="Linked", assigned_to=uuid4(), lead_id=uuid4()
        )

    def test_opportunity_relation_accepted(self) -> None:
        ActivityCreate(
            activity_type="NOTE",
            subject="Linked",
            assigned_to=uuid4(),
            opportunity_id=uuid4(),
        )

    @pytest.mark.parametrize("activity_type", ["TASK", "FOLLOW_UP"])
    def test_due_date_required_for_task_and_follow_up(self, activity_type: str) -> None:
        with pytest.raises(ValidationError):
            ActivityCreate(
                activity_type=activity_type,
                subject="No due date",
                assigned_to=uuid4(),
                customer_id=uuid4(),
            )

    @pytest.mark.parametrize("activity_type", ["CALL", "EMAIL", "MEETING", "NOTE"])
    def test_due_date_not_required_for_other_types(self, activity_type: str) -> None:
        ActivityCreate(
            activity_type=activity_type,
            subject="No due date needed",
            assigned_to=uuid4(),
            customer_id=uuid4(),
        )

    def test_unknown_activity_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ActivityCreate(
                activity_type="CARRIER_PIGEON",
                subject="x",
                assigned_to=uuid4(),
                customer_id=uuid4(),
            )


class TestCreateServiceValidation:
    def _data(self) -> ActivityCreate:
        return ActivityCreate(
            activity_type="NOTE", subject="x", assigned_to=uuid4(), customer_id=uuid4()
        )

    def test_create_rejects_assignee_with_no_membership(self) -> None:
        service = _service()
        service._member_repo.get_by_user_id = MagicMock(return_value=None)  # type: ignore[method-assign]

        with pytest.raises(ValidationException):
            service.create(uuid4(), self._data())

    def test_create_rejects_cross_tenant_customer(self) -> None:
        service = _service()
        active_member = MagicMock(status="active")
        service._member_repo.get_by_user_id = MagicMock(return_value=active_member)  # type: ignore[method-assign]
        service._customer_repo.get_by_id_or_none = MagicMock(return_value=None)  # type: ignore[method-assign]

        with pytest.raises(ValidationException):
            service.create(uuid4(), self._data())

    def test_create_succeeds_with_valid_data(self) -> None:
        service = _service()
        active_member = MagicMock(status="active")
        service._member_repo.get_by_user_id = MagicMock(return_value=active_member)  # type: ignore[method-assign]
        service._customer_repo.get_by_id_or_none = MagicMock(return_value=MagicMock())  # type: ignore[method-assign]
        service._repo.create = MagicMock(side_effect=lambda entity: entity)  # type: ignore[method-assign]

        result = service.create(uuid4(), self._data())

        assert result.subject == "x"


class TestComplete:
    def test_complete_already_completed_is_idempotent_noop(self) -> None:
        service = _service()
        activity = _activity("COMPLETED")
        service._get_or_raise = MagicMock(return_value=activity)  # type: ignore[method-assign]

        result = service.complete(uuid4(), uuid4())

        assert result is activity
        service.db.commit.assert_not_called()  # type: ignore[attr-defined]

    def test_complete_without_lead_skips_cascade_but_commits(self) -> None:
        service = _service()
        activity = _activity("PLANNED", lead_id=None)
        service._get_or_raise = MagicMock(return_value=activity)  # type: ignore[method-assign]

        result = service.complete(uuid4(), uuid4())

        assert result.status == "COMPLETED"
        assert result.completed_at is not None
        service.db.execute.assert_not_called()  # type: ignore[attr-defined]
        service.db.commit.assert_called_once()  # type: ignore[attr-defined]

    def test_complete_with_lead_triggers_cascade_update(self) -> None:
        service = _service()
        activity = _activity("PLANNED", lead_id=uuid4(), customer_id=None)
        service._get_or_raise = MagicMock(return_value=activity)  # type: ignore[method-assign]

        result = service.complete(uuid4(), uuid4())

        assert result.status == "COMPLETED"
        service.db.execute.assert_called_once()  # type: ignore[attr-defined]
        service.db.commit.assert_called_once()  # type: ignore[attr-defined]
