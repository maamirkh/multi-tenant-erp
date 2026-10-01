# Implementation Plan: Epic 11 — Reports & Analytics

**Branch**: `011-reports-analytics` | **Date**: 2026-09-11 | **Spec**: `specs/011-reports-analytics/spec.md`
**Input**: Approved Epic 11 specification (865 lines, Status: Draft — ready for review, correction pass complete, no blocking open questions per spec §53)

**Note**: This is a **planning-only** artifact. No code, migration, or dependency is created by this document. `tasks.md` is explicitly **not** created here (per governing prompt §66/§70).

---

## 0. Plan Status

| Field | Value |
|---|---|
| Stage | `/sp.plan` (design only) |
| Governing spec | `specs/011-reports-analytics/spec.md` (all 54 sections, FR-RPT-001 through FR-RPT-363) |
| Baseline | `mypy . = 0` (prod + tests), Ruff clean, real-Postgres CI, pre-Epic-11 stabilization complete (commit `0fc6e5d`) |
| Constitution version referenced | 1.2.1 |
| `tasks.md` | Not created — deferred to `/sp.tasks` after this plan is reviewed |
| Verdict | See §41 |

---

## 1. Summary

Epic 11 adds a new backend module `backend/modules/reports/` and a new frontend route group `frontend/src/app/(protected)/(reports)/` that together form a **thin orchestration layer**: a typed, code-defined Report Registry and Metric Catalog; one execution service enforcing tenant → `reports` entitlement → domain entitlement → RBAC → filter-validation gates identically for every report; six domain adapters that translate Reports' typed request/response contracts into calls against the six already-completed domain report/KPI services (never re-deriving their logic); a bounded Executive Dashboard composition service; a Customer 360 composite read model with section-level compound authorization; new Epic-11-owned `SavedReportView` persistence; and a unified CSV/XLSX export path with centralized row-limit and formula-injection protection. No business table outside Reports' own two new tables (`saved_report_views`, `reports_audit_log`) is ever written to. Financial figures continue to originate exclusively from Accounting; operational figures from their owning module. The `reports` Capability is new, registered `grain=module`, and — per spec §18/§34 (FR-RPT-255) — **disabled by default**, requiring its own feature-flag/master-toggle service mirroring CRM's and Installments' existing pattern (not the four core modules' `DefaultAlwaysEnabledModuleProvider`, which cannot represent an opt-in add-on).

---

## 2. Repository Findings (Re-Discovery, 2026-09-11)

Re-verified directly against the current tree (not solely the spec's discovery notes). All citations are `file:line`.

### 2.1 Module structure convention

Every module (`installments`, `crm`, `accounting`, `sales`, `purchase`, `inventory`) uses a **flat** vertical slice, not the Constitution §12 illustrative tree verbatim:

```
backend/modules/<name>/
  __init__.py  constants.py  dependencies.py  router.py  exceptions.py
  events/  handlers/  models/  repositories/  schemas/  services/
```

`modules/<name>/permissions/` and `modules/<name>/validators/` **do not exist anywhere** — permission checks live in `services/permission_check.py`; entitlement/policy logic lives in `services/access_policy.py` / `services/feature_flag_service.py`. Tests are **not** colocated — all tests live under `backend/tests/{unit,integration,security,performance}/.../<module>/`. Reports follows this exact convention (§6), not the Constitution's illustrative `permissions/`/`validators/` folders, matching every real module in the repo (a documented, justified deviation from the Constitution's illustrative — not mandatory — tree; see Constitution §12, which lists these as *likely* areas, and the actual repository precedent, which the spec's own governing prompt §6/§8 instructs this plan to follow over the abstract illustration).

### 2.2 Router composition & entitlement gating

`backend/api/v1/router.py:122-183`: five modules (`inventory`, `purchase`, `sales`, `accounting`, `crm`) are mounted with a named `require_capability_entitled("<key>")` gate instance at router-mount time; CRM additionally layers `Depends(require_crm_enabled)` (its own master-toggle check) behind the entitlement ceiling. **Installments (`api/v1/router.py:234-260`) is mounted with `get_current_company_member` only** — no capability gate — because origination-vs-servicing granularity cannot be expressed as a single router-level block; `InstallmentAccessPolicy.authorize()` enforces it per service method instead. This is the exact precedent Reports' execution service reuses for domain-level (not module-level) entitlement checks (§9, §13).

`CapabilitySeedService.MODULE_CAPABILITY_CATALOGUE` (`backend/modules/platform_admin/services/capability_seed_service.py:25-32`) currently has six tuples (`inventory`, `purchase`, `sales`, `accounting`, `crm`, `installments`) — no `reports` entry exists yet. `seed_capabilities()` (same file, L42-66) is idempotent. Epic 11 adds a seventh tuple here (§12, §16).

### 2.3 Entitlement resolution

`PlatformEntitlementService.resolve_effective_entitlement(*, company_id, capability_key) -> EffectiveEntitlement` (`modules/platform_admin/services/entitlement_service.py:118-161`) is the single authoritative resolver; no module re-implements this logic. `require_capability_entitled(capability_key)` (`modules/platform_admin/dependencies.py:220-300`) is the router-mount factory built on top of it.

`get_module_enablement_provider(capability_key, db)` (`modules/platform_admin/services/module_enablement.py:99-110`) **raises `ValueError` for any unregistered capability key**. `DefaultAlwaysEnabledModuleProvider` (L79-88, used for `inventory`/`sales`/`purchase`/`accounting`, listed in `_DEFAULT_RULE_MODULES` at L96) returns `True` unconditionally — this is architecturally wrong for `reports`, which spec §18/§34/FR-RPT-255 requires to be **disabled by default**. Epic 11 therefore needs its own `ReportsModuleEnablementProvider` (mirroring `CrmModuleEnablementProvider`/`InstallmentsModuleEnablementProvider`, L48-76) wired to a new `ReportsFeatureFlagService`, and `get_module_enablement_provider`'s dispatch table must add a `"reports"` branch. This is a small, precedented edit to `platform_admin` — the same edit CRM's and Installments' own onboarding required — not a boundary violation.

### 2.4 Installments servicing-continuity seam

`InstallmentAccessPolicy.authorize(*, company_id, operation)` (`modules/installments/services/access_policy.py`, ~86 lines):

```python
class InstallmentOperationClass(str, Enum):
    ORIGINATION = "ORIGINATION"
    SERVICING   = "SERVICING"
    READ        = "READ"
    ADMIN       = "ADMIN"
```

For `READ`/`SERVICING`, `authorize()` returns (permits) **regardless of whether the `installments` entitlement is currently active** — only `ORIGINATION` is blocked when disabled. `InstallmentReportingService` already calls this as `_authorize_read()` at the top of every public method (`services/reporting_service.py:115-119`), e.g. `get_contract_register(company_id, *, status=None, skip=0, limit=20) -> tuple[list[dict[str, Any]], int]`.

**Important finding, not a bug — a design clarification Reports must account for**: because `authorize(operation=READ)` permits unconditionally, it *cannot by itself* distinguish spec's Case A (disabled, no obligations → unavailable) from Case B (disabled, obligations exist → read-only). The distinguishing signal has to come from Reports asking two things, not duplicating Installments' policy: (1) is `installments` entitled (via the same `PlatformEntitlementService.resolve_effective_entitlement()` every other domain uses), and if not, (2) does the tenant have at least one existing contract at all — answered by calling `InstallmentReportingService.get_contract_register(company_id, skip=0, limit=1)` and reading its `total` (the second element of the returned tuple), which is an **existing, already-self-authorizing method** — zero new Installments code required, zero duplicated business logic. §13 makes this the one seam Reports touches.

### 2.5 Permission pattern & central registry

Every module has its own `services/permission_check.py::user_has_<module>_permission(db, company_id, user_id, permission_code, *, user_roles=None) -> bool` — no shared base implementation (confirmed identical ~30-line shape in accounting/sales/purchase/inventory/crm/installments). Central seeding: `RoleSeedService.seed_permissions()` (`modules/users_roles/services/role_seed_service.py:60-85`), idempotent, sourced from `INITIAL_PERMISSIONS` in `modules/users_roles/constants.py`, where each new module contributes its own `tuple[PermissionDefinition, ...]` (e.g. `INSTALLMENTS_PERMISSIONS`, `constants.py:114-225`) unioned in. Existing companies are backfilled via a dedicated migration (`071_installments_permission_backfill.py`) whose codes must match the constants tuple exactly. Reports follows the identical pattern: `REPORTS_PERMISSIONS` tuple + one backfill migration (§16).

### 2.6 Report/KPI services to wrap (authoritative sources)

| Domain | File | Class | Shape |
|---|---|---|---|
| Sales | `modules/sales/services/report_service.py` | `ReportService` | `run_report(...) -> ReportResponse` (own Pydantic schema, `sales/schemas/reports.py:169-178`: `{report_type, company_id, params, total, rows: list[dict]}`) |
| Purchase | `modules/purchase/services/report_service.py` | `ReportService` | methods like `purchase_order_summary(...)`, plain `dict[str, Any]` |
| Inventory | `modules/inventory/services/report_service.py` | `ReportQueryService` | methods like `inventory_summary(...)`, plain `dict[str, Any]` |
| Accounting | `modules/accounting/services/report_service.py` | `ReportService` | `get_gl_report(company_id, filters=None, cursor: tuple[date,UUID,int] \| None=None, limit=100) -> dict` — **the only cursor-paginated report in the repo**, returns `{items, has_more, next_cursor}` |
| Accounting (statements) | `modules/accounting/services/financial_statements.py` | `FinancialStatementService` | `get_trial_balance`, `get_pl`, `get_balance_sheet`, `get_cash_flow` — aggregate dict shapes |
| Accounting (KPIs) | `modules/accounting/services/kpi_service.py` | `FinancialKPIService` | `get_dashboard_kpis(company_id, as_of_date) -> dict[str, Any]` |
| CRM | `modules/crm/services/reporting_service.py` | `CrmReportingService` | `get_pipeline_report(...)`, `get_dashboard(company_id) -> CrmDashboard` |
| Installments | `modules/installments/services/reporting_service.py` | `InstallmentReportingService` | `get_contract_register(...) -> tuple[list[dict], int]` (offset/limit) and 7 sibling methods, `get_dashboard(...)` |

No two modules share a base class, method-naming convention, return-type shape, or pagination style. This confirms spec §11's premise exactly — a generic adapter interface cannot assume structural commonality; each adapter is bespoke per domain, normalizing only at its own boundary (§10).

### 2.7 Export services

| Module | File | Library | Return shape |
|---|---|---|---|
| Accounting | `services/report_export.py` | openpyxl + reportlab | `bytes` only (`export_to_excel`, `export_to_pdf`) |
| Sales | `services/report_export_service.py` | csv + openpyxl | `(bytes, filename, content_type)` |
| Purchase | `services/report_export_service.py` | csv + openpyxl | `bytes` only, static methods |
| Inventory | `services/export_service.py` | csv + openpyxl | `(bytes, filename)` |

Four different return contracts, no shared interface. **No CSV formula-injection sanitizer exists anywhere in the repository** (verified by grep across all `csv.writer`/`DictWriter` call sites) — this is a genuine, pre-existing gap in all four modules' exports, not something Epic 11 introduced. Per governing-prompt §58 bug-discovery policy: **classified as separate, pre-existing debt** in Sales/Purchase/Inventory/Accounting's own export paths; Epic 11 fixes it only in its own new export path (§21) and documents the other four as an unaddressed, out-of-scope finding (not silently buried — flagged in §36 Risk Register).

### 2.8 Schema, model, migration, audit, test-fixture, CI conventions

- `core/schemas/response.py`: `StandardResponse[T]{data, message, meta}`, `ErrorResponse{error: ErrorDetail{code, message, details}}`.
- `core/schemas/pagination.py`: `PaginatedData[T]{items, total, page, page_size, pages}`, `PaginatedResponse[T]{data: PaginatedData[T], message, meta}`, `PaginationParams{page≥1, page_size 1–100 default 20}`. **No cursor-pagination schema exists** — confirms spec §28's GL exception is real, not hypothetical (§19).
- `core/database/models/tenant_base.py:43`: `TenantBaseModel(BaseModel)` — single abstract class providing `id, company_id, created_at, updated_at, created_by, is_deleted, deleted_at` together (not composable mixins). `SavedReportView`/`ReportsAuditLog` inherit this directly (§16).
- **No existing "validated JSONB + version field" pattern anywhere in the repo** — every JSONB column examined (`companies.settings`, `installments.plan_template.*_rule`, etc.) is a plain untyped `dict`/`list` column with no companion schema-version integer. Epic 11's `SavedReportView.filter_config` establishes a **new** convention (Pydantic-validated at the service boundary + an explicit `schema_version` int column) rather than reusing a nonexistent one (§15, §16).
- Migrations: `backend/migrations/versions/`, `NNN_snake_case.py`, plain numeric string `revision`/`down_revision` (not hashes). Latest: `072_installments_requires_review.py` (`revision="072"`). **Epic 11's first migration is `073_...`.** Every migration checked has a real `downgrade()` (not `pass`).
- Audit: **no shared `core/` audit model/service** — every module owns its own (`InstallmentAuditLog`/`InstallmentAuditService`, `AuditLogService` in accounting, etc.). `record()` only stages via `repo.create()` + `flush()`; the **caller commits it in the same transaction** as the business mutation. Reports follows this: its own `ReportsAuditLog` model + `ReportsAuditService.record()` (§22).
- Test fixtures: `tests/integration/migrations/conftest.py` provides `pg_test_db()` (throwaway DB per test), `alembic_upgrade(url, revision="head")`, `db_engine()`. Per-module conftests re-export and wrap these into local `pg_engine`/`db_session` fixtures, but **hardcode the target revision string** (e.g. `alembic_upgrade(pg_url, "072")`) rather than `"head"` — Reports' own conftest must either use `"head"` or update the literal to its own migrations' final revision to avoid silently skipping them (§29).
- CI (`.github/workflows/backend.yml`): `lint` job blocks on `ruff check`, `ruff format --check`, and `mypy .` (explicitly: "any new first-party MyPy error, production or test, fails CI"); `test` job runs against a real `postgres:16-alpine` service with `--cov-fail-under=80` (global; a stricter 90% floor exists only for `modules/auth/**`); `security` job runs Bandit (`--exit-zero`, non-blocking today) and `pip-audit --severity HIGH` (blocking); `migrations` job statically validates the revision chain; `docker-build` builds the production image. Epic 11 changes none of this (§32).

### 2.9 Frontend findings

- App Router: `frontend/src/app/(protected)/(module-name)/...` — one nested route group per module. **No `(reports)` group exists.** Every domain already has at least a reports hub and/or KPI page (Accounting: 10 statement pages; Sales: hub + `[type]` dynamic page; Purchase: hub + 5 report pages + KPI page; Inventory: hub + KPI page; CRM: dashboard + combined reports page; Installments: dashboard + unified reports page) — Epic 11 does not touch or replace any of these (§23, §35).
- Auth/tenant context: `useAuth()` (`hooks/useAuth.ts:36`), `CompanyContext`/`useCompanyContext()` (`contexts/CompanyContext.tsx:63,119`) — but `CompanyProvider` only wraps the `(companies)` group, so every other module reads `erp_active_company_id` from `localStorage` directly and listens for the `erp-active-company-changed` window event. **No generic `usePermissions()` hook exists** — each module hand-rolls its own (`useInstallmentsPermissions`, `useCrmPermissions`), hitting a module-specific "my permissions" endpoint. **The global `Sidebar.tsx` has no per-module nav links at all today** (only "Dashboard"/"Companies") — its own code comment admits this is a placeholder. Reports therefore is not retrofitting a broken pattern; it is establishing the first real nav-permission integration for the tenant app (§23).
- Data fetching: **inconsistent across modules** — Installments is the only module using TanStack Query + a `lib/api/*.ts` wrapper + a query-key factory consistently; Accounting/CRM use manual `useEffect`/`fetch`; Purchase/Inventory's KPI pages bypass `lib/api` entirely with a hand-rolled `fetch` + `getAccessToken()`. Epic 11 explicitly adopts **Installments' pattern** as the Reports standard (§23) — a deliberate improvement, not a new invention.
- Shared components: **no `DataTable`, no date-range picker, no shared chart wrapper exist anywhere** (`components/shared/` exists but is empty). KPI cards are reimplemented per module (`accounting/KPICard.tsx`, ad hoc in Sales/Inventory pages, `crm/KpiTile.tsx`). `ExportButton.tsx` exists only in Accounting, not reused elsewhere. **No charting library is installed** (`package.json` confirmed: no recharts/visx/chart.js/nivo/d3). Stack: `next@^16.3.4`, `react@19.2.4`, `@tanstack/react-query@^5.0.0`, `tailwindcss@^4`, shadcn/ui primitives (only `button`/`card`/`dialog`/`input` present today), `zod@^3`, `react-hook-form@^7`. No `axios` — native `fetch` throughout (§23, §24).
- Discovery: **no tenant-facing "what am I entitled/permitted to see" endpoint exists today.** The only discovery-shaped endpoint (`GET /tenants/{companyId}/entitlements`, `platform_admin/router.py:877-884`) is Platform-Admin-only. Every existing module discovers denial reactively (403) or via its own narrow feature-flags endpoint. Epic 11's discovery endpoint (§18, FR-RPT-032) is therefore genuinely new — it is not replacing an existing pattern, it is introducing the first one (§23).

---

## 3. Technical Context

**Language/Version**: Python 3.12+ (backend, unchanged); TypeScript 5.x / Next.js 16 App Router (frontend, unchanged).
**Primary Dependencies**: FastAPI 0.115+, Pydantic v2, SQLAlchemy 2.x, Alembic — no new backend dependency. Frontend: TanStack Query, Tailwind CSS 4, shadcn/ui — **one new frontend dependency**: a charting library (§24, final pick made here, not installed until implementation).
**Storage**: PostgreSQL 16 (existing `db` Compose service) — two new tables (`saved_report_views`, `reports_audit_log`); no new datastore.
**Testing**: pytest (existing), real-Postgres fixture chain (`tests/integration/migrations/conftest.py`) for anything Postgres-specific; frontend test tooling is whatever the frontend already uses — **not independently re-verified in this discovery pass**; `/sp.tasks` must confirm the exact frontend test runner/config before writing frontend test tasks (flagged, non-blocking, §40).
**Target Platform**: Linux server (Docker Compose dev, Render/Neon initial prod per Constitution §6.6) — unchanged.
**Project Type**: Web application (existing `backend/` + `frontend/` split).
**Performance Goals**: Qualitative per spec Assumption A8 — no fabricated numeric SLA; concrete guardrails are the export row-limit (§21) and N+1-avoidance (§31).
**Constraints**: `mypy . = 0` must hold throughout (spec FR-RPT-350); no new CI job/gate weakening (FR-RPT-353); Reports never writes to another module's tables (NG2).
**Scale/Scope**: 6 domain adapters, ~35 "Now" report keys (§9 catalog), 1 dashboard, 1 cross-module composite (Customer 360), 1 new persistence entity (saved views) + 1 audit table.

---

## 4. Constitution Check

*Gate: must pass before Phase 0 (already satisfied by design; re-checked after §6–§15 design below).*

| Constitution Principle | Compliance |
|---|---|
| §5 Modular Monolith, §12 Module Design | New module `backend/modules/reports/`, vertical slice, no new microservice (§6). |
| §9 Multi-Tenant, §44 Rule 10/11 | Every query/service/repository call in Reports takes `company_id`; no cross-tenant path introduced (§27, §35 spec). |
| §11 Feature Toggles | `reports` + each domain plug into the existing Epic 9A entitlement mechanism, no parallel flag system (§12). |
| §13 Repository Rules, §14 Service Layer Rules | Reports' own two tables get their own repositories; report *execution* never touches another module's tables directly — only via that module's public service methods (§9, §10). |
| §17 Database Principles (Money) | All monetary arithmetic stays `Decimal`; no floats introduced (§20). |
| §18 Migration Policy | Every new migration has a real `downgrade()`; committed with the code that needs it (§16). |
| §19 Security | OWASP-aligned: parameterized queries only (inherited from wrapped services), IDOR-safe Customer 360 (§14), least-privilege `reports.*` permissions (§11 below). |
| §25 Performance | No re-fetch-then-sum in Python; adapters call the wrapped service's own aggregation methods (§10, §31). |
| §26 Dependency Management | Exactly one new dependency (chart library), justified in §24; default is to not add — justification required and provided. |
| §35 Audit Trail | Reports' own append-only `ReportsAuditLog`, who/what/when/before/after/context shape (§22). |
| §37 SaaS Readiness | `reports` plugs into the existing Plan/Capability/Subscription model (§12), not a parallel one. |
| §44 Rule 7 (no architecture violation without ADR) | Four candidate decisions flagged for ADR consent in §37 below — none auto-created. |

No violations requiring the Complexity Tracking table below §41's structure — omitted as not applicable.

---

## 5. Architecture Overview

### 5.1 Thin Reporting Orchestration (non-negotiable)

```
Reports layer  →  authoritative domain report/KPI service  →  typed result  →  unified response/export
```

Reports **never** issues raw SQL against Sales/Purchase/Inventory/Accounting/CRM/Installments tables (NG2, FR-RPT-003). Every "Now" catalog entry's `authoritative_source` in the Report Registry (§7) resolves to one of the eight services listed in §2.6. The only tables Reports itself writes to are `saved_report_views` and `reports_audit_log`.

### 5.2 Execution Model (adapts spec §8.1 to the concrete repo)

```
1. get_current_company_member                      (existing DI, unchanged)
2. require_capability_entitled("reports")           (router-mount gate, new — mirrors CRM's ceiling+toggle pattern)
   + require_reports_enabled                        (new ReportsFeatureFlagService toggle, §12)
3. ReportExecutionService.execute(report_key, ...)  — inside the service, per request:
   a. Report Registry lookup (404 if unknown key)          → FR-RPT-001
   b. Domain entitlement check via
      PlatformEntitlementService.resolve_effective_entitlement(capability_key=<domain>)
                                                             → FR-RPT-254 (identical call for all 6 domains,
                                                               never hardcoded "always on")
      — Installments' disabled case additionally consults
        InstallmentsServicingContinuityGate (§13)           → FR-RPT-104
   c. RBAC: user_has_reports_permission(db, company_id, user_id, definition.required_permission)
                                                             → FR-RPT-240..242
   d. Filter validation against definition.supported_filters/dimensions/measures/sortable_fields
                                                             → FR-RPT-120..123
   e. Branch scope applied only if definition.branch_filterable  → FR-RPT-160..164
   f. Dispatch to the domain adapter (§10)                 → typed result
4. Wrap in StandardResponse[T] / PaginatedResponse[T] / CursorPage[T] (GL only) / file Response (export)
```

Step 3 is **one function**, `ReportExecutionService.execute()` — every report key flows through it; no per-report endpoint duplicates 3a–3e (governing prompt §10's explicit requirement).

### 5.3 Why domain entitlement is checked in-service, not at router-mount

Reports has **one router** serving ~35+ report keys spanning six domains dynamically selected by path/query parameter — unlike Sales/CRM/etc., which each mount one router per module. A single router-mount gate cannot express "this domain, for this request." Domain entitlement is therefore evaluated per-request inside `ReportExecutionService`, using the exact same `resolve_effective_entitlement()` call every router-mount gate uses internally — same authority, different call site. This is a deliberate architectural choice, not a weaker check (FR-RPT-254 is satisfied identically).

---

## 6. Component / Module Structure

```
backend/modules/reports/
├── __init__.py
├── constants.py                 # REPORTS_CAPABILITY_KEY, EXPORT_ROW_LIMIT_CSV/XLSX, REPORTS_PERMISSIONS tuple
├── dependencies.py              # build_report_execution_service(), build_export_service(), build_dashboard_service(), ...
├── router.py                    # /companies/{company_id}/reports/*
├── exceptions.py                # ReportNotFoundError, ReportNotEntitledError, ReportPermissionDeniedError,
│                                 # FilterValidationError, UnsupportedSortFieldError, ExportTooLargeError,
│                                 # UnavailablePrerequisiteError, SavedViewNotFoundError, RetiredReportKeyError,
│                                 # ExportAuditPersistenceError (§21/§22/§26)
├── registry/
│   ├── __init__.py
│   ├── definitions.py           # ReportDefinition (frozen dataclass) + REPORT_REGISTRY: dict[str, ReportDefinition]
│   └── catalog_{sales,purchase,inventory,accounting,crm,installments,crossmodule}.py
│                                 # one module per domain registers its ReportDefinitions on import
├── metrics/
│   ├── __init__.py
│   └── definitions.py           # MetricDefinition (frozen dataclass) + METRIC_CATALOG: dict[str, MetricDefinition]
├── schemas/
│   ├── common.py                # DateRangeFilter, PeriodPreset enum, ComparisonRequest, FreshnessClassification
│   ├── pagination.py            # CursorPage[T]  (GL-report exception, §19)
│   ├── discovery.py             # ReportDiscoveryItem, ReportDiscoveryResponse
│   ├── dashboard.py             # ExecutiveDashboardResponse + per-widget schemas, WidgetState enum
│   ├── customer_360.py          # Customer360Response, SectionState enum, discriminated per-section unions
│   ├── saved_view.py            # SavedReportViewCreate/Update/Read, FilterConfigV1 (validated payload)
│   ├── export.py                # ExportRequest, ExportResult
│   └── {sales,purchase,inventory,accounting,crm,installments}.py   # per-domain filter + response schemas
├── models/
│   ├── saved_report_view.py     # SavedReportView(TenantBaseModel)
│   └── reports_audit_log.py     # ReportsAuditLog(TenantBaseModel)
├── repositories/
│   ├── saved_report_view_repository.py
│   └── reports_audit_repository.py
└── services/
    ├── permission_check.py       # user_has_reports_permission()  — same shape as every other module
    ├── feature_flag_service.py   # ReportsFeatureFlagService (master toggle, mirrors Crm/Installments)
    ├── date_range_service.py     # period-preset → half-open UTC range, using Company.default_timezone
    ├── comparison_service.py     # comparison engine (§20)
    ├── money_normalization.py    # Decimal precision/rounding helpers (§20)
    ├── csv_sanitizer.py          # sanitize_cell() — formula-injection neutralization (§21)
    ├── registry_service.py       # discovery filtering (permission+entitlement aware) — FR-RPT-032
    ├── execution_service.py      # ReportExecutionService — the one gate-chain+dispatch path (§5.2)
    ├── installments_continuity_gate.py   # InstallmentsServicingContinuityGate (§13)
    ├── dashboard_service.py      # ExecutiveDashboardService (§9 spec)
    ├── customer_360_service.py   # Customer360Service (§14)
    ├── saved_view_service.py     # SavedReportViewService (§15)
    ├── export_service.py         # ReportExportService — central export orchestration (§21)
    ├── audit_service.py          # ReportsAuditService.record() — stage-only, caller commits (§22)
    └── adapters/
        ├── base.py               # ReportAdapter Protocol[ReportResultT_co] + BaseReportResult/
        │                         # AggregateReportResult/PaginatedReportResult/CursorReportResult (§10) —
        │                         # no Any crosses this boundary; also declares count_export_rows()/
        │                         # iter_export_rows() for bounded export retrieval (§21)
        └── {sales,purchase,inventory,accounting,crm,installments}_adapter.py
```

Frontend (§23 for detail):

```
frontend/src/app/(protected)/(reports)/reports/
  page.tsx                       # Overview / Executive Dashboard
  sales/page.tsx  purchase/page.tsx  inventory/page.tsx  finance/page.tsx
  crm/page.tsx  installments/page.tsx
  customer-360/[customerId]/page.tsx
  [reportKey]/page.tsx           # generic per-report detail view driven by the registry response
frontend/src/lib/api/reports.ts
frontend/src/hooks/reports/{useReportDiscovery,useReport,useDashboard,useCustomer360,useSavedViews}.ts
frontend/src/components/reports/{DataTable,PeriodSelector,ComparisonSelector,FilterBar,KpiCard,
  ChartWrapper,ExportButton,SavedViewSelector}.tsx
frontend/src/components/reports/states/{EmptyState,ErrorState,PermissionDeniedState,
  ModuleDisabledState,UnavailableState}.tsx
```

No `permissions/`/`validators/` subfolders (§2.1 finding); no per-module `tests/` folder — tests land under the existing `backend/tests/{unit,integration,security,performance}/.../reports/` tree, mirroring every other module exactly.

---

## 7. Report Registry Design

```python
@dataclass(frozen=True)
class ReportDefinition:
    key: str                                  # stable, permanent — e.g. "sales.summary" (FR-RPT-312)
    name: str
    description: str
    domain: ReportDomain                      # enum: SALES | PURCHASE | INVENTORY | ACCOUNTING | CRM |
                                               #       INSTALLMENTS | EXECUTIVE | CROSSMODULE
    authoritative_source: str                 # e.g. "sales.ReportService.run_report" — traceable to §2.6
    required_permission: str                  # "reports.<domain>.view" (or executive/customer_360)
    export_permission: str | None             # "reports.<domain>.export" — None if not exportable
    domain_capability_key: str | None         # "sales" | ... | None for cross-module (resolved per-section instead)
    supported_filters: type[BaseModel]        # a typed Pydantic filter schema, never a raw dict
    supported_dimensions: tuple[str, ...]
    supported_measures: tuple[str, ...]
    sortable_fields: tuple[str, ...]
    export_formats: tuple[ExportFormat, ...]  # subset of {CSV, XLSX, PDF}
    drill_down_targets: tuple[DrillDownTarget, ...]
    branch_filterable: bool
    freshness: FreshnessClassification        # always TRANSACTIONAL_LIVE for Epic 11 (§32 spec, FR-RPT-230)
    pagination: PaginationStyle               # OFFSET | CURSOR | NONE (aggregate) — §19
    status: ReportStatus                      # NOW | DEFERRED
```

`REPORT_REGISTRY: dict[str, ReportDefinition]` is assembled at import time by importing each `catalog_<domain>.py` module, which calls `_register(definition)` into a shared private dict — the same "declare once, aggregate centrally" shape as `INITIAL_PERMISSIONS` (§2.5). **Only `status == NOW` entries are reachable through the router/execution service** — `DEFERRED` entries exist in the registry (for `/sp.tasks` sequencing and for the registry-consistency unit test, FR-RPT-004) but `ReportExecutionService` and the discovery endpoint both filter them out unconditionally (FR-RPT-011).

**Non-negotiables preserved**: curated (Python source, not a DB table — Assumption A7), typed (dataclass + Pydantic filter schema per entry, no `dict[str, Any]`), non-user-editable (no admin UI/endpoint can add a key), non-SQL-generating (`supported_filters` is a closed Pydantic model; nothing outside its declared fields is ever interpolated into a query — FR-RPT-002).

**Registry-consistency test (FR-RPT-004)**: a unit test iterates `REPORT_REGISTRY`, and for each entry with `status == NOW`, asserts `authoritative_source` resolves (via `importlib`) to an existing callable, and that `supported_filters`' fields are a subset of that callable's actual parameter names (via `inspect.signature`) — catching catalog/implementation drift automatically, not just at code-review time.

---

## 8. Metric Catalog Implementation

```python
@dataclass(frozen=True)
class MetricDefinition:
    semantic_id: str              # "metric.sales.gross" — stable, never renamed (mirrors report_key discipline)
    label: str
    description: str
    authoritative_domain: ReportDomain
    source_call: str              # "sales.ReportService — Net Sales via sales.summary"  (documentation only,
                                   # the metric is NEVER independently computed here — see below)
    date_basis: str
    money_precision: Literal["NUMERIC_15_2", "NUMERIC_20_6", "NA"]
    supports_comparison: bool
    inclusion_rule: str            # human-readable, matches spec §10's table verbatim
```

`METRIC_CATALOG` mirrors spec §10's table 1:1 (16 entries: Gross/Net Sales, Order Count, AOV, Sales Line Margin, Recognized Gross Profit Margin, Purchase Spend, AR Balance, AP Balance, Overdue Receivables, Operational Inventory Value, Cash Position, CRM Pipeline Value, CRM Win Rate, Outstanding Installment Principal, Overdue Installments). **A metric entry is documentation + a stable ID for dashboard-widget/report-column wiring — it is never itself a computation.** Every consumer (dashboard widget, report column, export field) resolves a metric by calling the adapter method named in `source_call`, never by re-deriving the number locally (FR-RPT-021). The distinct-name discipline (`metric.sales.line_margin` vs. `metric.accounting.gross_profit_margin`) from spec §10 is preserved verbatim — enforced by a unit test asserting no two `MetricDefinition`s share a `label` while having different `authoritative_domain`s and different `source_call`s (a direct, automatable check for FR-RPT-020/SC-004).

---

## 9. Report Execution Flow

`ReportExecutionService.execute(*, company_id, user_id, report_key, raw_filters, page, page_size, sort, comparison) -> BaseReportResult` is the **one** path (§5.2) — `BaseReportResult` (§10) is a concrete typed bound, never `Any`. Internally, `execute()` is a thin wrapper around a shared, reusable preamble (`_authorize_and_validate()`) plus dispatch — the preamble is also the exact seam `ReportExportService` reuses for export's authorization (§21), so the two paths can never silently diverge:

1. `definition = REPORT_REGISTRY.get(report_key)` → 404-class `ReportNotFoundError` if missing or `status == DEFERRED` (never distinguish the two in the error message — a deferred key looks identical to an unregistered one to the caller, preventing catalog-enumeration probing).
2. Domain entitlement — skip if `definition.domain_capability_key is None` (cross-module reports resolve per-section instead, §14):
   ```python
   if definition.domain_capability_key == "installments":
       # Installments never uses a plain entitled/not-entitled check — every request
       # (including fully-entitled ones) resolves through the continuity gate, whose
       # explicit Case-B allow-list is the single source of truth (§13).
       state = installments_continuity_gate.evaluate(company_id)
       if not installments_continuity_gate.is_allowed(definition.key, state):
           raise ReportNotEntitledError("installments")
   else:
       entitlement = platform_entitlement_service.resolve_effective_entitlement(
           company_id=company_id, capability_key=definition.domain_capability_key
       )
       if not entitlement.available:
           raise ReportNotEntitledError(definition.domain_capability_key)
   ```
3. `user_has_reports_permission(db, company_id, user_id, permission_code)` → `ReportPermissionDeniedError` (403-class) if `False`. `execute()` passes `definition.required_permission` (`.view`); `ReportExportService` passes `definition.export_permission` (`.export`) through the same preamble call (§21) — the only parameter that differs between the two callers.
4. `definition.supported_filters(**raw_filters)` — Pydantic validation; unknown fields rejected by `model_config = ConfigDict(extra="forbid")` → `FilterValidationError` (422-class), never silently dropped (FR-RPT-120).
5. `sort` checked against `definition.sortable_fields` → `UnsupportedSortFieldError` if not present (FR-RPT-123).
6. Branch filter accepted only if `definition.branch_filterable`; otherwise its mere presence in `raw_filters` was already rejected by step 4's `extra="forbid"` schema (the filter schema for non-branch-filterable reports simply has no `branch_id` field at all — FR-RPT-162 enforced structurally, not by a runtime `if`).

`_authorize_and_validate()` returns `(definition, validated_filters)` — steps 1–6 above. `execute()` continues:

7. Dispatch: `adapter = ADAPTER_REGISTRY[definition.domain]; result = adapter.run(definition.key, validated_filters, page, page_size, sort, comparison)` → a concrete `AggregateReportResult[T]` / `PaginatedReportResult[T]` / `CursorReportResult[T]` instance (§10), always a subtype of `BaseReportResult`.
8. Wrap (at the router layer, via `isinstance` narrowing over the three closed subtypes — no `cast`, no `Any`): `PaginatedResponse[RowT]` for a `PaginatedReportResult`, `CursorPage[RowT]` for a `CursorReportResult` (GL only), `StandardResponse[AggregateT]` for an `AggregateReportResult` (statement/KPI-dashboard reports).

`ReportExportService.export()` (§21) calls `_authorize_and_validate()` too, then diverges from step 7 — it never calls `adapter.run()` (which is built for one bounded page/aggregate), calling `adapter.count_export_rows()`/`adapter.iter_export_rows()` instead.

Every step raises a typed exception mapped 1:1 to `ErrorResponse` codes (§26) — no bare `HTTPException` inside the service (Constitution §14: services never raise HTTP exceptions directly; `router.py`'s exception handlers translate Reports' typed exceptions to the envelope, exactly like every other module's `exceptions.py` + a central handler already does).

---

## 10. Domain Adapter Strategy

### 10.1 Type boundary — no `Any` crosses out of a concrete adapter

`plan.md`'s own earlier draft of this section wrote `ReportAdapter.run(...) -> ReportResult[Any]`, which directly contradicted §32's "no `Any` escape hatches" — corrected here (2026-09-11 correction pass).

**The three zones, kept explicit and never conflated**:

1. **Legacy domain-service internals (outside Reports, unchanged)** — Sales/Purchase/Inventory/CRM/Installments' own report/KPI methods genuinely return `dict[str, Any]` / `list[dict[str, Any]]` / `tuple[list[dict[str, Any]], int]` today (§2.6). This is existing repository reality; Epic 11 does not (and per §57 must not) retrofit those modules' own return types.
2. **The adapter's translation implementation (the only place `Any` may appear in Reports' own code)** — inside each concrete `*_adapter.py`'s method bodies, code that reads a wrapped service's weakly-typed `dict`/`tuple` result and constructs a concrete, immediately-validated Pydantic row/result model. `Any` (or an untyped `dict`) may appear only as a local variable holding the *input* to this translation step — never as a parameter or return type of any adapter method itself, and never stored/passed onward.
3. **Reports' orchestration/public boundary (must be, and now is, fully typed)** — every adapter method signature, `ReportExecutionService`, the router, and every response schema.

**Corrected typed result model + `ReportAdapter` Protocol** (`services/adapters/base.py`):

```python
class BaseReportResult(BaseModel):
    meta: ReportEnvelopeMeta                   # §18 — report_key, applied filters, resolved period, freshness, drill-down refs

class AggregateReportResult(BaseReportResult, Generic[AggregateT]):
    data: AggregateT                            # statements, KPI dashboards — pagination == NONE

class PaginatedReportResult(BaseReportResult, Generic[RowT]):
    items: list[RowT]
    total: int                                   # offset-paginated list reports

class CursorReportResult(BaseReportResult, Generic[RowT]):
    items: list[RowT]
    has_more: bool
    next_cursor: str | None                       # accounting.gl only (§19)

ReportResultT_co = TypeVar("ReportResultT_co", bound=BaseReportResult, covariant=True)

class ReportAdapter(Protocol[ReportResultT_co]):
    def run(
        self, report_key: str, filters: BaseModel, page: int, page_size: int,
        sort: str | None, comparison: ComparisonRequest | None,
    ) -> ReportResultT_co: ...

    def count_export_rows(self, report_key: str, filters: BaseModel) -> int: ...   # §21

    def iter_export_rows(
        self, report_key: str, filters: BaseModel, sort: str | None, batch_size: int,
    ) -> Iterator[list[RowT]]: ...                                                 # §21 — bounded batches, never a full list
```

A single adapter class (e.g. `SalesAdapter`) serves several report keys whose concrete result shapes differ (some paginated, some aggregate) — it is declared `ReportAdapter[BaseReportResult]`, the common bound, and its `run()` implementation constructs whichever concrete subtype (`PaginatedReportResult[SalesSummaryRow]`, `AggregateReportResult[SalesKpiSet]`, ...) matches the requested `report_key`; both are valid, statically-checkable subtypes of `BaseReportResult` — no `Any`, no `cast`, no `# type: ignore`. `ADAPTER_REGISTRY: dict[ReportDomain, ReportAdapter[BaseReportResult]]` is therefore itself fully typed. `ReportExecutionService.execute()` and `ReportExportService` both receive `BaseReportResult` back (never narrower, since the concrete subtype genuinely isn't known until a runtime `report_key` string is resolved) and narrow it via `isinstance` over the three closed subtypes at the point they need shape-specific fields (the router's response-wrapping step, §9 step 8) — a normal, fully-typed closed-union pattern, not a weak/dynamic one.

Each concrete adapter is a small dispatch table keyed by `report_key` inside its own domain, translating Reports' validated filter object into that domain's actual method signature, and translating the domain's actual return shape into one of the three typed result models above **before returning**. No adapter method contains business logic — only parameter mapping and shape translation (spec §11's explicit boundary).

| Domain | Adapter maps Reports filters → | Return-shape translation |
|---|---|---|
| Sales | `ReportService.run_report(report_type=..., params={...})` | `ReportResponse{rows: list[dict]}` → adapter's own typed `SalesReportRow` list + `total` |
| Purchase | `ReportService.purchase_order_summary(...)` (+ 5 sibling methods) | plain `dict[str, Any]` → typed per-report Pydantic model (one per Purchase report family) |
| Inventory | `ReportQueryService.inventory_summary(...)` (+ siblings) | plain `dict[str, Any]` → typed per-report model; `inventory.valuation` response **must** carry `valuation_basis="operational_wac"` (FR-RPT-071) added by the adapter, not by Inventory's own service |
| Accounting | `FinancialStatementService.get_trial_balance/get_pl/get_balance_sheet/get_cash_flow`, `AccountsReceivableService`, `AccountsPayableService`, `ReportService.get_gl_report` (cursor), `FinancialKPIService.get_dashboard_kpis` | Statement/aging dicts → typed models; **GL is the one report whose adapter returns `CursorPage[GlLineRow]` instead of `PaginatedResponse`** — documented exception (§19), not forced into offset shape |
| CRM | `CrmReportingService.get_pipeline_report/get_dashboard/...` | `CrmDashboard`/dict → typed models |
| Installments | `InstallmentReportingService.get_contract_register(...)` (+ 7 siblings) | `tuple[list[dict], int]` → `PaginatedReportResult`-shaped typed rows; the Case A/B/allow-list decision (§13) is resolved by `ReportExecutionService`/`ReportExportService` **before** the adapter is ever called (§9 step 2), not inside the adapter — the adapter itself is unaware of entitlement state, matching every other domain's adapter |

**Error propagation**: if a wrapped service raises (timeout, unconfigured prerequisite, e.g. Accounting with no COA yet), the adapter catches only that domain's own documented exception types and re-raises as Reports' `UnavailablePrerequisiteError` — it never lets an unrelated `AttributeError`/`KeyError` leak as an unhandled 500 with internal detail (FR-RPT-272, FR-RPT-341).

**Pagination mapping**: adapters normalize their domain's native style (offset+total for Installments/Sales/Purchase/Inventory/CRM; aggregate/no-pagination for Accounting statements & all KPI dashboards; cursor+has_more for GL only) into exactly one of the three typed result models in §10.1 — never inventing a fourth shape.

**Export mapping** (corrected, 2026-09-11 — see §21 for full detail): export does **not** call `adapter.run()`, which is built for one bounded page/aggregate and would otherwise tempt a "just call it with `page_size=total`" shortcut that materializes an unbounded result set in memory. Instead `ReportExportService` calls `adapter.count_export_rows()` (bounded-cost count, checked against the format's row limit **before** any retrieval) and, once within limit, `adapter.iter_export_rows()` (yields typed row batches, never a full list) — both declared on the same `ReportAdapter` Protocol (§10.1) alongside `run()`, so every adapter implements the bounded-export seam as a first-class part of its contract, not a bolt-on. Authorization/validation is still provably identical to the online path because both `execute()` and `export()` call the same `_authorize_and_validate()` preamble (§9) — only retrieval diverges, never security (FR-RPT-213).

---

## 11. Permissions / RBAC

`REPORTS_PERMISSIONS: tuple[PermissionDefinition, ...]` added to `modules/users_roles/constants.py`, unioned into `INITIAL_PERMISSIONS` (§2.5 pattern), 13 codes exactly matching spec §33's table:

```
reports.executive.view
reports.sales.view            reports.sales.export
reports.purchase.view         reports.purchase.export
reports.inventory.view        reports.inventory.export
reports.accounting.view       reports.accounting.export
reports.crm.view              reports.crm.export
reports.installments.view     reports.installments.export
reports.customer_360.view
reports.branch_performance.view    (seeded now — cheap, no behavior; endpoint stays unregistered/404 until FR-RPT-012 is satisfied, §38)
reports.saved_view.manage
```

`user_has_reports_permission(db, company_id, user_id, permission_code, *, user_roles=None) -> bool` in `services/permission_check.py` — identical shape/chain to every other module's function (`CompanyMemberRepository` → `role_id` → `RolePermissionRepository.get_permissions_for_role()`), not a shared base class (matching the repo's actual, if duplicative, convention rather than introducing a premature shared abstraction — Constitution §7 DRY is satisfied at the *pattern* level across modules, not by inventing a shared base none of the six existing modules uses). Each permission is checked independently — no implicit grants (FR-RPT-240..242); `.view` and `.export` are always separate codes, enforced structurally by having genuinely separate `required_permission`/`export_permission` fields on `ReportDefinition` (§7), so an endpoint literally cannot check the wrong one by accident.

Role-to-permission assignment remains fully tenant-configurable via the existing RBAC role/permission UI — Epic 11 hardcodes no role mapping (FR-RPT-243); spec §33's role table is illustrative only.

---

## 12. Entitlements & Reports Capability Default

**Decision (locking spec §18/FR-RPT-255): `reports` is disabled by default.**

Implementation:
1. `CapabilitySeedService.MODULE_CAPABILITY_CATALOGUE` gains a seventh tuple: `{"key": "reports", "module": "reports", "display_name": "Reports & Analytics"}` (also fixes the pre-existing stale "five modules" docstring comment while touching this file — a one-line drive-by fix, not scope creep).
2. New `backend/modules/reports/services/feature_flag_service.py::ReportsFeatureFlagService` — same shape as `CrmFeatureFlagService`/`InstallmentsFeatureFlagService`: one module-wide flag row, `is_enabled(company_id) -> bool` defaulting to `False` when no row exists, `enable()`/`disable()` for Platform Admin's existing entitlement-management surface to call.
3. New `ReportsModuleEnablementProvider` (`modules/platform_admin/services/module_enablement.py`), mirroring `CrmModuleEnablementProvider`/`InstallmentsModuleEnablementProvider` exactly, wrapping `ReportsFeatureFlagService`.
4. `get_module_enablement_provider()`'s dispatch adds a `"reports"` branch pointing at the new provider — **this is the one required edit to `platform_admin`'s dispatch table**; without it, `resolve_effective_entitlement(capability_key="reports")` raises `ValueError` per the current code (§2.3 finding).
5. Router mount, mirroring CRM's three-dependency pattern exactly (`api/v1/router.py`):
   ```python
   reports_entitlement_gate = require_capability_entitled("reports")
   router.include_router(
       reports_router,
       prefix="/companies/{company_id}/reports",
       dependencies=[
           Depends(get_current_company_member),
           Depends(reports_entitlement_gate),
           Depends(require_reports_enabled),
       ],
   )
   ```
6. Every domain-specific report additionally re-checks its own domain's entitlement **inside** `ReportExecutionService` (§9 step 2) — `reports` being entitled never implies any domain is (FR-RPT-251).
7. Domain entitlement is resolved identically for all six domains via `resolve_effective_entitlement()` regardless of current default-resolved state — Sales/Purchase/Inventory/Accounting are never hardcoded as "always on" (FR-RPT-254), so a future Plan restriction or `EntitlementOverride` affecting any of them is honored automatically, with zero Reports code change.
8. Disabling `reports` never deletes `SavedReportView` rows — they simply become unreachable until re-entitled (FR-RPT-253); no cascade/delete logic is added.
9. Platform Admin's existing entitlement-toggle surface manages `reports` the same way it manages `crm`/`installments` today — no new Platform Admin UI/endpoint concept, just one more capability key it already knows how to list/toggle (FR-RPT-250, §38 spec unaffected).

This satisfies governing-prompt §18/§19 exactly: the decision is explicit, uses the existing entitlement platform (no parallel flag system), and is fully reversible without a schema migration if a future product decision flips the default (only the seed migration's `default_enabled` value would need to change, and only for *newly created* companies going forward — existing companies keep whatever their toggle row already says).

---

## 13. Installments Servicing-Continuity Design

**Corrected, 2026-09-11 correction pass**: the plan's earlier draft interpreted Case B as "every Now Installments report, since Reports is read-only anyway," including `installments.plan_performance`. That is wider than the approved specification's servicing-continuity intent — Case B exists to keep **existing obligations** explainable/inspectable/reconcilable, not to keep the entire Installments analytics surface open merely because Reports itself never writes. Corrected below with an explicit allow-list.

`services/installments_continuity_gate.py`:

```python
class InstallmentsAccessState(str, Enum):
    ENTITLED_FULL = "entitled_full"
    SERVICING_CONTINUITY = "servicing_continuity"   # Case B
    UNAVAILABLE = "unavailable"                       # Case A

class InstallmentsServicingContinuityGate:
    # Only reports needed to explain, inspect, or reconcile an EXISTING obligation.
    # installments.plan_performance (adoption-by-template analytics) and the standalone
    # installments.dashboard (13-metric bundle, not all of which are obligation-tied) are
    # deliberately excluded — see rationale below.
    _SERVICING_CONTINUITY_ALLOWLIST: frozenset[str] = frozenset({
        "installments.register",             # contract register + drill-down to contract/schedule detail
        "installments.collections",          # payments collected against existing contracts
        "installments.due_overdue",          # due/overdue status of existing schedule lines
        "installments.aging",                # delinquency buckets for existing contracts
        "installments.settlement_writeoff",  # settlement/default/write-off history of existing contracts
    })

    def __init__(self, entitlement_service: PlatformEntitlementService,
                 installment_reporting_service: InstallmentReportingService) -> None: ...

    def evaluate(self, company_id: UUID) -> InstallmentsAccessState:
        entitlement = self._entitlement_service.resolve_effective_entitlement(
            company_id=company_id, capability_key="installments"
        )
        if entitlement.available:
            return InstallmentsAccessState.ENTITLED_FULL
        _, total = self._installment_reporting_service.get_contract_register(
            company_id, skip=0, limit=1
        )
        return (
            InstallmentsAccessState.SERVICING_CONTINUITY if total > 0
            else InstallmentsAccessState.UNAVAILABLE
        )

    def is_allowed(self, report_key: str, state: InstallmentsAccessState) -> bool:
        if state is InstallmentsAccessState.ENTITLED_FULL:
            return True                                              # every "Now" Installments report, normally
        if state is InstallmentsAccessState.SERVICING_CONTINUITY:
            return report_key in self._SERVICING_CONTINUITY_ALLOWLIST  # explicit allow-list only
        return False                                                  # UNAVAILABLE (Case A) — nothing
```

`evaluate()` is the **exact seam** requested by governing prompt §14: Reports asks Installments (via its own already-self-authorizing `get_contract_register`, which internally calls `InstallmentAccessPolicy.authorize(operation=READ)` — always permitted, §2.4) whether any contract exists at all, and combines that with the standard entitlement check every other domain already uses. **No Installments entitlement logic is duplicated** — Reports never re-implements `InstallmentAccessPolicy`; it only asks a question Installments' own existing method already answers as a side effect of its `total` return value. `is_allowed()` is Reports' **own** policy layered on top — it does not ask Installments anything further; the allow-list is Reports-owned data, not duplicated Installments logic.

**Final rule, stated once, applied everywhere**:

| Installments state | Behavior |
|---|---|
| Entitled | Every approved "Now" Installments report accessible normally — no restriction. |
| **Case A** (disabled, no serviceable obligations) | All `installments.*` report surfaces unavailable — the normal, unconditional module-not-entitled behavior (FR-RPT-252). |
| **Case B** (disabled, serviceable obligations exist) | **Only** the explicit servicing-continuity allow-list (`installments.register`, `.collections`, `.due_overdue`, `.aging`, `.settlement_writeoff`) remains available, read-only. `installments.plan_performance` and the standalone `installments.dashboard` report key are **not** available under Case B. |

Applied uniformly at three call sites, via `installments_continuity_gate.is_allowed(report_key, state)`:
- `ReportExecutionService` (§9 step 2) — for every `installments.*` report key; a Case-B request for a non-allow-listed key (e.g. `installments.plan_performance`) raises the identical `ReportNotEntitledError("installments")` a Case-A request would.
- `ExecutiveDashboardService` — the Outstanding Installment Principal / Overdue Installments widget (spec FR-RPT-041's documented exception) is unaffected by this correction: both metrics are sourced from `installments.aging`/`installments.due_overdue`-shaped data, which is on the allow-list. This is the **only** Installments-dashboard-shaped surface available under Case B — the standalone, full 13-metric `installments.dashboard` report key is not (see allow-list rationale above); a future spec amendment could promote specific additional dashboard metrics onto the allow-list if a genuine obligation-explaining need for them is identified, but Epic 11 does not do so speculatively.
- `Customer360Service` — the Installments section (§14) always draws from contract/aging/collection-shaped data (never plan-adoption analytics), so it is inherently allow-list-scoped already; `is_allowed()` is still called explicitly for consistency and to fail closed if that ever changes.

Every response for a report served under `SERVICING_CONTINUITY` state additionally carries a `read_only_servicing_continuity: true` metadata flag (§26) so the frontend can render an explanatory banner.

Case A behaves identically to any other disabled domain (`ReportNotEntitledError`) — no special-casing beyond routing through this gate first.

---

## 14. Customer 360 Design

`Customer360Service.get(company_id, user_id, customer_id) -> Customer360Response`:

1. **Base gate**: `reports` entitlement (already enforced at router mount) + `user_has_reports_permission(..., "reports.customer_360.view")` → deny (generic 403) if absent.
2. **Customer master lookup + authorization**: resolve `customer_id` via Sales' own `CustomerRepository.get_by_id(company_id, customer_id)` (tenant-scoped). If not found *or* found but belonging to a different tenant → **identical, indistinguishable "not found" `ErrorResponse`** (reuses the platform's existing not-found error code — no new IDOR-prone code path). If found, additionally check the requesting user holds Sales' own customer-view permission (exact code TBD — confirmed during `/sp.tasks` against Sales' `permission_check.py`; provisional name `sales.customers.view`) — **this permission gates whether the identity/master-data section itself may ever be returned** (FR-RPT-116).
3. **Section composition** — four independent attempts, each producing one of three discriminated states:
   ```python
   class SectionState(str, Enum):
       PRESENT = "present"
       OMITTED = "omitted"          # not entitled / not permitted
       UNAVAILABLE = "unavailable"  # authorized, but no data / not configured

   class OmittedSection(BaseModel):
       state: Literal[SectionState.OMITTED]
       reason: Literal["not_entitled", "not_permitted"]

   class UnavailableSection(BaseModel):
       state: Literal[SectionState.UNAVAILABLE]
       reason: Literal["not_configured", "no_data_source"]

   SalesSection = Annotated[
       PresentSalesSection | OmittedSection | UnavailableSection, Field(discriminator="state")
   ]
   ```
   - **Sales**: gated by `reports` (already true) + `reports.sales.view` + `sales` entitlement. If authorized, always `PRESENT` (even zero transactions — Sales has no "not configured" concept; a real zero is a real zero).
   - **Accounting AR**: gated by `reports.accounting.view` + `accounting` entitlement. If authorized: `PRESENT` with the real (possibly zero) AR balance if a Chart of Accounts is configured for the tenant; `UNAVAILABLE(reason="not_configured")` if Accounting has no COA yet (exact "is COA configured" check confirmed during `/sp.tasks` against Accounting's existing setup-state service — not fabricated here).
   - **CRM**: gated by `reports.crm.view` + `crm` entitlement (CRM disabled → `OMITTED(reason="not_entitled")`, no exception — matches spec §19's unconditional CRM rule).
   - **Installments**: gated by `reports.installments.view`; entitlement resolved via `InstallmentsServicingContinuityGate.evaluate()` (§13) — `ENTITLED_FULL` or `SERVICING_CONTINUITY` → `PRESENT` (the section's underlying data is always contract/aging/collection-shaped, i.e. already within the §13 allow-list by construction — `is_allowed()` is still called explicitly per report reference this section renders, so a future data addition to this section fails closed rather than silently exceeding Case B's scope); `UNAVAILABLE` (gate) → `OMITTED(reason="not_entitled")`.
4. **Minimum-useful-response rule (FR-RPT-116)**: if every one of the four sections is `OMITTED`, the service checks whether step 2's Sales customer-view permission passed. If yes → return identity-only response with all four sections explicitly `OMITTED`. If no → the *entire* request is denied with the same generic not-found `ErrorResponse` from step 2, never a distinguishable empty-shell response.
5. Nothing is cached, persisted, or blended — every call is a fresh composite read (NG2, spec §20.1 "explicitly not a new source of truth").

This satisfies section-level compound authorization (FR-RPT-111), the three-state result model (FR-RPT-114), the confirmed-zero-vs-unavailable distinction (FR-RPT-115), and IDOR-safety (FR-RPT-116) exactly as specified, using only the existing per-domain entitlement/permission primitives — no new authorization primitive is invented.

---

## 15. Saved Report Views

```python
class SavedReportView(TenantBaseModel):
    __tablename__ = "saved_report_views"
    user_id: Mapped[UUID]                    # owner — FK users, indexed with company_id
    report_key: Mapped[str]                  # not FK'd to the registry (it's code, not a table) — validated at write/load time
    name: Mapped[str]
    schema_version: Mapped[int]              # new convention (§2.8) — starts at 1
    filter_config: Mapped[dict[str, Any]]    # JSONB — validated against FilterConfigV1 Pydantic model before persist
    grouping: Mapped[list[str] | None]       # JSONB
    sorting: Mapped[str | None]
    visible_columns: Mapped[list[str] | None]  # JSONB
    date_preset: Mapped[str | None]
    # id, company_id, created_at, updated_at, created_by, is_deleted, deleted_at — inherited from TenantBaseModel
```

`FilterConfigV1(BaseModel, extra="forbid")` — a validated shape (not arbitrary JSON), whose fields are restricted at *save time* to whatever the referenced `ReportDefinition.supported_filters` model for `report_key` currently declares (FR-RPT-201): the service round-trips the incoming filter payload through `definition.supported_filters(**payload)` before persisting, so an invalid or unregistered field is rejected at save time, not merely at load time. `schema_version` exists so a future structural change to saved-view storage has an explicit compatibility seam (governing prompt §23) — Epic 11 ships only version 1, no migration logic needed yet, just the column.

**Ownership & tenant scope**: every repository method takes `(company_id, user_id, ...)`; a user can only ever list/load/update/delete rows matching both (FR-RPT-205). **No sharing, no "list others'" permission** exists in Epic 11 (NG5) — `reports.saved_view.manage` is the only relevant permission, and it only ever operates on the caller's own rows.

**Re-validation at load** (FR-RPT-203/204): `SavedViewService.load(view_id, company_id, user_id)`:
1. Fetch row scoped to `(company_id, user_id)` → `SavedViewNotFoundError` if absent/owned-by-another-user (identical error either way — no ownership-probing signal).
2. `REPORT_REGISTRY.get(row.report_key)` → `RetiredReportKeyError` if the key no longer exists or is `DEFERRED`.
3. Re-run the full gate chain from §9 steps 2–4 (domain entitlement, `reports.<domain>.view` permission, filter re-validation against the *current* `supported_filters` schema) using the loading user's **current** state — a role change or module disablement since save time is honored immediately, never bypassed (FR-RPT-203).

**Deletion (corrected, 2026-09-11 correction pass — final, unambiguous decision): soft delete only.** `SavedReportView` inherits `TenantBaseModel`, which carries `is_deleted`/`deleted_at` as mandatory columns; `DELETE /reports/saved-views/{view_id}` sets them using the repository-standard soft-delete pattern every other model in the repo already uses (Constitution §17) — there is no hard-delete code path anywhere in the normal Reports API. Concretely:
- The repository's default list/load queries filter `is_deleted = false` (the platform's existing default-exclusion convention) — a soft-deleted view disappears from `GET /saved-views` and from `GET /saved-views/{view_id}` (which returns the same `SavedViewNotFoundError` as a row that never existed) immediately after deletion.
- Owner isolation is unaffected by this correction: a soft-deleted view's ID is still scoped to `(company_id, user_id)` before the soft-delete check even applies, so no other user or tenant can discover a deleted row's existence by ID-probing — a deleted view, a never-existing view, and another user's/tenant's view all return the identical `SavedViewNotFoundError`.
- No restore UI or API endpoint is planned in Epic 11 — the soft-deleted row simply persists (per the platform's audit-friendly convention) with no path back to visibility; this is a deliberate, documented no-op capability, not a gap.
- No physical/hard-delete method is exposed anywhere in Reports' own repository or service layer for this table.

---

## 16. Database / Migrations

All in `backend/migrations/versions/`, plain numeric revisions continuing from `072`. **Exact final numbering/splitting is a `/sp.tasks` decision** — candidates below, sequenced by dependency:

| # (candidate) | Migration | Mirrors |
|---|---|---|
| `073` | `reports_capability_seed` — adds `"reports"` row to the Capability catalogue seed | `070_installments_capability_seed.py` |
| `074` | `reports_permission_seed` — seeds `REPORTS_PERMISSIONS` for new companies + backfills existing companies | `071_installments_permission_backfill.py` |
| `075` | `reports_saved_report_views_table` — creates `saved_report_views` with indexes (§17) | `062_installments_foundation.py`-style table-creation migration |
| `076` | `reports_audit_log_table` — creates `reports_audit_log` with indexes (§17) | Accounting's/Installments' own audit-table migration |

Every migration includes a real `downgrade()` (drops indexes then table, or removes seeded rows by key — matching `070`/`071`'s actual reversal logic, §2.8). Permission/capability changes are **migration-driven for the seed data, service-driven for runtime resolution** — i.e., the migration inserts rows; `RoleSeedService`/`CapabilitySeedService` remain the idempotent runtime seeders new companies go through at creation time, exactly like every prior module's onboarding (§2.2, §2.5) — Epic 11 introduces no third mechanism.

---

## 17. Index Strategy

New indexes are scoped **only** to Reports' own two new tables and the one genuinely new cross-module lookup path (Customer 360) — no index is added for any wrapped report, per governing-prompt §25's explicit instruction (wrapped reports already have whatever indexes their owning module already validated):

- `saved_report_views`: `ix_saved_report_views_company_user (company_id, user_id)` (list-my-views lookup), `ix_saved_report_views_company_report_key (company_id, report_key)` (registry-retirement audit/cleanup queries).
- `reports_audit_log`: `ix_reports_audit_log_company_created_at (company_id, created_at)` (audit review, time-ordered), `ix_reports_audit_log_company_actor (company_id, actor_id)`.
- **Customer 360**: no new index expected — Sales' `Customer` PK lookup and Accounting's AR-by-customer query path are both already indexed by their owning modules for their own existing endpoints (aging report, customer statement); `/sp.tasks` MUST confirm this with an `EXPLAIN` check during implementation rather than assume it, but no index is *planned* here speculatively.
- **Export pagination paths**: reuse whatever offset/cursor indexes the wrapped service's own existing paginated query already relies on — Reports adds no new query shape here, only a row-count ceiling check (§21).

---

## 18. API Design

Base path: `/api/v1/companies/{company_id}/reports/...` (existing versioning convention, Constitution §32).

| Endpoint | Method | Envelope | Notes |
|---|---|---|---|
| `/reports/discovery` | GET | `StandardResponse[ReportDiscoveryResponse]` | FR-RPT-032 — permission+entitlement-filtered list of reachable `ReportDefinition` summaries |
| `/reports/{report_key}` | GET | `PaginatedResponse[T]` / `CursorPage[T]` (GL only) / `StandardResponse[T]` (aggregate) | The one execution path (§9) |
| `/reports/{report_key}/export` | GET | `Response` (file) | §21 |
| `/reports/dashboard` | GET | `StandardResponse[ExecutiveDashboardResponse]` | §9 spec |
| `/reports/customer-360/{customer_id}` | GET | `StandardResponse[Customer360Response]` | §14 |
| `/reports/saved-views` | GET, POST | `PaginatedResponse[SavedViewRead]` / `StandardResponse[SavedViewRead]` | §15 |
| `/reports/saved-views/{view_id}` | GET, PATCH, DELETE | `StandardResponse[SavedViewRead]` | §15, load re-validates |

Every response carries, per FR-RPT-311: resolved `report_key`, applied filters, resolved period (with timezone-derived boundaries), returned measures/dimensions, pagination metadata (where applicable), comparison data (where requested), `freshness` classification, and drill-down references — implemented as a common `ReportEnvelopeMeta` object embedded in each typed response's top level (not a change to `StandardResponse[T]`/`PaginatedResponse[T]` themselves, which stay exactly as `core/schemas/` already defines them per FR-RPT-310/Assumption A10 — `T` is simply a schema that always includes this metadata block).

---

## 19. Pagination & Filtering

- Default: `PaginationParams`/`PaginatedResponse[T]` verbatim (page ≥ 1, page_size 1–100 default 20) — FR-RPT-190.
- **Documented exception**: `accounting.gl` uses a module-local `CursorPage[T]{items: list[T], has_more: bool, next_cursor: str | None}` schema (opaque cursor string encoding Accounting's native `(date, UUID, int)` tuple) — matching governing-prompt §28's explicit instruction not to force cursor pagination into an artificial offset shape. This is the **only** report using this schema; every other list-shaped report is offset-paginated.
- Aggregate/dashboard-shaped endpoints (all KPI dashboards, Executive Dashboard, financial statements, Customer 360) are exempt from pagination entirely (FR-RPT-192) — `pagination == PaginationStyle.NONE` on their `ReportDefinition`.
- Filter schemas: one typed Pydantic model per report (or a small family sharing a common base — e.g. `DateRangeFilter` mixin for period + a `BranchFilterMixin` only for the six branch-filterable reports), `extra="forbid"`, referenced by `ReportDefinition.supported_filters`. No single giant untyped filter dict anywhere (FR-RPT-120, governing-prompt §29).
- Stable sort: every offset-paginated report declares a default sort with a secondary tie-break on `id`, preventing skip/duplicate across pages (FR-RPT-191) — enforced in the adapter's call to the wrapped service (most already support this internally; where a wrapped service doesn't, the adapter appends the tie-break client-side only for the current page's rows, never re-sorting a full unbounded result set in Python).

---

## 20. Date / Comparison / Money Handling

- **Date/time**: `services/date_range_service.py` resolves the 11 presets from spec §22 using `Company.default_timezone` (IANA, default `UTC`) and the existing `core/utils/datetime.py::ensure_utc()`/`utcnow()` — no new timezone library, no new infra (governing-prompt §30's explicit instruction). Boundaries are half-open `[start, end)` in company-local time, converted to UTC for the query (FR-RPT-131/132). Each `ReportDefinition` declares its own driving date field per §14–§19 spec sections (`invoice_date`/`order_date` for Sales, `posting_date` for Accounting, `created_at`+documented-gap for Purchase POs, `received_at` for goods receipts, etc.) — never a blanket `created_at` default.
- **Comparison**: `services/comparison_service.py` — given a metric/report result for the current period, compute the comparison period (previous period/month/quarter/year, same-period-last-year) and call the **same adapter method a second time** for that period (never re-deriving the number differently) — returns `{absolute_change, percentage_change, comparability: FULL | NOT_COMPARABLE | PARTIAL_CURRENT_PERIOD}`. Zero-denominator and incomplete-period rules follow spec §23 exactly (FR-RPT-141/142/143).
- **Money**: `services/money_normalization.py` — all arithmetic in `Decimal`; cross-precision combination (`NUMERIC(15,2)` Sales/Purchase + `NUMERIC(20,6)` Accounting/Installments) is performed at `NUMERIC(20,6)` and rounded only at final display using `ROUND_HALF_UP` at the tenant's configured currency decimal places (Assumption A4, FR-RPT-150/151/154) — mirrors Installments' own `Decimal("0.000001")`/`ROUND_HALF_UP` precedent exactly, no new rounding convention invented. Every monetary field in a response carries its currency code; cross-currency summation without an Accounting-sourced exchange rate is structurally impossible because the response schemas group amounts by currency rather than pre-summing them (FR-RPT-152) — where a report genuinely needs one base-currency total (P&L/Balance Sheet), it reuses Accounting's own existing `CurrencyService` translation unchanged (FR-RPT-153). Multi-currency support beyond Accounting is **not assumed** for Sales/Purchase/Inventory/CRM — `/sp.tasks` MUST verify each module's actual currency model before any report combines figures across them (Assumption A5, flagged as a per-adapter implementation check, not fabricated here).

---

## 21. Exports & Export Security

**Corrected, 2026-09-11 correction pass**: the plan's earlier draft described export retrieval as "pagination replaced by a full-scope count-then-fetch," which was ambiguous enough to be misread as "load the whole 25k–50k-row result into one Python list." That is explicitly **not** the architecture. This section separates the two concerns the correction requires: (a) the authorization/validation path, which export reuses byte-for-byte from the online path, and (b) row *retrieval*, which is bounded/chunked and never materializes an unbounded result set in memory.

### 21.1 Authorization/validation path — identical to the online report path, not a parallel one

`ReportExportService.export(report_key, raw_filters, sort, format, company_id, user_id)` calls the **exact same** `ReportExecutionService._authorize_and_validate()` preamble `execute()` uses (§9), passing `definition.export_permission` instead of `.view`:

```
report lookup (Registry, FR-RPT-001)
→ reports entitlement (already enforced at router mount, §12)
→ domain entitlement, including Installments' Case A/B/allow-list resolution via
  InstallmentsServicingContinuityGate.is_allowed() (§13) — identical to the online path;
  a report unreachable under Case B for viewing is equally unreachable for export
→ RBAC: definition.export_permission (distinct from .view — FR-RPT-212)
→ filter validation (definition.supported_filters, extra="forbid")
→ sort validation (definition.sortable_fields)
→ branch semantics (definition.branch_filterable)
```

No step here is reimplemented for export — there is exactly one authorization/validation code path in the whole module, shared by both callers (FR-RPT-213).

### 21.2 Bounded export retrieval seam

Once authorized, export diverges from `execute()`'s dispatch (which calls `adapter.run()`, built for one bounded page/aggregate). Instead:

```python
count = adapter.count_export_rows(definition.key, validated_filters)         # cheap, bounded-cost query
limit = EXPORT_ROW_LIMIT_XLSX if format is ExportFormat.XLSX else EXPORT_ROW_LIMIT_CSV
if count > limit:
    raise ExportTooLargeError(report_key, count, limit)                     # rejected BEFORE any row retrieval

for batch in adapter.iter_export_rows(definition.key, validated_filters, sort, batch_size=EXPORT_BATCH_SIZE):
    writer.write_rows(batch)                                                 # bounded per-batch, never the full set at once
```

`count_export_rows()` reuses the wrapped service's own existing count capability (most already return a `total`/`has_more` alongside their first page — no new aggregation query is invented per adapter; where a wrapped service's cheapest count path still requires a bounded probe, e.g. `limit=1`, that is acceptable since only a scalar count is read, not row data). `iter_export_rows()` yields typed row batches (`Iterator[list[RowT]]`, §10.1 — never `Any`, never a full materialized list) by internally paging the wrapped service across its native pagination (offset pages for Sales/Purchase/Inventory/CRM/Installments; cursor pages for GL, §21.4) and yielding each page-sized batch as it's fetched from the database — the database round-trip itself stays bounded to one page at a time, never one query fetching the entire filtered set.

The row-limit check (against `count`) always happens **before** `iter_export_rows()` is ever called — no batch retrieval is attempted for an over-limit request.

### 21.3 CSV strategy

`csv.writer` writes each batch's rows as `iter_export_rows()` yields them, appending to an in-memory buffer; every cell is passed through the centralized `services/csv_sanitizer.py::sanitize_cell(value)` — prefixes a value starting with `=`, `+`, `-`, or `@` with a leading `'` (single quote), the standard neutralization (FR-RPT-216). This is the **only** export path in the repo with this protection; Sales/Purchase/Inventory/Accounting's own existing export services are **not** retrofitted by Epic 11 (out of scope — flagged as pre-existing debt, §36). Because the repository's established export contract returns a final `bytes` payload (§2.7 — no async/streaming-response precedent exists anywhere today), the CSV *file* is still assembled into one `bytes` object before being returned; the invariant this correction protects is that **database retrieval and Python object construction stay bounded per batch**, not that the final byte buffer is smaller than the file. If a future `/sp.tasks`/implementation pass finds the repo's FastAPI conventions cleanly support a genuine `StreamingResponse`, that remains a valid **implementation option** to note — not mandated here, since no such precedent exists to build on today (governing-prompt §3's "prefer repository-established structure").

### 21.4 XLSX strategy

openpyxl's `write_only=True` streaming workbook mode (a real, purpose-built openpyxl feature for exactly this: writing large sheets without holding the whole workbook object graph in memory) consumes the same `iter_export_rows()` batches, with `sanitize_cell()` applied per cell before writing. XLSX still holds more in-memory structure than CSV's row-by-row stream even in `write_only` mode — this is the documented reason `EXPORT_ROW_LIMIT_XLSX` is configured **lower** than `EXPORT_ROW_LIMIT_CSV`. Final row ceilings for both formats are determined by implementation-time benchmarking (§40), not fixed here.

### 21.5 GL cursor strategy

`accounting.gl`'s adapter implements `iter_export_rows()` by consuming Accounting's **existing** `get_gl_report(cursor=...)` mechanism natively — following `next_cursor` page-by-page, yielding each page's rows as one batch — never converted into an artificial offset scan (consistent with §19's already-documented cursor exception). This is the same cursor advance Accounting's own router already performs for online GL browsing; export just keeps calling it until `has_more` is `False` instead of stopping after one page.

### 21.6 PDF

Unaffected by this correction — PDF export (Trial Balance, P&L, Balance Sheet, Cash Flow, AR/AP statements only) delegates directly to Accounting's existing, already-bounded `report_export.py::export_to_pdf()` (a statement/aggregate export, not a row-list export, so §21.2's batching seam does not apply to it); no new PDF generation code is written (FR-RPT-211, governing-prompt §36).

### 21.7 Filename & empty results

Filename derived deterministically from `report_key` + resolved period + format extension (e.g. `sales-summary_2026-08-01_2026-08-31.csv`), no user-supplied string interpolated unescaped (FR-RPT-215). An empty result set (`count == 0`) still produces a valid file with headers and zero data rows, not an error (FR-RPT-219).

### 21.8 Export audit durability — no file without a durable audit record

Directly implements the correction's binding invariant: **a successfully delivered export must have a successfully persisted audit record; there is no successful file delivery without durable export audit persistence.** Exact ordering inside `ReportExportService.export()`:

```
1. _authorize_and_validate()                    (§21.1 — raises on any authorization/validation failure)
2. count_export_rows() → reject if over limit    (§21.2 — raises ExportTooLargeError, no file generated)
3. iter_export_rows() → generate the full file bytes (CSV/XLSX) or call export_to_pdf() (PDF)
4. ReportsAuditService.record(...)               (§22 — stages the audit row: actor, tenant, report_key,
                                                    filter scope, format, row count)
5. commit the audit transaction
6. ONLY if step 5 succeeds: return (bytes, filename, content_type) to the router, which returns the file Response
```

If step 5 raises (a database/commit failure): the export is **not** delivered. The generated file bytes are discarded, no partial/successful response is returned, and `ReportExportService` raises a new `ExportAuditPersistenceError` (§26 — mapped to a 500-class `EXPORT_AUDIT_FAILED` `ErrorResponse`, an infrastructure failure, not a client error) — the caller sees a documented internal-error envelope, never a file, and never a response that pretends success. This is a single-transaction, single-database ordering, not a distributed transaction: because the file bytes are only *held in memory*, not yet sent to the client, until after the audit commit succeeds, no two-phase-commit or cross-system coordination is required — the HTTP response itself is simply not constructed until step 5 is durable.

### 21.9 Central, configurable row/batch limits

`constants.py`, not hardcoded per endpoint: `EXPORT_ROW_LIMIT_CSV`, `EXPORT_ROW_LIMIT_XLSX`, and `EXPORT_BATCH_SIZE` (the per-batch retrieval size used by `iter_export_rows()`, e.g. a candidate of 1,000 rows/batch — also non-binding). **50,000 rows remains a non-binding planning candidate for CSV** (per spec OQ-1); XLSX's limit is planned **lower** (candidate: 25,000). All three values are finalized during implementation via representative-payload memory/runtime benchmarking (§40 — explicitly non-blocking).

---

## 22. Audit & Observability

`models/reports_audit_log.py::ReportsAuditLog(TenantBaseModel)` — module-local, following §2.8's established per-module-audit-table convention exactly (no reuse of another module's audit table): `entity_type` (`"ReportExport"` | `"SavedReportView"`), `entity_id`, `action`, `actor_id`, `before`/`after` (nullable JSONB), `report_key`, `filter_scope` (JSONB), `format`, `row_count`, `reason` (nullable) — matching `InstallmentAuditLog`'s field shape (§2.8).

`ReportsAuditService.record(...)` — **stages only** (`repo.create()` + `flush()`, no commit); the caller (`ReportExportService`, `SavedViewService`) commits it together with its own business mutation in the same transaction, exactly like `InstallmentAuditService`/`AuditLogService` (§2.8). Audited actions (FR-RPT-300): every export, every saved-view create/update/delete, and (reusing Epic 9A's existing entitlement-change audit path unchanged) Platform Admin toggling the `reports` entitlement. **Ordinary report/dashboard views are never audit-logged** (FR-RPT-301) — only lightweight structured observability: `report_key`, `company_id`, `execution_duration_ms`, `outcome` (`success`/`denied`/`error`), `result_row_count`, `export_format` (where applicable), and a `slow_query` boolean marker (threshold left to `/sp.tasks`, no fabricated SLA) — emitted via the platform's existing structured-JSON logging convention (Constitution §22), never the report's actual row contents (FR-RPT-303).

**Export durability (corrected, 2026-09-11 — see §21.8 for the full ordering)**: for exports specifically, `record()`'s stage-then-caller-commits pattern is load-bearing, not incidental — `ReportExportService` commits the staged audit row **before** returning the file response, and treats a commit failure as a full export failure (`ExportAuditPersistenceError`, §26), never a partially-successful "file delivered, audit lost" outcome. This is the one place in Reports where "stage, caller commits" is elevated from a stylistic convention to a security/compliance invariant, because an export is an explicit data-exfiltration boundary (§27, spec §30) that MUST be traceable by construction.

---

## 23. Frontend Architecture

New route group `frontend/src/app/(protected)/(reports)/reports/`, matching the established `(module-name)` convention exactly (§2.9) rather than inventing a different nesting style:

```
reports/page.tsx                        # Executive Dashboard (Overview)
reports/sales/page.tsx
reports/purchase/page.tsx
reports/inventory/page.tsx
reports/finance/page.tsx                # Accounting-domain reports
reports/crm/page.tsx
reports/installments/page.tsx
reports/customer-360/[customerId]/page.tsx
reports/[reportKey]/page.tsx            # generic detail view for any registry-listed report key
```

Navigation visibility is driven **entirely** by the new discovery endpoint (§18, FR-RPT-320) — a section/link is present only if the discovery response includes at least one report key for that domain; there is no hardcoded per-module nav entry and no probe-then-hide-on-403 fallback (directly improving on the repo's only prior discovery-shaped attempt, the Platform-Admin console's own acknowledged 403-probing pattern, §2.9).

**Data fetching**: adopts Installments' pattern as the Reports standard (§2.9's explicit finding) — a new `lib/api/reports.ts` thin wrapper over the existing `apiClient` singleton, TanStack Query hooks under `hooks/reports/` with tenant-scoped query keys (`['reports', companyId, reportKey, filters]`), consistent loading/error/empty states. Auth/tenant context reuses `useAuth()` + the existing `erp_active_company_id` localStorage + `erp-active-company-changed` event pattern every non-`(companies)` module already uses (§2.9) — no new tenant-context mechanism invented.

**Shared components** (genuinely new — none of these exist today, §2.9): `DataTable` (pagination, server-driven sort indication, per-column money/date formatting, export trigger), `PeriodSelector`, `ComparisonSelector`, `FilterBar`, `KpiCard`, `ChartWrapper` (§24), `ExportButton` (generalized from Accounting's module-local one, but implemented as Reports' own component — not a retrofit of Accounting's existing pages), `SavedViewSelector`, and the five availability-state components (§26). These live in `frontend/src/components/reports/` — the currently-empty `frontend/src/components/shared/` is **not** used for these (they are Reports-specific in their data contracts, e.g. `DataTable` is generic but ships inside Reports' own package boundary for this epic; promoting it to a true cross-module shared component is a candidate for a future epic, not scope creep here). A shared money-formatting and date-formatting utility (FR-RPT-322) is added under `frontend/src/lib/format/` for Reports' own use, since no equivalent exists repo-wide (§2.9) — other modules' existing raw-numeric rendering is **not** retrofitted (out of scope, matches §57's "no mass refactor" instruction).

Every report page implements the five states from Constitution §23 (loading/error/empty) plus Reports-specific permission-denied/module-disabled states (§26), consistent with FR-RPT-324.

---

## 24. Charting Decision

**No charting library exists today** (§2.9 confirmed). Epic 11 introduces exactly **one**: **Recharts**.

| Criterion | Assessment |
|---|---|
| Maturity/maintenance | Long-established, large community, active releases — satisfies Constitution §26's "mature, actively maintained" bar. |
| React/Next 16 (React 19.2) compatibility | Composable React-component API (not a canvas/imperative wrapper); current major versions declare React 19 peer-dep support. Rendered as SVG, which keeps it inspectable/stylable with Tailwind and testable in the same way as any other DOM tree. |
| Accessibility | SVG output allows real DOM elements with `aria-label`/`role` attributes per data point, unlike canvas-based alternatives (Chart.js) which require a parallel accessibility layer built from scratch. Still requires the accessible-table-alternative wrapper (FR-RPT-331) regardless of library choice — no chart library provides that automatically. |
| Bundle impact | Larger than a hand-rolled inline-SVG sparkline (Accounting's `KPICard.tsx` today embeds one manually, §2.9) but justified because Epic 11 needs genuine trend/comparison charts across ~7 report families, not a single sparkline; Next.js route-based code-splitting confines the cost to `(reports)` pages only — no other module's bundle grows. |
| SSR/client boundary | Charts are interactive (tooltips/legends) and must be client components (`"use client"`); `ChartWrapper.tsx` is the single client-boundary component every report page imports, keeping the rest of each report page a Server Component where possible. |
| Alternatives considered | **visx** — lower-level, more code per chart, rejected as excess implementation cost for this epic's needs (KISS, Constitution §7). **Chart.js/react-chartjs-2** — canvas-based, weaker native accessibility story, rejected. **Nivo** — heavier bundle than Recharts for equivalent chart types, rejected. |

Not installed during planning (per governing-prompt §41) — this is the finalized recommendation for `/sp.tasks` to execute as its first frontend foundation task, with the justification above satisfying Constitution §26's dependency-addition documentation requirement inline.

---

## 25. Drill-Down Architecture

Each `ReportDefinition.drill_down_targets: tuple[DrillDownTarget, ...]` is an explicit, typed link descriptor — never a generic entity browser (governing-prompt §44):

```python
@dataclass(frozen=True)
class DrillDownTarget:
    label: str
    target_route: str              # frontend route template, e.g. "/sales/invoices/{invoice_id}"
    required_permission: str       # the UNDERLYING module's own record-view permission, e.g. "sales.invoices.read"
    preserves_filters: tuple[str, ...]  # which of the parent report's filters carry over
```

Drill-down is implemented as the frontend navigating to the underlying module's **existing, already-authorized** record route (Sales invoice detail, Accounting journal detail, Installment contract detail, etc.) — Reports issues no new "record detail" endpoint of its own; the target route re-authorizes independently via that module's own existing permission check (FR-RPT-181), exactly as it does for any direct visit today. Reports' only responsibility is (a) declaring the correct target route/permission pair per report family and (b) preserving the originating filter scope as query parameters so the underlying list view opens pre-filtered (FR-RPT-182). A soft-deleted/inactive target record remains viewable (historical truth) but is labeled inactive by that module's own existing detail view — unchanged by Reports (FR-RPT-183).

---

## 26. Availability & Error States

`schemas/common.py::FreshnessClassification` — always `TRANSACTIONAL_LIVE` for every Epic 11 report (FR-RPT-230); the enum exists now so a future caching layer has a place to add `CACHED_N_MINUTES` without a breaking response-shape change (FR-RPT-231/232 pre-specified cache-key shape, not implemented).

Dashboard/Customer-360 widget/section states (`WidgetState`/`SectionState`) distinguish exactly the four cases governing-prompt §46 requires: **zero** (real, confirmed value of 0), **empty** (list-shaped report, zero rows, still `PRESENT`), **omitted** (authorization gate failed — §14's `OMITTED`), **unavailable/not-configured** (authorized but no data source — §14's `UNAVAILABLE`). `ReportDefinition.status == DEFERRED` covers the fifth case (deferred/not-shipped) at the registry level, never surfaced to a runtime response at all (a deferred key 404s identically to an unregistered one, §9 step 1).

`exceptions.py` maps 1:1 to `ErrorResponse.error.code`:

| Exception | Code | HTTP class |
|---|---|---|
| `ReportNotFoundError` | `REPORT_NOT_FOUND` | 404 |
| `ReportNotEntitledError` | `REPORT_NOT_ENTITLED` | 403 |
| `ReportPermissionDeniedError` | `REPORT_PERMISSION_DENIED` | 403 |
| `FilterValidationError` | `REPORT_INVALID_FILTER` | 422 |
| `UnsupportedSortFieldError` | `REPORT_UNSUPPORTED_SORT` | 422 |
| `UnavailablePrerequisiteError` | `REPORT_UNAVAILABLE` | 409 |
| `ExportTooLargeError` | `EXPORT_TOO_LARGE` | 422 |
| `SavedViewNotFoundError` | `SAVED_VIEW_NOT_FOUND` | 404 |
| `RetiredReportKeyError` | `SAVED_VIEW_REPORT_RETIRED` | 410 |
| `ExportAuditPersistenceError` | `EXPORT_AUDIT_FAILED` | 500 (infrastructure failure — the export was generated but its audit record could not be durably committed, so the file is never delivered; §21.8) |

No internal SQL/stack-trace/service-exception detail is ever placed in `ErrorDetail.message`/`details` (FR-RPT-272) — each exception carries only the fields listed above, and the central FastAPI exception handler (existing platform convention, Constitution §21) renders them through `ErrorResponse` unchanged.

---

## 27. Security Architecture

Directly implements spec §35/§36's matrices using only the primitives already verified to exist:

- **Tenant isolation** (FR-RPT-260..263): every repository/service call takes `company_id` from `get_current_company_member`, never from a client-supplied body/query field; every adapter call passes `company_id` through unchanged to the wrapped domain service, which enforces its own tenant scoping identically to any other caller.
- **IDOR** (FR-RPT-271): drill-down and Customer 360 both reuse the "identical not-found for either 'doesn't exist' or 'wrong tenant'" pattern already established elsewhere in the repo (BR-INST-001/015 precedent) — no new error-message-distinguishability risk introduced.
- **Cross-module tenant scoping** (FR-RPT-262): Customer 360 checks tenant scope independently per section (each adapter call is itself tenant-scoped) rather than relying on the customer-lookup step alone to secure the other three sections.
- **Platform Admin boundary** (§38 spec, FR-RPT-290..292): Reports' router is mounted under the tenant-facing `/companies/{company_id}/...` prefix exactly like every other business module — Platform Admin's existing, separate router tree (`modules/platform_admin/router.py`) is never extended to read report data; enabling `reports` entitlement for a tenant only ever touches the Capability/toggle row, never a report/saved-view/audit table (enforced structurally: Platform Admin's module imports no Reports repository, mirroring its existing documented "imports no business-record repository from Inventory/Purchase/Sales/Accounting/CRM" invariant, `platform_admin/router.py:1212-1217`).
- **Export as exfiltration boundary** (§30 spec): `.export` permission distinct from `.view`, row-limit ceiling, audit record, and field parity with the online view (the export path calls the identical execution path, §21 — it cannot expose a field the online schema withholds because it's the same schema).

---

## 28. Test Architecture

Following the repo's actual test topology (§2.1/§2.8 — one central `backend/tests/` tree, not per-module), organized under `backend/tests/{unit,integration,security,performance}/.../reports/`:

- **Unit** (`tests/unit/modules/reports/`): registry consistency (§7), metric-catalog distinct-name check (§8), filter-schema validation (each `extra="forbid"` model rejects unknown fields), comparison-engine zero-denominator/partial-period logic (§20), saved-view `FilterConfigV1` validation, entitlement-branching logic (mocked `PlatformEntitlementService`), `InstallmentsServicingContinuityGate` Case A/B/allow-list branching (mocked), CSV `sanitize_cell()` against `=`/`+`/`-`/`@`-prefixed inputs.
  - **Type boundary** (§10.1, new): given a wrapped service returning a weakly-typed `dict[str, Any]`/`tuple[list[dict], int]` fixture, asserting the adapter's `run()`/`iter_export_rows()` output is a concrete `AggregateReportResult`/`PaginatedReportResult`/`CursorReportResult` instance (via `isinstance`, never requiring a consumer-side `cast` or `Any` check); a static check (part of the `mypy .` CI gate itself, not a separate test) that no adapter method signature or `ReportExecutionService`/`ReportExportService` public method mentions `Any`.
  - **Installments allow-list** (§13, new): `is_allowed()` returns `True` for every entitled-state report key; returns `True` only for the five allow-listed keys under `SERVICING_CONTINUITY`; returns `True` for none under `UNAVAILABLE`; explicitly asserts `is_allowed("installments.plan_performance", SERVICING_CONTINUITY) is False` and `is_allowed("installments.dashboard", SERVICING_CONTINUITY) is False`.
- **Contract** (`tests/integration/.../reports/`, using the default SQLite/mocked-service fixtures where a real DB isn't required): each adapter's `run()` against a **mocked** wrapped-service call, asserting the adapter's typed output schema shape is stable; registry-declared `supported_filters` fields are a subset of the real wrapped method's actual `inspect.signature()` parameters (FR-RPT-004, run against the *real* imported service classes, not mocks, since this is specifically catching signature drift); each adapter's `count_export_rows()`/`iter_export_rows()` against a mocked wrapped-service call, asserting batches never exceed `EXPORT_BATCH_SIZE` and the sum of all yielded batches equals `count_export_rows()`'s own return value.
- **Security** (`tests/security/reports/`): tenant isolation (cross-`company_id` attempts denied at every endpoint), IDOR (IDs from another tenant return identical not-found), full RBAC matrix (§11's 13 permissions × view/export split), entitlement-denial matrix (§29's Installments matrix + generic per-domain), saved-view ownership (User B cannot list/load User A's view; a soft-deleted view's ID returns the identical `SavedViewNotFoundError` to a probing owner or another user — §15), drill-down re-authorization (Scenario C), Platform Admin boundary (Scenario K — enabling entitlement grants no data access).
- **Real PostgreSQL** (`tests/integration/api/v1/reports/`, reusing `pg_test_db`/`alembic_upgrade("head")`/`pg_engine` per §2.8's established re-export pattern — **using `"head"`, not a hardcoded revision literal**, to avoid silently skipping Epic 11's own migrations): saved-view CRUD with real JSONB (including delete → soft-delete → excluded from list/load, §15); Customer 360 composite queries; GL cursor-pagination continuity, both for online browsing (no skip/duplicate across cursor pages) and for export (`iter_export_rows()` consuming the same cursor safely to completion, §21.5); Decimal-precision aggregation checks; migration upgrade/downgrade round-trip.
- **Financial invariants** (§30 below).
- **Export bounded-retrieval and audit-durability** (§21, new — real Postgres): row-limit rejected before any batch retrieval is attempted (assert zero adapter `iter_export_rows()` calls when `count_export_rows()` already exceeds the limit); CSV/XLSX generation consumes bounded batches (assert no single adapter call returns more than `EXPORT_BATCH_SIZE` rows); XLSX's independently-lower limit is enforced separately from CSV's; CSV formula-injection payloads neutralized; `.export` permission checked independently of `.view`; exactly one audit record is written per successful export; **a simulated audit-commit failure (e.g. a mocked/forced `IntegrityError`/connection failure on the audit transaction) results in no successful export response** — the endpoint returns `EXPORT_AUDIT_FAILED` (500-class), and no file bytes are ever returned to the test client.
- **Performance** (`tests/performance/reports/`): query-count assertions (no N+1) for every list-shaped report's adapter call, not wall-clock timing (§31, carrying forward the Pre-Epic-11 lesson explicitly referenced in the governing prompt and already the CI-documented convention, §2.8).
- **Frontend**: filter/permission-visibility/entitlement-visibility/export-action/saved-view/module-disabled-state tests, using whatever frontend test runner `/sp.tasks` confirms is already configured (§3 — not fabricated here).

---

## 29. Real-Postgres Validation

Every migration in §16 is validated with: clean `alembic upgrade head` from a throwaway `pg_test_db()`, `alembic downgrade` back one revision then re-upgrade (round-trip), and the CI `migrations` job's existing static revision-chain parse (§2.8, unchanged — no new CI job). Constraint/index verification (uniqueness where declared, FK integrity for `user_id`/`created_by`) is asserted directly against the real Postgres schema, not SQLite, per governing-prompt §52's explicit instruction.

**Installments matrix** (governing-prompt §48, spec §46 Scenarios H/M): fully entitled → all approved "Now" Installments reports accessible / Case A (disabled, no obligations) → all `installments.*` reports unavailable / Case B (disabled, obligations exist) → **only** the five-report servicing-continuity allow-list accessible read-only (`register`, `collections`, `due_overdue`, `aging`, `settlement_writeoff`) — explicitly asserted that `installments.plan_performance` and the standalone `installments.dashboard` remain `REPORT_NOT_ENTITLED` under Case B (§13 correction) / no origination-write path exists to even attempt (Reports has none) / Executive Dashboard's Installments widget Case A (omitted) and Case B (present, sourced only from allow-listed aging/due-overdue data, `read_only_servicing_continuity: true`) / Customer 360 Installments section Case A (`OMITTED`) and Case B (`PRESENT`, allow-list-scoped data only).

**Customer 360 matrix** (governing-prompt §49, spec Scenarios N/O): all domains enabled; CRM disabled (Scenario N); Installments disabled with/without obligations; Accounting permission missing; customer not found; cross-tenant customer ID (Scenario F); valid zero AR (confirmed-present zero); Accounting not configured (`UNAVAILABLE`); zero Sales transactions (confirmed-present zero); partial composition (some sections present, some omitted, response still returned) (Scenario O — minimum-useful-response, both branches).

**Entitlement matrix** (governing-prompt §50): every report family × {`reports` enabled/disabled} × {domain enabled/disabled} × {domain permission present/absent} × {export permission present/absent} — verified via direct API test, never inferred from UI hiding (FR-RPT-032's frontend behavior is a UX convenience, not a security boundary).

---

## 30. Financial Reconciliation Testing

Directly implements spec §48.3/FR-RPT-081: for Trial Balance, GL, P&L, Balance Sheet, Cash Flow, AR aging/statement, AP aging/statement, bank/cash book, and every Financial KPI — a test calls **both** Accounting's own existing endpoint and Epic 11's wrapped endpoint with byte-identical parameters and asserts equal totals (Scenario A). Because the adapter calls the exact same `FinancialStatementService`/`AccountsReceivableService`/`AccountsPayableService`/`FinancialKPIService` methods Accounting's own router already calls, this test is close to tautological by construction — its real value is catching any future drift if Reports' adapter parameter-mapping diverges from what Accounting's own router passes. Installment-Accounting reconciliation (US-6, governing-prompt §27's financial-invariant list) is tested by creating an overdue obligation and confirming both the Installment Aging report and Accounting's AR aging report reflect a consistent outstanding amount — proving both ultimately read the same `AccountingIntegrationGateway`-mediated truth (spec §7/FR-RPT-102), never two independently computed numbers.

---

## 31. Performance Plan

- No fragile wall-clock assertions anywhere in Epic 11's test suite (explicit carry-forward of the Pre-Epic-11 lesson, both the governing prompt and spec §48.5 state this identically) — query-count assertions instead (e.g. `assert_no_n_plus_one` helper pattern, or direct SQLAlchemy event-based query counting).
- Every aggregating report calls the wrapped service's own existing aggregation-capable method (`SUM`/`COUNT` at the database layer) — Reports never re-fetches full ORM rows to sum in Python (FR-RPT-221); this is inherited for free since adapters call the domain's own already-optimized methods, not new queries.
- GL's existing cursor pagination is reused unchanged for its own internal scale characteristics (already built for 500K+ rows per its docstring, §2.6) — Reports adds no additional query layer on top of it.
- Export memory/runtime profiling against representative payload widths is an implementation-phase activity (§21) that finalizes the row-limit constants — not a planning-time number.
- `group by`-capable reports document their practical cardinality ceiling (e.g., "by customer" bounded by actual customer count) per report family during `/sp.tasks`, not invented here per report (FR-RPT-223).

---

## 32. Type Safety

**Corrected, 2026-09-11 correction pass**: the plan's earlier draft simultaneously promised "no `Any` escape hatches" and defined `ReportAdapter.run(...) -> ReportResult[Any]` — an internal contradiction, fixed in §10.1. This section now states the claim precisely, in three zones, so it cannot be misread as "the legacy modules Epic 11 wraps contain no `Any`" (they do, and that is unrelated repository reality, not something Epic 11 controls or claims to fix):

| Zone | What it is | `Any` allowed? |
|---|---|---|
| **1. Legacy domain-service internals** | Sales/Purchase/Inventory/CRM/Installments/Accounting's own existing report/KPI methods (§2.6) — `dict[str, Any]`, `list[dict[str, Any]]`, `tuple[list[dict[str, Any]], int]` shapes | Yes — pre-existing, out of Epic 11's control, not retrofitted (§57 "no mass refactor"). |
| **2. Adapter translation implementation** | The body of each concrete `*_adapter.py` method — the code that reads zone 1's weak shape and constructs a concrete Pydantic result | `Any` may appear only as a transient local holding zone-1 input; never as a parameter or return annotation of any adapter method. |
| **3. Reports orchestration/public contracts** | `ReportAdapter` Protocol methods, `ReportExecutionService`, `ReportExportService`, the router, every request/response schema | **No.** Every signature here is `BaseReportResult` (or a concrete/generic subtype), a Pydantic model, an `Enum`/`Literal`, or a frozen dataclass — never `Any`, never a bare `dict`. |

Concretely:

- `ReportDefinition`/`MetricDefinition`/`DrillDownTarget` are frozen dataclasses (matching `PermissionDefinition`'s existing convention, §2.5) — not `dict[str, Any]`.
- Every filter schema, request schema, and response schema is a Pydantic v2 model with `ConfigDict(extra="forbid")` where closed-set validation matters (filters) — no untyped dict crosses a public boundary.
- `ReportAdapter` is a `Protocol[ReportResultT_co]` bound to `BaseReportResult` (§10.1) — dispatch is a typed dict lookup (`ADAPTER_REGISTRY: dict[ReportDomain, ReportAdapter[BaseReportResult]]`), never a dynamic `getattr`/string-eval callable resolution; `run()`/`count_export_rows()`/`iter_export_rows()` (§21.2) all return concrete typed results, never `Any`.
- `SectionState`/`WidgetState`/`InstallmentsAccessState`/`ExportFormat`/`ReportStatus`/`PaginationStyle` are all `Enum`/`Literal` types, never bare strings compared ad hoc.
- No `cast(Any, ...)`, no `# type: ignore` used as architecture, and no dynamic `eval`/`getattr`-based dispatch anywhere in zones 2–3 (governing-prompt correction-pass requirement) — the only mechanism for "this weak shape becomes that typed shape" is an explicit, statically-checkable adapter method body, never a runtime introspection trick.
- `mypy . = 0` is preserved by construction: every new file follows the exact typing discipline already enforced repo-wide (no `Any` escape hatches in zones 2–3, no broad suppressions) — verified by running the existing blocking `mypy .` CI job unchanged (§2.8) against Epic 11's code as it lands, not a new/relaxed configuration (FR-RPT-350/353). This claim is scoped to Epic 11's own code (zones 2–3); it does not assert, and has never asserted, that the legacy modules in zone 1 are themselves free of `Any` — they are not, and that is unrelated to this epic.

---

## 33. Implementation Phases

Dependency-ordered; each phase's exit criteria are the gates in §34.

| Phase | Scope | Depends on |
|---|---|---|
| **0 — Foundation** | Module scaffold (§6); `reports` Capability + `ReportsFeatureFlagService` + `ReportsModuleEnablementProvider` (§12); `REPORTS_PERMISSIONS` seed (§11); `ReportDefinition`/`MetricDefinition` types + empty registry; shared filter/date-range/comparison/money contracts (§20); router mount with entitlement gate (no report keys registered yet). | Nothing (first phase) |
| **1 — Saved Views** | `SavedReportView` model + migration + repository + `SavedViewService` + validation + ownership tests (§15). | Phase 0 (needs `TenantBaseModel`, permission `reports.saved_view.manage`) |
| **2 — Domain Adapters** | Six adapters (§10), each implementing `run()` **and** `count_export_rows()`/`iter_export_rows()` (§10.1/§21.2) from the start — not bolted on in Phase 6 — one domain at a time in this order: **Accounting first** (financial-invariant tests are the highest-value early signal and the riskiest domain to get wrong; also exercises the GL cursor-export seam, §21.5), then Sales, Purchase, Inventory, CRM, **Installments last** (needs `InstallmentsServicingContinuityGate` including its Case-B allow-list, §13, which itself needs Phase 0's entitlement wiring). Each domain's "Now" catalog rows (§9 spec) registered as `ReportDefinition`s as its adapter lands. | Phase 0 |
| **3 — Unified Execution API** | `ReportExecutionService` including the shared `_authorize_and_validate()` preamble (§9), discovery endpoint (§18), pagination/cursor handling (§19), drill-down metadata wiring (§25). | Phase 2 (needs at least one real adapter to test against) |
| **4 — Executive Dashboard** | `ExecutiveDashboardService` (§13 spec), per-widget gating including the Installments exception (allow-list-scoped, §13). | Phase 3 (reuses execution service's entitlement/permission primitives per widget) |
| **5 — Customer 360** | `Customer360Service` (§14), section-level composition, IDOR-safe base gate. | Phase 3 (Sales/Accounting/CRM/Installments adapters must exist) |
| **6 — Exports & Audit** | `ReportExportService` reusing Phase 3's `_authorize_and_validate()` and Phase 2's `count_export_rows()`/`iter_export_rows()` (§21.1/§21.2), `csv_sanitizer.py`, `ReportsAuditLog` + migration + `ReportsAuditService`, the durable-audit-before-file-release ordering (§21.8), row/batch-limit benchmarking (§21.9). | Phase 3 (reuses the shared authorization preamble; Phase 2's adapters already expose the bounded-retrieval methods) |
| **7 — Frontend Foundation** | `(reports)` route group scaffold, `lib/api/reports.ts`, discovery-driven nav, shared `DataTable`/`PeriodSelector`/`ComparisonSelector`/`FilterBar`/`KpiCard`/`ExportButton`/`SavedViewSelector`/state components, Recharts installed + `ChartWrapper` (§23, §24). | Phase 3 (needs the discovery endpoint) |
| **8 — Domain Report Pages** | Sales/Purchase/Inventory/Finance/CRM/Installments pages built on Phase 7's shell, wired to Phase 2's adapters via Phase 3's API. | Phases 2, 7 |
| **9 — Dashboard + Customer 360 UI** | Overview page (Phase 4's API), Customer 360 page (Phase 5's API). | Phases 4, 5, 7 |
| **10 — Security / Postgres / Reconciliation / Performance Hardening** | Full security matrix (§28/§29), real-Postgres suite, financial reconciliation suite (§30), N+1/query-count performance suite (§31). | All prior phases |
| **11 — Regression / Docs / Release Readiness** | Full existing-suite regression run (backward compatibility, §35), module docs (Constitution §30), `plan.md`/spec cross-check, PHR trail complete. | Phase 10 |

---

## 34. Phase Gates

| Gate | Must prove |
|---|---|
| Foundation (0) | Registry module imports cleanly with zero entries and zero mypy errors; `reports` entitlement round-trips through `resolve_effective_entitlement()` without the `ValueError` described in §2.3; no endpoint exists yet that could bypass the (still-empty) registry. |
| Saved Views (1) | Full CRUD + ownership isolation passes against real Postgres; `FilterConfigV1` rejects an unregistered field; **delete performs repository-standard soft-delete** — a deleted view is excluded from list/load and returns the identical `SavedViewNotFoundError` a never-existing or another-user's view would (§15) — no hard-delete path exists. |
| Adapters (2) | Each domain's wrapped reports produce output byte-identical (for Accounting) or field-consistent (for operational domains) with that domain's own existing endpoint for identical inputs (§30) — before Phase 3 exposes them through the unified API. **Typed normalization boundary proven**: every adapter's `run()`/`count_export_rows()`/`iter_export_rows()` returns/yields only `BaseReportResult` subtypes or typed row batches — zero `Any` in any adapter method signature (verified by `mypy .` plus the dedicated type-boundary unit test, §10.1/§28). **Installments allow-list proven**: `InstallmentsServicingContinuityGate.is_allowed()` grants exactly the five servicing-continuity keys under Case B and denies `installments.plan_performance`/`installments.dashboard` — verified before Phase 3 wires the Installments adapter into the unified API. |
| Execution API (3) | Every report key is reachable **only** through `ReportExecutionService.execute()` — a static-analysis/test check confirms no router path calls an adapter directly; `execute()` and `ReportExportService.export()` are proven to share the identical `_authorize_and_validate()` preamble (no parallel authorization path exists, §9/§21.1). |
| Dashboard (4) | Per-widget authorization independently verified; Installments exception (Case A omitted / Case B present, sourced only from allow-listed data) verified with real fixtures. |
| Customer 360 (5) | Section-level authorization matrix (§29) passes in full; tenant isolation (Scenario F) passes; minimum-useful-response (Scenario O) passes both branches. |
| Exports (6) | **Bounded retrieval proven**: no adapter call during export ever returns more than `EXPORT_BATCH_SIZE` rows, and the row-limit check is proven to run before any batch retrieval (§21.2). No data widening versus the online view (field-parity test, since export shares `_authorize_and_validate()` with the online path). Independent CSV/XLSX row limits enforced. CSV injection payload neutralized (Scenario L). **Durable audit before file release proven**: every successful export produces exactly one audit record committed before the response is returned; a simulated audit-commit failure is proven to produce zero successful file deliveries (`EXPORT_AUDIT_FAILED`, §21.8/§28). |
| Frontend Foundation (7) | Nav renders only discovery-authorized sections against at least two fixture tenants (one fully entitled, one partially disabled). |
| Domain Pages / Dashboard UI (8–9) | Loading/empty/error/permission-denied/module-disabled states all manually verified in-browser per page (Constitution §23 requirement — dev-server verification, not just type-checking). |
| Hardening (10) | Full security/Postgres/reconciliation/performance suites green. |
| **Final** | `mypy . = 0` repo-wide; Ruff + format clean; full existing + new test suite green; all migrations upgrade/downgrade clean against real Postgres; frontend build succeeds; every existing domain report endpoint (Sales/Purchase/Inventory/Accounting/CRM/Installments) still passes its own existing test suite unchanged (§35). |

---

## 35. Backward Compatibility

Epic 11 adds a parallel, unified surface — it does not touch any existing domain router, service, schema, or frontend page. Verified explicitly: `api/v1/router.py`'s existing five `require_capability_entitled(...)` mounts and Installments' existing mount (§2.2) are read, not edited, except for the one addition of Reports' own mount block. Every existing `/sales/reports/*`, `/purchase/reports/*`, `/inventory/reports/*`, `/accounting/reports/*`, `/crm/reports/*`, `/crm/dashboard`, `/installments/reports/*`, `/installments/dashboard` endpoint keeps functioning unchanged (FR-RPT-050/060/070/080/090/100). A compatibility test suite run (existing per-module test suites, re-run unmodified as part of Phase 11's gate) is the acceptance mechanism — no new assertions are needed beyond "still green," since nothing in those modules' own code is edited.

The **only** edits to existing modules' files are: (1) `platform_admin/services/capability_seed_service.py` — one new tuple + stale-comment fix (§12); (2) `platform_admin/services/module_enablement.py` — one new provider class + one dispatch branch (§12); (3) `users_roles/constants.py` — one new `REPORTS_PERMISSIONS` tuple unioned into `INITIAL_PERMISSIONS` (§11); (4) `api/v1/router.py` — one new router-mount block (§12). All four are additive, precedented (every prior module's onboarding made the identical four edits), and independently unit-tested.

---

## 36. Risk Register

| Risk | Mitigation |
|---|---|
| Reports accidentally re-derives a financial figure instead of calling Accounting's service, creating a second source of truth. | FR-RPT-003/081 as hard architectural constraints; §7's registry-consistency test (`inspect.signature` check) and §30's reconciliation tests catch drift automatically, not just at review time. |
| `InstallmentAccessPolicy.authorize(READ)`'s unconditional pass-through is misread by an implementer as "Case A/B is already handled" and the continuity gate (§13) is skipped. | §13 documents the exact seam and the reason it's needed in the plan itself (this finding is novel — not stated in the spec, discovered during this plan's re-verification); Phase 2's Installments adapter task explicitly references §13; a dedicated unit test asserts the gate is called before every `installments.*` dispatch. |
| Installments Case B allow-list is implemented too permissively (e.g. "every read-only report is fine since Reports never writes") and silently regresses to exposing `installments.plan_performance` or the full `installments.dashboard` bundle. | §13 makes the allow-list an explicit, named `frozenset` constant with a dedicated unit test asserting both excluded keys return `False`, plus a real-Postgres Case-B integration test (§29) that would fail immediately if either excluded report became reachable. |
| An implementer conflates `execute()`'s bounded `adapter.run()` dispatch with export's needs and calls `run(page_size=total_count)` as a shortcut, materializing an unbounded result set despite §21's bounded-retrieval design. | `ReportAdapter`'s Protocol (§10.1) makes `count_export_rows()`/`iter_export_rows()` first-class, separate methods from `run()` from Phase 2 onward (not introduced later in Phase 6) — there is no `run(page_size=total)` shortcut available to reach for, since `run()`'s `page_size` is typed against normal online pagination bounds, not an export-scale parameter. |
| A durable-audit-before-file-release bug ships the file response even when the audit commit fails (e.g. an `except` block that logs and continues instead of re-raising). | §21.8's ordering is a named, independently-tested invariant (§28) with a dedicated simulated-failure test that asserts zero successful file deliveries when the audit commit is forced to fail — this is a gate-blocking test (§34 Exports gate), not an optional nice-to-have. |
| Pre-existing CSV formula-injection gap in Sales/Purchase/Inventory/Accounting's own export services is mistaken for "already handled" because Epic 11 fixes it in its own path. | §2.7/§21 explicitly flag this as **unaddressed, out-of-scope debt** in this plan — not silently buried (governing-prompt §58 bug-discovery policy) — recommend a follow-up ticket outside Epic 11's scope. |
| `reports`' entitlement resolution hits the `ValueError` in `get_module_enablement_provider()` if the new dispatch branch (§12 step 4) is missed during implementation. | Phase 0's gate explicitly requires this round-trip to be tested before any other phase proceeds (§34). |
| Customer 360's section-level compound authorization is implemented as an all-or-nothing check by mistake (simpler to write, wrong per FR-RPT-111). | §14's design is explicit about four independent section evaluations; the Customer 360 test matrix (§29) includes a dedicated partial-composition scenario (Scenario N) that would fail immediately under an all-or-nothing implementation. |
| Export memory pressure from XLSX generation at the upper row-count candidate, or from an adapter's `iter_export_rows()` accidentally buffering more than one batch at a time despite the bounded-retrieval design. | §21's benchmarking step is a named implementation-phase task, not deferred indefinitely; XLSX's candidate limit is set lower than CSV's specifically because of this risk; the contract test (§28) asserting no single adapter call returns more than `EXPORT_BATCH_SIZE` rows catches an accidental full-materialization regression directly. |
| Frontend report-schema sprawl (one bespoke schema per report family, ~35 of them) becomes unmaintainable. | §7's typed registry + §10's adapter Protocol keep the *backend* contracts disciplined; frontend `DataTable` is column-config-driven (not one bespoke table component per report) specifically to contain this on the frontend side too (§23). |
| Accounting performance regression from Reports adding load on top of an already-tested-at-scale GL cursor path. | §31 — Reports adds zero new query layer on GL; it reuses the existing cursor mechanism unchanged. |
| Loose UUID cross-module references (Sales/Purchase line items → Inventory `Product`, no DB-level FK) surface as "missing" display names in a report if the referenced product was hard-deleted. | Adapters resolve display names defensively (never assume the FK-less reference resolves) and label unresolvable references explicitly, consistent with FR-RPT-053's documented loose-reference handling. |
| Inventory valuation figure misunderstood as a reconciled accounting balance despite the `valuation_basis` field. | FR-RPT-071 enforced structurally — the adapter, not Inventory's own service, injects `valuation_basis: "operational_wac"` into every response for this report/metric, and the frontend's Finance vs. Inventory section labeling makes the distinction visually explicit (§10, §23). |
| Migration/permission seed drift between `INITIAL_PERMISSIONS` and the backfill migration (the exact class of bug `071_installments_permission_backfill.py` exists to prevent recurring). | §16's `074` migration is generated directly from the `REPORTS_PERMISSIONS` tuple (not hand-typed independently), matching the precedent that caused Installments to need its own backfill migration in the first place. |
| Chart dependency overhead (Recharts) bloats an unrelated page's bundle. | Next.js route-based code-splitting confines the cost to `(reports)` routes; verified during Phase 7's gate via a bundle-size check on a non-Reports page before/after. |

---

## 37. ADR / Decision Needs

Per governing-prompt §64, four candidates evaluated against the three-part significance test (impact / alternatives / cross-cutting scope):

| Candidate | Significant? | Recommendation |
|---|---|---|
| Static typed Report Registry architecture (code-defined, not DB-backed) | Yes — long-term impact (every future report addition follows this pattern), real alternative existed (DB-backed metadata table), cross-cutting (all six domains + dashboard + AI-readiness depend on it). | **Suggest ADR** during implementation kickoff: "ADR: Static Code-Defined Report Registry over Database-Backed Report Metadata." |
| `reports` Capability default-resolved state (disabled-by-default) | Borderline — real product/business decision with a documented alternative, but narrow in blast radius (one boolean default, reversible via toggle, no schema implication). | **No ADR** — captured sufficiently in spec FR-RPT-255 + this plan's §12; a Constitution-level architectural pattern (entitlement defaults) already governs the *mechanism*, only the *value* is being chosen here. |
| Customer 360 section-level (not all-or-nothing) authorization | Yes — establishes a reusable cross-module composite-authorization pattern likely to recur in future cross-module features; real alternative existed (all-or-nothing gate) and was explicitly rejected during the spec's correction pass. | **Suggest ADR**: "ADR: Section-Level Compound Authorization for Cross-Module Composite Read Models." |
| Unified report adapter contract (`ReportAdapter` Protocol wrapping six structurally-incompatible domain services) | Borderline — real engineering pattern but narrowly scoped to Reports' own module boundary; doesn't constrain any other module's architecture. | **No ADR** — sufficiently documented in this plan's §10; revisit only if a seventh domain's wildly different shape later strains the Protocol. |

Per Constitution §39, **no ADR is auto-created** — these two suggestions will be surfaced with the standard "📋 Architectural decision detected..." prompt at the start of implementation (Phase 0), requiring explicit user consent before either is written.

---

## 38. Deferred Scope

Unchanged from spec §51 — this plan builds infrastructure that makes future promotion mechanical, but implements none of the following: arbitrary query builder (NG1); data warehouse/OLAP/caching (NG4, §32 cache-key shape pre-specified only); scheduled/emailed reports, shared saved views (NG5); async export jobs (NG7, §21's synchronous contract has an extensible seam — `ExportRequest` schema includes a `format`/`limit` shape a future async job could reuse unchanged); any AI capability (NG6, §50 spec — this plan's registry/metric-catalog typed contracts are the exact seam a future AI gateway would call, per FR-RPT-360/361/363, with zero privileged bypass path introduced); cross-tenant/platform analytics (NG9); `crossmodule.branch_performance` (locked Deferred, FR-RPT-012 — not implemented, not stubbed as a reachable endpoint); the ~30 "Deferred" per-domain report variants in spec §9's catalog (their `ReportDefinition`s may be added later with `status=NOW` — no structural change needed, just new registry entries); Tax Summary/Cost-Center P&L wrapping (source services exist, sequencing deferred to `/sp.tasks`); resolving ADR-0004 (explicitly not this epic's problem, §10's Inventory adapter honestly labels the gap instead).

---

## 39. Traceability

Every phase above maps to spec sections as follows (full FR-RPT-ID-level traceability is mechanical from this table + each phase's own spec-section references already inlined in §5–§27; `/sp.tasks` expands this into a task-level FR checklist):

| Phase | Primary spec sections |
|---|---|
| 0 | §8 (Reporting Architecture), §33/§34 (RBAC/Entitlements), §12 (Registry FRs) |
| 1 | §29 (Saved Report Views) |
| 2 | §14–§19 (per-domain analytics FRs), §7 (Source-of-Truth Matrix) |
| 3 | §12 (Registry FRs), §21 (Filter Contract), §28 (Pagination) |
| 4 | §13 (Executive Dashboard) |
| 5 | §20 (Cross-Module Analytics / Customer 360) |
| 6 | §30 (Exports), §39 (Audit) |
| 7–9 | §41–§43 (Frontend/UX, Accessibility, Concurrency/Failure states) |
| 10 | §36 (Security Matrix), §44 (NFRs), §48 (Test Strategy) |
| 11 | §47 (Success Criteria), §49 (Type Safety/CI) |

Security requirements (§36 spec), test scenarios (§46 spec Scenarios A–O), and acceptance criteria (§47 spec SC-001..008) are each independently satisfied by name in §27–§30 above — `/sp.tasks` should generate one task per Scenario/SC item referencing this plan's corresponding section.

---

## 40. Open Decisions

Per governing-prompt §65, target is **no blocking architectural questions** — confirmed:

| # | Decision | Status |
|---|---|---|
| 1 | Exact CSV/XLSX export row-count limits, and the export batch/chunk size (`EXPORT_BATCH_SIZE`) | Non-blocking — candidates set (§21.9: 50,000 CSV / 25,000 XLSX row limits, 1,000-row batches), finalized via Phase 6 benchmarking. The *architecture* (bounded, batch-by-batch retrieval, never a full materialization) is fixed regardless of the exact numbers chosen. |
| 2 | Final chart library | **Resolved in this plan** (§24: Recharts) — not left open. |
| 3 | Exact query-range/grouping-cardinality limits per report family | Non-blocking — documented per-family during `/sp.tasks`, not architecture-affecting (§31). |
| 4 | Whether a small number of new indexes are needed beyond §17's two tables | Non-blocking — `/sp.tasks`/implementation confirms via `EXPLAIN` on the Customer 360 path; no architectural dependency on the answer. |
| 5 | Exact Sales customer-view permission code name for Customer 360's base gate (§14) | Non-blocking — confirmed against Sales' existing `permission_check.py` during `/sp.tasks`; does not affect the authorization *design*, only which literal string is checked. |
| 6 | Accounting's exact "is COA configured" check for the AR section's `UNAVAILABLE` state (§14) | Non-blocking — confirmed against Accounting's existing setup-state service during `/sp.tasks`; the *design* (present-zero vs. unavailable-not-configured) does not change regardless of which existing check answers it. |
| 7 | Frontend test runner/config (§3, §28) | Non-blocking — confirmed during `/sp.tasks` before writing frontend test tasks; does not affect backend or frontend production architecture. |
| 8 | Whether `InstallmentReportingService.get_contract_register(limit=1)` is the final choice for the continuity gate's existence check, or a cheaper dedicated `COUNT` method is worth adding to Installments | Non-blocking — either satisfies §13's seam requirement without duplicating access-policy logic; `/sp.tasks` may pick the cheaper option if a trivial one-line addition to Installments' repository is judged worthwhile, subject to Installments module owners' consent (a cross-module touch, however small, per Constitution §12's "modules MUST NOT reach into another module's internals" — the current plan avoids needing consent at all by reusing an existing public method). |

None of these block Phase 0 from starting.

---

## 41. Readiness Verdict

### 41.1 Correction Pass (2026-09-11)

A targeted correction pass fixed five issues surfaced during a pre-`/sp.tasks` review, none of which changed scope, the Report Registry design, Customer 360's architecture, the `reports` disabled-by-default decision, the Recharts decision, or any deferred-scope item (§11 of the correction brief) — all held unchanged:

1. **Type-safety boundary** (§10.1, §32): `ReportAdapter.run(...) -> ReportResult[Any]` was internally inconsistent with the plan's own "no `Any` escape hatches" claim. Replaced with a covariant `Protocol[ReportResultT_co]` bound to a new closed `BaseReportResult` hierarchy (`AggregateReportResult`/`PaginatedReportResult`/`CursorReportResult`) — legacy modules' weak `dict[str, Any]` shapes may exist only as transient input inside an adapter's translation body; nothing weaker than `BaseReportResult` ever crosses into `ReportExecutionService`, `ReportExportService`, the router, or any response schema.
2. **Installments Case B scope** (§13): narrowed from "every Now Installments report" to an explicit five-report servicing-continuity allow-list (`register`, `collections`, `due_overdue`, `aging`, `settlement_writeoff`); `installments.plan_performance` and the standalone `installments.dashboard` are now explicitly unavailable under Case B.
3. **Export retrieval boundedness** (§21.1–21.7): replaced the ambiguous "full-scope count-then-fetch" wording with an explicit bounded-batch retrieval seam (`count_export_rows()`/`iter_export_rows()`) shared by CSV/XLSX/GL-cursor export, with a shared, non-duplicated authorization preamble (`_authorize_and_validate()`) reused from the online execution path.
4. **Export audit durability** (§21.8, §22): made explicit that a successful file response requires a durably committed audit record first — a simulated audit-commit failure now has a named test asserting zero successful file deliveries, mapped to a new `ExportAuditPersistenceError`/`EXPORT_AUDIT_FAILED` (§26).
5. **Saved-view deletion** (§15): resolved the "hard delete" vs. "soft-delete" self-contradiction — final, single answer is repository-standard soft delete, no hard-delete path, no restore UI in Epic 11.

Every downstream section that referenced the corrected material (module structure §6, execution flow §9, Customer 360 §14, migrations/index sections unaffected, test architecture §28, real-Postgres validation §29, implementation phases §33, phase gates §34, risk register §36, open decisions §40) was updated in the same pass so no section contradicts another.

### 41.2 Validation against spec.md's own §67 checklist

- [x] Every "Now" report in §9's catalog is accounted for by a domain adapter in §10 and a phase in §33.
- [x] Every new persistence requirement (`saved_report_views`, `reports_audit_log`) is planned in §15/§16/§22.
- [x] Every permission (§33 spec, 13 codes) is planned in §11.
- [x] Every entitlement behavior (§34 spec) is planned in §12, including the identical-resolution requirement for all six domains (FR-RPT-254).
- [x] The Installments servicing-continuity exception is preserved and its exact seam identified (§13) — including a novel finding (§2.4/§36) about how Case A/B is actually distinguished, since the underlying `InstallmentAccessPolicy` alone cannot do it.
- [x] Customer 360 is planned as a partial-composition, section-level-authorized read model (§14), never all-or-nothing.
- [x] Inventory valuation remains explicitly operational-only, with `valuation_basis` injected structurally (§10, §36).
- [x] Branch Performance remains Deferred, not stubbed as reachable (§38).
- [x] Export security (row limits, CSV-injection neutralization, audit, field parity) is planned centrally (§21).
- [x] Financial invariant testing is planned against Accounting's own existing endpoints (§30).
- [x] Frontend scope (routes, shared components, chart library) is fully planned and the chart library decision is finalized, not left open (§23/§24).
- [x] `mypy . = 0` is preserved by construction, with no new suppressions planned (§32).
- [x] No AI implementation appears anywhere in this plan (§38) — only stable, typed contracts a future AI gateway could reuse unchanged.

No blocking open questions remain (§40). All four required edits to existing modules (§35) are additive and precedented. Two ADR suggestions are queued for consent at implementation kickoff (§37), not auto-created. The five correction-pass items (§41.1) are resolved consistently across every section that referenced them — no plan section contradicts another.

**EPIC 11 PLAN READY FOR TASKS**
