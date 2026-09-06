"""Unit tests: LeadService lifecycle transitions, validation, and
assignment — mocked repository/session, no DB (plan.md §27.1/§48.1).

Covers:
  - Every valid/invalid (from_status, to_status) pair from spec.md §14.2
    (table-driven, 36 combinations).
  - BR-005: disqualification_reason required for UNQUALIFIED/LOST.
  - spec.md §15: qualification_notes required for QUALIFIED.
  - spec.md §30.3: assign() rejects a non-member / inactive-member owner.

Task: T033 (tasks.md Phase 3).
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from core.exceptions.base import ValidationException
from modules.crm.constants import LEAD_STATUSES, LEAD_VALID_TRANSITIONS
from modules.crm.exceptions import InvalidLeadTransitionError, LeadNotFoundError
from modules.crm.models.lead import Lead
from modules.crm.services.lead_service import LeadService


def _service() -> LeadService:
    return LeadService(
        db=MagicMock(),
        repo=MagicMock(),
        member_repo=MagicMock(),
        audit_service=MagicMock(),
    )


def _lead(status: str, **overrides: object) -> Lead:
    lead = Lead(company_id=uuid4(), status=status)
    for key, value in overrides.items():
        setattr(lead, key, value)
    return lead


class TestTransitionMatrix:
    """Every (from_status, to_status) pair — valid transitions succeed and
    apply the target status; invalid transitions raise
    InvalidLeadTransitionError. Precondition fields (disqualification_reason,
    qualification_notes) are pre-populated here so this test isolates pure
    state-machine behavior; their own requirement is tested separately
    below."""

    @pytest.mark.parametrize(
        "from_status,to_status",
        [(f, t) for f in sorted(LEAD_STATUSES) for t in sorted(LEAD_STATUSES)],
    )
    def test_transition(self, from_status: str, to_status: str) -> None:
        service = _service()
        overrides: dict[str, object] = {}
        if to_status in ("UNQUALIFIED", "LOST"):
            overrides["disqualification_reason"] = "Not a fit"
        if to_status == "QUALIFIED":
            overrides["qualification_notes"] = "Confirmed budget and need"
        lead = _lead(from_status, **overrides)

        allowed = LEAD_VALID_TRANSITIONS.get(from_status, frozenset())
        if to_status in allowed:
            result = service._transition_status(lead, to_status)
            assert result.status == to_status
        else:
            with pytest.raises(InvalidLeadTransitionError):
                service._transition_status(lead, to_status)


class TestQualifyDisqualifyPreconditions:
    def test_disqualify_to_unqualified_requires_reason(self) -> None:
        service = _service()
        lead = _lead("CONTACTED")
        with pytest.raises(ValidationException):
            service._transition_status(lead, "UNQUALIFIED")

    def test_disqualify_to_lost_requires_reason(self) -> None:
        service = _service()
        lead = _lead("NEW")
        with pytest.raises(ValidationException):
            service._transition_status(lead, "LOST")

    def test_qualify_requires_qualification_notes(self) -> None:
        service = _service()
        lead = _lead("CONTACTED")
        with pytest.raises(ValidationException):
            service._transition_status(lead, "QUALIFIED")

    def test_qualify_method_sets_notes_then_transitions(self) -> None:
        service = _service()
        lead = _lead("CONTACTED")
        service._get_or_raise = MagicMock(return_value=lead)  # type: ignore[method-assign]

        result = service.qualify(lead.id, lead.company_id, "Budget confirmed")

        assert result.status == "QUALIFIED"
        assert result.qualification_notes == "Budget confirmed"

    def test_disqualify_method_sets_reason_then_transitions(self) -> None:
        service = _service()
        lead = _lead("CONTACTED")
        service._get_or_raise = MagicMock(return_value=lead)  # type: ignore[method-assign]

        result = service.disqualify(lead.id, lead.company_id, "Not a fit")

        assert result.status == "UNQUALIFIED"
        assert result.disqualification_reason == "Not a fit"

    def test_disqualify_rejects_invalid_target_status(self) -> None:
        service = _service()
        with pytest.raises(ValueError):
            service.disqualify(uuid4(), uuid4(), "reason", target_status="QUALIFIED")


class TestGetOrRaise:
    def test_raises_lead_not_found_when_repo_returns_none(self) -> None:
        service = _service()
        service._repo.get_by_id_or_none = MagicMock(return_value=None)  # type: ignore[method-assign]
        with pytest.raises(LeadNotFoundError):
            service.get(uuid4(), uuid4())


class TestAssign:
    def test_rejects_owner_with_no_membership(self) -> None:
        service = _service()
        lead = _lead("NEW")
        service._get_or_raise = MagicMock(return_value=lead)  # type: ignore[method-assign]
        service._member_repo.get_by_user_id = MagicMock(return_value=None)  # type: ignore[method-assign]

        with pytest.raises(ValidationException):
            service.assign(lead.id, lead.company_id, uuid4())

    def test_rejects_inactive_member(self) -> None:
        service = _service()
        lead = _lead("NEW")
        service._get_or_raise = MagicMock(return_value=lead)  # type: ignore[method-assign]
        inactive_member = MagicMock(status="inactive")
        service._member_repo.get_by_user_id = MagicMock(return_value=inactive_member)  # type: ignore[method-assign]

        with pytest.raises(ValidationException):
            service.assign(lead.id, lead.company_id, uuid4())

    def test_assigns_active_member(self) -> None:
        service = _service()
        lead = _lead("NEW")
        service._get_or_raise = MagicMock(return_value=lead)  # type: ignore[method-assign]
        active_member = MagicMock(status="active")
        service._member_repo.get_by_user_id = MagicMock(return_value=active_member)  # type: ignore[method-assign]
        service._repo.update = MagicMock(side_effect=lambda entity: entity)  # type: ignore[method-assign]
        owner_id = uuid4()

        result = service.assign(lead.id, lead.company_id, owner_id)

        assert result.owner_id == str(owner_id)
