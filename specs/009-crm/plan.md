# Implementation Plan: Epic 9 — CRM (Customer Relationship Management)

**Branch**: `009-crm` | **Date**: 2026-08-15 | **Spec**: [specs/009-crm/spec.md](./spec.md)
**Input**: Feature specification from `specs/009-crm/spec.md`

---

## Table of Contents

1. Executive Summary
2. Current Architecture Assessment
3. Spec vs Existing-System Reconciliation
4. CRM Architecture
5. Domain Boundaries
6. Data Model Plan
7. Database/Migration Plan
8. Repository Plan
9. Service Plan
10. Customer Master Strategy
11. Lead Management
12. Opportunity/Pipeline
13. Activities/Tasks
14. Customer 360
15. Sales Integration
16. Accounting Integration
17. RBAC
18. Audit Trail
19. Events
20. AI Readiness
21. API Design
22. Search/Filtering/Pagination
23. Frontend Architecture
24. Dashboard/Reporting
25. Security
26. Performance
27. Testing Strategy
28. Regression Strategy
29. File-Level Changes
30. Implementation Sequence
31. Task Dependencies
32. ADRs
33. Risk Register
34. Known Gaps
35. Definition of Done
36. Final Implementation Readiness Assessment

---

## 1. Executive Summary

Epic 9 adds a CRM module (`backend/modules/crm/`) to DevSphere ERP as a new peer to `modules/sales`, `modules/purchase`, `modules/accounting`, etc. — same modular-monolith shape, zero new infrastructure. CRM introduces 6 new tables (Lead, LeadSource, Pipeline, PipelineStage, Opportunity, Activity) and reuses, by reference, the existing Sales `Customer` (and its Contacts/Addresses), the existing Accounts Receivable read services, the existing RBAC/audit/event-bus/feature-flag per-module patterns, and the existing API/pagination/response conventions. No Epic 1–8 table, model, service, or API contract is modified.

The implementation strategy is **10 sequential phases** (§30), progressing from foundation scaffolding through the data model, repositories, services, Lead management, Opportunity/pipeline, Activities, Customer 360, RBAC/audit/events, the API layer, the frontend, and finally reporting + hardening + regression verification. Every phase is independently testable, mirroring the phase discipline already proven across Epics 5–8.

**The critical architectural constraint carried over from Epic 8's own plan.md and reinforced by the pre-Epic-9 hardening audit**: every CRM write path MUST end in an explicit `db.commit()` within its own service method (never rely on request-teardown), and every repository method touching a `company_id`-scoped or cross-module-referenced row MUST filter by `company_id` in the same query — these are not new rules invented for CRM, they are the exact two defect classes (missing commits, cross-tenant lookups) the hardening audit found and fixed across Epics 5–8 immediately before this epic began. CRM is being planned with that lesson already applied, not discovered the hard way a second time.

### Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x (frontend) — unchanged from Epics 5–8.
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy 2.x (sync — CRM follows the sync `Session`/`get_db` pattern used throughout the backend, not an async pattern), Alembic, Next.js (App Router), Tailwind CSS, shadcn/ui.
**Storage**: PostgreSQL 16 (Docker Compose in dev; Neon PostgreSQL in production) — no new storage technology.
**Testing**: pytest (backend, SQLite in-memory for unit/integration + live Postgres verification for constraint/commit-sensitive paths per §27.5), Jest/RTL if exercised on the frontend (matching Epics 5–8's own frontend test posture — no new frontend test framework).
**Target Platform**: Linux server (Docker), browser (Next.js SSR + CSR).
**Project Type**: Web application — FastAPI backend + Next.js frontend, extending the existing monolith.
**Performance Goals**: per spec.md §47 — list endpoints p95 < 300ms at 100K rows; lead conversion p95 < 2s; Customer 360 p95 < 1s; pipeline report p95 < 2s at 10K open opportunities; dashboard p95 < 1s.
**Constraints**: `company_id` isolation on every query (repository + service + API layers, never frontend-only); every cross-module FK (`customer_id`, `source_lead_id`, `quotation_id`) validated against `company_id` at write time; all monetary values `Numeric(15,2)` (never float); soft-delete only, no hard delete of any CRM entity; lead conversion is a single-transaction, single-commit, idempotent operation; no distributed locking.
**Scale/Scope**: 6 new tables, 19 new RBAC permissions, 11 new domain events, ~25 new API endpoints, 1 new feature flag (`feature.crm.enabled`). Comparable in size to Epic 4 (Users & Roles), materially smaller than Epic 7 (Sales, 20+ tables) or Epic 8 (Accounting, 30+ tables).

### Constitution Check

*GATE: Must pass before Phase 1 implementation. Re-checked after design phase (§36).*

| Principle | Status | Notes |
|---|---|---|
| Clean Architecture layering | PASS | Router → Service → Repository, zero cross-layer violations planned (§8, §9, §21) |
| Multi-tenancy (`company_id` everywhere) | PASS | All 6 tables extend `TenantBaseModel`; every repository method takes `company_id` (§6, §7) |
| Soft delete on non-financial entities | PASS | All 6 CRM entities soft-delete only, no hard delete (§25 of spec.md, reaffirmed §7 here) |
| Audit trail completeness | PASS | New `CrmAuditService`, same shape as `CompanyAuditService`/`AccountingAuditLogRepository`, synchronous within the same transaction (§18) |
| Repository Pattern | PASS | No direct DB access from services or routers; all CRM data access via repositories (§8) |
| Feature Flag strategy | PASS | `feature.crm.enabled`, own `CrmFeatureFlagService` mirroring `SalesFeatureFlagService`/`AccountingFeatureFlagService` (§17 of spec.md; wired here in §21.7) |
| No hardcoded secrets | PASS | No new secrets introduced |
| No circular dependencies | PASS | CRM depends on Sales/Accounting service interfaces (one direction only); Sales/Accounting have zero knowledge of or dependency on CRM (§5, §15, §16) |
| Epic 4 RBAC integration | PASS | 19 permissions follow `crm.<resource>.<action>`, seeded via the existing `RoleSeedService`/`Permission`/`RolePermission` tables (§17) |
| Epic 7/8 integration | PASS | Reuses `Customer`, `AccountsReceivableService` by reference; publishes/consumes events via the existing per-module `InProcessEventBus` pattern (§15, §16, §19) |
| Backward compatibility | PASS | Zero modification to Epic 1–8 code; §16 "Modified Files" list is empty by design (§29) |
| Monetary precision | PASS | `Opportunity.value` is `Numeric(15,2)`, matching every existing Sales/Accounting monetary column |
| Missing-commit defect class avoided | PASS | Every planned write method in §9 explicitly ends in `db.commit()`; directly informed by the pre-Epic-9 hardening audit findings |
| Cross-tenant lookup defect class avoided | PASS | Every planned cross-module FK validation in §6/§8 explicitly filters by `company_id`; directly informed by the same audit's tenant-isolation finding |

**Constitution Check Result: ALL PASS — Phase 1 implementation approved to proceed.**

---

## 2. Current Architecture Assessment

This plan is grounded in direct inspection of the current repository (not assumed from spec.md), performed as part of both the Epic 9 spec-writing phase and this planning phase. Verified facts:

### 2.1 Module Skeleton (verified against `modules/purchase/`, `modules/accounting/`, `modules/sales/`)

Every existing business module follows an identical skeleton:
```
modules/<name>/
├── models/          # SQLAlchemy ORM, extend TenantBaseModel
├── schemas/         # Pydantic v2 request/response
├── repositories/     # One class per aggregate, extends BaseRepository[Model]
├── services/         # Application services, constructed with injected repos
├── events/           # Dataclass event definitions + module-local InProcessEventBus
├── handlers/          # (only some modules) cross-module event subscribers
├── dependencies.py   # FastAPI DI factories (Depends(get_db) → repo → service)
├── constants.py       # (some modules) enums/constants
├── exceptions.py       # Typed exception classes
└── router.py           # FastAPI router, StandardResponse[T]/PaginatedResponse[T]
```
CRM will follow this exact skeleton (§29).

### 2.2 Base Model (verified: `backend/core/database/models/tenant_base.py`)

`TenantBaseModel` provides: `id` (`Uuid`, `server_default=text("gen_random_uuid()")`), `company_id` (`Uuid`, not null, indexed), `created_by` (`Uuid`, nullable), `created_at`/`updated_at` (`DateTime(timezone=True)`, `server_default=func.now()`, `updated_at` also `onupdate=func.now()`), `is_deleted` (`Boolean`, `server_default=false()`), `deleted_at` (nullable). **No `updated_by` column exists anywhere in the codebase's base models** — CRM will not invent one (matches the finding already made during spec-writing).

### 2.3 Router Mounting (verified: `backend/api/v1/router.py`, `backend/main.py`)

Every module router is imported and mounted identically:
```python
from modules.accounting.router import router as accounting_router
...
router.include_router(
    accounting_router,
    prefix="/companies/{company_id}/accounting",
    dependencies=[Depends(get_current_company_member)],
)
```
This is the single tenant-membership gate applied at include-time, not per-endpoint. CRM's router will be mounted the same way at `/companies/{company_id}/crm`.

### 2.4 App Startup (verified: `backend/main.py`'s `lifespan`)

`run_migrations()` runs on startup; `register_integration_handlers()` (currently Accounting's cross-module event subscriptions) is called inside `lifespan`. CRM will add its own `register_crm_integration_handlers()` call alongside it, in the same place, for the two event subscriptions in §15.4/§19.2 — never modifying the existing Accounting registration call.

### 2.5 RBAC Reality (verified during spec-writing research, re-confirmed here)

`modules/users_roles/constants.py` holds the single permission catalog (`INITIAL_PERMISSIONS: tuple[PermissionDefinition, ...]`) and `SYSTEM_ROLES`/`DEFAULT_ROLE_PERMISSIONS`. **Sales and Purchase routers currently enforce authentication only** (`Depends(require_authenticated)`, no per-permission checks). **Accounting is the only module doing real fine-grained RBAC**, via `user_has_accounting_permission()` in `modules/accounting/services/permission_check.py`. This asymmetry is real and current, not a documentation gap — confirmed by direct code inspection during the spec phase. CRM's architectural decision to follow Accounting's pattern (spec.md §53 AD-01) is reaffirmed here (§17).

### 2.6 Audit Reality

No platform-wide audit table exists. `CompanyAuditLog` (Companies module) and `AccountingAuditLog` (Accounting module, append-only, no update/delete method) are both module-local. CRM will add its own module-local `crm_audit_log` table (§18), continuing this exact established pattern rather than inventing a shared table.

### 2.7 Customer Master Reality (verified: `modules/sales/models/customer.py`)

`Customer` (table `customers`) already exists with: `customer_code`, `customer_type`, `category_id` (required FK), `group_id` (nullable), `legal_name`, `trading_name`, `status` (DRAFT/ACTIVE/ON_HOLD/BLOCKED/INACTIVE), `payment_term_id`, `credit_limit`, `credit_status`, `rating`, `currency_code`, `tax_registration_number`, `custom_fields` (JSONB), `notes`, `version` (optimistic lock), `tsvector_search`. It has **no owner/salesperson-assignment field and no acquisition-source field** — a genuine, confirmed gap, not something CRM would be duplicating by adding its own `owner_id`/`source_id` on Lead/Opportunity instead of on Customer. `CustomerContact`, `CustomerAddress`, `CustomerBankDetail`, `CustomerNote` are separate child tables — no generic/standalone Contact entity exists anywhere in the codebase.

### 2.8 Accounts Receivable Reuse Points (verified: `modules/accounting/services/ar_service.py`)

`AccountsReceivableService.get_customer_ledger(company_id, customer_id)` (returns `total_outstanding_base`, `credit_status`), `.get_customer_aging(company_id, customer_id, as_of_date)`, `.get_customer_statement(company_id, customer_id, from_date, to_date)` are the exact, existing, already-tested methods Customer 360 will call — confirmed present and correctly scoped by `company_id`.

### 2.9 Testing Directory Convention (verified: `backend/tests/`)

```
tests/unit/modules/<name>/
tests/integration/repositories/<name>/
tests/integration/api/v1/<name>/
tests/security/<name>/
tests/performance/<name>/
```
CRM's test suite will populate `tests/{unit,integration/repositories,integration/api/v1,security,performance}/crm/`.

### 2.10 Frontend Convention (verified: `frontend/src/app/(protected)/`)

Route groups `(accounting)`, `(purchase)`, `(sales)`, `(inventory)`, `(companies)` already exist side by side under `(protected)/`. CRM adds `(crm)/` alongside them — confirmed this is a flat sibling structure, not nested.

---

## 3. Spec vs Existing-System Reconciliation

| # | Spec.md requirement | Reconciliation |
|---|---|---|
| A. Already exists, reused as-is | Customer, CustomerContact, CustomerAddress, `AccountsReceivableService`, `TenantBaseModel`, `StandardResponse`/`PaginatedResponse`/`PaginationParams`, `get_current_company_member`, permission catalog + `RoleSeedService`, per-module `InProcessEventBus` pattern, `SalesQuotation` (referenced by id only) |
| B. Partially exists, extended safely | The **permission catalog** is extended with 19 new `crm.*` rows (additive, same table, no schema change) — not the Customer table itself, which is left completely untouched |
| C. Genuinely new | 6 tables (§6), `modules/crm/` module skeleton, `CrmAuditService`+`crm_audit_log`, `CrmFeatureFlagService`, `user_has_crm_permission()` helper, `register_crm_integration_handlers()` |
| D. Would duplicate an existing system (avoided) | A CRM-local Customer/Contact table (avoided — reuse `customers`/`customer_contacts`); a CRM-local financial ledger (avoided — read-only calls into `AccountsReceivableService`); a second RBAC/audit/event-bus/pagination system (avoided — all four follow the established per-module pattern, not a new cross-cutting mechanism) |
| E. Existing functionality at risk, and how it is protected | Customer's `category_id`-required constraint could break Lead-conversion Customer creation if not handled — mitigated by auto-provisioning a default CRM-conversion Customer Category the same way a default Pipeline is auto-provisioned (§10.3); `Customer.version` optimistic lock could reject a conversion under concurrent Sales-side edits — mitigated by the conversion service catching the stale-version case and retrying the read (not silently swallowing it) |

---

## 4. CRM Architecture

CRM is planned as a fifth "customer-facing" module alongside Sales, sitting upstream of it in the business process but architecturally a **peer**, not a layer Sales depends on. Sales and Accounting have zero code-level awareness of CRM's existence — no import of `modules.crm` appears anywhere in `modules/sales/` or `modules/accounting/`. CRM imports *from* Sales (`CustomerService`, `CustomerRepository`, `SalesOrderRepository`-adjacent read paths) and *from* Accounting (`AccountsReceivableService`), one direction only, exactly mirroring how Accounting already imports from Sales/Purchase/Inventory today (via event handlers, not direct service calls, for those three — CRM's Accounting integration is a direct read-only service call instead, since it needs a synchronous response to render Customer 360, not a fire-and-forget side effect; see §16 for the explicit reasoning).

```
        ┌─────────────┐        reads         ┌──────────────┐
        │     CRM      │ ───────────────────► │    Sales      │
        │ (this epic)  │   Customer, Quotation  │  (Epic 7)     │
        └──────┬───────┘   (by reference only) └──────────────┘
               │
               │ reads (read-only service calls)
               ▼
        ┌──────────────┐
        │  Accounting   │
        │  (Epic 8)     │
        └──────────────┘
```

No CRM code path writes to `customers`, `sales_quotations`, `sales_orders`, `sales_invoices`, `payments`, or any `accounting_*` table. This is enforced structurally (§8: no `INSERT`/`UPDATE`/`DELETE` statement against those tables appears anywhere in CRM's repository layer), not just as a documented intention.

---

## 5. Domain Boundaries

Restated from spec.md §9 with implementation-layer precision:

| Table/Concern | Owner Module | CRM's Access |
|---|---|---|
| `customers`, `customer_contacts`, `customer_addresses` | Sales (`modules/sales`) | Read via `CustomerRepository.get_by_id_or_none()`; write via `CustomerService.create()` (conversion only, §10) |
| `sales_quotations`, `sales_orders`, `sales_invoices` | Sales | Read `quotation_id` link only; never written by CRM |
| `accounting_journal_entries`, AR/AP ledgers, payments | Accounting (`modules/accounting`) | Read via `AccountsReceivableService` methods only; never written by CRM |
| `permissions`, `roles`, `role_permissions`, `company_members` | Users & Roles (`modules/users_roles`) | Read via the existing `CompanyMemberRepository`/`RolePermissionRepository` (for ownership validation, §5 of spec.md); CRM adds *rows* to `permissions`/`role_permissions` via the standard seeding mechanism, never a new table |
| `companies`, feature flags | Companies (`modules/companies`) | CRM's own feature flag lives in a CRM-local table (`crm_feature_flags`, mirroring `sales_feature_flags`/`accounting_feature_flags` — confirmed each module owns its own flag table, no shared one exists) |
| `crm_leads`, `crm_lead_sources`, `crm_pipelines`, `crm_pipeline_stages`, `crm_opportunities`, `crm_activities`, `crm_audit_log`, `crm_feature_flags` | **CRM (this epic)** | Full ownership |

---

## 6. Data Model Plan

All 6 tables from spec.md §37, planned here with SQLAlchemy-level precision matching the established model conventions (verified against `modules/purchase/models/purchase_order.py` and `modules/accounting/models/gl.py` for exact `mapped_column` idiom).

### 6.1 `LeadSource` (table: `crm_lead_sources`)

```python
class LeadSource(TenantBaseModel):
    __tablename__ = "crm_lead_sources"
    __table_args__ = (
        Index("ix_crm_lead_sources_company_active", "company_id", "is_active"),
        UniqueConstraint("company_id", "code", name="uq_crm_lead_sources_company_code"),
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
```
*(Note: `UniqueConstraint` here is a plain constraint, not a partial index, since `is_deleted` filtering for soft-deleted rows reusing a code is an acceptable edge case at this table's low cardinality — unlike the pipeline default-flag constraint in §6.3, which genuinely needs partial-index semantics.)*

### 6.2 `Lead` (table: `crm_leads`)

Full field list per spec.md §37.2. Notable planning details:
- `status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'NEW'"))` with a DB `CHECK` constraint enumerating the 6 states.
- `owner_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)` — matches the exact `sales_rep_id`-style convention confirmed on `SalesOrder`/`SalesQuotation` (plain UUID column, no enforced cross-module FK).
- `converted_customer_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)` — same cross-module-reference convention.
- `converted_opportunity_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("crm_opportunities.id"), nullable=True)` — real FK, since this is same-module.
- `version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))` — optimistic lock, matching `Customer.version`.

### 6.3 `Pipeline` (table: `crm_pipelines`)

```python
__table_args__ = (
    Index(
        "uq_crm_pipelines_company_default",
        "company_id",
        unique=True,
        postgresql_where=text("is_default = true AND is_deleted = false"),
    ),
)
```
This is the **database-level enforcement of BR-008** (exactly one default pipeline per company) — a partial unique index, matching the exact pattern already used elsewhere in this codebase for a similar "at most one default/active X" invariant (the same idiom Accounting used for its own single-active-fiscal-year-style constraints).

### 6.4 `PipelineStage` (table: `crm_pipeline_stages`)

Two partial unique indexes (at most one `is_won_stage=true`, at most one `is_lost_stage=true`, per `pipeline_id`), same technique as §6.3.

### 6.5 `Opportunity` (table: `crm_opportunities`)

- `customer_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)` — required, cross-module reference convention.
- `value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, server_default=text("0"))`.
- `probability: Mapped[int] = mapped_column(Integer, nullable=False)` — `CHECK (probability BETWEEN 0 AND 100)`.
- `status: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'OPEN'"))`.
- `weighted_value` is **not a stored column** — computed at read time in the service/schema layer (`value * probability / 100`), consistent with the spec's BR-010 ("never independently editable") and avoiding a denormalized column that could drift from its inputs. (§26 revisits this if list-view performance profiling later justifies a computed/generated column — deferred, not pre-built.)

### 6.6 `Activity` (table: `crm_activities`)

`CHECK (lead_id IS NOT NULL OR customer_id IS NOT NULL OR opportunity_id IS NOT NULL)` — DB-level enforcement of BR-006, not application-only.

### 6.7 `CrmAuditLog` (table: `crm_audit_log`) — see §18 for full design.

### 6.8 `CrmFeatureFlag` (table: `crm_feature_flags`) — see §17.7-equivalent, modeled directly on `SalesFeatureFlag`/`AccountingFeatureFlag`.

No JSON columns are introduced anywhere in the CRM schema — every field identified in spec.md has a clear normalized, typed column; the input brief's caution against unjustified JSON is honored (Customer's own `custom_fields: JSONB` precedent exists but is not needed here since CRM's field set is fully known and finite).

---

## 7. Database/Migration Plan

**One new Alembic migration**, numbered sequentially after the current head. As of this plan, the confirmed current migration head is `054` (`054_fix_quotation_revision_modified_at_length.py`, the last hardening-audit fix) — CRM's migration will be `055_crm_foundation.py`, with `down_revision = "054"`, preserving the single linear chain (verified via `alembic heads`/`alembic history` showing zero branches as of the pre-Epic-9 audit).

### 7.1 Migration Contents

- `op.create_table()` for all 8 tables in dependency order: `crm_lead_sources`, `crm_pipelines`, `crm_pipeline_stages`, `crm_leads`, `crm_opportunities`, `crm_activities`, `crm_audit_log`, `crm_feature_flags`.
- Every column's `server_default` MUST be declared explicitly in the raw `op.create_table()` DDL, matching the ORM model exactly — this is the single most important lesson from migrations 051–054 (four separate real defects, all caused by raw DDL omitting a `server_default` the ORM model declared). This migration will be diffed column-by-column against its own models before being considered complete (§27.5).
- All indexes and partial-unique constraints from §6 created in the same migration (not deferred to a later one).
- `downgrade()` drops all 8 tables in reverse dependency order — a clean, fully reversible migration (no data to preserve on downgrade, since this is a new-table migration, not an alter-existing-table one).

### 7.2 Verification Plan

Bi-directional verification (`upgrade` → `downgrade` → `upgrade`) against an isolated throwaway Postgres container, exactly the technique already used and proven throughout Epics 5–8's hardening (never against the shared persistent dev database). A drift-check script (the same one written ad hoc during the pre-Epic-9 audit, comparing `Base.metadata` against live `information_schema` per column) will be re-run against this migration specifically before it is considered done.

### 7.3 No Existing Table Altered

This migration contains zero `ALTER TABLE` statements against any Epic 1–8 table — confirmed as a hard constraint of this plan (§29 "DO NOT TOUCH" list).

---

## 8. Repository Plan

One repository class per aggregate, each extending the existing `BaseRepository[Model]` (`core/repositories/base.py`) for standard `create`/`update`/`soft_delete`/`get_by_id_or_none` (all of which already commit correctly, per `BaseRepository`'s own established, audited implementation):

| Repository | File | Notes |
|---|---|---|
| `LeadSourceRepository` | `modules/crm/repositories/lead_source.py` | Simple CRUD + `list_for_company()` |
| `LeadRepository` | `modules/crm/repositories/lead.py` | + `find_matching_customer_candidates()` (email/phone/legal_name lookup, §10), `list_filtered()` (status/source/owner/date-range) |
| `PipelineRepository` | `modules/crm/repositories/pipeline.py` | + `get_default_for_company()` |
| `PipelineStageRepository` | `modules/crm/repositories/pipeline_stage.py` | + `count_open_opportunities_on_stage()` (for BR-007's deactivation guard) |
| `OpportunityRepository` | `modules/crm/repositories/opportunity.py` | + `list_filtered()`, aggregate query methods for §24 reporting (`sum_value_by_stage()`, `sum_weighted_value()`, etc.) |
| `ActivityRepository` | `modules/crm/repositories/activity.py` | + `list_filtered()`, `list_overdue()` |
| `CrmAuditLogRepository` | `modules/crm/repositories/audit_log.py` | `create()` + `list_for_entity()` only — **no `update`/`delete` method defined at all**, exactly matching `AccountingAuditLogRepository`'s precedent |

**Every method accepting an `id` parameter also requires and filters by `company_id` in the same query** — no two-step "fetch then check company_id" pattern anywhere, directly per the pre-Epic-9 hardening audit's Finding 8 (defense-in-depth gap flagged in `JournalLineRepository`/`transfer_repository.update_line`) — CRM's repositories are planned to not repeat that gap from day one rather than needing a follow-up hardening pass.

---

## 9. Service Plan

| Service | File | Key methods (each ending in explicit `db.commit()` on every write path) |
|---|---|---|
| `LeadService` | `services/lead_service.py` | `create()`, `update()`, `qualify()`, `disqualify()`, `assign()`, `soft_delete()` |
| `LeadConversionService` | `services/lead_conversion_service.py` | `convert()` — the single-transaction, idempotent, optimistic-locked method from spec.md §16; kept in its **own** service file (not folded into `LeadService`) because of its cross-module orchestration complexity (calls `CustomerService`, `OpportunityService`, `CrmAuditService`, publishes an event) — separating it makes the transaction boundary and its tests easy to reason about in isolation |
| `PipelineService` | `services/pipeline_service.py` | `create_pipeline()`, `update_pipeline()`, `create_stage()`, `update_stage()` (rejects deactivation per BR-007) |
| `OpportunityService` | `services/opportunity_service.py` | `create()`, `update()`, `assign()`, `change_stage()`, `win()`, `lose()` |
| `ActivityService` | `services/activity_service.py` | `create()`, `update()`, `complete()` (cascades `Lead.last_contact_date`/status, §19.2), `soft_delete()` |
| `Customer360Service` | `services/customer_360_service.py` | `get_customer_360(company_id, customer_id)` — a dedicated **read/query service**, per the input brief's explicit "create a dedicated read/query service rather than contaminating transactional services" instruction; composes CRM repositories + `CustomerRepository` (Sales) + `AccountsReceivableService` (Accounting), never writes anything |
| `CrmReportingService` | `services/reporting_service.py` | Pipeline/lead/activity report aggregations (§24), dashboard KPI computation — mirrors the existing `kpi_service.py` "compute a dict of metrics" pattern already used by Sales and Accounting |
| `CrmAuditService` | `services/audit_service.py` | `record(*, company_id, actor_user_id, entity_type, entity_id, action, before_state=None, after_state=None)` — same signature shape as `CompanyAuditService.record()` |
| `CrmFeatureFlagService` | `services/feature_flag_service.py` | `is_enabled(company_id)` — mirrors `SalesFeatureFlagService`/`AccountingFeatureFlagService` exactly |

Every service is constructed via `dependencies.py` DI factories in the exact `Depends(get_db) → Repo(db) → Service(repo, ...)` chain already used by every existing module (verified against `modules/purchase/dependencies.py`).

---

## 10. Customer Master Strategy

**Decision**: `Customer` (Sales, `modules/sales/models/customer.py`) remains the single, unmodified customer master. CRM never creates a second one.

### 10.1 What CRM Adds vs What It Reuses

CRM does **not** alter the `customers` table (no new column, no new migration against it). The two fields the input brief's own §4 implicitly wants ("sales representative ownership," "lead source") that Customer does not have are kept CRM-side instead: `Lead.owner_id`/`Lead.source_id` (pre-conversion) and `Opportunity.owner_id`/`Opportunity.source_lead_id` (post-conversion) fully cover this need without touching Customer at all — a customer's "current owner" for CRM purposes is derivable as "the owner of its most recent Opportunity," not a stored Customer column, avoiding any Customer-table change.

### 10.2 Conversion Write Path

`LeadConversionService.convert()` calls the **existing, unmodified** `CustomerService.create()` (Sales) when no matching Customer is found (match logic: email → phone → legal_name, `company_id`-scoped, excluding soft-deleted rows, per spec.md §16.1). This is a genuine cross-module service call, not a duplicated implementation — `CustomerService.create()`'s own validation, sequencing, and commit behavior are reused unchanged.

### 10.3 Required-Field Gap Handling

`Customer.category_id` is a required FK. `CustomerService.create()` will be called with a company-scoped default "General"/"CRM-Converted" `CustomerCategory` — auto-provisioned the same way a default `Pipeline` is auto-provisioned on first CRM enable (spec.md §54 assumption), via a new `CrmProvisioningService.ensure_defaults(company_id)` call triggered once when `feature.crm.enabled` is turned on for a company (implementation detail added here, not present in spec.md, marked below).

> **RECOMMENDATION — NOT REQUIRED BY CURRENT SPEC**: `CrmProvisioningService.ensure_defaults()` as a distinct, explicitly-named service is an implementation-layer addition to satisfy spec.md §54's assumption about auto-provisioning; spec.md describes the *outcome* (a default pipeline exists) but not this specific mechanism. Necessary as an architectural dependency of §10.3/§11.

### 10.4 Preserving Existing Guarantees

`Customer.version` (optimistic locking) is respected, not bypassed — if a concurrent Sales-side edit changes a Customer's `version` between CRM's match-lookup and its use in Opportunity creation, no write is made to Customer at all in that path (Opportunity only *references* `customer_id`, it doesn't update the Customer row), so there is no actual conflict to handle for the *existing-customer* match branch. The *new-customer* branch calls `CustomerService.create()` once, which sets the initial `version=1` itself — no race exists there either, since it's a fresh insert.

---

## 11. Lead Management

Implementation-layer detail beyond spec.md §14–§15: `LeadService.qualify()`/`disqualify()` are thin wrappers around a single `_transition_status()` private helper (mirroring the exact `_transition_status()` idiom already used in `modules/inventory/services/product_service.py` for its own lifecycle transitions) — one state-machine validation function, not two separate ad hoc implementations. `LeadService.create()` validates BR-005-adjacent field requirements (at least one of first/last/company name; at least one of email/phone) at the Pydantic schema layer first (`LeadCreate` schema `model_validator`), with a service-layer re-check only for the fields no schema validator can express (uniqueness-adjacent checks, none required here since Lead has no unique constraint on email/phone by design — duplicates are expected and handled at conversion time, not at capture time).

---

## 12. Opportunity/Pipeline

`OpportunityService.change_stage()` reads the target `PipelineStage`, confirms `stage.pipeline_id == opportunity.pipeline_id` (INV-004) and `stage.is_active`, then updates `stage_id` and `probability` (inherited from the stage's default, unless the caller explicitly passes an override in the same request — both paths supported per spec.md §17.1's "independently overridable"). `win()`/`lose()` are guarded by `status == 'OPEN'` checked via `UPDATE ... WHERE status = 'OPEN'` (the row-level concurrency guard from spec.md §43, not a separate `version` column). `PipelineStageRepository.count_open_opportunities_on_stage()` backs the BR-007 deactivation guard in `PipelineService.update_stage()`.

---

## 13. Activities/Tasks

`ActivityService.complete()` is transactionally coupled to `LeadService`'s `last_contact_date`/status cascade (spec.md §19.2) — implemented as one service method that, within its own single-commit transaction, updates the Activity AND (if `lead_id` is set and the Lead is currently `NEW`) the linked Lead's `status`/`last_contact_date`, rather than as two separate service calls with two separate commits (avoiding a re-run of the exact "two writes, only one committed" defect class the hardening audit found repeatedly). `GREATEST(current, this_completion_timestamp)` semantics for `last_contact_date` (spec.md Edge Cases) are implemented as a SQL `GREATEST()` expression in the `UPDATE`, not a read-then-compare-then-write round trip, to avoid a race between two near-simultaneous completions.

---

## 14. Customer 360

`Customer360Service.get_customer_360()` issues, per request: one `CustomerRepository.get_by_id_or_none()` call (Sales), one `LeadRepository` query (leads where `converted_customer_id = customer_id`), one `OpportunityRepository` query (opportunities where `customer_id = customer_id`, paginated/limited), one `ActivityRepository` query (activities where `customer_id = customer_id`, paginated/limited, most-recent-first), and two `AccountsReceivableService` calls (`get_customer_ledger()`, `get_customer_aging()`). This is **6 bounded queries, zero N+1 loops** — no per-opportunity or per-activity additional query is issued (each list query already returns its needed fields; no lazy-loaded relationship is traversed row-by-row). Sales quotation/order/invoice "summary counts" (spec.md §20.1) are single `COUNT(*)`-style aggregate queries against the existing Sales repositories, not full document fetches.

---

## 15. Sales Integration

### 15.1 Direction and Mechanism

CRM → Sales is **read-only + one write path** (Customer creation during conversion, §10.2). Sales has zero code referencing `modules.crm` — confirmed as a hard constraint (§29).

### 15.2 Opportunity → Quotation Handoff

Per spec.md §21.1, this is a **UI-orchestrated redirect with pre-fill**, not a backend API call between modules — the frontend Opportunity detail page's "Create Quotation" button navigates to Sales' existing quotation-creation UI with `customer_id` pre-filled via query parameter. The created `quotation_id` is written back onto `Opportunity.quotation_id` via a small, explicit `PATCH /crm/opportunities/{id}` call from the frontend after Sales confirms creation — not an automatic backend event subscription, matching the spec's explicit "not automatic" decision.

### 15.3 No Duplicated Sales Logic

Confirmed nothing in this plan re-implements: invoice creation, order creation, pricing resolution, inventory reservation/stock deduction, or payment posting. CRM's `Opportunity.value` is a manually-entered estimate, never derived from or reconciled against a real Quotation/Order total by CRM code (a human keeps them roughly aligned; no automated sync is planned, avoiding a whole class of consistency-maintenance code neither the spec nor this plan requires).

### 15.4 Events Consumed

`register_crm_integration_handlers()` (new, `modules/crm/handlers/integration_handlers.py`) subscribes to Sales's existing `InProcessEventBus` for `sales.quotation.accepted` and `sales.order.credit_hold` (both events already exist and are published by Sales today — confirmed in `specs/007-sales-management/spec.md` §34), each handler doing nothing more than writing a CRM Activity/note for salesperson visibility (spec.md §21.2) — no state mutation on any CRM aggregate is triggered by an inbound Sales event, keeping the "human always confirms pipeline movement" invariant (§18.1 of spec.md) intact.

---

## 16. Accounting Integration

**Direct, synchronous, in-process read-only service calls** — not an event subscription — because Customer 360 needs a response within the same HTTP request (spec.md NFR-003's 1-second p95 target assumes an in-process call, not a fire-and-forget async round trip). This exactly mirrors how Sales' own `credit_check_service.py` already calls into Accounting synchronously for credit-hold checks (confirmed precedent) — CRM is not inventing a new cross-module calling convention, it is reusing the one that already exists for exactly this kind of "needs a live answer now" scenario. No CRM code ever calls `PostingEngine`, writes an `ARTransaction`, or touches any table under `modules/accounting/models/`. Credit-limit *enforcement* (blocking an order) remains entirely Sales/Accounting's responsibility (`credit_check_service.py`); CRM only *displays* the credit status/outstanding balance it reads, per spec.md §22's explicit ownership statement — this plan does not add any CRM-side enforcement logic.

---

## 17. RBAC

### 17.1 Permission Registration

19 `PermissionDefinition` tuples (§31.1 of spec.md) appended to `modules/users_roles/constants.py`'s `INITIAL_PERMISSIONS` tuple — an additive change to an existing file (the only Epic 1–8 file this plan modifies at all, and only by appending new tuple entries, never altering an existing one). `DEFAULT_ROLE_PERMISSIONS` gets 19 new entries added to the relevant existing role-slug keys (`owner`, `admin`, `manager`, `accountant`, `salesperson`, `viewer`; `cashier`/`store-keeper` keys are untouched since they receive zero new grants), matching the access matrix in spec.md §31.2 exactly.

### 17.2 Seeding

No new seeding mechanism — the existing `RoleSeedService.seed_permissions()`/`seed_roles_for_company()` (idempotent, already runs at company-creation time) will pick up the new catalog entries automatically once §17.1's additive constants change ships. **Existing companies** (created before this epic) need their permission catalog backfilled — handled by the migration in §7 also calling the equivalent of `RoleSeedService.seed_permissions()` logic for the new rows only (an idempotent, additive `INSERT ... ON CONFLICT DO NOTHING`-style migration step, not a destructive reseed), so no company loses or has altered any of its existing role-permission grants.

### 17.3 Enforcement

New `modules/crm/services/permission_check.py::user_has_crm_permission(db, company_id, user_id, permission_code)` — same generic-on-`permission_code` shape as `user_has_accounting_permission`, a CRM-local thin wrapper (per the established per-module convention — no shared cross-module permission-check function exists today, confirmed during spec research), called inline in every CRM router handler per the endpoint table in spec.md §38.

### 17.4 No New Role

Confirmed: zero new system roles created. All 19 permissions map onto the 8 existing role slugs only.

---

## 18. Audit Trail

### 18.1 `CrmAuditLog` Table

```python
class CrmAuditLog(TenantBaseModel):
    __tablename__ = "crm_audit_log"
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)  # LEAD | OPPORTUNITY | ACTIVITY
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```
JSONB is justified here specifically (unlike §6.8's "no JSON" rule for the core entities) because `before_state`/`after_state` are, by definition, a variable-shape snapshot of whichever entity changed — exactly the same justified use of JSONB `CompanyAuditLog` and `AccountingAuditLog` already make for the identical reason.

### 18.2 `CrmAuditLogRepository`

`create()` and `list_for_entity(company_id, entity_type, entity_id)` only — no `update`/`delete` method exists on the class at all (not "exists but raises `NotImplementedError`" — genuinely absent, matching `AccountingAuditLogRepository`'s exact precedent, confirmed by direct inspection during spec research).

### 18.3 Call Sites (all within the same transaction as the state change, same-commit)

`LeadService.create/update/assign/qualify/disqualify`, `LeadConversionService.convert`, `OpportunityService.create/change_stage/assign/win/lose`, `ActivityService.complete` (status-transition only, per spec.md §44's explicit "not routine note-taking" scoping).

---

## 19. Events

### 19.1 Event Bus

New `modules/crm/events/__init__.py`:
```python
_crm_event_bus: EventBus = InProcessEventBus()
def get_event_bus() -> EventBus:
    return _crm_event_bus
```
Exact copy of the pattern already independently implemented in `modules/sales/events/__init__.py`, `modules/accounting/events/__init__.py`, `modules/purchase/events/__init__.py` — no shared/global bus instance, consistent with the confirmed "each module owns its own bus" convention.

### 19.2 Event Definitions

12 dataclasses in `modules/crm/events/{lead_events,opportunity_events,activity_events}.py`, each following the exact `@dataclass` + `event_type`/`aggregate_type` field-default idiom shown in `modules/sales/events/order_events.py::OrderCreated` — per spec.md §36 for the full list and payload shapes.

### 19.3 Publish Call Sites

`get_event_bus().publish(...)` called from the relevant service method, after the `db.commit()` that persisted the underlying change (matching the existing convention observed across Sales/Purchase: commit first, publish second, so a subscriber never observes an event for data that isn't actually durably persisted yet).

### 19.4 Registration

`register_crm_integration_handlers()` (§15.4) wired into `main.py`'s `lifespan`, alongside (not replacing) the existing `register_integration_handlers()` call for Accounting.

---

## 20. AI Readiness

No implementation in this epic — restated from spec.md §51, with the implementation-layer confirmation that nothing in this plan blocks it: `Lead.score` is a plain nullable `Integer` column any future job can `UPDATE`; all 12 events (§19) carry `company_id` + entity id + relevant business fields sufficient for a future training pipeline to consume without a payload redesign; `crm_audit_log`'s `before_state`/`after_state` JSONB provides the same "who/what/when/before/after" signal shape Accounting's own AI-readiness section already relies on. No AI SDK, model, or inference endpoint is added anywhere in this plan.

---

## 21. API Design

### 21.1 Router File

`modules/crm/router.py`, mounted in `api/v1/router.py` as:
```python
router.include_router(
    crm_router,
    prefix="/companies/{company_id}/crm",
    dependencies=[Depends(get_current_company_member)],
)
```
— the one-line addition to `api/v1/router.py` (plus its corresponding import line) is the **only** change to that shared file this plan makes; both are pure additions, zero existing lines touched.

### 21.2 Endpoint Set

The ~25 endpoints enumerated in spec.md §38.1–§38.6, unchanged here — this plan does not add or remove any endpoint from the approved spec's list.

### 21.3 Router → Service → Repository Discipline

No router handler in `modules/crm/router.py` will import or instantiate a repository directly — every handler calls exactly one service method (or, for `GET /crm/customers/{id}/360`, the dedicated `Customer360Service`), matching the Clean Architecture layering already enforced (and re-verified as PASS) across every existing module.

### 21.4 Every Endpoint Specifies

Per spec.md §38's own per-endpoint table (permission code) plus this plan's addition: `Depends(require_authenticated)` (base auth, same as every module) → inline `user_has_crm_permission()` check (§17.3) → Pydantic request schema validation → service call → Pydantic response schema → `StandardResponse[T]`/`PaginatedResponse[T]` envelope. Error handling uses the existing typed-exception-to-HTTP-status translation already registered globally in `main.py`'s exception handlers (`NotFoundException` → 404, `ConflictException` → 409, validation errors → 422) — no new exception-handling middleware is added; CRM's `exceptions.py` defines typed subclasses (`LeadNotFoundError`, `InvalidLeadTransitionError`, etc.) that plug into the existing handler registry the same way every other module's exceptions do.

### 21.5 Feature Flag Gate

A single FastAPI dependency, `require_crm_enabled` (`modules/crm/dependencies.py`), applied at router-include time alongside `get_current_company_member` — checked once per request, before any handler runs, returning the documented "feature not enabled" error response (matching FR-020 of spec.md) rather than each handler re-checking it individually.

---

## 22. Search/Filtering/Pagination

All list endpoints use the shared `PaginationParams`/`PaginatedResponse[T]` (`core/schemas/pagination.py`) — `page`/`page_size`, max `page_size=100`, confirmed as the intended shared-kernel convention (its own module docstring states "All list endpoints in DevSphere ERP return `PaginatedResponse[T]`"). Filtering (status, source, owner, date ranges, stage, value ranges — per spec.md §42) is implemented as repository-level `WHERE` clauses built from optional query parameters, never an in-memory filter over a fully-loaded list. Free-text search (lead name, company name) uses `ILIKE '%term%'` against indexed columns at Epic 9's expected data volumes (spec.md §42's explicit decision not to add a `tsvector` full-text index pre-emptively, unlike `Customer.tsvector_search`) — revisit only if a future performance benchmark shows it's needed (§26).

---

## 23. Frontend Architecture

New route group `frontend/src/app/(protected)/(crm)/`, sibling to the existing `(accounting)`/`(sales)`/`(purchase)`/`(inventory)`/`(companies)` groups (confirmed flat structure, verified by listing the actual directory). Pages per spec.md §39's table. `frontend/src/components/crm/` for CRM-specific components, reusing the existing shared component library (tables, forms, modals, loading/empty/error-state patterns) rather than introducing new ones — confirmed no new UI dependency is added. `frontend/src/lib/api/crm.ts` — one API client file, matching the existing `frontend/src/lib/api/accounting.ts` pattern exactly. Permission-aware UI: action buttons (convert, assign, win/lose, pipeline-manage) are conditionally rendered based on the authenticated user's CRM permissions, fetched once via the existing session/permissions context (no new client-side permission-fetching mechanism introduced).

---

## 24. Dashboard/Reporting

`CrmReportingService` (§9) computes, per spec.md §40–41: pipeline value by stage/owner/source, won/lost value and win rate for a period, average deal size, average sales cycle, lead counts by status/source, conversion rate, activities completed, overdue follow-ups. Every aggregate is a single SQL `GROUP BY`/aggregate-function query against the CRM tables (plus, for lead-source attribution, a join to `crm_lead_sources`) — no report performs a full-table scan-and-aggregate-in-Python, and no report duplicates an Accounting calculation (financial figures shown alongside pipeline data, if any, are fetched live via §16's read-only calls, never recomputed).

---

## 25. Security

Implementation-layer confirmation of spec.md §46's 12 SEC test cases: cross-tenant 404s are achieved structurally because every repository `get_by_id_or_none()`-style method requires `company_id` in its `WHERE` clause (§8) — there is no code path where a CRM resource can be fetched by `id` alone. `converted_customer_id`/`converted_opportunity_id` are never accepted as client input on any request schema (Pydantic schemas for `LeadCreate`/`LeadUpdate` simply don't declare those fields) — SEC-07 is enforced by the schema shape itself, not a runtime check that could be forgotten. All error responses flow through the existing global exception handlers (`main.py`), which are already confirmed (Phase 16/17 of Epic 8's own hardening) to redact stack traces/internal paths in non-development `ENVIRONMENT` settings — CRM adds no new exception-handling code path that could bypass that existing redaction.

---

## 26. Performance

Indexes planned in §6 directly target spec.md §47's targets: `(company_id, status)`/`(company_id, owner_id)` on Lead and Opportunity cover the two most common list-filter combinations; `(company_id, due_date)` on Activity covers the overdue-follow-ups report; `(company_id, pipeline_id, stage_id)` on Opportunity covers the Kanban pipeline view's grouping query. `weighted_value` is computed at read time (§6.5) rather than stored, which is a deliberate performance/correctness trade-off — if a future load test against the 10,000-open-opportunities target (spec.md NFR-004) shows read-time computation is too slow in the pipeline aggregate report specifically, the mitigation is a computed/generated SQL column (`GENERATED ALWAYS AS (value * probability / 100) STORED`) added via a follow-up migration, not a redesign — flagged here as a monitored risk (§33), not pre-emptively built. No caching layer, materialized view, or Elasticsearch index is introduced in this epic.

---

## 27. Testing Strategy

Mirrors spec.md §48, with implementation-layer file-path precision:

### 27.1 Unit (`tests/unit/modules/crm/`)
Lead/Opportunity state-machine transition tests (valid + invalid pairs), `weighted_value` calculation, customer-matching priority logic (mocked repository, no DB), Activity-completion cascade logic.

### 27.2 Repository (`tests/integration/repositories/crm/`)
Tenant isolation per table (6 tables × create-in-A/query-from-B), the 3 partial-unique-index constraints (§6.3/§6.4), the Activity CHECK constraint (§6.6), lead-conversion transaction atomicity (forced mid-conversion failure → assert Lead untouched, no orphan Customer/Opportunity).

### 27.3 API (`tests/integration/api/v1/crm/`)
Full CRUD + action-endpoint coverage per spec.md §38; all 12 SEC-01–SEC-12 cases as real HTTP requests (matching the exact test style already used in `tests/integration/api/v1/accounting/test_journal_api.py`'s `TestRejectRBAC`-class pattern, itself a direct product of the pre-Epic-9 hardening audit's own new regression tests — CRM inherits that improved testing discipline from day one, not as a later retrofit).

### 27.4 Security (`tests/security/crm/`)
RBAC matrix test: all 19 permissions × all 8 roles (152 assertions), matching the exact style of `tests/security/accounting/test_rbac.py`.

### 27.5 PostgreSQL-Specific Verification

Per spec.md §48.5 and this plan's own §7.2/§9: live Docker/Postgres verification of the migration, plus a live create → fresh-HTTP-GET check for Lead creation, Opportunity creation, and Lead conversion specifically (the three highest-risk write paths, chosen because they are exactly the shape of write that the pre-Epic-9 hardening audit found broken 50+ times elsewhere in this codebase) — this is not optional or deferred; it is a Definition-of-Done item (§35).

### 27.6 E2E

Lead → Qualify → Convert → Opportunity → (Create Quotation handoff, verified up to the point Sales takes over) — one Playwright/manual-equivalent test, matching spec.md §48.4.

---

## 28. Regression Strategy

Zero Epic 1–8 files are modified except the one additive, append-only change to `modules/users_roles/constants.py` (§17.1) and the one additive `include_router()` call plus import line in `api/v1/router.py` (§21.1). Because both changes are pure additions (new tuple entries, new router-mount block) with no existing line altered, the expected regression risk is minimal — but per the established pre-Epic-9-audit discipline, the **full targeted regression suite** (Users/Roles, plus a quick full-suite run given the shared `constants.py` file) will be run after implementation, not assumed clean from the diff shape alone. Any pre-existing flaky/unrelated test (matching the one already-known timing-sensitive test called out in this epic's own kickoff prompt) will be re-run in isolation and documented, not silently ignored, following the exact verification discipline established during the hardening audit.

---

## 29. File-Level Changes

### 29.1 NEW FILES

```
backend/modules/crm/
├── __init__.py
├── constants.py
├── dependencies.py
├── exceptions.py
├── router.py
├── models/
│   ├── __init__.py
│   ├── lead.py               # Lead, LeadSource
│   ├── pipeline.py           # Pipeline, PipelineStage
│   ├── opportunity.py        # Opportunity
│   ├── activity.py           # Activity
│   ├── audit.py               # CrmAuditLog
│   └── feature_flag.py        # CrmFeatureFlag
├── schemas/
│   ├── __init__.py
│   ├── lead.py, pipeline.py, opportunity.py, activity.py, customer_360.py, reports.py
├── repositories/
│   ├── __init__.py
│   ├── lead_source.py, lead.py, pipeline.py, pipeline_stage.py, opportunity.py, activity.py, audit_log.py, feature_flag_repository.py
├── services/
│   ├── __init__.py
│   ├── lead_service.py, lead_conversion_service.py, pipeline_service.py, opportunity_service.py,
│   ├── activity_service.py, customer_360_service.py, reporting_service.py, audit_service.py,
│   ├── feature_flag_service.py, permission_check.py, provisioning_service.py
├── events/
│   ├── __init__.py
│   ├── lead_events.py, opportunity_events.py, activity_events.py
└── handlers/
    ├── __init__.py
    └── integration_handlers.py

backend/migrations/versions/055_crm_foundation.py

backend/tests/unit/modules/crm/...
backend/tests/integration/repositories/crm/...
backend/tests/integration/api/v1/crm/...
backend/tests/security/crm/...
backend/tests/performance/crm/...

frontend/src/app/(protected)/(crm)/
├── dashboard/page.tsx
├── leads/page.tsx, leads/[leadId]/page.tsx, leads/new/page.tsx
├── opportunities/page.tsx, opportunities/pipeline/page.tsx, opportunities/[opportunityId]/page.tsx
├── activities/page.tsx
├── customers/[customerId]/page.tsx
├── reports/page.tsx
└── settings/page.tsx

frontend/src/components/crm/...
frontend/src/lib/api/crm.ts

specs/009-crm/
├── data-model.md, research.md, quickstart.md
├── contracts/events.md, contracts/crm-v1.yaml (generated later, mirroring Epic 8's own late-phase OpenAPI generation)
└── tasks.md   # NOT created in this phase — /sp.tasks output
```

### 29.2 MODIFIED FILES (exhaustive — nothing else)

| File | Change |
|---|---|
| `backend/modules/users_roles/constants.py` | Append 19 new `PermissionDefinition` tuples to `INITIAL_PERMISSIONS`; append corresponding entries to `DEFAULT_ROLE_PERMISSIONS` for `owner`/`admin`/`manager`/`accountant`/`salesperson`/`viewer` |
| `backend/api/v1/router.py` | Add one import line + one `include_router()` block for `crm_router` |
| `backend/main.py` | Add one call to `register_crm_integration_handlers()` inside `lifespan`, alongside the existing Accounting call |

### 29.3 DO NOT TOUCH

Every file under `backend/modules/{sales,purchase,inventory,accounting,companies,auth}/`, every existing migration (`001`–`054`), every existing frontend route group, every existing test file. Confirmed zero planned changes to any of these.

---

## 30. Implementation Sequence

10 phases (consolidating the input brief's suggested 20-step list into cohesive, independently-testable phases — matching the phase granularity already proven across Epics 5–8, where each phase is a real, demonstrable increment, not an artificially small step):

| Phase | Name | Delivers |
|---|---|---|
| 0 | Foundation & Domain Boundaries | Module skeleton, `dependencies.py`, `exceptions.py`, feature-flag scaffolding, `CrmProvisioningService` stub |
| 1 | Data Model & Migration | All 8 tables, migration `055`, bi-directional Postgres verification (§7.2) |
| 2 | Repository Layer | All 7 repositories (§8), repository-level tenant-isolation tests |
| 3 | Lead Management | `LeadService`, `LeadSourceRepository`-backed CRUD, lifecycle + qualification, unit + API tests |
| 4 | Lead Conversion | `LeadConversionService`, Customer-matching, default-category/pipeline provisioning, atomicity + idempotency tests (highest-risk phase, tested most heavily) |
| 5 | Opportunity & Pipeline | `PipelineService`, `OpportunityService`, Kanban-supporting stage-change/win/lose endpoints |
| 6 | Activities | `ActivityService`, Lead-cascade logic, overdue-follow-up query |
| 7 | Customer 360 & Reporting | `Customer360Service`, `CrmReportingService`, dashboard endpoint |
| 8 | RBAC, Audit, Events, API Layer | Permission catalog append, `CrmAuditService`, event bus + handlers, full `router.py` wiring into `api/v1/router.py` |
| 9 | Frontend, Hardening & Final Verification | All `(crm)/` pages, live Postgres verification of every write path, full regression suite (§28), performance benchmarks, documentation, Definition of Done sign-off (§35) |

This order differs from the input brief's suggested 20-step list in one deliberate way: **Customer 360 is placed after Opportunity/Activities (phase 7), not before Sales/Accounting integration**, because Customer 360 is itself the aggregation point that *consumes* Lead/Opportunity/Activity data — building it earlier would mean building it against an empty data model and re-testing it after every subsequent phase. RBAC/Audit/Events are consolidated into one phase (8) rather than three, because in practice (confirmed by how Epic 8 was actually built) these three concerns are threaded through every service method as they're written, not bolted on afterward — planning them as a separate later phase in isolation would be artificial; phase 8 here represents the *verification and API-wiring* checkpoint for concerns that were actually being satisfied incrementally in phases 3–7 (each phase's own service methods already call `CrmAuditService.record()` and `get_event_bus().publish()` as they're written, per §18.3/§19.3 — phase 8 confirms full coverage, it doesn't introduce audit/events from scratch at the end).

---

## 31. Task Dependencies

| Phase | Prerequisite Phase(s) | DB Dependency | API Dependency | Frontend Dependency | Test Dependency |
|---|---|---|---|---|---|
| 0 | none | none | none | none | none |
| 1 | 0 | none (creates schema) | none | none | Phase 0's module skeleton must exist for models to import into |
| 2 | 1 | Migration `055` applied | none | none | Phase 1's tables must exist |
| 3 | 2 | `crm_leads`, `crm_lead_sources` | none | none | Phase 2's `LeadRepository`/`LeadSourceRepository` |
| 4 | 3, 10.3's provisioning | `crm_opportunities` (created here alongside Lead conversion, or pulled forward from Phase 5 if sequencing proves cleaner during actual implementation) | Sales' `CustomerService.create()` (existing, unmodified) | none | Phase 3's Lead lifecycle must be stable first |
| 5 | 2 (can run parallel to 3/4) | `crm_pipelines`, `crm_pipeline_stages`, `crm_opportunities` | none | none | Phase 2 |
| 6 | 2 (can run parallel to 3/4/5) | `crm_activities` | none | none | Phase 2; soft dependency on Phase 3 for the Lead-cascade test |
| 7 | 3, 4, 5, 6 | all CRM tables | Accounting's `AccountsReceivableService` (existing, unmodified), Sales' `CustomerRepository` (existing, unmodified) | none | Phases 3–6 must all have data to aggregate |
| 8 | 3, 4, 5, 6, 7 | `crm_audit_log`, `crm_feature_flags` | `modules/users_roles/constants.py` append, `api/v1/router.py` append | none | Phases 3–7's service methods (audit/event call sites already exist in them per §30's note) |
| 9 | 8 | none | Phase 8's full router must be live | Phases 3–8 | Full regression suite (§28), full security matrix (§27.4) |

**Note on Phase 4's Opportunity dependency**: Opportunity's table is logically owned by Phase 5 (Pipeline) but is *also* required by Phase 4 (Lead Conversion, which creates an Opportunity). The migration in Phase 1 creates the table once, up front, so this is not a real circular dependency — only a note that Phase 4's service code and Phase 5's service code both touch the `Opportunity` model, and whichever is implemented first will define the model file (`models/opportunity.py`) the other then imports.

---

## 32. ADRs

### ADR-1: Customer Master Ownership

**Decision**: `Customer` remains solely owned by Sales; CRM never creates a second customer table.
**Reason**: Confirmed via direct inspection that `Customer` already exists, is actively used by Sales/Accounting, and adding CRM-specific fields (`owner_id`, `source_id`) directly to it would require an Epic 7 migration this epic is explicitly forbidden from making.
**Alternatives considered**: (a) Add `owner_id`/`source_id` columns to `Customer` directly. (b) Create a CRM-local `crm_customer_profile` 1:1 extension table.
**Why rejected**: (a) violates the explicit "do not modify Epic 1-8 tables" constraint and couples Sales' schema to a CRM concept it doesn't otherwise need. (b) was seriously considered but rejected as unnecessary — every "extension" field CRM needs (owner, source) is naturally a property of the *Lead* or *Opportunity* relationship to a customer, not of the customer itself (a customer can have been engaged by different salespeople over time via different opportunities), so a 1:1 extension table would need updating on every new engagement anyway, providing no benefit over just reading the latest Opportunity's `owner_id`.
**Impact**: Zero schema risk to Sales; Customer 360's "current owner" is a derived value (most recent Opportunity's `owner_id`), not a stored fact — acceptable given no requirement demands persisted, directly-queryable "current owner" outside the Customer 360 view itself.

### ADR-2: CRM vs Sales Boundary

**Decision**: CRM reads Sales data by direct repository/service call; Sales has zero awareness of CRM.
**Reason**: One-directional dependency keeps Sales fully independent and un-modifiable by this epic, matching the explicit backward-compatibility mandate (§28).
**Alternatives considered**: Bidirectional event-based integration (Sales publishes events CRM subscribes to, AND CRM publishes events Sales subscribes to for lead-context enrichment).
**Why rejected**: Sales publishing events specifically *for* CRM would require modifying Sales code (new event publish call sites) — forbidden. CRM subscribing to Sales' *existing* events (already published, e.g. `sales.quotation.accepted`) is fine and is exactly what's planned (§15.4) — the distinction is "consume what already exists" vs "ask Sales to add something new," and only the former is in scope.
**Impact**: Sales' `git diff` for this epic is empty. CRM's Sales integration is entirely additive from CRM's side.

### ADR-3: CRM vs Accounting Boundary

**Decision**: Synchronous, in-process, read-only service calls (not events) for Customer 360's financial data.
**Reason**: Customer 360 needs a live answer within one HTTP request; an event-based/eventually-consistent model would either require CRM to cache financial data (explicitly forbidden by spec.md §20.2) or accept stale data, neither acceptable.
**Alternatives considered**: (a) Event-driven with CRM caching last-known AR balance. (b) A new Accounting API endpoint CRM calls over HTTP.
**Why rejected**: (a) directly violates "CRM should NOT duplicate financial values." (b) is unnecessary network-hop overhead for an in-process monolith — the existing precedent (Sales' `credit_check_service.py` calling Accounting in-process) already proves the simpler pattern works and is idiomatic here.
**Impact**: Customer 360 latency is bounded by Accounting's own service response time, which is already known-fast (verified during Epic 8's own performance benchmarking).

### ADR-4: Lead Conversion Strategy

**Decision**: Single transaction, single commit, optimistic-locked, idempotent-by-status.
**Reason**: Directly informed by the pre-Epic-9 hardening audit's central finding — this is the highest-value place in the whole epic to apply that lesson correctly the first time.
**Alternatives considered**: (a) Saga/compensating-transaction pattern (create Customer, then Opportunity, each with its own commit, with manual rollback logic on failure). (b) Distributed lock on the Lead row during conversion.
**Why rejected**: (a) reintroduces exactly the multi-commit fragility the hardening audit spent an entire session fixing elsewhere — a single DB transaction already gives atomic rollback for free, with no compensating-logic code to get wrong. (b) is explicitly forbidden by the input brief ("do not add unnecessary distributed locking") and unnecessary given the `version`-column optimistic-lock pattern already proven elsewhere in this codebase (`Customer.version`) handles the realistic concurrency window (a human clicking "convert" twice, not a high-throughput contention scenario).
**Impact**: Conversion is provably atomic and safe to retry; §27.2's forced-failure test directly verifies this.

### ADR-5: Opportunity Ownership

**Decision**: `Opportunity.owner_id` is a plain UUID column (no enforced FK), matching `SalesOrder.sales_rep_id`'s exact convention.
**Reason**: Consistency with the established cross-module-reference idiom already used throughout Sales; a real FK to `users.id` would require importing the Auth module's model into CRM's model file, a coupling none of the sibling modules (Sales, Purchase) currently accept either.
**Alternatives considered**: A real `ForeignKey("users.id")` constraint (the Users/Roles-internal convention, e.g. `CompanyMember.user_id`).
**Why rejected**: Would make CRM's `Opportunity` model inconsistent with its closest sibling, `SalesOrder`, for no functional benefit — ownership validation (§30.3 of spec.md) is already enforced at the service layer via `CompanyMemberRepository`, which is a stronger and more informative check (confirms *active membership in this company*, not just "any user exists") than a bare FK constraint would provide anyway.
**Impact**: None negative; matches existing convention exactly.

### ADR-6: Customer 360 Aggregation Strategy

**Decision**: A dedicated `Customer360Service` (read-only query service), not a method bolted onto an existing transactional service.
**Reason**: Explicit instruction in the input brief; also matches Clean Architecture's separation between write-side application services and read-side query composition.
**Alternatives considered**: Add a `get_360()` method to `CustomerService` (Sales) directly.
**Why rejected**: Would require modifying a Sales file (forbidden) and would blur Sales' own service responsibility (transactional customer management) with a CRM-specific read-model composition concern that has nothing to do with Sales' own needs.
**Impact**: Clean separation; `Customer360Service` lives entirely within `modules/crm/`, importing *from* Sales/Accounting but never modifying them.

### ADR-7: Tenant Isolation Strategy

**Decision**: Every CRM repository method requires `company_id`; no fetch-by-id-alone method exists anywhere in the CRM codebase.
**Reason**: Directly informed by the pre-Epic-9 hardening audit's tenant-isolation findings.
**Alternatives considered**: Rely on the router-level `get_current_company_member` gate alone, matching Sales/Purchase's weaker per-endpoint isolation posture.
**Why rejected**: That gate only proves the *caller* belongs to the company in the URL — it says nothing about whether a resource ID embedded in the request body/query actually belongs to that company (exactly the class of bug the hardening audit found in `invoice_service.py`). CRM's repositories close that gap structurally from the start.
**Impact**: Slightly more verbose repository signatures (every method takes `company_id`) in exchange for a category of bug being structurally impossible rather than merely tested-for.

### ADR-8: RBAC Strategy

**Decision**: Real, fine-grained RBAC enforcement (Accounting's pattern), not Sales/Purchase's current auth-only pattern.
**Reason**: Restated from spec.md §53 AD-01; reaffirmed here after direct code verification that the asymmetry is real and current.
**Alternatives considered**: Match Sales/Purchase's simpler auth-only pattern for consistency with "most" of the existing codebase.
**Why rejected**: "Most modules do it" is not, on its own, sufficient reason to repeat a pattern already identified as a gap by the very audit that immediately preceded this epic; CRM's owner-based, assignable, customer-relationship data has a stronger access-control need than either Sales/Purchase module's current CRUD-only exposure.
**Impact**: A small amount of extra per-endpoint code (`user_has_crm_permission()` inline check) in exchange for genuine access control from day one; explicitly flagged as a recommendation for Sales/Purchase to later adopt the same pattern (out of this epic's scope).

### ADR-9: Audit Strategy

**Decision**: CRM-local `crm_audit_log` table + `CrmAuditService`, not a shared platform-wide table.
**Reason**: No shared table exists today (verified); inventing one is a cross-cutting platform change outside this epic's scope.
**Alternatives considered**: Write CRM audit events into `CompanyAuditLog` (Companies module) by adding `entity_type`/`entity_id` columns to it.
**Why rejected**: Would require modifying an Epic 3 (Companies) table/model — forbidden. Also would couple CRM's audit granularity (per-entity-type, high volume from Activity completions) to a table whose current use case (company-level configuration changes) is much lower-volume; mixing them risks Companies' own audit queries slowing down as CRM audit volume grows.
**Impact**: One more append-only table in the schema, consistent with the established per-module pattern; zero coupling to Companies' internals.

### ADR-10: Event Strategy

**Decision**: CRM's own `InProcessEventBus` instance; 12 events only (no speculative event coverage).
**Reason**: Matches the established one-bus-per-module convention exactly; 11 is the minimum set needed to cover spec.md's own auditable/reportable-transition list, no more.
**Alternatives considered**: A shared/global event bus instance across all modules.
**Why rejected**: No such shared instance exists today (confirmed); introducing one would be a cross-cutting platform change (and, per the constitution §49, the bus implementation must already be abstracted behind an interface — the per-module instantiation already satisfies that without needing a shared singleton).
**Impact**: None negative; CRM's events are fully isolated from and cannot be silently coupled to any other module's event volume/failure modes.

### ADR-11: Soft-Delete/Archive Strategy

**Decision**: All 6 CRM entities are soft-delete only; a WON/LOST Opportunity is additionally *practically* immutable (business rule) even though its `is_deleted` flag exists structurally.
**Reason**: Matches `TenantBaseModel`'s universal soft-delete convention and the constitution's "never hard-delete historical business records" rule; matches Sales Invoice's own "issued invoices are immutable" precedent for the WON/LOST case.
**Alternatives considered**: Hard-delete Leads/Activities after a retention period via a scheduled job.
**Why rejected**: No existing module in this codebase implements scheduled hard-deletion of business records; introducing one for CRM alone would be new infrastructure outside this epic's scope and contradicts the constitution's blanket rule.
**Impact**: CRM tables grow monotonically (soft-deleted rows retained) — acceptable at CRM's expected data volumes (§26); a future data-retention epic can add archival tooling generically across all modules if ever needed, not CRM-specifically.

### ADR-12: AI-Readiness Strategy

**Decision**: Data-model and event readiness only; zero AI code.
**Reason**: Explicit epic-scope boundary in spec.md §51 and the input brief's own instruction.
**Alternatives considered**: none seriously considered — this was never ambiguous.
**Impact**: None — purely a scope confirmation.

### ADR-13: Performance Strategy

**Decision**: Index-first, computed-at-read-time `weighted_value`, no caching/search infrastructure at launch; a generated SQL column is the pre-identified fallback if benchmarking later proves it necessary.
**Reason**: Matches the constitution's "avoid premature optimization" principle while still providing concrete, named indexes for every confirmed high-frequency query pattern.
**Alternatives considered**: Pre-build a materialized view for the pipeline report; pre-build a `tsvector` search index on Lead.
**Why rejected**: Neither is justified by any confirmed current performance problem — both are explicitly named in the input brief as things to avoid pre-emptively; CRM's expected data volumes (spec.md §26/§47) do not yet demonstrate a need.
**Impact**: Simpler initial implementation; a documented, specific fallback path exists if a future load test proves it wrong (§33 risk register).

---

## 33. Risk Register

| # | Risk | Mitigation |
|---|---|---|
| R-01 | Duplicate customer master accidentally introduced | ADR-1; code review checklist item (§35) explicitly checks for any new table resembling `Customer`; ownership matrix (§5) is the reviewable artifact |
| R-02 | Breaking Epic 7 Customer references | Zero `ALTER TABLE customers` anywhere in this plan (§7.3); `CustomerService.create()` called unmodified, not monkey-patched or subclassed |
| R-03 | Cross-tenant data leakage | ADR-7; every repository method requires `company_id`; full isolation test suite (§27.2) covering all 6 tables |
| R-04 | Customer 360 N+1 queries | §14's explicit 6-bounded-query design, verified by a query-count assertion in the Customer 360 integration test (a new test technique for this codebase, recommended here as a concrete regression guard against future N+1 regressions as the view grows) |
| R-05 | CRM dashboard/report performance at scale | Indexes per §26; performance test at 10K+ opportunities per spec.md §47/NFR-004, run before Phase 9 sign-off |
| R-06 | RBAC permission matrix mistakes (wrong role gets/lacks access) | Full 19×8 matrix test (§27.4), not a spot-check; matrix is committed as a table in spec.md §31.2, reviewable independent of code |
| R-07 | Lead conversion creates duplicate customers | ADR-4; exact-match-only detection (email→phone→legal_name) is deliberately conservative; forced-failure atomicity test (§27.2) |
| R-08 | Historical data integrity (soft-deleted rows corrupting reports) | All reporting queries (§24) explicitly filter `is_deleted = false`; no report aggregates across soft-deleted rows |
| R-09 | Migration `055` repeats the 051–054 defect class (missing server default/constraint) | §7.1's explicit column-by-column diff-against-model verification step; §7.2's bi-directional live-Postgres check; this is the single most heavily cross-referenced risk in this plan given its four-times-repeated history in this exact codebase |
| R-10 | Future AI integration requires a data-model change anyway, despite "readiness" claims | Accepted risk — no readiness claim can be proven until an actual AI feature is built; mitigated only by following the same readiness pattern Accounting's own (already-partially-tested-in-practice-via-Phase-17) AI-readiness work established, which is the best available precedent in this codebase |
| R-11 | Sales/Purchase's weaker auth-only RBAC pattern makes CRM's stricter pattern look inconsistent to future developers, inviting a "just match the other modules" downgrade later | ADR-8's reasoning documented explicitly in-spec and in-plan, with an explicit recommendation (not a requirement of this epic) that Sales/Purchase adopt CRM's/Accounting's stronger pattern in a future hardening pass |
| R-12 | `Customer.category_id`-required constraint blocks lead conversion if the default-category provisioning step is skipped or fails silently | `CrmProvisioningService.ensure_defaults()` is called synchronously when `feature.crm.enabled` is turned on (not lazily on first conversion attempt), so a missing default category is a visible, testable failure at flag-enable time, not a confusing runtime error deep inside a conversion transaction |

---

## 34. Known Gaps

**GAP-01**: Spec.md §21.1 describes the Opportunity → Quotation handoff as UI-orchestrated with a follow-up `PATCH` call to set `Opportunity.quotation_id`. This means `quotation_id` can, in principle, go stale or be left unset if a user creates a Quotation in Sales directly (bypassing the CRM "Create Quotation" button) and never links it back.
**Why it exists**: Spec.md explicitly forbids an automatic/forced transition here (§21.1's own reasoning) — a fully automatic link would require either a Sales-side event CRM subscribes to specifically for this (requiring a new Sales event, which requires modifying Sales — forbidden) or a periodic reconciliation job (new infrastructure, out of scope per §30 of the input brief).
**Affected Epic**: 9 (CRM) and 7 (Sales) at their boundary.
**Recommended solution**: Accept as a known, documented limitation for Epic 9; the Customer 360 view (§14) still shows all Quotations for the customer directly from Sales regardless of whether `Opportunity.quotation_id` is set, so no information is actually lost to the user — only the specific Opportunity-to-Quotation traceability link may be incomplete in edge cases.
**Fix now or defer**: Defer. Not a correctness or security issue, purely a traceability nicety; fixing it properly would require a Sales-side change this epic is explicitly forbidden from making.

**GAP-02**: No per-record ownership filtering (a Salesperson can view all leads/opportunities in the company via `crm.leads.view`, not just their own) — restated from spec.md §53 AD-02.
**Why it exists**: Deliberately deferred to avoid introducing row-level security as a second authorization dimension within the same epic that establishes CRM's foundational RBAC.
**Affected Epic**: 9.
**Recommended solution**: A future epic/phase adds an optional `owner_id = current_user_id` filter, toggleable per company (some companies want full visibility, some want strict territory isolation) — the data model (`owner_id` already present on Lead/Opportunity) supports this additively, no schema change needed later.
**Fix now or defer**: Defer, as explicitly directed by spec.md.

**GAP-03**: Sales/Purchase's own RBAC enforcement remains auth-only (unrelated to CRM directly, but CRM's stricter posture highlights the inconsistency).
**Why it exists**: Pre-existing, confirmed during both the pre-Epic-9 hardening audit and this plan's own research; not introduced by CRM.
**Affected Epic**: 6 (Purchase), 7 (Sales).
**Recommended solution**: A future hardening pass (already recommended once, by the pre-Epic-9 audit itself) brings Sales/Purchase up to Accounting's/CRM's RBAC strictness.
**Fix now or defer**: Defer — explicitly out of Epic 9's scope; Epic 9 does not modify Sales/Purchase code at all (§29.3).

---

## 35. Definition of Done

Epic 9 implementation is DONE only when every item below is true:

- [x] All 8 CRM tables created via migration `055`, verified bi-directionally against real Postgres (§7.2), zero server-default/constraint drift from their ORM models (§7.1) — T100 item 1, live isolated-container replay.
- [x] All 7 repositories implemented, every method `company_id`-scoped, tenant-isolation tests passing for all 6 business tables (§27.2) — `test_tenant_isolation.py`, fresh pass.
- [x] All 9 services implemented, every write path ending in an explicit `db.commit()` (verified by code review against the exact checklist the pre-Epic-9 hardening audit used)
- [x] All ~25 API endpoints implemented and live, Router→Service→Repository discipline confirmed (no repository imported into `router.py`) — 36 CRM-domain endpoints + 4 module-administration endpoints (`/status`, `/enable`, `/disable`, `/my-permissions`) added post-closure to genuinely close the "CRM can be enabled" and "permission-aware frontend" gaps below; `grep` confirms zero repository imports in `router.py`.
- [x] All 19 RBAC permissions registered and enforced, full 19×8 matrix test passing (§27.4) — `test_rbac.py`, fresh pass (152/152).
- [x] `crm_audit_log` recording all actions listed in spec.md §44, verified by an audit-coverage test — `test_audit_coverage.py`, fresh pass; independently re-confirmed live (T100 item 5).
- [x] All 12 domain events published on their correct trigger, verified by an event-coverage test — `test_event_coverage.py`, fresh pass; independently re-confirmed live (T100 item 6).
- [x] `feature.crm.enabled` gates the entire module correctly (flag-off → documented error; flag-on → normal operation) — `test_feature_flag_gate.py` fresh pass, plus a **new, genuine gap closed post-closure**: no endpoint previously existed for a company to actually flip this flag from off to on (see the new `/status`/`/enable`/`/disable` endpoints above). Verified live: full off→on→off→on round trip via real HTTP.
- [x] Customer 360 composes CRM + live Sales + live Accounting data correctly, 6-bounded-query design confirmed (no N+1), verified against seeded AR data — `test_customer_360.py` fresh pass; independently re-confirmed live in this closure pass (real credit status/aging/sales-history rendered for a real converted customer).
- [x] Sales integration: zero Sales files modified; Opportunity→Quotation handoff working end-to-end via the UI-orchestrated flow (§15.2) — confirmed true, including after this closure pass; zero Sales files appear in any diff across the whole epic.
- [ ] Accounting integration: zero Accounting files modified; `AccountsReceivableService` calls confirmed live-correct — **the "zero Accounting files modified" half is honestly no longer true**, left unchecked. Live-browser verification found `frontend/src/app/(protected)/(accounting)/dashboard/page.tsx` colliding with CRM's own dashboard at the literal `/dashboard` URL, breaking the entire app (not an `AccountsReceivableService` issue — a pure Next.js routing collision). Fixed via a rename only (`accounting-dashboard/page.tsx`), explicitly approved before being made; zero Accounting business logic touched. `AccountsReceivableService` calls themselves remain confirmed live-correct (see Customer 360 item above). See PHR 0010 for the full account.
- [x] All CRM reports/KPIs (§24) return correct aggregates against seeded data — live-confirmed in T100 item 12 and again in this closure pass (dashboard KPIs, pipeline/lead/activity reports all rendering real, correct data).
- [x] All 12 SEC-01–SEC-12 security test cases passing as real HTTP requests (§27.3) — `test_tenant_and_security.py`, 16/16, fresh pass.
- [x] Performance targets met per spec.md §47 (§27.5/§26), benchmarked at the stated volumes — see tasks.md's Performance Checklist (T092–T095 + T100, all green).
- [x] Full frontend `(crm)/` route group implemented, permission-aware, using existing shared components only — **the "permission-aware" half was a genuine gap, closed post-closure**: the frontend now hides (not just disables) permission-gated actions via a new `useCrmPermissions()` hook backed by `GET /crm/my-permissions`, wired across Leads/Opportunities/Activities/Settings. Verified live: owner role sees and can use every gated action; the endpoint returns the correct 19/19 codes.
- [x] Live Docker/Postgres verification performed for Lead creation, Opportunity creation, and Lead conversion specifically (§27.5) — not SQLite-only — T100 items 8–9, plus re-confirmed again via the full happy-path browser pass in this closure round.
- [x] Full regression suite (Epics 1–9) passes with zero unexplained failures; any pre-existing flaky test documented, not silently ignored (§28) — fresh full-suite run: 5581 passed, 3 failed, all 3 triaged (2 pre-existing Epic 8 flaky/timing, 1 pre-existing environment issue, zero CRM-caused); a 3rd, CRM-suite-only failure observed in one contaminated concurrent run was reproduced in isolation and confirmed passing (test-run contamination from editing `router.py` mid-run, not a real regression).
- [x] `ruff`/`mypy` clean on all new CRM files (zero new errors; pre-existing repo-wide debt in *other* modules not claimed as CRM's responsibility, matching the established reporting convention from the pre-Epic-9 audit) — re-confirmed after all post-closure changes: `ruff check` all-pass, `mypy` zero errors attributable to any `modules/crm/` file (107 errors remain, all pre-existing transitive debt in `sales`/`auth`/`users_roles`/`core`, unchanged in count from before this epic).
- [x] `specs/009-crm/data-model.md`, `research.md`, `quickstart.md`, `contracts/events.md` produced (standard SDD artifacts, not yet created in this plan.md-only phase) — all present, confirmed via directory listing.
- [ ] This plan's own §29.2 "Modified Files" list is exhaustive and accurate — no other Epic 1–8 file was touched, confirmed via `git diff --stat` against the pre-Epic-9 baseline — **honestly no longer exhaustive**, left unchecked to match the Accounting item above. §29.2 pre-dates the post-closure fixes; it does not (and could not) list `accounting-dashboard/page.tsx`, `AuthContext.tsx` (Epic 2), or `companies/[id]/page.tsx` (Epic 3) — all 3 documented in tasks.md's "Post-Closure Gap Remediation" section and in PHR 0010, none rewriting §29.2 retroactively.

---

## 36. Final Implementation Readiness Assessment

Re-reading `specs/009-crm/spec.md` in full against this plan: every functional requirement (FR-001 through FR-022), every business rule (BR-001 through BR-010), every invariant (INV-001 through INV-004), every API endpoint (§38.1–§38.6), every event (§36 of spec.md, 12 events), every permission (§31.1, 19 codes), and every acceptance criterion (§58, 22 items) has a concrete implementation path documented somewhere in this plan (§6–§24, cross-referenced throughout). No spec requirement was found without a corresponding plan section. No existing ERP capability is duplicated (§3, §5, §32 ADR-1 through ADR-3). Epic 7 (Sales) and Epic 8 (Accounting) remain the unmodified source of truth for their domains (§29.3, ADR-2, ADR-3). Multi-tenancy (§ADR-7), RBAC (§17, ADR-8), audit (§18, ADR-9), and events (§19, ADR-10) are each fully defined with concrete file/table/method names, not left abstract. AI-readiness is scoped correctly (§20, ADR-12) with zero AI implementation. Testing (§27) and regression (§28) strategy both explicitly require live-Postgres verification, directly carrying forward the single most important lesson of the pre-Epic-9 hardening audit rather than repeating its root cause. Migration strategy (§7) preserves the single linear Alembic chain. Backward compatibility is reviewed file-by-file (§29.2/§29.3 — exactly 3 files modified, all additive). Known gaps are documented, not hidden (§34). No Epic 10 work of any kind appears anywhere in this plan.

## PLAN READINESS

- Spec fully covered: YES
- Existing architecture reconciled: YES
- Customer master duplication avoided: YES
- Sales boundary defined: YES
- Accounting boundary defined: YES
- Multi-tenancy defined: YES
- RBAC defined: YES
- Audit defined: YES
- Events defined: YES
- AI readiness defined: YES
- Testing defined: YES
- Performance defined: YES
- Migration strategy defined: YES
- Backward compatibility reviewed: YES
- Known gaps documented: YES
- Epic 10 excluded: YES
