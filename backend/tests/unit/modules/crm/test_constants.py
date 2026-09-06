"""Unit tests for CRM module constants.

Prevents silent drift between spec.md's documented lifecycle and the code's
transition maps (mirrors ``tests/unit/modules/accounting/test_constants.py``'s
existing precedent).

Spec ref: specs/009-crm/spec.md §14.2 (Lead Lifecycle), §17.2 (Opportunity
Lifecycle), §19.1 (Activity types/statuses/priorities).
"""

from __future__ import annotations

from modules.crm.constants import (
    ACTIVITY_PRIORITIES,
    ACTIVITY_STATUSES,
    ACTIVITY_TYPES,
    CRM_ENABLED_FLAG_KEY,
    LEAD_STATUSES,
    LEAD_TERMINAL_STATUSES,
    LEAD_VALID_TRANSITIONS,
    OPPORTUNITY_STATUSES,
    OPPORTUNITY_TERMINAL_STATUSES,
    OPPORTUNITY_VALID_TRANSITIONS,
)


class TestLeadStatuses:
    def test_exactly_six_statuses(self) -> None:
        assert LEAD_STATUSES == {
            "NEW",
            "CONTACTED",
            "QUALIFIED",
            "UNQUALIFIED",
            "CONVERTED",
            "LOST",
        }

    def test_transition_map_keys_match_statuses(self) -> None:
        assert set(LEAD_VALID_TRANSITIONS.keys()) == LEAD_STATUSES

    def test_transition_map_matches_spec_14_2_exactly(self) -> None:
        """Per spec.md §14.2's lifecycle diagram, verbatim."""
        expected = {
            "NEW": {"CONTACTED", "LOST"},
            "CONTACTED": {"QUALIFIED", "UNQUALIFIED"},
            "QUALIFIED": {"CONVERTED", "UNQUALIFIED"},
            "UNQUALIFIED": {"NEW"},
            "CONVERTED": set(),
            "LOST": set(),
        }
        actual = {k: set(v) for k, v in LEAD_VALID_TRANSITIONS.items()}
        assert actual == expected

    def test_every_transition_target_is_a_known_status(self) -> None:
        for targets in LEAD_VALID_TRANSITIONS.values():
            assert targets <= LEAD_STATUSES

    def test_terminal_statuses(self) -> None:
        assert LEAD_TERMINAL_STATUSES == {"CONVERTED", "LOST"}
        for status in LEAD_TERMINAL_STATUSES:
            assert LEAD_VALID_TRANSITIONS[status] == frozenset()

    def test_unqualified_is_reopenable_to_new(self) -> None:
        """§14.2: 'terminal, but reopenable by a manager (transition back to NEW)'."""
        assert LEAD_VALID_TRANSITIONS["UNQUALIFIED"] == frozenset({"NEW"})


class TestOpportunityStatuses:
    def test_exactly_three_statuses(self) -> None:
        assert OPPORTUNITY_STATUSES == {"OPEN", "WON", "LOST"}

    def test_transition_map_keys_match_statuses(self) -> None:
        assert set(OPPORTUNITY_VALID_TRANSITIONS.keys()) == OPPORTUNITY_STATUSES

    def test_transition_map_matches_spec_17_2_exactly(self) -> None:
        """Per spec.md §17.2: OPEN -> WON | LOST, both terminal."""
        expected = {
            "OPEN": {"WON", "LOST"},
            "WON": set(),
            "LOST": set(),
        }
        actual = {k: set(v) for k, v in OPPORTUNITY_VALID_TRANSITIONS.items()}
        assert actual == expected

    def test_every_transition_target_is_a_known_status(self) -> None:
        for targets in OPPORTUNITY_VALID_TRANSITIONS.values():
            assert targets <= OPPORTUNITY_STATUSES

    def test_terminal_statuses(self) -> None:
        assert OPPORTUNITY_TERMINAL_STATUSES == {"WON", "LOST"}
        for status in OPPORTUNITY_TERMINAL_STATUSES:
            assert OPPORTUNITY_VALID_TRANSITIONS[status] == frozenset()


class TestActivityConstants:
    def test_activity_types(self) -> None:
        assert ACTIVITY_TYPES == {
            "CALL",
            "EMAIL",
            "MEETING",
            "TASK",
            "NOTE",
            "FOLLOW_UP",
        }

    def test_activity_statuses(self) -> None:
        assert ACTIVITY_STATUSES == {"PLANNED", "COMPLETED", "CANCELLED"}

    def test_activity_priorities(self) -> None:
        assert ACTIVITY_PRIORITIES == {"LOW", "MEDIUM", "HIGH"}


class TestFeatureFlagKey:
    def test_crm_enabled_flag_key(self) -> None:
        assert CRM_ENABLED_FLAG_KEY == "feature.crm.enabled"
