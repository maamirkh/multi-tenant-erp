# ADR-0005: Static Code-Defined Report Registry over Database-Backed Report Metadata

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Accepted
- **Date:** 2026-09-29
- **Feature:** 011-reports-analytics
- **Context:** Epic 11 needs one governed catalog of every report the platform offers: 45 "Now" reports across Sales, Purchase, Inventory, Accounting, CRM and Installments, plus the Executive Dashboard and Customer 360 composites, and 3 Deferred reports. Every report needs the same metadata: required and export permissions, entitlement (capability) key, typed filter schema, export formats, drill-down targets, freshness class, pagination kind, status (Now/Deferred) and execution kind (Adapter/Composite). This catalog drives discovery, authorization, execution, exports and the UI. plan.md §7 and §37 flagged the choice of where this catalog lives as significant: every future report follows the pattern, a database-backed alternative existed, and all six domains plus both composites depend on it. Implemented and verified through Phases 0–11.

<!-- Significance checklist (ALL must be true to justify this ADR)
     1) Impact: Long-term consequence for architecture/platform/security?
     2) Alternatives: Multiple viable options considered with tradeoffs?
     3) Scope: Cross-cutting concern (not an isolated detail)?
     If any are false, prefer capturing as a PHR note instead of an ADR. -->

## Decision

Define the report catalog **in code**, versioned with the codebase, never as a database table:

- `modules/reports/registry/definitions.py`: `ReportDefinition` is a frozen dataclass, matching the existing `PermissionDefinition` convention. Each definition carries its typed Pydantic filter model (`supported_filters`), so a report's filters, permissions and handler are checked by `mypy` together.
- One catalog file per domain (`catalog_sales.py`, `catalog_purchase.py`, … `catalog_executive.py`, `catalog_crossmodule.py`), registered through `register()`. A duplicate key raises at import time. `load_all.py` imports every catalog.
- `REPORT_REGISTRY` is exposed as a read-only `Mapping`. Execution resolves a key to its definition, then to the domain adapter (`ADAPTER`) or the dedicated composite service (`COMPOSITE`). Deferred keys are registered but can never execute, and are indistinguishable from unknown keys (404).
- `test_registry_consistency.py` enforces the invariants in CI: unique keys, the exact Now/Deferred shape, every `required_permission` is a known permission code (`users_roles.constants.PERMISSION_BY_CODE`), every `ADAPTER` entry has a registered domain adapter and a resolvable source, and every `COMPOSITE` entry maps to the identical handler. `test_reports_permission_migration_matches_constants.py` keeps those codes in step with migration 075.
- Per-tenant variation (which reports a company sees) comes from **entitlements and permissions**, never from editing the catalog.

## Consequences

### Positive

- Filters, permissions and execution are type-checked together (`mypy . = 0`); a report cannot reference a filter model or permission that does not exist.
- The catalog changes in the same reviewed commit as the code that serves it, so metadata can never drift from the implementation or be edited in production.
- Consistency is enforced by tests rather than by runtime checks against a table, and there is no extra query per request.
- Tenant isolation is simpler: the catalog is global and read-only, and all tenant-specific behavior sits in the entitlement/RBAC layer.
- The typed metadata is machine-readable for future consumers (for example AI-assisted discovery) without schema changes.

### Negative

- Adding or changing a report needs a code change and a deployment; there are no tenant-defined or admin-defined reports.
- A custom report builder (explicitly out of Epic 11 scope) would need a separate, database-backed layer alongside this registry.
- Permission codes live in three places (catalog, `users_roles` constants and migration 075), kept in sync only by tests.

## Alternatives Considered

**Alternative A — Database-backed report metadata table** (a `report_definitions` table seeded by migration, editable by platform admins). Rejected: filter schemas and handlers are code and cannot be type-checked from rows; metadata could drift from the implementation; every request would need an extra lookup; and each change would need a migration anyway to stay in step with the code.

**Alternative B — Hybrid: code-defined definitions with per-tenant overrides in the database** (for example renaming or hiding reports per company). Rejected for Epic 11: the entitlement and permission layers already control visibility per tenant, and overrides would add a second source of truth. It can be added later without changing the registry contract.

**Alternative C — Implicit registration via decorators on adapter methods.** Rejected: it scatters the catalog across six domain adapters, makes exact counts and ordering harder to audit, and couples catalog metadata to import side effects of the adapter modules.

## References

- Feature Spec: `specs/011-reports-analytics/spec.md`
- Implementation Plan: `specs/011-reports-analytics/plan.md` (§7, §37)
- Related ADRs: ADR-0006
- Code: `backend/modules/reports/registry/`, `backend/tests/unit/modules/reports/test_registry_consistency.py`
