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
    """[Phase-13 closure] Allowlist updated for four Phase-12 N+1-elimination
    read methods (tasks.md T213 — never a per-contract loop for a
    company-wide report/dashboard aggregate): ``get_lines_for_versions``
    (batch line fetch for a set of schedule versions, replacing per-contract
    ``get_lines()`` calls in the customer-statement/summary services),
    ``list_active_lines_for_company`` (the due/overdue/aging report base
    population), ``sum_schedule_outstanding_for_company`` and
    ``sum_schedule_outstanding_for_statuses`` (single-query dashboard KPI
    aggregates). All four are pure ``SELECT``/aggregate reads — verified
    individually against the repository source, no ``update``/``delete``
    substring, no write/flush/commit call — so this update does not weaken
    the append-only invariant `test_no_update_method_exists_on_schedule_
    repository` (above) already enforces independently."""
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
        "get_lines_for_versions",
        "get_line_by_id",
        "list_active_lines_for_company",
        "sum_schedule_outstanding_for_company",
        "sum_schedule_outstanding_for_statuses",
    }
