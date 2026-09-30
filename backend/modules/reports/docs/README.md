# Reports & Analytics Module (Epic 11)

Specification: `specs/011-reports-analytics/` (`spec.md`, `plan.md`,
`tasks.md`, `data-model.md`, `contracts/reports-api.yaml`). This document
summarizes what was implemented; the spec remains authoritative.

## Purpose

One governed, read-only reporting layer over the existing ERP modules. Every
figure comes from its source module's own public service — Reports never
re-implements a formula ("One Metric → One Authoritative Definition → Many
Consumers").

## Scope

**In scope (implemented):**

- A static, code-defined report registry: 48 definitions — **45 "Now"**
  (Accounting 9, Inventory 8, Sales 8, Installments 7, Purchase 7, CRM 4,
  Executive Dashboard 1, Customer 360 1) and **3 Deferred**.
- Generic execution (`GET /{report_key}`) through six domain adapters
  (`ADAPTER` kind) and two dedicated composite read models (`COMPOSITE`
  kind): the Executive Dashboard (10 widgets) and Customer 360.
- Discovery, period presets and period-over-period comparison.
- Exports for 33 exportable reports, audited before delivery: CSV/XLSX,
  plus PDF for the four Accounting statements (delegated to Accounting's
  own `export_to_pdf()`).
- Personal saved views (soft delete, re-authorized on load).
- Frontend under `/analytics/*` (Overview, six domain hubs, generic report
  page, Customer 360).

**Out of scope:** see [Future Enhancements](#future-enhancements).

## Business Rules

- **Tenant isolation:** every query is scoped by the path `company_id`; no
  cross-tenant fallback. A foreign id is a 404, never a 403.
- **Authorization order** (`ReportExecutionService._authorize_and_validate`):
  registry lookup → Reports entitlement → domain entitlement → permission →
  filter validation. Undiscoverable and Deferred keys are indistinguishable
  (404).
- **Compound authorization:** a Dashboard widget or Customer 360 section is
  present only if the user holds its own domain's permission *and* the
  domain is entitled; otherwise it is **omitted** (never shown as zero).
  `unavailable` means a prerequisite is missing (e.g. no chart of accounts).
- **Installments servicing continuity:** with Installments disabled, a
  tenant that still has contracts keeps read-only servicing reports
  (Case B, flagged `read_only_servicing_continuity`); a tenant with none
  gets nothing (Case A). `plan_performance` is excluded under Case B.
- **Money:** `Decimal` only, normalized to `NUMERIC(20,6)` precision and
  rounded only at display.
- **Currencies (FR-RPT-152):** amounts in different currencies are never
  summed or converted. Money aggregates are reported per currency (a
  `currency_code` on rows, `*by_currency` lists on aggregates, widgets and
  Customer 360). A single value field is set only when one currency is
  present, is a real zero when there is no data, and is `null` when there are
  several currencies. See
  [`multi_currency_findings.md`](multi_currency_findings.md).
- **Exports:** CSV cells are neutralized against formula injection; XLSX is
  written in bounded write-only mode; the audit row must commit before the
  file is returned. Row caps: CSV 50,000, XLSX 25,000 (batches of 1,000).
  The GL export pages by cursor and uses limit+1 to detect overflow.
- **Bounded reads:** list reports are SQL-paginated (Category A); the
  Installments reports cap their population at 50,000 (Category B);
  aggregates are Category D.
- **Branches:** Epic 11 adds no branch authorization. `branch_id` is
  accepted only where the source module already supports it.

## User Stories

1. As an executive, I see ten key figures for a period, with comparison.
2. As a manager, I run any report I'm permitted to, filter it, and export it.
3. As a sales user, I open a Customer 360 view combining Sales, Accounting
   AR, CRM and Installments data I'm permitted to see.
4. As any report user, I save a filter set as a personal view and reload it.
5. As an auditor, I can see who exported which report with which filters.

## Database Design

Two tables hold Epic 11 data; a third holds the per-company override flag.

| Table | Migration | Purpose |
|---|---|---|
| `saved_report_views` | 076 | Personal saved views: `company_id`, `user_id`, `report_key`, `name` (≤150), `schema_version`, `filter_config` (JSONB), `grouping`, `sorting`, `visible_columns`, `date_preset`, soft delete. Indexed on (`company_id`, `user_id`) and (`company_id`, `report_key`). |
| `reports_audit_log` | 077 | Append-only audit of exports and saved-view changes: `entity_type`, `entity_id`, `action`, `actor_id`, `before`/`after` (JSONB), `report_key`, `filter_scope`, `format`, `row_count`, `reason`. Indexed on (`company_id`, `created_at`) and (`company_id`, `actor_id`). |
| `reports_feature_flags` | 073 | Per-company Reports enablement override (mirrors `crm_feature_flags`). |

Other migrations: 074 seeds the `reports` capability; 075 seeds the 16
permissions; 078 adds `ix_installment_schedule_lines_company_id` for
Customer 360 (T268). Head: **078**.

## API Design

Prefix: `/api/v1/companies/{company_id}/reports`
(contract: `contracts/reports-api.yaml`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/discovery` | Reports the caller can run, with filters, formats and drill-down targets |
| GET | `/dashboard` | Executive Dashboard (10 widgets, `period`, `compare`) |
| GET | `/customer-360/{customer_id}` | Customer 360 composite |
| GET | `/{report_key}` | Run a report (offset or cursor pagination) |
| GET | `/{report_key}/export` | Export CSV/XLSX/PDF in the same filter scope |
| GET, POST | `/saved-views` | List / create saved views |
| GET, PATCH, DELETE | `/saved-views/{view_id}` | Load (re-authorized), update, soft delete |

Responses use the standard envelope; report results carry
`ReportEnvelopeMeta` (applied filters, period, freshness, drill-down,
comparison, servicing-continuity flag).

## Permissions

16 codes (migration 075):

| Domain | View | Export |
|---|---|---|
| Sales | `reports.sales.view` | `reports.sales.export` |
| Purchase | `reports.purchase.view` | `reports.purchase.export` |
| Inventory | `reports.inventory.view` | `reports.inventory.export` |
| Accounting | `reports.accounting.view` | `reports.accounting.export` |
| CRM | `reports.crm.view` | `reports.crm.export` |
| Installments | `reports.installments.view` | `reports.installments.export` |
| Executive | `reports.executive.view` | — |
| Customer 360 | `reports.customer_360.view` | — |
| Saved views | `reports.saved_view.manage` | — |
| Branch performance | `reports.branch_performance.view` | — |

`reports.crm.export` and `reports.branch_performance.view` currently unlock
nothing: no CRM report is exportable, and branch performance is Deferred.

## Validation Rules

- Filter schemas are per-report Pydantic models with `extra="forbid"`;
  unknown or malformed filters are a 422.
- Date ranges must be ordered; period presets resolve in the company's
  timezone.
- Page size and export row caps are enforced server-side.
- Saved views: name up to 150 characters; `filter_config` is validated
  against the report's filter schema, and a view is re-authorized on load.

## Future Enhancements

Deferred (registered, never executable, 404 like an unknown key):

- `accounting.tax`
- `accounting.cost_center_pl`
- `crossmodule.branch_performance`

Not planned in Epic 11: async export jobs, caching, scheduled or shared
saved views, a custom report builder, cross-tenant analytics and
AI/NL-to-SQL. Converting currencies to the base currency (instead of
reporting each separately) is not implemented.

## Test Strategy

- **Unit** (`tests/unit/modules/reports/`): registry consistency, filters,
  money normalization, CSV sanitizer, authorization ordering.
- **Integration** (`tests/integration/api/v1/reports/`): every endpoint over
  HTTP on SQLite; `postgres/` runs real-PostgreSQL cases (NUMERIC precision,
  export scope, audit durability) against throwaway databases.
- **Security** (`tests/security/reports/`): full entitlement and RBAC
  matrices, tenant isolation, IDOR, platform-admin and support-access
  boundaries, CSV injection.
- **Migrations** (`tests/integration/migrations/`): each migration up/down,
  and the full chain.
- **Performance** (`tests/performance/reports/`): query-count (no N+1),
  representative scale, Customer 360 `EXPLAIN` plans.
- **Frontend**: Jest + jest-axe (`src/__tests__/reports/`) and the
  Playwright smoke test `frontend/e2e/reports-smoke.spec.ts`.
