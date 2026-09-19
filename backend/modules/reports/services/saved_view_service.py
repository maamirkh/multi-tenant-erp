"""``SavedViewService`` — create/list/update/delete/load for private saved
report views (spec §29, plan.md §15).

``load()`` (``GET /saved-views/{id}``, T140) is the **only** place this
module re-runs ``ReportExecutionService._authorize_and_validate()`` — full
entitlement/permission/filter-schema re-validation against the loading
user's **current** state, never the state at save time (FR-RPT-203). Phase
1 deliberately didn't implement this until ``_authorize_and_validate()``
existed (Phase 3) — exposing "load without re-validation" would itself
have been insecure.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from modules.reports.exceptions import (
    FilterValidationError,
    ReportNotFoundError,
    RetiredReportKeyError,
    SavedViewNotFoundError,
)
from modules.reports.models.saved_report_view import SavedReportView
from modules.reports.registry.definitions import REPORT_REGISTRY, ReportStatus
from modules.reports.repositories.saved_report_view import SavedReportViewRepository
from modules.reports.schemas.common import JsonValue
from modules.reports.schemas.saved_view import (
    SavedReportViewCreate,
    SavedReportViewUpdate,
)
from modules.reports.services.execution_service import ReportExecutionService


def _resolve_and_validate_filters(
    report_key: str, filter_config: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    """Round-trip *filter_config* through ``report_key``'s current
    ``supported_filters`` model (FR-RPT-201/203). Returns the validated,
    normalized dict to persist. Raises ``ReportNotFoundError`` if
    ``report_key`` doesn't resolve to a ``status == NOW`` entry, or
    ``FilterValidationError`` if the payload fails that model's
    validation."""
    definition = REPORT_REGISTRY.get(report_key)
    if definition is None or definition.status is not ReportStatus.NOW:
        raise ReportNotFoundError(report_key)

    try:
        validated = definition.supported_filters(**filter_config)
    except ValidationError as exc:
        raise FilterValidationError(report_key, str(exc)) from exc

    result: dict[str, JsonValue] = validated.model_dump(mode="json")
    return result


def save(
    repo: SavedReportViewRepository,
    company_id: UUID,
    user_id: UUID,
    payload: SavedReportViewCreate,
) -> SavedReportView:
    validated_filters = _resolve_and_validate_filters(
        payload.report_key, payload.filter_config
    )
    entity = SavedReportView(
        company_id=company_id,
        user_id=user_id,
        report_key=payload.report_key,
        name=payload.name,
        schema_version=1,
        filter_config=validated_filters,
        grouping=payload.grouping,
        sorting=payload.sorting,
        visible_columns=payload.visible_columns,
        date_preset=payload.date_preset,
    )
    return repo.create(entity)


def update(
    repo: SavedReportViewRepository,
    view_id: UUID,
    company_id: UUID,
    user_id: UUID,
    payload: SavedReportViewUpdate,
) -> SavedReportView:
    entity = repo.get_for_owner(view_id=view_id, company_id=company_id, user_id=user_id)
    if entity is None:
        raise SavedViewNotFoundError(str(view_id))

    new_report_key = payload.report_key or entity.report_key
    new_filter_config = (
        payload.filter_config
        if payload.filter_config is not None
        else entity.filter_config
    )
    validated_filters = _resolve_and_validate_filters(new_report_key, new_filter_config)

    entity.report_key = new_report_key
    entity.filter_config = validated_filters
    if payload.name is not None:
        entity.name = payload.name
    if payload.grouping is not None:
        entity.grouping = payload.grouping
    if payload.sorting is not None:
        entity.sorting = payload.sorting
    if payload.visible_columns is not None:
        entity.visible_columns = payload.visible_columns
    if payload.date_preset is not None:
        entity.date_preset = payload.date_preset

    return repo.update(entity)


def delete(
    repo: SavedReportViewRepository, view_id: UUID, company_id: UUID, user_id: UUID
) -> None:
    deleted = repo.soft_delete_for_owner(
        view_id=view_id, company_id=company_id, user_id=user_id
    )
    if not deleted:
        raise SavedViewNotFoundError(str(view_id))


def list_views(
    repo: SavedReportViewRepository,
    company_id: UUID,
    user_id: UUID,
    skip: int = 0,
    limit: int = 20,
) -> tuple[list[SavedReportView], int]:
    return repo.list_for_user(
        company_id=company_id, user_id=user_id, skip=skip, limit=limit
    )


def load(
    db: Session,
    repo: SavedReportViewRepository,
    execution_service: ReportExecutionService,
    view_id: UUID,
    company_id: UUID,
    user_id: UUID,
    user_roles: list[str] | None = None,
) -> SavedReportView:
    """The only place ``load()`` exists — Phase 1 never had it (module
    docstring). Same not-found outcome for absent/other-owner/soft-deleted
    (no ownership- or existence-probing signal); a retired ``report_key``
    (missing or ``DEFERRED``) fails with ``RetiredReportKeyError``, never
    silently executing a different report; every other failure mode
    (entitlement, permission, stale filter schema) comes from re-running
    the identical preamble ``execute()`` uses, against the loading user's
    current state."""
    entity = repo.get_for_owner(view_id=view_id, company_id=company_id, user_id=user_id)
    if entity is None:
        raise SavedViewNotFoundError(str(view_id))

    definition = REPORT_REGISTRY.get(entity.report_key)
    if definition is None or definition.status is not ReportStatus.NOW:
        raise RetiredReportKeyError(entity.report_key)

    execution_service._authorize_and_validate(  # noqa: SLF001 — the one sanctioned cross-module reuse (T140)
        db,
        company_id=company_id,
        user_id=user_id,
        report_key=entity.report_key,
        raw_filters=dict(entity.filter_config),
        sort=None,
        permission_kind="view",
        user_roles=user_roles,
    )
    return entity
