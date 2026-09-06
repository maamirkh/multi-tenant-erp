"""Unit tests for the Installments contract lifecycle transition table.

Prevents silent drift between plan.md §9.1/§9.2's documented state
machine and the code's transition map (mirrors
``tests/unit/modules/crm/test_constants.py``'s existing precedent).

Covers tasks.md T020: ``_LEGAL_TRANSITIONS`` has no path to a persisted
``REJECTED`` value (ADR-INST-11 — rejection is an audited action, never a
persisted status) and no transition outside the enumerated
``InstallmentContractStatus`` set is present.

Spec ref: specs/010-installments/plan.md §9.1/§9.2.
"""

from __future__ import annotations

from modules.installments.constants import _LEGAL_TRANSITIONS, InstallmentContractStatus

_KNOWN_STATUSES = frozenset(status.value for status in InstallmentContractStatus)


class TestLegalTransitionsTable:
    def test_no_rejected_value_anywhere(self) -> None:
        """REJECTED is an audited action, not a persisted status
        (ADR-INST-11) — it must never appear as a key or a transition
        target."""
        assert "REJECTED" not in _LEGAL_TRANSITIONS
        for targets in _LEGAL_TRANSITIONS.values():
            assert "REJECTED" not in targets

    def test_status_enum_has_no_rejected_member(self) -> None:
        assert "REJECTED" not in _KNOWN_STATUSES

    def test_transition_map_keys_match_known_statuses_exactly(self) -> None:
        assert set(_LEGAL_TRANSITIONS.keys()) == _KNOWN_STATUSES

    def test_every_transition_target_is_a_known_status(self) -> None:
        """No transition outside the enumerated set is present."""
        for targets in _LEGAL_TRANSITIONS.values():
            assert targets <= _KNOWN_STATUSES

    def test_transition_map_matches_plan_9_2_exactly(self) -> None:
        expected = {
            "DRAFT": {"PENDING_APPROVAL", "APPROVED", "CANCELLED"},
            "PENDING_APPROVAL": {"APPROVED", "DRAFT", "CANCELLED"},
            "APPROVED": {"ACTIVE", "CANCELLED"},
            "ACTIVE": {"COMPLETED", "CANCELLED", "DEFAULTED"},
            "DEFAULTED": {"ACTIVE", "COMPLETED", "WRITTEN_OFF"},
            "COMPLETED": set(),
            "CANCELLED": set(),
            "WRITTEN_OFF": set(),
        }
        actual = {k: set(v) for k, v in _LEGAL_TRANSITIONS.items()}
        assert actual == expected

    def test_terminal_statuses_have_no_outgoing_transitions(self) -> None:
        for status in ("COMPLETED", "CANCELLED", "WRITTEN_OFF"):
            assert _LEGAL_TRANSITIONS[status] == frozenset()

    def test_values_are_frozensets(self) -> None:
        """Immutable by construction — matches the platform's frozen-
        datastructure convention for lifecycle tables."""
        for targets in _LEGAL_TRANSITIONS.values():
            assert isinstance(targets, frozenset)
