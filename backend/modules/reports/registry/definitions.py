"""Report Registry types + the registry itself (plan.md §7).

``ReportDefinition`` is a frozen dataclass (matching ``PermissionDefinition``'s
existing convention) — curated, in-code, versioned with the codebase
(Assumption A7), never a database table.

Spec ref: specs/011-reports-analytics/plan.md §7.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

from modules.reports.schemas.common import FreshnessClassification


class ReportDomain(StrEnum):
    SALES = "sales"
    PURCHASE = "purchase"
    INVENTORY = "inventory"
    ACCOUNTING = "accounting"
    CRM = "crm"
    INSTALLMENTS = "installments"
    EXECUTIVE = "executive"
    CROSSMODULE = "crossmodule"


class ReportStatus(StrEnum):
    NOW = "now"
    DEFERRED = "deferred"


class PaginationStyle(StrEnum):
    OFFSET = "offset"
    CURSOR = "cursor"
    NONE = "none"


class ExportFormat(StrEnum):
    CSV = "csv"
    XLSX = "xlsx"
    PDF = "pdf"


class ReportExecutionKind(StrEnum):
    """Structural, typed discriminator (micro-pass Blocker A) between a
    report resolved through ``ADAPTER_REGISTRY`` (the 43 domain-wrapped
    reports) and one resolved through ``COMPOSITE_REPORT_HANDLERS`` (the
    two cross-module compositions, Executive Dashboard and Customer 360) —
    replaces a hardcoded report-key exception list in the registry-
    consistency test (T032)."""

    ADAPTER = "adapter"
    COMPOSITE = "composite"


@dataclass(frozen=True)
class DrillDownTarget:
    """Registry-time drill-down link descriptor (plan.md §25) — an
    explicit, typed link, never a generic entity browser."""

    label: str
    target_route: str
    required_permission: str
    preserves_filters: tuple[str, ...]


@dataclass(frozen=True)
class ReportDefinition:
    """One catalog entry (spec §9/§10). Every field here is required at
    registration time — there is no optional/partial ``ReportDefinition``.
    """

    key: str
    name: str
    description: str
    domain: ReportDomain
    authoritative_source: str
    required_permission: str
    export_permission: str | None
    domain_capability_key: str | None
    supported_filters: type[BaseModel]
    supported_dimensions: tuple[str, ...]
    supported_measures: tuple[str, ...]
    sortable_fields: tuple[str, ...]
    export_formats: tuple[ExportFormat, ...]
    drill_down_targets: tuple[DrillDownTarget, ...]
    branch_filterable: bool
    freshness: FreshnessClassification
    pagination: PaginationStyle
    status: ReportStatus
    execution_kind: ReportExecutionKind


_REGISTRY: dict[str, ReportDefinition] = {}


def register(definition: ReportDefinition) -> None:
    """Add *definition* to the shared registry. Raises ``ValueError`` on a
    duplicate ``key`` — a report key is registered exactly once, ever."""
    if definition.key in _REGISTRY:
        raise ValueError(f"Report key '{definition.key}' is already registered.")
    _REGISTRY[definition.key] = definition


REPORT_REGISTRY: Mapping[str, ReportDefinition] = _REGISTRY
