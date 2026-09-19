"""``GET /reports/discovery`` response shapes (T130, contracts/reports-api.yaml
``ReportDiscoveryResponse``/``ReportDiscoveryItem``) — a permission- and
entitlement-filtered summary of every ``status=NOW`` ``ReportDefinition``
the requesting user currently holds, computed by
``registry_service.list_discoverable_reports()`` (T030).
"""

from __future__ import annotations

from pydantic import BaseModel

from modules.reports.registry.definitions import ReportDefinition


class ReportDiscoveryItem(BaseModel):
    key: str
    name: str
    domain: str
    description: str
    exportable: bool
    export_formats: list[str]
    branch_filterable: bool
    drill_down_targets: list[str]

    @classmethod
    def from_definition(cls, definition: ReportDefinition) -> ReportDiscoveryItem:
        return cls(
            key=definition.key,
            name=definition.name,
            domain=definition.domain.value,
            description=definition.description,
            exportable=definition.export_permission is not None,
            export_formats=[fmt.value for fmt in definition.export_formats],
            branch_filterable=definition.branch_filterable,
            drill_down_targets=[t.label for t in definition.drill_down_targets],
        )


class ReportDiscoveryResponse(BaseModel):
    reports: list[ReportDiscoveryItem]
