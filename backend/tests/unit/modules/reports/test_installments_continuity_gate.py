"""T111 — the single most important test in the Installments sub-phase:
full ``InstallmentsServicingContinuityGate.evaluate()`` state matrix, and
``is_allowed()``'s exact per-key behavior under each state (FR-RPT-104,
mirroring FR-INST-353-358's Case A/B split)."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from modules.platform_admin.services.entitlement_service import EffectiveEntitlement
from modules.reports.services.installments_continuity_gate import (
    InstallmentsAccessState,
    InstallmentsServicingContinuityGate,
)

_ALL_7_KEYS = (
    "installments.register",
    "installments.collections",
    "installments.due_overdue",
    "installments.aging",
    "installments.settlement_writeoff",
    "installments.plan_performance",
    "installments.dashboard",
)

_ALLOWED_UNDER_CONTINUITY = frozenset(
    {
        "installments.register",
        "installments.collections",
        "installments.due_overdue",
        "installments.aging",
        "installments.settlement_writeoff",
    }
)


def _gate(
    *, available: bool, contract_total: int
) -> InstallmentsServicingContinuityGate:
    entitlement_service = MagicMock()
    entitlement_service.resolve_effective_entitlement.return_value = (
        EffectiveEntitlement(
            capability_key="installments",
            available=available,
            reason="plan_and_toggle" if available else "tenant_toggle_disabled",
        )
    )
    reporting_service = MagicMock()
    reporting_service.get_contract_register.return_value = ([], contract_total)
    return InstallmentsServicingContinuityGate(
        entitlement_service=entitlement_service, reporting_service=reporting_service
    )


def test_evaluate_returns_entitled_full_when_available() -> None:
    gate = _gate(available=True, contract_total=0)
    assert gate.evaluate(uuid.uuid4()) is InstallmentsAccessState.ENTITLED_FULL


def test_evaluate_returns_entitled_full_regardless_of_contract_count() -> None:
    gate = _gate(available=True, contract_total=5)
    assert gate.evaluate(uuid.uuid4()) is InstallmentsAccessState.ENTITLED_FULL


def test_evaluate_returns_servicing_continuity_when_disabled_with_existing_contracts() -> (
    None
):
    gate = _gate(available=False, contract_total=1)
    assert gate.evaluate(uuid.uuid4()) is InstallmentsAccessState.SERVICING_CONTINUITY


def test_evaluate_returns_unavailable_when_disabled_with_no_contracts() -> None:
    gate = _gate(available=False, contract_total=0)
    assert gate.evaluate(uuid.uuid4()) is InstallmentsAccessState.UNAVAILABLE


@pytest.mark.parametrize("report_key", _ALL_7_KEYS)
def test_is_allowed_true_for_all_7_keys_under_entitled_full(report_key: str) -> None:
    assert (
        InstallmentsServicingContinuityGate.is_allowed(
            report_key, InstallmentsAccessState.ENTITLED_FULL
        )
        is True
    )


@pytest.mark.parametrize("report_key", _ALL_7_KEYS)
def test_is_allowed_under_servicing_continuity_matches_allowlist(
    report_key: str,
) -> None:
    expected = report_key in _ALLOWED_UNDER_CONTINUITY
    assert (
        InstallmentsServicingContinuityGate.is_allowed(
            report_key, InstallmentsAccessState.SERVICING_CONTINUITY
        )
        is expected
    )


def test_plan_performance_and_dashboard_denied_under_servicing_continuity() -> None:
    assert (
        InstallmentsServicingContinuityGate.is_allowed(
            "installments.plan_performance",
            InstallmentsAccessState.SERVICING_CONTINUITY,
        )
        is False
    )
    assert (
        InstallmentsServicingContinuityGate.is_allowed(
            "installments.dashboard", InstallmentsAccessState.SERVICING_CONTINUITY
        )
        is False
    )


@pytest.mark.parametrize("report_key", _ALL_7_KEYS)
def test_is_allowed_false_for_all_7_keys_under_unavailable(report_key: str) -> None:
    assert (
        InstallmentsServicingContinuityGate.is_allowed(
            report_key, InstallmentsAccessState.UNAVAILABLE
        )
        is False
    )
