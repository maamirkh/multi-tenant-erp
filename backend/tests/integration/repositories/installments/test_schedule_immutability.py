"""[Phase 4] Structural test: schedule-version/line immutability — no
update method exists on ``InstallmentScheduleRepository`` (tasks.md T072,
mirroring plan.md §31's own "doesn't exist" structural-test instruction).

Immutability is enforced by omission, not a DB trigger: if this test ever
fails, someone added a mutating method that would let already-issued
contractual schedule history be silently rewritten (BR-INST-017).
"""

from __future__ import annotations

import inspect

from modules.installments.repositories.schedule import InstallmentScheduleRepository


def test_no_update_method_exists_on_schedule_repository() -> None:
    method_names = {
        name for name, _ in inspect.getmembers(InstallmentScheduleRepository)
    }
    forbidden_substrings = ("update", "delete", "edit", "modify", "set_")
    offending = {
        name
        for name in method_names
        if not name.startswith("__")
        and any(bad in name.lower() for bad in forbidden_substrings)
    }
    assert offending == set(), (
        f"InstallmentScheduleRepository must have no mutating method, found: "
        f"{offending}"
    )


def test_repository_only_exposes_the_documented_read_and_create_methods() -> None:
    public_methods = {
        name
        for name, _ in inspect.getmembers(
            InstallmentScheduleRepository, predicate=inspect.isfunction
        )
        if not name.startswith("_")
    }
    assert public_methods == {
        "create_version_with_lines",
        "get_active_version",
        "get_version",
        "get_lines",
    }
