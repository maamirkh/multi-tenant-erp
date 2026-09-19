# Epic 11 — Reports & Analytics: Phase 1 Data Model

Derived from `spec.md` §7–§10, §20, §29 and `plan.md` §6–§17. Conceptual model only — no migration code (per planning stop condition). Two categories of "entity" appear here: (1) the two genuinely new **persisted** tables Epic 11 introduces, and (2) the **in-memory, code-defined** typed structures (Report Registry, Metric Catalog) that are not database rows but are load-bearing enough to a plan-stage data model that they are documented with the same rigor. All persisted entities inherit `TenantBaseModel` (`id` UUID PK, `company_id`, `created_at`/`updated_at`, `created_by`, `is_deleted`/`deleted_at`) per `plan.md` §2.8/§6.

---

## Persisted Entities

### SavedReportView

Private, user-owned reporting configuration (spec §29).

| Field | Type | Notes |
|---|---|---|
| `user_id` | `UUID` (FK → users) | Owner; indexed with `company_id` |
| `report_key` | `VARCHAR` | Not FK'd to the registry — the registry is code, not a table; validated at write/load time instead |
| `name` | `VARCHAR(150)` | |
| `schema_version` | `INT` | New convention (`plan.md` R6) — Epic 11 ships only `1` |
| `filter_config` | `JSONB` | Validated against `FilterConfigV1` before persist; never arbitrary JSON/SQL (FR-RPT-201) |
| `grouping` | `JSONB` \| NULL | List of dimension names |
| `sorting` | `VARCHAR` \| NULL | One of the report's declared `sortable_fields` |
| `visible_columns` | `JSONB` \| NULL | List of column names |
| `date_preset` | `VARCHAR` \| NULL | One of the standard period presets (spec §22) |

**Validation**: `filter_config` round-tripped through the target report's *current* `supported_filters` Pydantic model before persist (rejects unregistered fields) and again at load time (re-validates against whatever that model currently is — FR-RPT-203).
**Relationships**: none by foreign key to any business table — `report_key` is a soft reference to the code-defined registry, deliberately not enforced by a DB constraint (the registry can evolve independently of persisted rows; a retired key fails gracefully at load, FR-RPT-204, rather than via a DB error).
**Constraints**: no uniqueness constraint on `(company_id, user_id, name)` — the spec does not require preventing duplicate names, so none is invented (Constitution §7 YAGNI).
**Ownership scope**: every repository method requires both `company_id` and `user_id`; a view is never listable/loadable by any other user, even within the same tenant (FR-RPT-205).
**Lifecycle**: standard soft-delete (`is_deleted`/`deleted_at`, inherited from `TenantBaseModel`) even though no restore UI ships in this epic — a deliberate no-op capability for consistency with every other model in the repo, not a gap (`plan.md` §15).

### ReportsAuditLog

Append-only audit record for reporting actions (spec §39).

| Field | Type | Notes |
|---|---|---|
| `entity_type` | `VARCHAR` | `"ReportExport"` \| `"SavedReportView"` |
| `entity_id` | `UUID` | The export event's own generated ID, or the `SavedReportView.id` |
| `action` | `VARCHAR` | e.g. `"EXPORTED"`, `"CREATED"`, `"UPDATED"`, `"DELETED"` |
| `actor_id` | `UUID` \| NULL | Acting user |
| `before` / `after` | `JSONB` \| NULL | Previous/new state, for saved-view update/delete |
| `report_key` | `VARCHAR` \| NULL | Populated for export actions |
| `filter_scope` | `JSONB` \| NULL | The exact filters applied — populated for export actions |
| `format` | `VARCHAR` \| NULL | `CSV` \| `XLSX` \| `PDF` — export actions only |
| `row_count` | `INT` \| NULL | Export actions only |
| `reason` | `VARCHAR` \| NULL | Optional, matches Accounting/Installments' audit shape |

**Validation**: none beyond type — this is a write-once record, never updated.
**Relationships**: none by foreign key — mirrors every other module's own audit table (no shared `core/` audit model exists to inherit from, `plan.md` §2.8).
**Constraints**: append-only at the application layer (`ReportsAuditService.record()` only ever inserts, never updates/deletes) — no DB-level immutability trigger, consistent with Constitution §17's prohibition on business logic in triggers.
**Write pattern**: staged via `repo.create()` + `flush()` only; the caller (`ReportExportService`/`SavedViewService`) commits it in the same transaction as the business action it documents — never a separately committed side effect (`plan.md` §22).

---

## Code-Defined Typed Structures (not persisted)

### ReportDefinition

One frozen instance per catalog row in spec §9. See `plan.md` §7 for the full field list (`key`, `name`, `description`, `domain`, `authoritative_source`, `required_permission`, `export_permission`, `domain_capability_key`, `supported_filters`, `supported_dimensions`, `supported_measures`, `sortable_fields`, `export_formats`, `drill_down_targets`, `branch_filterable`, `freshness`, `pagination`, `status`). Aggregated into `REPORT_REGISTRY: dict[str, ReportDefinition]`, keyed by `key`. Governed by the registry-consistency unit test (`plan.md` §7) rather than a database constraint — its "referential integrity" (does `authoritative_source` really exist? do `supported_filters`' fields really match the wrapped method's parameters?) is verified at test time via `inspect.signature()`, not at runtime per request.

### MetricDefinition

One frozen instance per row in spec §10's KPI/Metric Catalog. See `plan.md` §8 for the full field list (`semantic_id`, `label`, `description`, `authoritative_domain`, `source_call`, `date_basis`, `money_precision`, `supports_comparison`, `inclusion_rule`). Aggregated into `METRIC_CATALOG: dict[str, MetricDefinition]`. A metric is documentation-plus-identity for wiring, never itself a computation (`plan.md` §8).

### DrillDownTarget

One frozen instance per `ReportDefinition.drill_down_targets` entry (`label`, `target_route`, `required_permission`, `preserves_filters`) — see `plan.md` §25.

---

## Cross-Module Reference Shape (Customer 360)

Customer 360 (`crossmodule.customer_360`) has **no entity of its own** — it is a request-time composition keyed by `customer_id` (Sales' `Customer.id`), fanning out to four independent, tenant-scoped lookups:

```
customer_id (Sales Customer PK)
  ├── Sales activity        — Sales' own Customer/Order/Invoice repositories, keyed by customer_id
  ├── Accounting AR balance — AccountsReceivableService, keyed by customer_id (loose reference, no DB FK
  │                            across module boundaries — matches the repository's existing convention of
  │                            UUID-only cross-module references, e.g. Sales/Purchase → Inventory Product)
  ├── CRM activity          — CrmReportingService, keyed by customer_id (if CRM links leads/opportunities
  │                            to a Sales customer_id; exact linkage field confirmed during /sp.tasks)
  └── Installments exposure — InstallmentReportingService, keyed by customer_id
```

Each section's result is one of the three `SectionState` variants (`plan.md` §14/R5) — `PRESENT[T]`, `OMITTED{reason}`, `UNAVAILABLE{reason}` — assembled into the response's four named section fields. No intermediate or final state is written back to any table.

---

## State Transitions

Neither `SavedReportView` nor `ReportsAuditLog` has a business status/workflow state machine — `SavedReportView` has only implicit lifecycle (`created → updated* → soft-deleted`), and `ReportsAuditLog` is create-only. The only "state" of interest in this epic is the **per-request, non-persisted** `InstallmentsAccessState` (`ENTITLED_FULL | SERVICING_CONTINUITY | UNAVAILABLE`, `plan.md` §13) and `SectionState`/`WidgetState` (`PRESENT | OMITTED | UNAVAILABLE`, `plan.md` §14/§26) — both computed fresh on every request from live entitlement/data-availability signals, never stored.
