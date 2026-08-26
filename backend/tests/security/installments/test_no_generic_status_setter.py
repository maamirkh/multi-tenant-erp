"""Structural/reflective test (tasks.md T084, FR-INST-106): no public
``set_status()``/``update_status()`` method exists anywhere on
``InstallmentContractService`` — every mutation goes through a named
business-action method that asserts ``_LEGAL_TRANSITIONS``, never a
generic status setter available to any actor however privileged.
"""

from __future__ import annotations

import inspect

from modules.installments.services.contract_service import InstallmentContractService


def test_no_generic_status_setter_method_exists() -> None:
    method_names = {
        name
        for name, _ in inspect.getmembers(
            InstallmentContractService, predicate=inspect.isfunction
        )
    }
    forbidden = {"set_status", "update_status", "change_status", "setstatus"}
    assert not (method_names & forbidden), (
        f"InstallmentContractService must not expose a generic status "
        f"setter, found: {method_names & forbidden}"
    )


def test_all_named_lifecycle_methods_are_present() -> None:
    """The approved named business-action methods do exist — this test
    fails loudly if one is ever accidentally renamed or removed."""
    method_names = {
        name
        for name, _ in inspect.getmembers(
            InstallmentContractService, predicate=inspect.isfunction
        )
        if not name.startswith("_")
    }
    expected = {"submit", "approve", "reject", "cancel", "mark_defaulted"}
    assert expected <= method_names


def test_status_field_is_never_publicly_settable_via_kwargs() -> None:
    """None of the named lifecycle methods accept an arbitrary
    ``status``/``new_status`` keyword argument — the target status is
    always implied by the method itself, never caller-supplied."""
    for method_name in ("submit", "approve", "reject", "cancel", "mark_defaulted"):
        method = getattr(InstallmentContractService, method_name)
        params = inspect.signature(method).parameters
        assert "status" not in params
        assert "new_status" not in params
