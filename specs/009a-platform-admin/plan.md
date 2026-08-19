# Implementation Plan: Epic 9A — Platform Administration / Super Admin

**Branch**: `009a-platform-admin` | **Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)
**Input**: Finalized, Product-Owner-review-ready Specification, commit `83846ab` on `009a-platform-admin`, plus 3 subsequent surgical wording corrections (committed).
**Constitution**: v1.2.1 (authoritative; §50 Platform Administration & SaaS Control Plane Principles)

**Note**: This plan reuses this repository's own established `plan.md` convention (numbered `##` sections, deep repository-grounded "Current-State Findings," per-decision rationale, ADR log) as demonstrated by `specs/009-crm/plan.md` and `specs/008-accounting-finance/plan.md`, rather than the minimal generic template — the generic `.specify/templates/plan-template.md` skeleton is too shallow for the depth this Epic's own Specification demands.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Git / Epic Baseline Verification](#2-git--epic-baseline-verification)
3. [Repository Current-State Findings](#3-repository-current-state-findings)
4. [Platform Domain Architecture](#4-platform-domain-architecture)
5. [Platform Administrator Identity Design](#5-platform-administrator-identity-design)
6. [Platform Session / Authentication Boundary](#6-platform-session--authentication-boundary)
7. [Initial Platform Owner Bootstrap](#7-initial-platform-owner-bootstrap)
8. [Platform RBAC Technical Design](#8-platform-rbac-technical-design)
9. [Tenant Lifecycle Integration](#9-tenant-lifecycle-integration)
10. [Session Revocation Strategy](#10-session-revocation-strategy)
11. [Plans & Subscriptions Architecture](#11-plans--subscriptions-architecture)
12. [Module / Capability Entitlement Architecture](#12-module--capability-entitlement-architecture)
13. [Entitlement Resolution Service](#13-entitlement-resolution-service)
14. [Existing Feature-Toggle Security Hardening](#14-existing-feature-toggle-security-hardening)
15. [Canonical Tenant Context Integration](#15-canonical-tenant-context-integration)
16. [Administrative Overrides](#16-administrative-overrides)
17. [Quota Architecture](#17-quota-architecture)
18. [Usage Metering](#18-usage-metering)
19. [AI Credits Future-Readiness](#19-ai-credits-future-readiness)
20. [Audit Architecture](#20-audit-architecture)
21. [Cross-Tenant Support Access](#21-cross-tenant-support-access)
22. [Platform Dashboard](#22-platform-dashboard)
23. [Frontend Architecture](#23-frontend-architecture)
24. [API Architecture](#24-api-architecture)
25. [Data Model](#25-data-model)
26. [Database Integrity & Concurrency](#26-database-integrity--concurrency)
27. [Existing Module Integration Matrix](#27-existing-module-integration-matrix)
28. [Security Threat Analysis](#28-security-threat-analysis)
29. [Bulk Operations](#29-bulk-operations)
30. [Observability](#30-observability)
31. [Performance / Scalability](#31-performance--scalability)
32. [Testing Strategy](#32-testing-strategy)
33. [Migration / Backward Compatibility Strategy](#33-migration--backward-compatibility-strategy)
34. [Entitlement Rollout Strategy](#34-entitlement-rollout-strategy)
35. [CRM Integration](#35-crm-integration)
36. [Implementation Sequencing](#36-implementation-sequencing)
37. [Architecture Decision Records](#37-architecture-decision-records)
38. [Risks / Mitigations](#38-risks--mitigations)
39. [Complexity Tracking](#39-complexity-tracking)
40. [Technical Unknowns Resolved](#40-technical-unknowns-resolved)
41. [Out of Scope (Explicit Non-Goals)](#41-out-of-scope-explicit-non-goals)
42. [Final Cross-Check / Planning Readiness](#42-final-cross-check--planning-readiness)

---

## 1. Executive Summary

Epic 9A adds a genuinely reachable **Platform Administration control plane** to DevSphere ERP: a first-class `PlatformAdministrator` identity structurally separate from every tenant identity; a real, permission-enforced Platform RBAC (unlike tenant RBAC's currently-inert `Permission`/`RolePermission` scaffold — see §3.2); the missing tenant-suspend/reactivate write path; a generic module/capability entitlement model sitting above the five modules' existing per-module feature-flag tables; SaaS Plan/Subscription/Quota/Override data structures; a fail-closed Platform audit trail; and a time-bounded, inspection-only cross-tenant support-access workflow. It also closes one genuine, spec-mandated security prerequisite discovered during repository reconnaissance: three of the five existing modules' feature-toggle mutation endpoints have no authorization check beyond active tenant membership (§14, §27).

### Technical Context

**Language/Version**: Python 3.12+ (backend, FastAPI 0.115+, Pydantic v2, SQLAlchemy 2.x async-capable ORM used synchronously per existing convention), TypeScript 5.x (frontend, Next.js 16 App Router)
**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic, PyJWT (existing hand-rolled auth — not a third-party "Better Auth" package, see §3.1), Next.js, TanStack Query, TailwindCSS
**Storage**: PostgreSQL 16 (existing `db` Docker Compose service) — no new datastore
**Testing**: pytest (SQLite in-memory for unit/integration, matching existing `backend/tests/conftest.py`), real Docker Compose PostgreSQL for live/migration verification, Playwright-driven browser scripts for frontend live verification (matching this project's established pattern from Epics 7–9)
**Target Platform**: Existing Docker Compose stack (`db`, `api`, `web`, `minio`) — no new service
**Project Type**: Web application (existing `backend/` + `frontend/` structure) — Platform Administration is a new backend module plus a new frontend route group, not a new project
**Performance Goals**: None fabricated (per spec §24, resolved OQ-4) — qualitative: paginated from the outset, indexed lookups, no full-table fetches
**Constraints**: No Redis (confirmed absent from stack, §3.8); no new deployable service; Modular Monolith preserved (Constitution §5)
**Scale/Scope**: Proportionate to current tenant count; no numeric SLA invented

### Constitution Check

*GATE: Must pass before Phase 0 research below. Re-checked in §42 after design.*

| Constitution Principle | Compliance Approach | Status |
|---|---|---|
| §5 Modular Monolith | New `backend/modules/platform_admin/` module within the existing app, same deployable, same DB (§4) | ✅ PASS |
| §9 Multi-Tenant Principles | Platform tables intentionally outside tenant isolation; every reference to a tenant is explicit/audited (§20, §21) | ✅ PASS |
| §11 Feature Toggles | Existing per-module toggle tables reused unmodified; new Plan Entitlement layer sits above them (§12) | ✅ PASS |
| §16 Authentication & Authorization | Reuses `User` credentials; adds a structurally distinct Platform session/token type, never forking core auth (§6) | ✅ PASS |
| §19 Security Principles | Least privilege, IDOR/BOLA protection, CSRF, fail-closed audit all explicitly designed (§20, §28) | ✅ PASS |
| §35 Audit Trail | Reuses the who/what/when/before/after/context schema shape; one new append-only table, not a parallel mechanism (§20) | ✅ PASS |
| §37 SaaS Readiness | Directly operationalizes Plan/Subscription/Quota concepts that had zero implementation (§11, §17) | ✅ PASS |
| §46 Business Configuration | Platform config kept structurally separate from tenant `company_settings` (deferred to Tasks; no violation) | ✅ PASS |
| §47 Plugin Architecture | Billing/AI/notification providers remain adapter boundaries; no provider coupling introduced (§19, §41) | ✅ PASS |
| §50 Platform Administration | This entire plan is the technical realization of §50 | ✅ PASS |

No violations requiring justification. §39 documents the handful of genuinely new abstractions (entitlement resolver, platform session boundary) and why each is necessary rather than speculative.

---

## 2. Git / Epic Baseline Verification

Verified via `git` commands immediately before writing this plan (all read-only, no branch/history change):

- Active branch: `009a-platform-admin` ✅
- Working tree: clean ✅ (only this plan's own new files added afterward)
- `merge-base(009-crm, 009a-platform-admin)` = `37e5ba3` = exact `009-crm` tip → Epic 9A is a direct descendant of the completed Epic 9 codebase, not a concurrent/divergent branch ✅
- `backend/modules/crm/` present on this branch (confirmed during repository reconnaissance, §3) ✅
- `specs/009a-platform-admin/spec.md` present, `Status: Ready for Product Owner approval`, Constitution Version `v1.2.1` ✅
- `.specify/memory/constitution.md` on this branch: `**Version**: 1.2.1` ✅

One tooling note (not a Git/Epic issue): `.specify/scripts/bash/setup-plan.sh`'s branch-name regex (`^[0-9]{3}-`, in `common.sh`'s `check_feature_branch()`) rejects `009a-platform-admin` because of the trailing letter before the dash — while the same file's `find_feature_dir_by_prefix()` gracefully falls back to an exact-match path lookup for non-standard prefixes and resolves correctly. Per explicit instruction not to change branches or Git history, this plan's paths were computed manually, replicating exactly what the script's own fallback logic would have produced (`specs/009a-platform-admin/{spec,plan,research,data-model,quickstart}.md`), and the plan template was copied via the same `cp .specify/templates/plan-template.md` step the script performs. This is a pre-existing, narrow tooling gap (worth a one-line fix to the regex in a future unrelated chore), not a defect in Epic 9A's branch/history.

---

## 3. Repository Current-State Findings

Gathered via targeted, cited code reconnaissance (three parallel research passes) immediately before writing this plan. Format: **Existing capability → reusable component → gap → Epic 9A treatment.**

### 3.1 Authentication & Session Model

- `CurrentUser.roles` is confirmed **hardcoded to `[]`** in `backend/core/auth/dependencies.py`'s `get_current_user()` — every existing `super_admin`-string check (`companies/dependencies.py`'s `require_super_admin()`, `router.py:_requester_role()`, `accounting/services/permission_check.py`) is **dead code that always denies**, exactly as the Specification's Problem Statement (§3) documents.
- "Better Auth" is a **naming convention/placeholder** in this codebase, not the `better-auth` npm/pip package — `backend/core/auth/interfaces.py`'s own docstring says *"REPLACE IN AUTHENTICATION EPIC: wire this to the Better Auth adapter."* The real implementation is a hand-rolled JWT (`PyJWT`, HS256) + refresh-token + session-table system.
- **Reusable**: `sessions` table (`backend/modules/auth/models/session.py`: `user_id`, `is_revoked`, `revoked_at`, `ip_address`, `user_agent`, `device_info` JSONB) and `refresh_tokens` table (SHA-256-hashed, rotate-on-use) are a solid, general revocation primitive.
- **Gap (pre-existing, documented, not fixed by this Epic)**: `get_current_user()` **never queries `Session.is_revoked`** on any request — a revoked session's still-unexpired access token continues to authenticate until natural expiry (default 15 min). Even today's normal `logout()` doesn't immediately invalidate an in-flight access token. The first draft of this plan proposed fixing this as an Epic 9A prerequisite; the corrected suspension design (§10.2) does not depend on it, so it is recorded as an adjacent finding (§10.4, §41) rather than absorbed into scope.
- **Gap (critical, second reconnaissance pass — materially changes ADR-6)**: **a `Session` has no tenant dimension whatsoever.** `backend/modules/auth/models/session.py` defines `sessions` with `user_id`, `is_revoked`, `revoked_at`, `ip_address`, `user_agent`, `device_info` — and **no `company_id`**; its own docstring says *"One user may have multiple concurrent active sessions (e.g., browser + mobile)"*, i.e. a Session models **a device login for a human**, not access to a tenant. Correspondingly, the access-token payload (`jwt_service.py`) is `{sub, email, sid, iat, exp, nbf, jti, iss, aud, typ}` — **no company claim**. And `CurrentUser.company_id` derives from `User.company_id`, which `backend/modules/auth/models/user.py`'s own docstring documents as *"a **nullable** UUID placeholder … Epic 003 (Companies) migration will populate the column"* — it is not a reliable per-request tenant scope. **Company context enters a request exclusively via the URL path parameter `{company_id}`**, validated per-request by `get_current_company_member`.
- **Finding (third reconnaissance pass — supplies the authentication-freshness primitive)**: **login and refresh differ in exactly the way Epic 9A needs.** `AuthService.login()` calls `self._session_repo.create_session(...)`, producing a **new `Session` row** with a new `id` and a new `created_at`. `AuthService.refresh()` calls `rotate_refresh_token(...)` and then `create_access_token(..., session_id=new_record.session_id)` — it **reuses the existing `session_id` and never creates a `Session` row**. Therefore **`Session.created_at` is precisely the authentication-event timestamp**: it advances only on a genuine login and is carried, unchanged, across any number of token refreshes. It already exists (inherited from `BaseModel`, `server_default=func.now()`, documented *"immutable after INSERT"*), is generated server-side, and is never client-supplied. `CurrentUser` already carries `session_id` (from the signed `sid` claim), so this value is reachable at any authorization boundary with one primary-key lookup — **no new JWT claim and no new `Session` column are required** (§10.2).
- **Epic 9A treatment**: reuse the `Session`/`refresh_tokens` *pattern* structurally (new `PlatformSession`/`PlatformRefreshToken` tables, §5–§6) rather than the same tables (tenant sessions must never double as platform sessions, per BR-9A-003). Crucially, because sessions are globally user-scoped, **blunt `UPDATE sessions WHERE user_id IN (members of suspended company)` is rejected** — it would sign a multi-tenant user out of unrelated, still-active companies (a tenant-isolation violation). §10 replaces it with company-scoped access invalidation keyed on `Session.created_at`.

### 3.2 `users_roles` RBAC Reality

- `Permission` (table `permissions`, PK = the dot-notation code string itself) and `RolePermission` (table `role_permissions`) models exist and are seeded, but **production authorization does not consult them** — every wired dependency (`require_rank(minimum_rank)` in `users_roles/dependencies.py`) is **rank-based** (`owner`=100 … `viewer`=20), not permission-code-based. `require_permission_stub()` in `core/auth/interfaces.py` is a literal no-op never used by any router.
- **Epic 9A treatment**: Platform RBAC must be **genuinely enforced by permission code** from day one (the Specification's explicit granular-permission requirement, §15 of spec.md) — it cannot simply mirror tenant RBAC's current pattern, because that pattern is decorative. This is documented explicitly as ADR-2 (§37) rather than silently copying an inert precedent.

### 3.3 Company / Tenant Lifecycle

- `CompanyStatus` enum (`pending_setup`, `active`, `inactive`, `suspended`, `deleted`) and `Company.subscription_id` (nullable FK placeholder, no target table, doc-commented `"Future FK placeholder → subscriptions.id"`) confirmed exactly as spec.md describes.
- `CompanySuspendedError` is raised in exactly one place — `get_current_company()` in `companies/dependencies.py`, checking `company.status == suspended`. This is a **per-request dependency**, not middleware.
- **Gap (critical, second reconnaissance pass — invalidates an assumption in this plan's first draft)**: `get_current_company()` is **not** the dependency the business modules use. All five business-module routers are mounted with `dependencies=[Depends(get_current_company_member)]` (`backend/api/v1/router.py`, lines 93–123), and `get_current_company_member` (`users_roles/dependencies.py`) checks **only** `CompanyMember.status in ("active", "pending_invitation")` — it **never reads `Company.status` at all**. Consequently, suspending a company today would **not** block `/companies/{id}/inventory/…`, `/sales/…`, `/purchase/…`, `/accounting/…`, or `/crm/…` — only the `companies` module's own routes (which use `get_current_company`) would reject. The first draft of this plan asserted "`CompanySuspendedError` already gives block-on-next-request for free"; that is **true only for the `companies` module**, and is corrected here. Closing this is a mandatory part of Epic 9A's suspension feature, not an optional extra — see §10.
- `CompanySuspendedEvent`/`CompanySuspensionLiftedEvent` (`companies/events.py`) are defined but **never instantiated anywhere** — confirmed via full-tree grep. Epic 9A is the first producer.
- **Epic 9A treatment**: reuse `CompanyStatus`/`CompanySuspendedError`/the two domain events exactly as-is (§9); add the missing suspend/reactivate service method plus the new active-session-revocation step (§10).

### 3.4 Audit Infrastructure — Three Independent Patterns, Not One

| Table | Commit semantics | Verbatim evidence |
|---|---|---|
| `auth.audit_logs` | **Fail-open** | `audit_service.py`: *"catches and logs any internal exception so that a broken audit write never causes the caller to fail."* |
| `companies.company_audit_logs` | **Independently committed** | Repository calls `self.db.add(log); self.db.commit()` — decoupled from the caller's own transaction |
| `accounting.accounting_audit_log` | **Fail-closed (only existing precedent)** | Service docstring: *"only flush()es (never commits) — the caller commits the audit record together with the financial action... in the same database transaction."* |

- **Epic 9A treatment**: Platform audit (BR-9A-024, FR-9A-204: audit-write failure MUST fail the mutation) can **only** follow the Accounting precedent — the auth and companies patterns are structurally incompatible with fail-closed semantics. This is ADR-5 (§37, §20).

### 3.5 BaseRepository / BaseService / Transaction Pattern

- `backend/core/repositories/base.py`'s `BaseRepository.create()`/`.update()` call `self.db.commit()` **directly and unconditionally**. `backend/core/services/base.py`'s `BaseService` is a trivial session-holder with no unit-of-work logic. `get_db()` only guarantees `.close()`, never auto-commit/rollback.
- **Gap**: using `BaseRepository.create()`/`.update()` as-is for a Platform privileged mutation would commit the state change **before** any audit row exists, defeating fail-closed by construction (two separate commits, not one atomic operation).
- **Epic 9A treatment**: Platform repositories handling audited mutations bypass `BaseRepository.create()/.update()`'s auto-commit convenience methods for those specific write paths — using `db.add()` + `db.flush()` directly, with the **service** layer owning a single `db.commit()` per operation (state change + audit row together), matching the Accounting precedent exactly. Non-audited reads/writes (e.g., listing Plans) use `BaseRepository` normally.

### 3.6 Alembic Conventions

- Highest existing migration: `056_crm_permission_backfill.py` (`revision="056"`, linear `down_revision` chain, no branching). Convention: `NNN_snake_case_description.py`, 3-digit zero-padded, multi-file-per-epic is normal (Accounting alone spans `044`–`050`), **never edit a past migration** — fixes land as new additive migrations.
- **Epic 9A treatment**: new migrations start at `057` (§26, §33).

### 3.7 Test Infrastructure

- `backend/tests/conftest.py`: SQLite in-memory (`StaticPool`, SAVEPOINT-rollback-per-test), JSONB/INET monkey-patched to TEXT, `gen_random_uuid()` registered as a Python UDF. Real-Postgres verification is a separate, later, live-Docker-Compose step (established Epic 7–9 pattern).
- Directory convention confirmed: `backend/tests/{unit,integration/api/v1,integration/repositories,performance,security}/modules/<module>/` — **`performance/` and `security/` are per-module**, confirming Epic 9A gets its own `tests/performance/platform_admin/`, `tests/security/platform_admin/`.

### 3.8 Docker Compose / Infra

- Services confirmed: `db` (`postgres:16-alpine`), `api`, `web`, `minio`. **No Redis** anywhere in `docker-compose.yml` or `backend/requirements*.txt`. This directly forecloses any Redis-based session-revocation-list or caching design (§10, §31) without a separately-justified ADR — none is justified here, so PostgreSQL-only is used throughout.

### 3.9 Existing Admin Surface Is Dead, Not Reusable

- `GET /admin/companies` (`companies/router.py:126`) is guarded by `require_super_admin()`, which — per §3.1 — **always returns 403** for every caller, including a genuine future super admin, because `CurrentUser.roles` is permanently `[]`.
- Frontend: `AdminCompanyListPage` (`(companies)/admin/companies/page.tsx`) calls `useCompanies()` → `listCompanies()` → bare `GET /api/v1/companies`, which **has no backend route at all** (only `/admin/companies`, `/{company_id}`, `/{company_id}/addresses`, `/{company_id}/audit-logs` exist). `listAdminCompanies()` — the correct function, hitting the real `/admin/companies` route with pagination — exists but is called from **nowhere**.
- **Epic 9A treatment**: this page and its backend guard are **not touched or fixed** by Epic 9A (spec §28 Risk #3 — explicitly out of scope, flagged for separate remediation). Epic 9A builds an entirely new, correctly-authenticated Platform Dashboard/tenant-list surface from scratch (§22, §23), which structurally cannot inherit this bug because it never calls `listCompanies()`/`useCompanies()` at all.

### 3.10 Feature-Toggle Reality — Confirmed 3-of-5 Gap, Not 5-of-5

| Module | Table | Mutation endpoint | Auth on mutation | Gap confirmed |
|---|---|---|---|---|
| Inventory | `inventory_feature_flags` | `PUT .../inventory/feature-flags/{flag_key}` | `require_authenticated` + membership only | **Yes** |
| Sales | `sales_feature_flags` | `PUT .../sales/feature-flags/{flag_key}` | Same | **Yes** |
| Purchase | `purchase_feature_flags` | `PUT .../purchase/feature-flags/{flag_key}` | Same | **Yes** |
| Accounting | `accounting_feature_flags` | `PUT .../accounting/feature-flags/{flag_key}` | Same **plus** explicit `user_has_accounting_permission(..., "accounting.approvalworkflow.manage")` check — already patched during "pre-Epic-9 hardening audit" | **No** — already fixed |
| CRM | `crm_feature_flags` | `POST .../crm/enable` / `/disable` | Same **plus** `require_admin_or_above()` | **No** — already gated |

- **Epic 9A treatment**: §14/§27 target exactly Inventory, Sales, and Purchase — not all five. Accounting's own patch (`user_has_accounting_permission`) is the concrete precedent for the minimal fix pattern to replicate on the other three.

### 3.11 Quota / Entitlement / Plan — Confirmed Absent

- Full-tree grep for `quota`, `usage_limit`, `UsageRecord`, `entitlement`, `capability` (as a class), `class.*Plan\b` returns **zero implementation hits** — only the `Company.subscription_id` placeholder column and the `ActiveSubscriptionError` deletion-guard exception (which only checks the column's presence, not any real subscription logic). Confirms spec.md's claim exactly; nothing to reuse here, everything in §11–§13 is new.

### 3.12 Outbox / Relay Reality

- `backend/core/events/outbox.py`'s `OutboxRecord` (table `event_outbox`) is a real, usable transactional-outbox write side. `relay.py`'s `relay_pending_events()` is confirmed **exactly** a logging-only stub — reads unpublished records, `logger.info`s each, flips `published=True`. No message-bus client anywhere. Spec's "logging-only stub" characterization (FR-9A-241) is accurate; the Platform Health view must display this honestly (§22).

### 3.13 Frontend: CompanyContext, AuthContext, Token Storage

- `CompanyContext.tsx` (`STORAGE_KEY = 'erp_active_company_id'`): `setActiveCompany()` writes `window.localStorage.setItem(STORAGE_KEY, company.id)`. **Critical nuance**: `CompanyProvider` is mounted **only** inside `(companies)/layout.tsx`, not at the root `(protected)/layout.tsx` — `useCompanyContext()` is unusable outside that one route group. Every other module (Sales/Purchase/Accounting/Inventory/CRM) reads the same `erp_active_company_id` localStorage key **directly**, not via the React hook (confirmed: this is exactly the pattern already applied across those modules' bug fixes earlier in this Epic 9A session).
- **Correct understanding of "canonical tenant context"** (refines spec BR-9A-034): the canonical source of truth is the **`erp_active_company_id` localStorage key value itself**; `CompanyContext.tsx`'s Provider is one *writer* of it (from the company-picker page), and most modules are direct *readers* of the same key. Epic 9A's frontend must read via this same key for any tenant-side behavior, and — per BR-9A-035 — never write to it from the Platform Admin area.
- `tokenStorage.ts`: access token is **in-memory only** (module-level `let`, no `localStorage`), refresh token is `localStorage["erp_refresh_token"]`. `acquireRefreshLock()` (`lib/auth/client.ts`) is a real singleton promise-lock preventing concurrent refresh races — reused as the reference pattern for a parallel platform-session refresh lock (§6).

### 3.14 Frontend: Route Groups & Collision Risk

Confirmed existing groups and literal URLs: `(accounting)` → `/accounting-dashboard`, `/reports/*`, `/banking/:accountId`, `/fiscal-calendar/:yearId`; `(companies)` → `/companies`, `/companies/:id`, **`/admin/companies`**; `(crm)` → bare `/reports`, bare `/settings`, `/leads/:leadId`, `/crm-customers/:customerId`; `(inventory)` → `/inventory/*`; `(purchase)` → `/purchase-orders/:id`, `/goods-receipts/:id`, no bare `/purchase`; `(sales)` → `/sales-orders/:id`, `/customers/:id`, no bare `/sales`.

- **Collision risk identified**: `(crm)` already owns the **bare, unprefixed** `/reports` and `/settings` paths; `(companies)` already owns `/admin/companies`. A new admin area MUST NOT claim bare `reports`, `settings`, or any `admin/*` segment.
- **Epic 9A treatment**: new route group `(platform-admin)`, every route explicitly prefixed `/platform-admin/...` (§23) — verified against every table above, zero collision.

### 3.15 Frontend: Layout / Navigation / Sidebar Reality

- `Sidebar.tsx`'s "SuperAdmin" link visibility check (`user?.account_status === 'ACTIVE' && user?.is_email_verified`) is an **explicit placeholder**, not a real role check (the file's own comment says so) — it is not copied.
- One shared shell (`AppLayout`) mounted once at `(protected)/layout.tsx`; every per-group `layout.tsx` is currently a no-op pass-through except `(companies)`'s, which adds `CompanyProvider`.
- **Epic 9A treatment**: `(platform-admin)/layout.tsx` gets its **own** dedicated shell (not `AppLayout`, not the tenant `Sidebar`) — genuinely permission-aware nav driven by the authenticated Platform Administrator's resolved permission set, not a hardcoded placeholder (§23).

### 3.16 Frontend: API Client Convention

- Single shared `apiClient` singleton (`lib/api/client.ts`) — centralizes base URL, `Authorization` header injection, 401-retry-via-`acquireRefreshLock()`, `StandardResponse<T>` unwrapping. Every domain file (`accounting.ts`, `crm.ts`, etc.) delegates to it via a `<domain>Base(companyId)` path-builder helper.
- **Gap (second reconnaissance pass — materially changes the frontend design)**: `ApiClient`'s **transport is already parameterized** (`constructor(baseUrl?: string)`, and `apiClient = new ApiClient()` is just the default instance), but its **auth is hardcoded at module scope, not injectable**: `buildHeaders()` calls the tenant `getAccessToken()` directly; `request()`'s 401 branch calls the tenant `acquireRefreshLock()` directly and, on failure, calls the tenant `clearTokens()` and dispatches the tenant `session-expired` event; `postMultipart()` likewise hardcodes `getAccessToken()`. **Reusing this singleton unchanged for Platform requests would therefore attach the tenant token to Platform requests and drive a Platform 401 into the tenant refresh flow** — violating the required token/refresh separation. The first draft of this plan said Platform would "reuse the same `apiClient` singleton"; that is corrected in §23 (Clarification 6).

### 3.17 Frontend: Middleware

- No `frontend/src/middleware.ts` exists anywhere in the tree — all route protection is client-side, inside `(protected)/layout.tsx`'s `ProtectedContent` (generic authenticated-vs-not only, no role/permission awareness at all today).
- **Epic 9A treatment**: `(platform-admin)/layout.tsx` implements its own guard (redirect to `/platform-admin/login` if no valid platform session), matching the existing project-wide convention of client-side guards backed by authoritative server-side rejection — not introducing Next.js middleware as a new pattern the rest of the app doesn't use.

---

## 4. Platform Domain Architecture

New backend module: **`backend/modules/platform_admin/`** (two-word snake_case, matching the existing `users_roles` naming convention). Skeleton matches the most complete existing pattern (Accounting/CRM, §3.9 of the reconnaissance — those two already have `handlers/`, `exceptions.py`, `events/`):

```
backend/modules/platform_admin/
├── models/          # PlatformAdministrator, PlatformRole, PlatformPermission, PlatformRolePermission,
│                     # PlatformAdminRoleAssignment, PlatformSession, PlatformRefreshToken, Capability,
│                     # Plan, PlanCapability, Subscription, QuotaDefinition, PlanQuota, TenantQuotaOverride,
│                     # EntitlementOverride, UsageRecord, AiCreditLedgerEntry, PlatformAuditEvent,
│                     # SupportAccessGrant  (§25 — full rationale per entity)
├── repositories/    # one per aggregate above, plus PlatformEntitlementResolver's read-only queries
├── services/        # PlatformAuthService, PlatformRbacService, TenantLifecycleService (suspend/reactivate),
│                     # PlanService, SubscriptionService, PlatformEntitlementService (the resolver, §13),
│                     # QuotaService, UsageService, PlatformAuditService, SupportAccessService,
│                     # PlatformDashboardService
├── schemas/         # Pydantic request/response models per §24
├── router.py        # platform-scoped routes only (§24) — never mounted under /companies/{company_id}/...
├── admin_router.py  # OR a second router file for bootstrap-adjacent/self-service endpoints if warranted
├── dependencies.py  # get_current_platform_admin(), require_platform_permission(code), platform-scoped
│                     # equivalents of get_current_company_member (none needed — platform has no tenant scope)
├── constants.py      # PLATFORM_PERMISSION_CODES, default role bundles (candidates from spec §15.2)
├── exceptions.py     # PlatformSessionInvalidError, InsufficientPlatformPermissionError, etc.
└── events/           # reuses backend/core/events/outbox.py — no new event infrastructure
```

### Platform-Owned State vs. Tenant-Owned Business State

| Platform-owned (new, this module) | Tenant-owned (existing, untouched) |
|---|---|
| `PlatformAdministrator`, `PlatformRole`, `PlatformPermission`, `PlatformSession` | `User`, `CompanyMember`, tenant `Session`, tenant `Role`/`Permission` |
| `Plan`, `PlanCapability`, `Subscription`, `QuotaDefinition`, `PlanQuota` | `Company`, `CompanyStatus`, all 5 modules' business records |
| `TenantQuotaOverride`, `EntitlementOverride`, `UsageRecord`, `AiCreditLedgerEntry` | The 5 existing per-module `*_feature_flags` tables (reused, not owned) |
| `PlatformAuditEvent`, `SupportAccessGrant` | `company_audit_logs`, `accounting_audit_log`, `auth.audit_logs` (untouched) |

`Capability` sits at the boundary: it's a Platform-owned *registry* (what capabilities exist and which module they belong to), but its *resolution* (§13) reads tenant-owned feature-flag state without ever writing to it.

---

## 5. Platform Administrator Identity Design

**Decision**: shared underlying `User` identity (credentials/password hash reused — no second password system) **plus** a wholly separate `PlatformAdministrator` principal table, 1:1 on `user_id`, structurally independent of `CompanyMember`.

```python
class PlatformAdministrator(BaseModel):  # NOT TenantBaseModel — no company_id
    __tablename__ = "platform_administrators"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_login_at: Mapped[datetime | None]
    deactivated_at: Mapped[datetime | None]
    deactivated_by: Mapped[UUID | None] = mapped_column(ForeignKey("platform_administrators.id"))
```

**Why reuse `User` for credentials**: avoids a second password-hashing/reset/email-verification system (Constitution §2 Simplicity; "avoid a second application stack" per the planning brief). `User` already has no inherent tenant scoping of its own — `CompanyMember` is what ties a `User` to a company, and a `User` row with **zero** `CompanyMember` rows plus one `PlatformAdministrator` row is a valid, fully-functional Platform Administrator with no tenant membership anywhere (satisfies BR-9A-010).

**Why NOT any of the forbidden patterns** (from spec §6): a `PlatformAdministrator` row is never inferable from `CurrentUser.roles` (permanently `[]`, §3.1), never a `CompanyMember` special-case, never a client-side flag — every check is a server-side row lookup keyed by the authenticated principal from a **platform-typed** token (§6).

**Rejected alternative**: fully separate identity system (own `platform_users` table with its own password hash). Rejected because it duplicates password/reset/lockout logic that already exists and is tested for `User`, for no isolation benefit — the isolation Epic 9A actually needs is at the **session/authorization** layer (§6, §8), not the credential-storage layer.

---

## 6. Platform Session / Authentication Boundary

**Decision**: a structurally distinct token type and a structurally distinct session table — never the tenant `sessions`/`refresh_tokens` tables, never the tenant JWT `typ` claim value.

- New `platform_sessions` table (mirrors `sessions`' shape: `platform_administrator_id`, `is_revoked`, `revoked_at`, `ip_address`, `user_agent`, `created_at`, `expires_at`).
- New `platform_refresh_tokens` table (mirrors `refresh_tokens`' shape, SHA-256-hashed, rotate-on-use, FK to `platform_sessions`).
- JWT claims add `typ: "platform_access"` / `typ: "platform_refresh"` (tenant tokens use `typ: "access"`/`"refresh"` today, confirmed §3.1) — a new dependency, `get_current_platform_admin()`, decodes and **rejects any token whose `typ` isn't the platform variant**, structurally (not just conventionally) preventing a tenant session from ever being accepted as a platform session, and vice versa. This satisfies BR-9A-002/BR-9A-003/FR-9A-141 at the token-verification layer, not just by convention.
- **Login flow**: a dedicated `POST /api/v1/platform/auth/login` (email + password against the same `User.password_hash`, then a lookup requiring an **active** `PlatformAdministrator` row for that `user_id` — a `User` without one gets a generic "invalid credentials"-shaped rejection, never leaking whether the email exists as a tenant user).
- **Refresh/expiry/revocation**: identical mechanics to tenant auth (`acquireRefreshLock()`-style singleton reused on the frontend, §23), but against `platform_refresh_tokens`/`platform_sessions` exclusively.
- **Logout/deactivation**: `PlatformAdministrator.is_active = False` triggers immediate bulk-revocation of all that administrator's `platform_sessions` rows (same transactional pattern as §10's tenant-suspension session revocation) — satisfies FR-9A-031/BR-9A-011.
- **Frontend context separation**: a new `PlatformAuthContext` (parallel to, never nested inside, `AuthContext`), with its own token accessor (`getPlatformAccessToken()`, in-memory only, matching the tenant pattern's XSS-mitigation rationale) — the tenant and platform contexts never share state, never read each other's storage keys.

**Rejected alternative**: encode a `platform_admin: true` claim inside the existing tenant JWT. Rejected outright — this is exactly the "tenant-authenticated session becomes a Platform session simply because the same human has Platform privileges" pattern the Specification explicitly forbids (§7 of the planning brief, BR-9A-003).

---

## 7. Initial Platform Owner Bootstrap

**This section was rewritten (Correction 4).** The first draft used an Alembic data migration that silently `return`ed when the bootstrap environment variables were absent. That is unsafe: Alembic would stamp the revision as applied, and because a migration never re-runs once stamped, a deployment could end up **permanently unbootstrapped with no Platform Owner and no error** — and adding the env vars later would have no effect.

**Decision**: bootstrap is **separated from schema-migration versioning** entirely. Schema migrations (`057`–`061`, §33) create tables only. Provisioning the first Platform Owner is an **explicit, separately-invoked, idempotent operator command** — a small module run with the interpreter that already exists in the `api` container:

```
docker exec erp-system-api-1 python -m modules.platform_admin.bootstrap
```

Behaviour (exit codes are the operator-visible contract):

| Condition | Result | Exit |
|---|---|---|
| No Platform Owner exists **and** valid config supplied | Creates `User` (or reuses an existing one by email) + `PlatformAdministrator` + `platform_owner` role assignment, in one transaction; prints the created administrator id | `0` |
| A Platform Owner already exists | Makes **no change**, prints "Platform Owner already provisioned — no action taken" | `0` (safe, repeatable) |
| Required config missing | Makes no change, prints an explicit error naming the missing variables | **non-zero** (loud failure, never a silent success) |
| Config present but invalid (malformed email, unusable password hash) | Makes no change, prints a specific validation error | **non-zero** |

- **Never silently unbootstrapped**: missing configuration is a non-zero exit with an explicit message (requirement 6); nothing is ever stamped as "done" without an owner existing. Re-running after fixing configuration works normally, because no migration revision gates it.
- **Cannot overwrite an existing owner**: the existence check short-circuits before any write; there is no flag or argument that forces replacement (requirement 2/5).
- **Public/tenant signup can never create Platform authority**: no code path in `backend/modules/auth/` touches `platform_administrators` — structurally impossible, not merely policy (requirement 3).
- **No plaintext secrets in source**: credentials come from the environment — `PLATFORM_OWNER_BOOTSTRAP_EMAIL` and `PLATFORM_OWNER_BOOTSTRAP_PASSWORD_HASH` (**pre-hashed** by the operator using the project's existing hashing utility), following the same `.env`/Compose convention the repository already uses (requirement 4).
- **Not a public API**: it is a module entry point inside the container, never an HTTP route (§24 exposes no bootstrap endpoint).
- **Smallest mechanism, no new framework**: a plain `python -m ...` module with an `if __name__ == "__main__":` entry point — no Click/Typer/`manage.py` scaffolding introduced, since the repository has none and needs none for one command.

**Mandatory deployment order** (requirement 7), documented in `quickstart.md`:

```
1. alembic upgrade head          # schema only (057–061); no credential provisioning
2. python -m modules.platform_admin.bootstrap   # explicit; non-zero exit on any failure
3. verify a Platform Owner exists (the command's own exit code / re-run output)
4. only then expose Platform Admin functionality (§36 Phase G)
```

- **Subsequent Platform Administrators** are created exclusively through the normal `platform.admins.manage`-gated API (§8) — this command is a one-time bootstrap path, never a repeatable admin-creation mechanism.
- **Traceability**: FR-9A-036 asks for infrastructure-level traceability for an action that necessarily precedes the Platform audit trail's existence. The command emits a structured log line (§30) recording the created administrator id and the invoking environment; once the audit trail exists, every *subsequent* administrator change is fully audited (§20). Migration history is no longer the traceability vehicle, because tying provisioning to migration versioning is precisely what created the unsafe state above.

**Rejected alternative**: keeping the Alembic data migration (with a hard failure instead of a silent return). Rejected because a migration that *fails* on missing configuration would block schema upgrades entirely for anyone who hasn't set bootstrap credentials — coupling two unrelated deployment concerns in the opposite direction. Separating them is the only option that is safe in both directions.

---

## 8. Platform RBAC Technical Design

Genuinely enforced, permission-code-based (§3.2 — deliberately *not* mirroring tenant RBAC's currently-inert pattern).

**Model** (full rationale in §25):
- `PlatformPermission` (code PK, e.g. `"platform.tenants.suspend"`, mirroring the existing tenant `Permission` model's code-as-PK convention for consistency)
- `PlatformRole` (code, name, description)
- `PlatformRolePermission` (role_id, permission_id, unique pair)
- `PlatformAdminRoleAssignment` (platform_administrator_id, role_id, assigned_by, assigned_at, unique pair) — supports multiple roles per administrator (FR-9A-142), effective permissions = union

**Enforcement**: `require_platform_permission(code: str)` FastAPI dependency — resolves the authenticated `PlatformAdministrator`'s role assignments → union of permission codes → membership check. Genuinely wired on every sensitive route (§24), unlike the tenant `require_permission_stub()`.

**Self-escalation prevention** (BR-9A-012): role-assignment mutations check the acting administrator already holds `platform.rbac.manage` **and** — if assigning the `platform_owner` role specifically — that the actor already holds that same role (a role can never grant a role of equal-or-higher privilege than the actor doesn't already have).

**Last-Platform-Owner protection**: a service-level check (not just DB constraint) blocking the final active `platform_owner`-role assignment from being removed or deactivated — mirrors the spirit of "prevent removing the last owner" patterns; enforced in `PlatformRbacService`, tested explicitly (§32).

**Frontend capability rendering**: `(platform-admin)` nav renders only links the authenticated administrator's resolved permission set actually allows — but this is UX only; every route's real enforcement is server-side `require_platform_permission`.

Candidate roles (from spec §15.2 — configurable, not hardcoded, seeded as **data**, not enum values): Platform Owner, Platform Operations Admin, Support Admin, Billing/Subscription Admin, Security/Audit Admin, Read-Only Platform Analyst.

---

## 9. Tenant Lifecycle Integration

`TenantLifecycleService.suspend(company_id, actor, reason)` / `.reactivate(company_id, actor, reason)`, added to the **existing** `Company`/`CompanyStatus` model — no duplication of Company ownership.

### 9.1 Pre-Suspension Status Must Be Persisted (Correction 2)

The Specification requires `suspended → pre-suspension status`, i.e. `active → suspended → active` **and** `inactive → suspended → inactive`. Reactivation therefore cannot hardcode `active`, and the previous status must **not** be inferred from audit rows or UI state (unreliable, and audit is append-only history, not authoritative current state).

**Decision**: two new nullable columns on the existing `companies` table (migration `057`, §33) — no new table, since these are per-company scalar facts with a 1:1 lifetime:

| Column | Purpose |
|---|---|
| `pre_suspension_status` (varchar, nullable) | The `CompanyStatus` value held immediately before suspension. Set on suspend, read on reactivate, cleared (set NULL) on successful reactivate. NULL whenever `status != 'suspended'`. |
| `access_invalidated_at` (timestamptz, nullable) | Watermark for company-scoped access invalidation (§10). Set on suspend; **deliberately never cleared** on reactivate. |

**Integrity** (§26): a CHECK constraint enforces `pre_suspension_status IS NOT NULL` exactly when `status = 'suspended'`, so a suspended company can never exist without a recorded restore target, and a non-suspended company can never carry a stale one.

### 9.2 Suspend — one atomic transaction

1. `require_platform_permission("platform.tenants.suspend")` (route-level).
2. `SELECT ... FOR UPDATE` on the `Company` row (§26 — decided, not deferred), then validate current status is `active` or `inactive` (else the specific rejected-transition error, Edge Case #1).
3. `pre_suspension_status = <current status>`; `status = suspended`; `access_invalidated_at = now()`.
4. Company-scoped access invalidation (§10) — **not** blanket session revocation.
5. Enqueue `CompanySuspendedEvent` (existing, previously-unused domain event) as an `OutboxRecord` (§3.12) — written in this same transaction, per the transactional-outbox pattern the repository already implements.
6. `db.flush()` all of the above; `db.add(PlatformAuditEvent)` recording `before_state` (the pre-suspension status) and `after_state` (`suspended`) plus the mandatory reason; `db.flush()`; then a **single `db.commit()`** covering everything (§20 — fail-closed: an audit-write failure rolls back the status change, the invalidation watermark, and the outbox record together).

### 9.3 Reactivate — restores the recorded status

Same permission/locking/audit/outbox shape, with `platform.tenants.reactivate`, and: validate current status **is** `suspended` (else the Edge Case #2 rejection); read `pre_suspension_status`; set `status = pre_suspension_status`; set `pre_suspension_status = NULL`; enqueue `CompanySuspensionLiftedEvent`; audit `before_state = suspended`, `after_state = <restored status>`.

`access_invalidated_at` is **not** cleared — that is exactly what prevents reactivation from silently resurrecting pre-suspension access artifacts (FR-9A-018, §10). Tenant users must perform a **genuine login** to regain access to this company; redeeming a pre-suspension refresh token is explicitly insufficient, because the watermark is compared against authentication time (`Session.created_at`), which a refresh does not advance (§10.2).

**Defensive fallback**: if `pre_suspension_status` were ever NULL on a `suspended` row (impossible under the CHECK constraint above, but defended anyway), reactivation fails closed with an explicit operator-visible error rather than silently guessing `active`.

**Concurrency**: the `SELECT ... FOR UPDATE` in step 2 serialises concurrent suspend/reactivate attempts on the same tenant — exactly one transition commits; the loser re-reads the now-changed status and receives the specific already-suspended / not-suspended rejection, never a duplicate audit row (Acceptance Scenario 6).

---

## 10. Session Revocation Strategy

This is the plan's single most consequential Technical Unknown, fully resolved here from repository evidence (§3.1, §3.3; §40; ADR-6). **This section was rewritten after a second reconnaissance pass disproved the first draft's mechanism.**

### 10.1 Why blanket session revocation is rejected

The first draft proposed `UPDATE sessions SET is_revoked=true WHERE user_id IN (SELECT user_id FROM company_members WHERE company_id = :id)`. Repository evidence rejects this on two independent grounds:

1. **Tenant-isolation violation.** A `Session` has **no `company_id`** and models a *device login for a human identity*, not access to a tenant (§3.1, quoting the model's own docstring). A user who is a member of Company A **and** Company B holds one session covering both. Revoking by `user_id` would sign that user out of Company B — which is still active — purely because Company A was suspended. That is collateral cross-tenant damage, forbidden by Constitution §9 and by the Specification's own multi-tenant-safety requirements.
2. **It would not even work.** The five business modules mount `get_current_company_member`, which never reads `Company.status` (§3.3). Killing sessions is not what makes a suspended tenant inaccessible on those routes — nothing currently does.

### 10.2 Decision: company-scoped access invalidation, enforced at the company-access boundary

Two complementary layers, both tenant-scoped by construction, no new infrastructure:

**Layer 1 — request-time company-status enforcement (closes the §3.3 gap).**
A small shared helper, `assert_company_access_allowed(db, company_id, session_id)`, is called from **both** existing company-access dependencies — `get_current_company_member` (`users_roles/dependencies.py`, used by all five business-module mounts) and `get_current_company` (`companies/dependencies.py`, which already checks status and gains the watermark check). It rejects when `Company.status == suspended` (raising the existing `CompanySuspendedError`) or `deleted`. Because these dependencies resolve the `{company_id}` **path parameter**, enforcement is inherently scoped to the company actually being addressed — a request to Company B is entirely unaffected by Company A's suspension.

**Layer 2 — durable access-invalidation watermark, keyed on authentication time (not token issuance time).**

`Company.access_invalidated_at` (§9.1) is set at suspension. The helper then denies when:

```
Session.created_at  <=  Company.access_invalidated_at
```

where `Session` is loaded by the `sid` claim the caller's token already carries (`CurrentUser.session_id`).

**Why `Session.created_at` and explicitly NOT the token's `iat`** (this is the Correction-1 fix): `iat` records when an *access token was minted*, which a **refresh** also does. Using `iat` would let a pre-suspension refresh credential be redeemed after reactivation to mint a token with a fresh `iat > access_invalidated_at`, restoring access **without the user ever re-authenticating** — defeating FR-9A-018. `Session.created_at`, by contrast, advances **only on a genuine login** (§3.1: `login()` creates a new `Session`; `refresh()` reuses the existing one), so it is a true authentication-freshness value that survives arbitrarily many refreshes unchanged.

| Concept | Value | Advances on login? | Advances on refresh? | Used for authorization? |
|---|---|---|---|---|
| Access-token issuance | JWT `iat` | Yes | **Yes** | **No** — never treated as proof of fresh authentication |
| Authentication event | `Session.created_at` | Yes | **No** | **Yes** — compared against the watermark |

**Why no new claim or column is needed**: `Session.created_at` already exists (`BaseModel`, `server_default=func.now()`, immutable after INSERT), and `sid` is already a signed claim resolved into `CurrentUser.session_id` by the existing `get_current_user()`. The helper performs one primary-key lookup on `sessions`. Consequently **Epic 9A makes no change whatsoever to `get_current_user()`, to `CurrentUser`, or to the JWT payload** — a strictly smaller footprint than the `iat`-plumbing this section previously described, and correct where that was not.

**Not client-controllable** (requirement 7): the value is read from the database, keyed by a claim inside a signature-verified JWT. A client can neither forge `sid` (signature) nor alter `Session.created_at` (server-generated, no API writes it).

**Optional, not required**: because the helper already loads the `Session` row, checking `Session.is_revoked` there would be free and would partially mitigate the adjacent logout defect (§10.4). It is deliberately **not** made a requirement of this Epic to keep the change surface minimal; Tasks-phase may include it as a one-line addition if desired.

### 10.3 Properties this design satisfies

| Requirement | How |
|---|---|
| Suspended tenant immediately inaccessible | Layer 1, on the very next request to that company, across all five business modules **and** the companies module |
| No cross-tenant blast radius | Both layers key off the request's `{company_id}`; a multi-tenant user keeps full access to unaffected companies |
| Server-side enforcement only | Both layers run inside FastAPI dependencies; `erp_active_company_id` is never consulted (§15) |
| **Old refresh credentials cannot restore access** | The watermark compares `Session.created_at`, which a refresh does not advance — redeeming a pre-suspension refresh token yields a new access token bound to the **same** pre-suspension session, and is still denied |
| **Only genuine re-authentication restores access** | A new login creates a new `Session` row whose `created_at > access_invalidated_at` |
| Multi-device | Deterministic and per-session — see §10.3.1 |
| Reactivation does not resurrect | `access_invalidated_at` is never cleared (§9.3), and no refresh path can produce a post-watermark authentication time |
| Manipulated company id cannot bypass | The addressed `company_id` is exactly what is checked; substituting another company's id simply gets that company's own membership + status check |
| Authentication freshness cannot be forged | Read from the DB, keyed by a signed `sid` claim; no API writes `Session.created_at` |
| No Redis / new infrastructure | Two nullable `companies` columns and one indexed primary-key read; no new claim, no new session column |

### 10.3.1 Multi-device semantics (explicit)

Freshness is evaluated **per session**, and each device holds its own `Session` row, so behaviour is deterministic per device:

| Situation | Company A (suspended at T1, reactivated at T2) | Company B (unaffected) |
|---|---|---|
| Device 1 logged in **before** T1 | Denied — its `Session.created_at < T1`, and refreshing does not change that | Allowed throughout |
| Device 2 logged in **before** T1 | Denied, independently of Device 1 | Allowed throughout |
| Device 1 redeems its old refresh token after T2 | **Still denied** — same session, same `created_at` | Allowed |
| Device 1 performs a genuine **new login** after T2 | Allowed (new session, `created_at > T1`), if membership is otherwise valid | Allowed |
| Device 2 takes no action after Device 1 re-logs in | **Still denied** — one device re-authenticating never restores another device's session | Allowed |

Each device therefore recovers Company A access independently, and only by a real login. No global "logout all devices" is triggered, so Company B access is never disturbed on any device.

### 10.4 Deliberately out of scope: global tenant-session revocation

Epic 9A does **not** revoke rows in the global `sessions` table for tenant suspension, because in this codebase a session is not a tenant-scoped artifact (§10.1). The Specification's requirement that suspension "actively revoke/invalidate all currently active tenant-user sessions … not merely block their next request" (FR-9A-017/222, BR-9A-032, resolved OQ-3) is satisfied in substance: every pre-existing session's **access to that tenant** is invalidated immediately and durably. This is a **mechanism refinement forced by a repository fact, not a change to the business decision** — the guarantees the Product Owner approved (immediate inaccessibility, no resurrection on reactivation, re-authentication required) are all preserved, and are delivered *without* the tenant-isolation violation the literal mechanism would have caused. Flagged here explicitly for Product-Owner visibility rather than silently reinterpreted.

**Separately noted, not fixed here**: `get_current_user()` still never checks `Session.is_revoked`, so ordinary tenant logout does not invalidate an in-flight access token before expiry (§3.1). That is a genuine pre-existing defect, but it is **not** required for Epic 9A's correctness under the design above. It is documented as an adjacent finding (§41) in the same manner as the dead `/admin/companies` surface — not silently absorbed into this Epic's scope. Platform sessions, by contrast, *do* check revocation, because `get_current_platform_admin()` is new code written correctly from the start (FR-9A-220, §6).

**Precise scope of changes to the universal auth path: none.** Epic 9A adds **no query, no claim, no field, no rejection logic, and no new failure mode** to `get_current_user()`, `CurrentUser`, or the JWT payload. The `sid` claim and `CurrentUser.session_id` it needs already exist. Every piece of rejection logic introduced by this Epic lives in the **company-scoped** dependencies (§10.2), which run only on `{company_id}` routes. This is why regression risk is materially lower than for either previously-considered design (§38).

---

## 11. Plans & Subscriptions Architecture

**Plan** (Platform-owned, reusable SaaS offering — `Plan` model, §25): code, name, status (`draft`/`published`/`retired`), description, `is_commercially_available`, `billing_cycle_metadata`/`pricing_metadata` (JSONB, informational only per Assumption A5), timestamps. Plan **names are configuration-driven data**, never hardcoded (FR-9A-151) — "Basic/Pro/Enterprise" never appears in code.

**Subscription** (tenant plan assignment, distinct record — BR-9A-014): `company_id` (unique among **active** subscriptions via a partial unique index, §26), `plan_id`, `status` (`active`/`ended` only — `trial` deliberately excluded per resolved OQ-1/Assumption A3, though the enum column itself is a plain VARCHAR+CHECK, matching `CompanyStatus`'s own pattern, so adding `trial` later needs no migration redesign, only a CHECK-constraint update), `effective_date`, `ended_at`, `actor_id`, `reason`.

`Company.subscription_id` (existing nullable placeholder column, §3.3/§3.11) finally gets a real FK constraint to `subscriptions.id`, used as a **denormalized "current subscription" pointer** for query convenience — kept in sync in the same transaction as any `Subscription` status change (never a second source of truth; the `subscriptions` table with its partial-unique-active-index remains authoritative).

**Downgrade/usage-conflict handling** (FR-9A-165/166): `SubscriptionService.change_plan()` calls the entitlement/quota resolver (§13, §17) for the target plan **before** committing, surfaces any over-limit conflict, requires an explicit `acknowledged: true` flag on the request to proceed.

No payment gateway, invoicing, or tax — `billing_cycle_metadata`/`pricing_metadata` are inert JSONB fields, a clean future Plugin/Adapter (Constitution §47) extension point, never referenced by any enforcement logic in this Epic.

---

## 12. Module / Capability Entitlement Architecture

**`Capability`** registry (Platform-owned): `key` (PK, e.g. `"inventory"`, `"sales"`, `"purchase"`, `"accounting"`, `"crm"` — module-grain; future rows like `"installments"`, `"reports"` reserved without any schema change), `module`, `grain` (`module`/`feature` enum, per Assumption A7), `display_name`, `is_active`.

**`PlanCapability`**: `plan_id`, `capability_key`, `allowed` (bool) — this is the **Plan Entitlement ceiling** (§13's resolution table).

No per-module boolean column is added anywhere — the five existing `*_feature_flags` tables are **read, never migrated or restructured** (Assumption A6 honored exactly).

**Genuinely new-module extensibility**: adding a future module (Installments, Reports, HR, …) requires only one new `Capability` row and, if that module ships its own feature-toggle table later, one new adapter (§13) — never a schema migration to this registry.

---

## 13. Entitlement Resolution Service

Single authoritative server-side resolver, `PlatformEntitlementService.resolve_effective_entitlement(company_id, capability_key) -> EffectiveEntitlement`, implementing the spec's §17.2 resolution table exactly:

| Plan Entitlement | Tenant Toggle | Result |
|---|---|---|
| Allowed | Enabled | Available |
| Allowed | Disabled | Unavailable |
| Not Allowed | (any) | Unavailable (ceiling) |
| Not Allowed, active Override | (irrelevant) | Available for override's duration |

**Module-grain Tenant Toggle lookup — genuine Technical Unknown, resolved with an adapter pattern, not an assumption**: reconnaissance confirmed CRM has exactly one well-known master flag key (`feature.crm.enabled`), but did **not** confirm whether Inventory/Sales/Purchase/Accounting each have an equivalent single "whole-module" master flag versus only fine-grained sub-feature flags. Rather than assume a uniform convention, the resolver uses a small `ModuleEnablementProvider` protocol with one ~15-line implementation per module (5 total) — each knows how to answer "is this module's Tenant Toggle currently enabled for company X," reading that module's actual flag-key convention once verified during Tasks-phase implementation. This is flagged explicitly in §40 as a Tasks-phase verification item, not fabricated here.

### 13.1 Enforcement is at point-of-use, not only at toggle mutation (Correction 1)

The first draft of this plan enforced the Plan ceiling primarily where a tenant *mutates* a feature toggle. That is insufficient and left a real bypass:

> Tenant's toggle for CRM is enabled under a Plan that allows CRM → Platform Admin moves the tenant to a Plan that does **not** allow CRM → the tenant's stored toggle row is untouched and still `true` → `require_crm_enabled` (which reads only `crm_feature_flags`) still passes → the tenant keeps using CRM despite the new Plan denying it.

This inverts the architecture: Plan Entitlement is supposed to be the **authoritative ceiling** over Tenant Toggle. Corrected as follows.

**Primary enforcement point — a mount-level dependency on every entitled module.** A new dependency factory, `require_capability_entitled("<capability_key>")`, calls the single shared resolver and rejects with a specific `CapabilityNotEntitledError` (HTTP 403) when the effective result is Unavailable. It is added to each of the five business-module router mounts in `backend/api/v1/router.py`, alongside the existing `get_current_company_member`:

```python
router.include_router(
    crm_router,
    prefix="/companies/{company_id}/crm",
    dependencies=[
        Depends(get_current_company_member),
        Depends(require_capability_entitled("crm")),   # NEW — Plan ceiling, point-of-use
        Depends(require_crm_enabled),                  # PRESERVED — existing tenant-toggle gate
    ],
)
```

Why this location: it is the same single place the repository already centralises per-module request gating (§3.10), so **every** endpoint in a module is covered automatically — no per-endpoint annotation to forget, no per-module reimplementation of the resolution logic (spec requirement 8), and existing module-specific authorization and toggle gates are preserved untouched beside it (requirements 1–2).

**Consequences that satisfy the correction's requirements:**

- A Plan downgrade takes effect **on the tenant's very next request**, with **no** need to manually flip old tenant feature flags (requirement 5). Stored toggle values are left exactly as they are, so if the tenant is later moved back to an allowing Plan, their original preference resumes automatically (requirement 6, and spec §17.2's last row).
- Frontend capability checks (§23) remain **UX only** — a thin read endpoint drives menu/visibility, and manipulating it or `localStorage` changes nothing, because the mount-level dependency is the authoritative boundary (requirement 4, §28).
- `PlatformEntitlementService` remains the single deterministic resolver for Plan × Toggle × Override (requirement 7).
- Applied uniformly to Inventory, Sales, Purchase, Accounting, and CRM (requirement 10) — see §27's matrix.

**Relationship to §14**: the mutation-point check in §14 is retained, but it is now a *secondary* guard (it stops a tenant from switching a toggle **on** beyond the ceiling, giving a clear immediate error instead of a silently-ineffective write). Point-of-use enforcement here is what actually governs runtime access.

**Evaluation timing**: resolved per request, never cached indefinitely (FR-9A-170), so plan/entitlement/override changes are effective immediately. Cost is a small number of indexed point-lookups on a request that is already hitting the database for membership (§31).

**No per-module reinvention**: every module calls the **same** resolver function — none independently re-implements the Plan × Toggle × Override logic.

---

## 14. Existing Feature-Toggle Security Hardening

Scoped precisely to the 3 modules confirmed vulnerable (§3.10): **Inventory, Sales, Purchase**. Accounting and CRM are already correctly gated and are **not modified**.

**Minimum hardening, replicating Accounting's own existing patched pattern exactly** (not inventing a new one): each of the three modules' `PUT .../feature-flags/{flag_key}` handler gains one additional check —

```python
if not user_has_module_permission(db, company_id, user.user_id, "<module>.settings.manage"):
    raise <Module>PermissionDeniedError(...)
```

— mirroring `user_has_accounting_permission()`'s exact shape (role-based lookup via `RolePermissionRepository`, tenant `CompanyMember`), added as a new permission code per module (`inventory.settings.manage`, `sales.settings.manage`, `purchase.settings.manage`) registered in each module's own `constants.py`, seeded via the existing `RoleSeedService` convention. This is targeted security-integration work — **no module is otherwise rewritten** (§39 Complexity Tracking explicitly rejects a broader refactor).

**Entitlement ceiling at the mutation point (secondary guard)**: after the permission check passes, the mutation additionally consults `PlatformEntitlementService` — a tenant cannot switch a module-grain toggle **on** beyond the Plan ceiling (FR-9A-185), receiving an explicit error rather than performing a write that would be silently ineffective at runtime.

**This is not the primary enforcement point.** Runtime access is governed by the mount-level `require_capability_entitled(...)` dependency described in §13.1. The mutation-point check exists only so that an out-of-ceiling toggle attempt fails loudly and immediately; removing it would not create a runtime bypass, whereas removing §13.1's check would. Both are retained.

---

## 15. Canonical Tenant Context Integration

Confirmed precisely (§3.13): the persisted value lives in the `erp_active_company_id` **localStorage key**, and `CompanyContext.tsx`'s React Provider is scoped only to `(companies)`, so most modules read that key directly today.

**Architectural refinement (Clarification 5).** The first draft named the raw localStorage key itself as "the canonical source of truth," which conflates a *persistence detail* with an *architectural contract*. Corrected layering:

```
Canonical tenant-context accessor/contract   ← what code depends on
                 ↓
   erp_active_company_id (localStorage)      ← persistence detail, unchanged
```

Epic 9A introduces a small, explicit accessor module (e.g. `lib/tenant-context/activeCompany.ts`) exposing `getActiveCompanyId()` / `setActiveCompanyId()` / `clearActiveCompanyId()`, backed by exactly the existing key so it is 100% compatible with current behaviour and with `CompanyContext.tsx`.

- **No ERP-wide frontend refactor in this Epic** (requirement 1). Existing modules keep their current direct reads; they are not rewritten (requirement 2). The accessor is additive.
- **New Epic 9A code uses the accessor**, never a raw `localStorage` call (requirement 3) — so future migration of the persistence detail is a one-file change rather than another repo-wide sweep.
- Four concepts are kept explicitly distinct (requirement 7):

| Concept | Where it lives | Authority |
|---|---|---|
| Tenant **UI selection state** | `getActiveCompanyId()` → `erp_active_company_id` | UX convenience only — **never** an authorization input |
| **Authenticated identity** | tenant JWT (`sub`/`sid`), in-memory access token | Server-verified signature |
| **Server-authoritative company membership/access** | `get_current_company_member` + `assert_company_access_allowed` on the `{company_id}` path param (§10) | The only authorization authority |
| **Platform selected-tenant context** | `PlatformSelectedTenantContext` (in-memory, §23) | UX only; Platform authorization comes from the platform JWT + `require_platform_permission` |

- **Manipulating localStorage grants nothing** (requirement 6): the server authorizes against the `{company_id}` in the request path, re-checking membership and company status every time (§10, §28) — a forged local value simply produces a request to a company the caller is checked against and rejected for.
- **Platform Admin's own tenant-selection context** (for inspecting/suspending a tenant, or initiating support access) is a wholly separate, in-memory React context — `PlatformSelectedTenantContext` — that **never reads or writes** `erp_active_company_id` (BR-9A-035). Selecting Tenant X in the Platform Dashboard has zero effect on what a tenant-side tab in the same browser would see as its active company.
- **Platform authority never derives from tenant context** (BR-9A-036): `require_platform_permission()` and `get_current_platform_admin()` never inspect any request header, cookie, or body field resembling a tenant company id for authorization purposes — only the platform JWT's own claims.
- **Verification requirement** (FR-9A-219): during Tasks-phase implementation, any newly-touched code path (the 3 hardened modules, §14) is checked against this convention; no new ad-hoc company-id source is introduced anywhere in Epic 9A's own new code.

---

## 16. Administrative Overrides

`EntitlementOverride` and `TenantQuotaOverride` (separate tables, §25 — entitlement vs. quota kept as distinct concepts per spec §17.1): `company_id`, target key, `reason` (mandatory), `actor_id`, `granted_at`, `expires_at` (nullable — null means permanent, explicitly distinguishable from temporary, never implicit), `revoked_at` (nullable), `is_active` (computed/maintained flag for fast lookup).

**Precedence**: the resolver (§13) checks for an active, non-expired override **last**, after Plan/Toggle — an active override always wins regardless of Plan Entitlement (this is the entire point of an override), but a temporary override that has passed its `expires_at` is treated as inactive without requiring a background job — the resolver itself checks `expires_at > now()` at read time; a lightweight periodic sweep (reusing whatever scheduled-task mechanism, if any, Tasks-phase finds already established — none was confirmed during reconnaissance, so this may be a simple flag-update-on-next-access pattern rather than a new scheduler) marks `is_active=false` and writes the automatic-reversion audit entry (FR-9A-172).

Never implemented as hidden edits to `PlanCapability`/`PlanQuota` rows or tenant feature-flag rows (explicit requirement) — always its own row, in its own table, fully auditable independent of the Plan/Toggle it temporarily overrides.

---

## 17. Quota Architecture

`QuotaDefinition` (key registry: `users`, `branches`, `transactions`, `storage`, `api_calls`, `ai_credits`, each with an `enforcement_style` — `hard`/`soft`/`informational`, BR-9A-030) + `PlanQuota` (plan_id, quota_key, `limit_value` nullable — **null explicitly means unlimited**, FR-9A-182, never an implausibly large number) + `TenantQuotaOverride` (§16).

**Entitlement vs. Quota, kept distinct** (spec §17.3's explicit requirement): `Capability`/`PlanCapability` answer "does this exist at all"; `QuotaDefinition`/`PlanQuota` answer "how much may be consumed" — two independent lookups in the resolver, never conflated into one table or one check.

**Effective quota** = `TenantQuotaOverride.override_limit` (if active) else `PlanQuota.limit_value` (via the tenant's current `Subscription.plan_id`) else `unlimited` if no `PlanQuota` row exists for that plan+key. Current usage comes from `UsageRecord` (§18). Five states rendered (FR-9A-181): `ok`, `approaching` (configurable threshold, default TBD at Tasks-phase — not fabricated here), `reached`, `unlimited`, `unavailable` (measurement failure — §18 governs this explicitly, never silently zero).

---

## 18. Usage Metering

**Decision**: periodic/batch `UsageRecord` rows (`company_id`, `metric_key`, `quantity`, `period_start`, `period_end`, `source`, `recorded_at`) — PostgreSQL only, no event-streaming platform, no Redis counters (§3.8, §31, Constitution §5 discipline). A scheduled job (mechanism TBD at Tasks-phase — reusing whatever periodic-task pattern, if any, already exists; none confirmed during reconnaissance, so this may start as a manually-triggerable admin endpoint plus a documented cron recommendation rather than inventing new scheduler infrastructure) computes each metric per company per period and writes one row — never real-time per-event writes for high-frequency metrics like `api_calls`.

**Measurement-failure handling** (FR-9A-062): if a given period's computation fails or hasn't run yet, the quota view shows `unavailable` explicitly (§17) — never defaults to zero. This is enforced by the *absence* of a `UsageRecord` row for the current period being a distinct, explicitly-checked state in `QuotaService`, not an implicit fallback.

---

## 19. AI Credits Future-Readiness

No AI provider is integrated (Non-Goal, unconditionally). Schema-only readiness via **`AiCreditLedgerEntry`** — a single append-only ledger table (`company_id`, `delta` signed numeric, `reason`, `actor_platform_administrator_id` nullable (null = future automatic usage debit; populated = manual admin adjustment, FR-9A-233), `provider` free-text/enum-ish string (never structurally coupled to a specific vendor, FR-9A-234), `model`, `input_tokens`, `output_tokens`, `total_tokens`, `estimated_cost`, `billable_cost`, `occurred_at`). Current balance = `SUM(delta)` per company — one table serves both future automatic usage tracking and this Epic's one real capability, manual credit adjustments, without a parallel structure. `PlatformAuditEvent` FK links every manual adjustment to its audit record (BR-9A-027). Until AI capability is active for any tenant, the frontend shows an explicit "not yet active" state (FR-9A-235) — the table exists and is empty, never populated with zero-value placeholder rows.

---

## 20. Audit Architecture

**`PlatformAuditEvent`** (one new table, append-only — no update/delete route exists anywhere in the router, BR-9A-023): `actor_platform_administrator_id` (nullable, for the rare system-initiated event), `action`, `target_type`, `target_id` (nullable), `company_id` (nullable — populated whenever the action is tenant-scoped), `reason` (nullable — populated for actions requiring one), `before_state`/`after_state` (JSONB), `context` (JSONB — includes `request_id` for correlation), `support_access_grant_id` (nullable FK — links an action-level entry to its owning support session, satisfying "session-level AND action-level" audit, §21, without a second parallel audit table per BR-9A-022), `created_at`.

**Fail-closed transaction boundary** (BR-9A-024/FR-9A-204, following the Accounting precedent exactly, §3.4/§3.5): every service method performing a privileged mutation does `db.add(audit_row); db.flush()` **before** its single `db.commit()`, alongside the actual state-change writes (also via `flush()`, not `BaseRepository.create()`'s auto-commit) — if the audit-row insert violates a constraint or the flush otherwise fails, the exception propagates, the whole transaction rolls back, and the mutation is never persisted. This is the concrete transaction design the Specification (§21 of the planning brief) requires — not a vague intention.

**Filtering** (FR-9A-200): indexed columns for `actor_platform_administrator_id`, `company_id`, `action`, `created_at` support the platform audit view's required filters without full-table scans.

---

## 21. Cross-Tenant Support Access

`SupportAccessGrant` (`platform_administrator_id`, `company_id`, `reason` mandatory, `started_at`, `expires_at` (mandatory, no indefinite grant), `ended_at` nullable, `ended_by` nullable, `status` enum `active`/`expired`/`terminated`).

**Scope enforcement** (BR-9A-021, strictly inspection-only, no business records — resolved OQ-2): the support-access endpoints (§24) expose **only** already-existing read paths already reachable from the Tenant Detail view (configuration, entitlements, users, lifecycle/audit) scoped to the granted tenant — implemented as thin wrappers around existing tenant-side read services, called with the Platform session's authority, never by mutating `erp_active_company_id` or reusing tenant `CompanyContext` (§15). There is **no code path** in this design that reaches Sales/Purchase/Accounting/CRM/Inventory's own business-record tables — support access literally cannot query them because the support-access router never imports those modules' repositories.

**Per-action audit**: every read performed during an active grant writes a `PlatformAuditEvent` row with `support_access_grant_id` populated (§20) — in addition to the grant's own start/end audit rows.

**Termination**: expiry is checked at request time (`expires_at < now()` → 403, `status` flipped to `expired` lazily on next check, matching the override-expiry pattern in §16 rather than requiring a background job); explicit termination by the initiating actor or a sufficiently-privileged admin sets `status=terminated`, `ended_at=now()`, `ended_by`.

No impersonation anywhere in this design — a support session is always attributed to the Platform Administrator's own identity, never assumes the tenant user's identity.

---

## 22. Platform Dashboard

`PlatformDashboardService` — a handful of bounded, indexed aggregate queries (never unbounded `SELECT *` across all tenants): tenant counts by `CompanyStatus` (single `GROUP BY`), recent registrations (indexed `created_at DESC LIMIT N`), Plan/Subscription-status distribution (`GROUP BY`), quota warnings (join against the most recent `UsageRecord` per company/metric — bounded by the "approaching" threshold), recent Platform Admin actions (`PlatformAuditEvent` indexed `created_at DESC LIMIT N`), operational health (§3.12 — surfaces `/health*` and the outbox's real pending/published counts, **explicitly labeled** as a stub relay, never implying real delivery).

**States** (FR-9A-003): each widget independently tracks `loading`/`populated`/`empty`/`unavailable` — a failed sub-query never silently renders as `0` or is omitted in a way indistinguishable from "genuinely zero." Widgets requiring a permission the viewing administrator lacks are omitted entirely (FR-9A-004), not shown empty or erroring.

AI usage summary widget only renders once `AiCreditLedgerEntry` has at least one row anywhere (§19) — until then it's absent, not populated-empty.

---

## 23. Frontend Architecture

New route group **`(platform-admin)`**, every literal URL prefixed `/platform-admin/...` (§3.14 — zero collision with any existing group's paths, verified against the full table):

```
frontend/src/app/(platform-admin)/
├── layout.tsx                          # dedicated shell — NOT AppLayout, NOT tenant Sidebar
├── platform-admin/
│   ├── login/page.tsx                  # /platform-admin/login — outside the guarded shell
│   ├── dashboard/page.tsx              # /platform-admin/dashboard
│   ├── tenants/page.tsx                # /platform-admin/tenants
│   ├── tenants/[tenantId]/page.tsx     # /platform-admin/tenants/:tenantId
│   ├── plans/page.tsx                  # /platform-admin/plans
│   ├── subscriptions/page.tsx          # /platform-admin/subscriptions
│   ├── entitlements/page.tsx           # /platform-admin/entitlements
│   ├── quotas/page.tsx                 # /platform-admin/quotas
│   ├── administrators/page.tsx         # /platform-admin/administrators
│   ├── roles/page.tsx                  # /platform-admin/roles
│   ├── audit/page.tsx                  # /platform-admin/audit
│   ├── usage/page.tsx                  # /platform-admin/usage
│   ├── support-access/page.tsx         # /platform-admin/support-access
│   └── health/page.tsx                 # /platform-admin/health
```

- `PlatformAuthContext` (§6) — own login/logout/token accessor, never nested inside or sharing state with `AuthContext`/`CompanyContext`.
- `PlatformSelectedTenantContext` (§15) — the "which tenant is currently being inspected/supported" concept, entirely separate from `erp_active_company_id`.
- `(platform-admin)/layout.tsx` performs its own guard (redirect to `/platform-admin/login` if no valid platform session) — matching the existing project-wide client-side-guard convention (§3.17), not introducing Next.js middleware.
- Navigation is genuinely permission-aware (§8) — rendered from the authenticated administrator's resolved permission set, not a hardcoded placeholder list like the tenant Sidebar's current "SuperAdmin" check.
- **API client / token separation (Clarification 6)** — see §23.1 below; the shared singleton is **not** reused as-is.
- Every list view (tenants, plans, audit, …) is paginated from the outset (FR-9A-110) — no "load all" pattern.
- Loading/empty/error/degraded states are explicit per view (§22's pattern applied consistently).

### 23.1 API Client / Token Separation (Clarification 6)

Repository evidence (§3.16) shows `ApiClient`'s **transport** is already injectable (`constructor(baseUrl?: string)`) but its **auth is hardcoded at module scope**: `buildHeaders()` and `postMultipart()` call the tenant `getAccessToken()`; the 401 branch calls the tenant `acquireRefreshLock()`, `clearTokens()`, and dispatches the tenant `session-expired` event. Reusing that singleton for Platform traffic would therefore attach a tenant token to Platform requests and drive a Platform 401 into the tenant refresh flow — exactly the crossover this clarification forbids.

**Decision**: make auth an injected strategy on the existing `ApiClient` class, then export **two configured instances** from the same implementation:

```ts
interface AuthStrategy {
  getToken(): string | null;
  refresh(): Promise<unknown>;   // that domain's own single-flight lock
  onAuthFailure(): void;         // that domain's own clear + expiry event
}

export class ApiClient {
  constructor(private readonly auth: AuthStrategy, baseUrl?: string) { ... }
  // buildHeaders() -> this.auth.getToken()
  // 401 TOKEN_EXPIRED -> this.auth.refresh(), failure -> this.auth.onAuthFailure()
}

export const apiClient         = new ApiClient(tenantAuthStrategy);    // existing behaviour, unchanged
export const platformApiClient = new ApiClient(platformAuthStrategy);  // Epic 9A
```

How each requirement is structurally guaranteed:

| Requirement | Guarantee |
|---|---|
| Tenant requests never get a Platform token | `apiClient` holds `tenantAuthStrategy`; it has no reference to platform storage |
| Platform requests never get a tenant token | `platformApiClient` holds `platformAuthStrategy`; `lib/api/platform.ts` imports only this instance |
| Separate refresh flows | Each strategy's `refresh()` targets its own endpoint (`/auth/refresh` vs `/platform/auth/refresh`) |
| Separate concurrent refresh locks | Two independent module-level single-flight promises — the tenant's existing `acquireRefreshLock()` is untouched; the platform strategy gets its own `acquirePlatformRefreshLock()` built on the same proven pattern (§3.13) |
| Platform 401 never triggers tenant refresh | The 401 branch calls `this.auth.refresh()` — the instance's own strategy, structurally incapable of reaching the other domain |
| Tenant 401 never triggers Platform refresh | Same mechanism, mirrored |
| No duplicated HTTP code | URL building, header assembly, error parsing, 401-retry-once control flow, `StandardResponse<T>` unwrapping, and all verb helpers stay in the one `ApiClient` class |

**Backward compatibility**: `apiClient` keeps its exact current behaviour (the tenant strategy is just today's hardcoded calls, moved behind the interface), so no existing domain file (`accounting.ts`, `crm.ts`, `sales.ts`, …) changes at all — they continue importing the same `apiClient` symbol. This is a surgical change to one file, not a frontend refactor.

**Tests** (§32): explicit zero-crossover tests — a Platform request must carry the platform token and never the tenant token (and vice versa); a Platform 401 must invoke only the platform refresh lock; a tenant 401 must invoke only the tenant refresh lock; and a failed platform refresh must not clear tenant tokens or emit the tenant `session-expired` event.

---

## 24. API Architecture

Platform-scoped routes live under **`/api/v1/platform/...`** — never under `/api/v1/companies/{company_id}/...` (Platform Administration is never company-scoped by construction; the one exception, tenant-detail/support-access endpoints, still lives under `/api/v1/platform/tenants/{company_id}/...`, keeping the `platform` prefix authoritative even when a tenant is the *target* of an action).

Separation by concern (never generic CRUD):

| Concern | Example routes | Guard |
|---|---|---|
| Dashboard | `GET /platform/dashboard` | `platform.dashboard.view` |
| Tenant inspection | `GET /platform/tenants`, `GET /platform/tenants/{id}` | `platform.tenants.read` |
| Tenant lifecycle | `POST /platform/tenants/{id}/suspend`, `.../reactivate` | `platform.tenants.suspend`/`.reactivate` (separate) |
| Plans | `GET/POST/PATCH /platform/plans` | `.read`/`.manage` |
| Subscriptions | `POST /platform/tenants/{id}/subscription` | `platform.subscriptions.manage` |
| Entitlements/overrides | `POST /platform/tenants/{id}/entitlement-overrides` | `platform.entitlements.override` |
| Quotas/overrides | `POST /platform/tenants/{id}/quota-overrides` | `platform.quotas.override` |
| Platform Admins | `GET/POST/PATCH /platform/administrators` | `platform.admins.read`/`.manage` |
| Platform RBAC | `GET/POST /platform/roles` | `platform.rbac.read`/`.manage` |
| Support access | `POST /platform/tenants/{id}/support-access`, `DELETE .../support-access/{grant_id}` | `platform.support_access.initiate` |
| Audit | `GET /platform/audit` | `platform.audit.read` |
| Usage/quotas view | `GET /platform/tenants/{id}/usage` | `platform.quotas.read` |
| Health | `GET /platform/health` | `platform.monitoring.read` |

Sensitive mutations (suspend/reactivate, RBAC changes, overrides, support-access initiation) require: permission check → explicit reason field validated server-side → concurrency-safe write (§26) → transactional fail-closed audit (§20) → consistent `StandardResponse<T>` error envelope matching the existing project-wide convention.

Exact endpoint names remain adjustable at `/sp.tasks` time if a better repository-idiomatic naming surfaces — this table is a sufficient contract to plan against, not a frozen OpenAPI spec (that's `contracts/platform-admin-v1.yaml`, generated as a supporting artifact, §44 in the calling brief).

---

## 25. Data Model

Every entity evaluated against the calling brief's candidate list; none created blindly — each row below states ownership, key relationships, and why it's needed (or, where the brief listed something not created, why not).

| Entity | Owns | Key relationships | Tenant- vs Platform-scoped | Notes |
|---|---|---|---|---|
| `PlatformAdministrator` | Identity | 1:1 `User` | Platform | §5 |
| `PlatformRole` | RBAC | — | Platform | §8 |
| `PlatformPermission` | RBAC | — | Platform | §8, code-as-PK like tenant `Permission` |
| `PlatformRolePermission` | RBAC | role↔permission | Platform | §8 |
| `PlatformAdminRoleAssignment` | RBAC | admin↔role | Platform | §8, supports multiple roles |
| `PlatformSession` | Session | `PlatformAdministrator` | Platform | §6, never reuses tenant `sessions` |
| `PlatformRefreshToken` | Session | `PlatformSession` | Platform | §6 |
| `Capability` | Entitlement registry | — | Platform | §12, no per-module column |
| `Plan` | Commercial | — | Platform | §11, config-driven names |
| `PlanCapability` | Entitlement ceiling | `Plan`↔`Capability` | Platform | §12–13 |
| `Subscription` | Tenant assignment | `Company`↔`Plan` | Platform (references a tenant) | §11, partial-unique-active index |
| `QuotaDefinition` | Quota registry | — | Platform | §17 |
| `PlanQuota` | Quota ceiling | `Plan`↔`QuotaDefinition` | Platform | §17 |
| `TenantQuotaOverride` | Quota exception | `Company`↔`QuotaDefinition` | Platform (references a tenant) | §16 |
| `EntitlementOverride` | Entitlement exception | `Company`↔`Capability` | Platform (references a tenant) | §16 |
| `UsageRecord` | Metering | `Company` | Platform (references a tenant) | §18, periodic |
| `AiCreditLedgerEntry` | AI readiness | `Company`, `PlatformAuditEvent` | Platform (references a tenant) | §19 |
| `PlatformAuditEvent` | Audit | polymorphic target, `SupportAccessGrant` | Platform | §20, append-only |
| `SupportAccessGrant` | Support session | `PlatformAdministrator`↔`Company` | Platform (references a tenant) | §21 |

**Additive columns on an existing table** (not new entities — added by the correction pass, §9.1, ADR-12): `companies.pre_suspension_status` (varchar, nullable — the lifecycle status to restore on reactivation) and `companies.access_invalidated_at` (timestamptz, nullable — the company-scoped access watermark, §10.2). Both are NULL for every existing row, both are additive-only, and neither requires a backfill (§33).

**Not created** (candidate list items deliberately excluded, with reason): a separate "Tenant Feature State" model — reused as-is from the existing 5 per-module tables (§12); a separate `SupportAccessActionLog` table — folded into `PlatformAuditEvent` via a nullable FK instead, per BR-9A-022's "no parallel audit schema" (§20); a `PlatformCredential`/second password table — reuses `User` (§5); a `CompanySuspension` table — the two scalar columns above cover a strict 1:1 fact without a join (ADR-12).

Every platform-scoped table above inherits a lean `BaseModel` (id, timestamps) — **never** `TenantBaseModel`, which would incorrectly force a `company_id` column onto genuinely platform-owned rows like `PlatformRole`. Rows that *reference* a tenant (Subscription, overrides, UsageRecord, AiCreditLedgerEntry, SupportAccessGrant) carry an explicit, auditable `company_id` foreign key — never implicit tenant scoping via inheritance.

---

## 26. Database Integrity & Concurrency

- `PlatformRole.code`, `PlatformPermission.code` (PK), `Capability.key` (PK), `QuotaDefinition.key` (PK): unique by construction.
- **One active subscription per tenant**: `CREATE UNIQUE INDEX ... ON subscriptions (company_id) WHERE status = 'active'` (partial unique index — PostgreSQL-native, matches this project's Postgres-16 target) rather than an application-only check.
- **No duplicate active overrides**: `CREATE UNIQUE INDEX ... ON entitlement_overrides (company_id, capability_key) WHERE is_active = true` (same partial-index pattern) — and equivalently for `tenant_quota_overrides (company_id, quota_key)`.
- **Last-Platform-Owner protection**: service-level check (§8), not purely a DB constraint (the invariant — "at least one active administrator holds the `platform_owner` role" — isn't expressible as a simple column constraint; a `CHECK` alone can't count across rows).
- **Suspend/reactivate concurrency**: `SELECT ... FOR UPDATE` on the `Company` row at the start of both operations — **decided, not deferred** (§40 records the rationale: no existing version column on `Company`, rare low-contention administrative operations, and a trivially testable "exactly one transition commits" guarantee).
- **Pre-suspension status integrity**: `CHECK ((status = 'suspended' AND pre_suspension_status IS NOT NULL) OR (status <> 'suspended' AND pre_suspension_status IS NULL))` — makes it structurally impossible to have a suspended company with no restore target, or a non-suspended company carrying a stale one (§9.1, ADR-12).
- **Pre-suspension status domain**: `CHECK (pre_suspension_status IS NULL OR pre_suspension_status IN ('active','inactive'))` — only the two statuses from which suspension is permitted can ever be recorded as a restore target, so reactivation can never restore a company into `pending_setup` or `deleted`.
- **Constraint creation is guarded, not assumed** (Correction 2): migration `057` must verify that no `companies.status = 'suspended'` row already exists before creating the first constraint above, and fail loudly with a remediation message if any does — because such a row's true prior status is unrecoverable and must never be fabricated (§33.1, ADR-12).
- **Valid date ranges**: `expires_at > granted_at`/`started_at` CHECK constraints on override and support-access tables; `effective_date` validation on `Subscription` at the service layer (Edge Case #16).
- **Valid quota values**: `limit_value >= 0` CHECK where not null (null = unlimited, never negative-as-sentinel).

---

## 27. Existing Module Integration Matrix

Evidence-based (§3.10), not assumed:

| Module | Current Toggle | Current Authorization (mutation) | Point-of-Use Plan Ceiling (§13.1) | Tenant Toggle Hardening Needed (§14) | Existing Module-Enabled Gate | Tests Needed |
|---|---|---|---|---|---|---|
| Inventory | `inventory_feature_flags` (generic multi-flag) | `require_authenticated` + membership only — **no permission check** | **Yes** — mount `require_capability_entitled("inventory")` | **Yes** (new `inventory.settings.manage` permission) | None exists (§3.10) → adapter returns `enabled=True`, Plan ceiling alone governs (§40) | Security test (membership-only can no longer mutate) + entitlement matrix tests |
| Purchase | `purchase_feature_flags` (generic multi-flag) | Same gap | **Yes** — `require_capability_entitled("purchase")` | **Yes** (new `purchase.settings.manage`) | None exists → same rule | Same |
| Sales | `sales_feature_flags` (generic multi-flag) | Same gap | **Yes** — `require_capability_entitled("sales")` | **Yes** (new `sales.settings.manage`) | None exists → same rule | Same |
| Accounting | `accounting_feature_flags` (generic multi-flag) | Already patched: `user_has_accounting_permission(..., "accounting.approvalworkflow.manage")` | **Yes** — `require_capability_entitled("accounting")` | **No** — already correctly gated, reused as the reference pattern | None exists → same rule | Entitlement matrix tests + regression test confirming the existing permission check still behaves identically |
| CRM | `crm_feature_flags` (single master flag `feature.crm.enabled`) | Already patched: `require_admin_or_above()` | **Yes** — `require_capability_entitled("crm")`, mounted **in front of** the preserved `require_crm_enabled` (§35) | **No** — already correctly gated | `require_crm_enabled` **preserved unchanged**; adapter reads `feature.crm.enabled` | Entitlement matrix tests incl. the explicit "Plan denies + toggle still enabled → denied" case + regression test |

Every module's row now carries a point-of-use ceiling, satisfying Correction 1 requirement 10 (uniform application). No module implements its own resolution logic — all five delegate to the single `PlatformEntitlementService` (requirement 8).

---

## 28. Security Threat Analysis

| Threat | Mitigation layer |
|---|---|
| Tenant user attempts Platform API access | `require_platform_permission()` rejects any non-`platform_access`-typed token structurally (§6) |
| Forged platform role/claim in a tampered JWT | HS256 signature verification (existing `PyJWT` infra, unchanged); `typ` claim alone is never trusted without a valid signature |
| Stale Platform session after role removal | Permission re-resolved on every request from `PlatformAdminRoleAssignment` (no caching of "effective permissions" in the token itself) — FR-9A-221 |
| Stale tenant session after suspension | §10.2 Layer 1 (company status checked on every company-scoped request, all five modules) + Layer 2 (`access_invalidated_at` watermark vs. `Session.created_at`) |
| **Pre-suspension refresh credential redeemed after reactivation to regain access** | Closed by keying Layer 2 on `Session.created_at` rather than the token's `iat`: a refresh reuses the same session and so cannot advance authentication time (§10.2). Only a genuine login creates a new session |
| **Client forges a fresh authentication time** | Impossible: the value is read from the database, keyed by the `sid` claim inside a signature-verified JWT; no API endpoint writes `Session.created_at` |
| **Migration fabricates a lifecycle state for an already-suspended company** | Closed by §33.1's preflight — the migration refuses to proceed rather than guessing, so `suspended → pre-suspension status` stays deterministic |
| **Suspending Company A signs a multi-tenant user out of Company B** | Structurally impossible under ADR-6: enforcement keys off the request's `{company_id}`, and no global `sessions` row is touched (§10.1–§10.3). Proven by the cross-tenant test suite (§32) |
| **Plan downgrade bypassed by a stale enabled tenant toggle** | §13.1's mount-level `require_capability_entitled(...)` evaluates the Plan ceiling on every request to the module, independent of the stored toggle value |
| **Platform 401 drives the tenant refresh flow / token crossover** | ADR-11's injected `AuthStrategy` — each `ApiClient` instance can only reach its own domain's token and refresh lock (§23.1) |
| **Deployment left with no Platform Owner** | ADR-8: bootstrap is a separate command that exits non-zero on missing/invalid config; §7's deployment order requires verifying an owner exists before exposing Platform Admin |
| **Reactivation restores the wrong lifecycle status** | `pre_suspension_status` persisted at suspension and CHECK-constrained (§9.1, §26); reactivation fails closed rather than guessing if it is ever absent |
| Cross-tenant IDOR on any `/platform/tenants/{id}/...` route | Every such route still requires `require_platform_permission()`; `company_id` is never itself an authorization credential (FR-9A-212) |
| Manipulated `erp_active_company_id` | Platform authority never reads this key at all (§15, BR-9A-036) — manipulating it has zero effect on Platform routes |
| Platform selected-tenant context leaking into tenant `CompanyContext` | Structurally separate React contexts and separate localStorage keys (§15, §23) — no shared state exists to leak |
| Self-privilege escalation | §8's explicit role-assignment guard |
| Last Platform Owner removal | §8/§26's service-level protection |
| Entitlement escalation via tenant feature toggle | §14's resolver-ceiling check added at the exact mutation point |
| Expired override still honored | Resolver checks `expires_at` at read time, never trusts a stale `is_active` flag alone (§16) |
| Quota bypass | Enforcement style (`hard`/`soft`/`informational`) is a first-class, deliberately-declared field — a `hard` quota's enforcement point is the module's own write path (Tasks-phase wiring), not optional |
| Support-session misuse (reading beyond scope) | §21 — no code path to business-record repositories exists in the support-access router at all |
| Audit bypass | §20's fail-closed transaction boundary — a mutation cannot commit without its audit row |
| Bootstrap abuse | §7 — idempotent, env-var-sourced, no public endpoint, never overwrites |
| Mass-assignment vulnerabilities | Pydantic v2 schemas with explicit field allow-lists (existing project-wide convention) for every request body |
| Dangerous bulk operations | §29 — deferred/gated behind a separate permission, per-tenant auditability preserved |
| CSRF | Existing project auth architecture's CSRF posture (Constitution §19) applied unchanged to Platform routes — no new exemption |

---

## 29. Bulk Operations

Not required for Epic 9A's MVP (spec §12.16/FR-9A-111 makes bulk actions optional, gated behind a separate permission if implemented at all). This plan **defers** privileged bulk mutations (e.g., bulk suspend) to a later Tasks-phase decision, consistent with "if unnecessary for MVP, defer" — bulk *read*/export (tenant directory, audit export, FR-9A-120) is in scope from the start since it's read-only and low-risk. If a bulk privileged mutation is added later, it must: require its own explicit permission (distinct from the single-tenant action, BR-9A-009), validate each tenant independently, require the same reason/confirmation, and produce one audit record per tenant (BR-9A-029) — never a blended one.

---

## 30. Observability

Reuses existing structured-logging conventions (Constitution §22) — no new logging library. Logged fields for Platform operations: correlation/`request_id`, actor `platform_administrator_id`, action, target `company_id` (when applicable), permission-denial events, lifecycle mutations, support-access start/end, entitlement-resolution failures, quota-enforcement rejections, audit-write failures (logged **before** the exception propagates, so an operator can see *why* a mutation failed even though the audit row itself never persisted), degraded usage-measurement events.

**Never logged**: passwords, secrets, raw JWTs, tenant business-record contents. **Operational logs and `PlatformAuditEvent` remain conceptually and physically distinct** (§20) — a log line is not a substitute for, or a copy of, an audit record.

---

## 31. Performance / Scalability

No fabricated numeric SLA (resolved OQ-4). Concrete, sensible patterns: mandatory pagination on every list endpoint (§23, §24); indexed filtering on every audit/tenant/usage query (§20, §22, §26); no full-table frontend fetches; the entitlement resolver (§13) is a small number of indexed point-lookups per call, not a table scan; dashboard aggregates use `GROUP BY`/indexed `LIMIT` queries, never per-tenant N+1 loops.

**Cost of the two new per-request checks** (both on company-scoped routes only): `assert_company_access_allowed` (§10.2) reads one `Company` row by primary key — and `get_current_company` already loads that same row, so for the `companies` module that part is free — plus one `sessions` row by primary key for the authentication-freshness comparison. Both are single-row PK lookups added to a request that is already querying `company_members`. `require_capability_entitled` (§13.1) adds the resolver's indexed point-lookups on the same request. Both are candidates for **request-scoped memoisation** (cache the resolved `Company` and entitlement result on the FastAPI request state so multiple dependencies in one request share one read) — a local, per-request optimisation with no cross-request cache and therefore no invalidation or consistency concern, unlike the process-level cache §31 declines below. **No caching layer introduced** — no Redis exists in the stack (§3.8), and nothing in this Epic's access patterns (bounded lists, indexed point-lookups) currently justifies the invalidation-consistency complexity a cache would add; if a future ADR justifies one, it would need its own explicit rationale, invalidation strategy, and consistency analysis, none of which exists today.

---

## 32. Testing Strategy

Directory convention confirmed and reused exactly (§3.7): `backend/tests/{unit,integration/repositories,integration/api/v1,performance,security}/modules/platform_admin/`, plus `frontend` equivalents.

**Unit**: permission evaluation (union-of-roles), entitlement resolution (every row of §13's table), quota resolution (5 states), override precedence (§16), tenant-lifecycle state-machine transitions (valid + all prohibited transitions from spec §23.1), support-access expiry, bootstrap guard logic, and the `ModuleEnablementProvider` default rule (module with no master toggle → `enabled=True`, §40).

**Entitlement point-of-use enforcement (Correction 1)** — the explicit matrix, run against every one of the five modules:

| Scenario | Expected |
|---|---|
| Plan allows + toggle enabled | Access **allowed** |
| Plan denies + toggle enabled | Access **denied** (403 `CapabilityNotEntitledError`) |
| Plan changes allowed → denied, tenant toggle left untouched | Previously-working requests become **denied on the next request**, with no toggle mutation |
| Plan denies, tenant attempts to switch toggle on | Mutation **rejected** at the §14 secondary guard |
| Plan re-allows after a denying period, original toggle never modified | Access **resumes automatically** at the tenant's preserved preference |
| Frontend entitlement response tampered with / capability UI forced | Server still **denies** — frontend is UX only |

**Tenant lifecycle (Correction 2)**: `active → suspended → active`; `inactive → suspended → inactive`; repeated suspension rejected (Edge Case #1); repeated reactivation rejected (Edge Case #2); concurrent suspend/suspend and suspend/reactivate under `SELECT ... FOR UPDATE` (exactly one commits, no duplicate audit row); audit-write failure rolls back the status change **and** the watermark **and** the outbox record (fail-closed, §20); the CHECK constraint rejects a hand-crafted `suspended` row with NULL `pre_suspension_status`.

**Cross-tenant suspension isolation + authentication freshness** — the suite that proves ADR-6. Cases A–F are mandatory:

| # | Scenario | Expected |
|---|---|---|
| **A** | Login before suspension → suspend → reactivate → replay the **old access token** | **Denied** for A (watermark vs. `Session.created_at`) |
| **B** | Login before suspension → suspend → reactivate → redeem the **old refresh token** to mint a brand-new access token → use it | **Still denied** — refresh reuses the same session, so authentication time never advances past the watermark. *This is the Correction-1 regression test; it must fail loudly if anyone re-keys the check to `iat`.* |
| **C** | Login before suspension → suspend → reactivate → **genuine new login** | **Allowed** (new `Session`, `created_at > access_invalidated_at`), assuming membership is otherwise valid |
| **D** | User belongs to A **and** B; suspend A | A-scoped requests denied; **B-scoped requests still succeed on the same token** |
| **E** | Multi-device: two devices authenticated before suspension → suspend → reactivate | Both denied for A; Device 1 re-logging in restores **only Device 1**; Device 2 stays denied until it re-authenticates; both keep B throughout (§10.3.1) |
| **F** | Attempt to fabricate freshness: tamper with `iat`/`sid`, forge a token, or alter `erp_active_company_id` | All denied — `sid` is signature-protected, `Session.created_at` is server-generated and unwritable via any API, and client company context is never an authorization input |
| — | User belongs only to Company A; A suspended | All A-scoped requests denied |
| — | Manipulated `{company_id}` to dodge suspension | Denied — enforcement follows the addressed company, membership re-checked |
| — | A reactivated after re-login | `Company.status` is the **pre-suspension** value, not hardcoded `active` |

**Migration 057 preflight (Correction 2)**:

| # | Scenario | Expected |
|---|---|---|
| 1 | Database with **no** suspended companies | Migration succeeds; both columns and both CHECK constraints created |
| 2 | Database containing a pre-existing `status='suspended'` row with NULL `pre_suspension_status` | Migration **refuses to proceed**, raising a clear error naming the affected companies and the remediation options |
| 3 | Same as 2, inspected afterwards | **No** arbitrary state invented — no column added, no constraint created, no `pre_suspension_status` backfilled; the database is byte-for-byte unchanged |
| 4 | Full `upgrade head → downgrade 056 → upgrade head` cycle on **real PostgreSQL** | Clean in both directions; the two `companies` columns and their constraints appear and disappear correctly (partial unique indexes and CHECK constraints are PostgreSQL-specific, so SQLite cannot substitute here) |

**Bootstrap (Correction 4)**: first successful bootstrap; missing configuration → non-zero exit, **no** partial writes; repeated invocation with an owner present → no change, zero exit; attempted overwrite of an existing owner → refused; invalid configuration (malformed email / unusable hash) → non-zero exit with a specific message; and a test asserting **no Alembic migration** provisions credentials.

**API-client token separation (Clarification 6)**: platform requests carry only the platform token; tenant requests carry only the tenant token; a platform 401 invokes only the platform refresh lock; a tenant 401 invokes only the tenant refresh lock; a failed platform refresh does not clear tenant tokens nor emit the tenant `session-expired` event (and vice versa).

**Repository/service**: platform-scoped isolation (no `company_id` leakage into platform-only tables), role assignment (self-escalation rejection, last-owner protection), Plan/Subscription state changes, **audit fail-closed transaction behavior** (inject a forced audit-write failure, assert the state change is also rolled back — this is the single most important test in the whole suite given §20's design), quota/override persistence.

**API integration**: unauthorized tenant-typed token → every `/platform/*` route rejected; each Platform permission code individually tested (holding it grants exactly that capability, not adjacent ones); suspend/reactivate end-to-end including company-scoped access invalidation and pre-suspension-status restoration; plan assignment/downgrade-conflict; the 3 hardened modules' feature-toggle mutation now requires the new permission; the mount-level entitlement ceiling active on all five modules; quota enforcement per declared style; support-access scope boundary (attempt to reach a business-record endpoint during an active grant → rejected); audit trail completeness for every privileged action type in FR-9A-202's list.

**Tenant isolation/security**: Company A cannot affect Company B via any Platform-scoped-but-tenant-referencing endpoint; Platform-selected-tenant context cannot leak into `erp_active_company_id` (a live browser test, not just unit); tenant users cannot obtain Platform authority via any manipulated claim; feature toggles cannot exceed Plan ceiling; manipulated ids/context cannot bypass isolation.

**Frontend**: `(platform-admin)` route guards (unauthenticated → redirect); permission-aware nav rendering; the two-context separation (`PlatformAuthContext`/`PlatformSelectedTenantContext` vs. tenant `AuthContext`/`CompanyContext`) proven via a test that manipulates one and asserts zero effect on the other; loading/empty/degraded states per widget; confirmation dialogs on suspend/reactivate/RBAC changes.

**Live verification**: real Docker Compose PostgreSQL migration cycle (up→down→up, matching the established Epic 8/9 methodology, §3.6/§33), plus Playwright-driven browser verification of the full Platform Dashboard → suspend a real tenant → confirm tenant-side session rejection → reactivate → confirm re-login required — mirroring this session's own established live-verification pattern from Epics 7–9. SQLite is used only for the fast unit/integration suite, never as the final proof of migration or PostgreSQL-specific constraint (partial unique indexes) correctness.

---

## 33. Migration / Backward Compatibility Strategy

New migrations start at `057` (§3.6), strictly additive, never editing `001`–`056`:

| # | Contents |
|---|---|
| 057 | `platform_administrators`, `platform_roles`, `platform_permissions`, `platform_role_permissions`, `platform_admin_role_assignments`, `platform_sessions`, `platform_refresh_tokens`, `platform_audit_events`; **plus** two additive nullable columns on the existing `companies` table — `pre_suspension_status`, `access_invalidated_at` — their CHECK constraints, and a **mandatory preflight guard** on pre-existing suspended rows (§33.1) |
| 058 | `capabilities`, `plans`, `plan_capabilities`, `subscriptions` (+ partial unique index) + real FK constraint on existing `companies.subscription_id` |
| 059 | `quota_definitions`, `plan_quotas`, `tenant_quota_overrides`, `entitlement_overrides` (+ partial unique indexes) |
| 060 | `usage_records`, `ai_credit_ledger_entries` |
| 061 | `support_access_grants` + `support_access_grant_id` nullable FK added to `platform_audit_events` |

**There is deliberately no bootstrap migration.** Provisioning the first Platform Owner is a separate, explicitly-invoked operator command (§7, Correction 4) — the previously-planned `062` data migration was removed because a migration that silently no-ops on missing configuration can permanently stamp a deployment as bootstrapped when no Platform Owner exists. Schema versioning and credential provisioning are now fully decoupled.

**Existing tenants unaffected — with one guarded exception, Correction 2**: the only changes to existing tables are additive and nullable — the two `companies` columns in `057` and the FK constraint in `058` on the already-nullable, already-unused `companies.subscription_id` (existing rows keep `NULL`). No backfill of business data. Existing per-module feature-flag values are read, never migrated. Existing CRM-enabled/disabled state is untouched. No default Plan/Subscription is force-assigned as part of these migrations — that's §34's rollout, not a schema migration.

The exception is that the new `pre_suspension_status` CHECK constraint is **not** automatically satisfiable by every conceivable existing database, so `057` must verify rather than assume — see §33.1.

### 33.1 Migration 057 Preflight: Pre-Existing Suspended Companies (Correction 2)

The CHECK constraint requires `pre_suspension_status IS NOT NULL` whenever `status = 'suspended'`. Migration `057` adds the column as NULL for all existing rows. If any company is **already** `suspended` in the target database, the constraint would be violated at creation time.

This plan previously asserted that no such row can exist because Epic 9A introduces the only suspension write path. That reasoning is *probably* true but must not be silently relied upon — a row could have been set by direct SQL, a fixture, a restored backup, or a future/parallel change. And critically, **the true pre-suspension status of such a row is unrecoverable**: `status = 'suspended'` records where the company *is*, never where it *was*. Guessing `active` (or `inactive`) would make `suspended → pre-suspension status` non-deterministic and could silently restore a tenant into the wrong lifecycle state — precisely the defect ADR-12 exists to prevent.

**Required migration behaviour** (before adding the constraint):

```python
suspended = conn.execute(text(
    "SELECT id, slug FROM companies WHERE status = 'suspended'"
)).fetchall()

if suspended:
    raise RuntimeError(
        f"Migration 057 cannot proceed: {len(suspended)} company row(s) are already "
        f"status='suspended' and have no recoverable pre_suspension_status.\n"
        f"Affected: {[r.slug for r in suspended]}\n"
        f"The correct prior lifecycle state cannot be inferred from current state and "
        f"MUST NOT be guessed. Remediate explicitly before re-running, e.g. set each "
        f"row's status back to its true prior value ('active' or 'inactive'), or set "
        f"pre_suspension_status explicitly for each row, then re-run this migration."
    )
```

| Case | Behaviour |
|---|---|
| Zero suspended rows (the expected case) | Proceed normally: add columns, add constraints |
| One or more suspended rows | **Fail loudly**, naming the affected companies and the remediation options; add nothing |
| — | Never backfill `active`/`inactive` arbitrarily; never weaken or skip the constraint |

Failing the migration is the correct outcome rather than an inconvenience: it is a loud, operator-visible, fully-reversible stop (nothing has been altered when it raises) that forces an explicit human decision about lifecycle data that only a human can know.

**Rollback**: every migration's `downgrade()` drops exactly what its `upgrade()` created, in reverse dependency order — matching the existing convention across `044`–`056`. `057`'s downgrade drops the two `companies` columns and their constraints; the preflight is an upgrade-time guard only and has no downgrade counterpart.

---

## 34. Entitlement Rollout Strategy

The new entitlement layer must not instantly change existing tenant access. Staged sequence, informed by §3's findings rather than assumed:

1. Migrations `057`–`061` run, then the explicit bootstrap command (§7) provisions the first Platform Owner and is verified to have succeeded — schema exists, zero tenant-visible behavior change (no enforcement wired yet).
2. Seed `Capability` rows for the 5 existing modules (data step, not a migration — via a `PlatformAdministrator`-gated admin action or a one-time seed script, consistent with §7's bootstrap pattern).
3. Seed one baseline "Legacy/Unlimited" `Plan` with `PlanCapability.allowed = true` for all 5 seeded capabilities and `PlanQuota` rows all set to `unlimited` (`limit_value = NULL`).
4. Bulk-assign every **existing** tenant a `Subscription` to this baseline plan (a one-time data step, auditable, actor = the bootstrap Platform Owner) — this is the step that makes `Company.subscription_id` non-null for pre-existing tenants for the first time.
5. Existing per-module feature-flag values (Tenant Toggle) are **preserved exactly as they are** — nothing about step 2-4 touches those tables.
6. Only **after** steps 2–5 are verified (existing tenants' effective entitlement resolves to "available" for everything they already had) is enforcement activated: the mount-level `require_capability_entitled(...)` dependency is added to all five module routers (§13.1), and §14's secondary mutation-point check is wired into the 3 hardened modules. Because every existing tenant is already on the baseline all-allowed Plan by step 4, this activation is a no-op for their effective access — which is precisely what step 7 verifies.
7. Verify via the live-verification suite (§32) that no existing tenant lost access to anything they had before this Epic.
8. Only then is the Platform Admin UI (§23) exposed/enabled for real operator use.

This ordering directly follows from the repository facts in §3 (there is currently no Plan/Subscription concept at all, so step 1-4 aren't optional scaffolding — they're the necessary precondition before step 6's enforcement can be safely turned on without breaking every existing tenant simultaneously).

---

## 35. CRM Integration

CRM is complete (§2) and its business logic is untouched. Integration is limited to:

**(a)** CRM becomes one `Capability` row (`key="crm"`) consumed by the generic resolver exactly like the other four modules — no CRM-specific entitlement code or architecture.

**(b)** Its already-correct `require_admin_or_above()` gate on `/crm/enable`/`/disable` is **not weakened or replaced**; §14's secondary ceiling check is added alongside it, following the same "add, don't replace" pattern used for Accounting's existing check.

**(c) `require_crm_enabled` alone is explicitly NOT sufficient for runtime access (Correction 1).** It reads only `crm_feature_flags` and therefore cannot see the Plan ceiling — a tenant moved to a Plan that denies CRM would otherwise keep full CRM access on a stale enabled toggle. `require_crm_enabled` is **preserved unchanged** as the tenant-toggle gate, and the mount-level `require_capability_entitled("crm")` dependency is added **in front of it** on the same router mount (§13.1's code block shows the exact composition). Effective access is then genuinely `Plan × Toggle × Override`: the Plan ceiling denies first, and the existing toggle gate continues to honour the tenant's own choice within what the Plan allows. This is additive — no CRM file is modified; the change is one line in `backend/api/v1/router.py`.

**(d)** Canonical tenant-context consistency (§15) and Platform Admin administrative visibility (§21–§22) require no CRM code change.

---

## 36. Implementation Sequencing

The brief's proposed Phase A–G ordering is **adopted with two refinements**, both forced by §3/§10's second-pass findings:

1. The **company-access enforcement helper** (`assert_company_access_allowed`, §10.2 Layer 1 + Layer 2) is built in **Phase B**, immediately before suspend/reactivate, because suspension is not genuinely enforced on any business-module route without it (§3.3). It is *not* in Phase A, because unlike the first draft's discarded `get_current_user()` change it touches the company-access dependencies rather than the universal auth path.
2. The **explicit bootstrap command** (§7) moves from Phase G to **Phase A**, since it is no longer a migration that runs implicitly at the end — it is an operator step that must exist as soon as a Platform Owner is needed to exercise anything else, and Phase A is where Platform identity/RBAC first become usable.

**Phase A — Security/Foundation**: `platform_admin` module skeleton; `PlatformAdministrator`/session/RBAC models + migration `057` (including the two `companies` lifecycle columns); genuine `require_platform_permission()`; platform session revocation enforced in `get_current_platform_admin()` (FR-9A-220); the explicit bootstrap command (§7) + its test matrix; Platform audit foundation (§20's transaction pattern proven with a trivial first audited action).

**Phase B — Tenant Control**: `assert_company_access_allowed` wired into both company-access dependencies, keyed on `Session.created_at` (§10.2 — closes the §3.3 enforcement gap; requires no auth-path change); tenant directory/detail read endpoints; suspend/reactivate with pre-suspension-status persistence and restore (§9); `SELECT ... FOR UPDATE` concurrency handling (§26). Test cases A–F (§32) are written in this phase, not deferred to Phase G — case B in particular is the guard against the refresh bypass and must exist as soon as the mechanism does.

**Phase C — SaaS Commercial Control Plane**: migrations `058`–`059`; Plans, Subscriptions, Capabilities, `PlanCapability`, Overrides; the `PlatformEntitlementService` resolver + the five `ModuleEnablementProvider` adapters (built, unit-tested, but not yet mounted).

**Phase D — Existing Module Hardening + Rollout Steps 1–5**: §14's 3-module permission hardening; §34 steps 1–5 (capability seed, baseline all-allowed Plan, bulk-assign existing tenants) — deliberately *before* enabling any enforcement.

**Phase E — Enforcement Activation + Quotas/Usage**: §34 step 6 — mount `require_capability_entitled(...)` on all five module routers (§13.1) and wire §14's secondary mutation-point check; migration `060`; Quota/Usage/AI-ledger.

**Phase F — Support/Operations**: migration `061`; support access; audit explorer; Platform Dashboard; health/degraded states.

**Phase G — Verification/Hardening**: the full §32 test suite; real-Postgres migration-cycle and live verification (§34 step 7); cross-tenant isolation suite; regression suite confirming zero existing-tenant access loss; only then, Platform Admin UI exposed for real use.

---

## 37. Architecture Decision Records

Thirteen decisions meet the ADR bar (long-term consequence, real alternatives considered, cross-cutting scope) — trivial implementation choices are not elevated to ADRs. ADR-3, ADR-6, and ADR-8 were **revised** by the correction pass; ADR-11–13 are **new**.

1. **Platform Identity/Session Separation** — shared `User` credentials + separate `PlatformAdministrator`/`PlatformSession`/distinct JWT `typ` claim (§5–§6). Rejected: fully separate credential system; embedding a platform flag in the tenant JWT.
2. **Platform RBAC Enforcement Model** — genuine permission-code enforcement, deliberately diverging from tenant RBAC's currently-inert `Permission`/`RolePermission`/rank-based reality (§3.2, §8). Rejected: mirroring the inert pattern as-is.
3. **Entitlement Resolution Architecture & Enforcement Point** *(revised)* — `Capability`/`PlanCapability`/per-module `ModuleEnablementProvider` adapters + single resolver, enforced by a **mount-level `require_capability_entitled(...)` dependency on every entitled module router** (§13.1), with the toggle-mutation check retained only as a secondary guard (§14). Rejected: one boolean column per module; a generic cross-table query without an adapter abstraction; **and — corrected — enforcing the ceiling only at toggle-mutation time, which left a real bypass whenever a Plan downgrade left a stale enabled toggle behind.**
4. **Quota/Usage Architecture** — generic key-based registries + periodic `UsageRecord`, PostgreSQL-only (§17–§18). Rejected: Redis counters (no Redis in stack); per-event streaming (over-engineered for current scale).
5. **Audit Fail-Closed Transaction Strategy** — flush-not-commit repositories + single service-level commit, following the Accounting precedent, not Auth/Companies' (§3.4–§3.5, §20). Rejected: `BaseRepository`'s default auto-commit convenience methods for audited paths.
6. **Tenant Suspension Enforcement — Company-Scoped Access Invalidation, Keyed on Authentication Time** *(rewritten twice)* — enforce at the company-access boundary via `assert_company_access_allowed` (company status **plus** an `access_invalidated_at` watermark compared against **`Session.created_at`**), keyed off the request's `{company_id}` path parameter (§10.2). Repository evidence establishes `Session.created_at` as a true authentication-freshness value: `login()` creates a new `Session`, `refresh()` reuses the existing one, so it advances only on genuine re-authentication (§3.1). Requires **no** new JWT claim, **no** new session column, and **no** change to `get_current_user()`/`CurrentUser`. **Rejected: comparing the watermark to the token's `iat`** — a refresh mints a token with a fresh `iat`, so a pre-suspension refresh credential redeemed after reactivation would silently restore access without any re-authentication, violating FR-9A-018. **Rejected: revoking rows in the global `sessions` table by `user_id`** — a `Session` carries no `company_id` and models a device login for a human identity, so that would sign multi-tenant users out of unrelated active companies *and* would not block the five business modules, which never read `Company.status` (§3.3). Also rejected: a Redis revocation list (no Redis in stack); `Company.status` alone without a watermark (pre-suspension tokens would resume working after reactivation).
7. **Support-Access Context Separation** — dedicated `PlatformSelectedTenantContext`, never touching `erp_active_company_id`/`CompanyContext` (§15, §21). Rejected: reusing tenant `CompanyContext` with a "platform mode" flag.
8. **Platform Owner Bootstrap Mechanism** *(rewritten)* — an explicit, separately-invoked, idempotent `python -m modules.platform_admin.bootstrap` operator command, env-var sourced, **decoupled from Alembic revision versioning**, with non-zero exit on missing/invalid configuration (§7). **Rejected: the originally-planned idempotent Alembic data migration**, because silently returning on absent configuration lets Alembic stamp the revision as applied while leaving a deployment permanently unbootstrapped — and a migration never re-runs once stamped. Also rejected: making that migration *fail* on missing config (would block unrelated schema upgrades). No CLI framework is introduced — a bare `python -m` module entry point suffices.
9. **`Company.subscription_id` Reuse Strategy** — add the real FK to the new `subscriptions` table; keep it as a synced denormalized pointer, with the partial-unique-index on `subscriptions` remaining authoritative (§11, §26). Rejected: dropping the column and starting fresh (unnecessary churn on an already-reserved, currently-inert column).
10. **Platform Module Boundary & Directory** — `backend/modules/platform_admin/` + frontend `(platform-admin)` route group, fully prefixed URLs (§4, §23). Rejected: a `backend/modules/platform/` name (ambiguous with the generic word "platform" used elsewhere in docs); reusing/extending `companies` module (would blur the platform/tenant boundary the whole Epic exists to establish).
11. **Frontend API Client / Token Separation** *(new)* — inject an `AuthStrategy` into the existing `ApiClient` class and export two configured instances (`apiClient` tenant / `platformApiClient` platform) sharing one transport implementation (§23.1). Rejected: reusing the existing singleton unchanged — repository evidence shows it hardcodes the tenant token accessor and tenant refresh lock at module scope, so a Platform 401 would drive the tenant refresh flow and Platform requests would carry the tenant token. Also rejected: a fully separate duplicated HTTP client (needless duplication of URL building, error parsing, retry control flow, and response unwrapping).
12. **Pre-Suspension Status Persistence** *(new; extended by Correction 2)* — two additive nullable columns on `companies` (`pre_suspension_status`, `access_invalidated_at`) with a CHECK constraint tying the former to `status = 'suspended'`, **and a migration preflight that refuses to proceed if any company is already suspended** (§9.1, §26, §33.1). Rejected: inferring the previous status from audit history (append-only history is not authoritative current state, and a defect or gap in audit would corrupt lifecycle restoration); a separate `company_suspension` table (a 1:1 scalar fact does not warrant a table); **and — corrected — assuming no pre-existing suspended row can exist**, since such a row's true prior status is unrecoverable and backfilling a guess would make `suspended → pre-suspension status` non-deterministic.
13. **Canonical Tenant-Context Accessor** *(new)* — a thin accessor module fronting the unchanged `erp_active_company_id` key, mandatory for new Epic 9A code, optional for existing modules (§15). Rejected: declaring the raw localStorage key itself the architectural contract (conflates persistence detail with contract); refactoring all existing modules onto the accessor in this Epic (out of scope, unrelated churn).

---

## 38. Risks / Mitigations

| Risk | Mitigation |
|---|---|
| `assert_company_access_allowed` (ADR-6) is added to `get_current_company_member`, which every company-scoped route in the app already depends on — regression risk to all five business modules | The check reads a `Company` row and a `Session` row, both by PK, and compares two timestamps; it rejects only on `suspended`/`deleted` status or a pre-watermark session, neither of which any existing tenant can be in at rollout time (`access_invalidated_at` is NULL for every existing row, and a NULL watermark denies nothing, §33). Phase B runs the full existing module regression suite before Phase C proceeds (§36). Blast radius is strictly *narrower* than either rejected design, since the universal auth path is untouched (§10.4) |
| Someone later "simplifies" the freshness check back to the token's `iat`, silently reopening the refresh bypass | Test case B (§32) exists specifically to fail in that event, and §10.2 documents the reasoning inline at the point of the comparison rather than only in an ADR |
| A database somehow contains an already-suspended company when `057` runs | §33.1's preflight fails the migration loudly and changes nothing, forcing explicit operator remediation instead of a fabricated lifecycle state |
| Multi-tenant users could lose access to unrelated companies if suspension were implemented as global session revocation | Explicitly rejected in ADR-6; §10.3 and the cross-tenant test suite (§32) prove Company B access survives Company A's suspension |
| A stale enabled tenant toggle could outlive a Plan downgrade | Closed by §13.1's mount-level point-of-use enforcement; regression-tested by the "Plan changes allowed→denied without touching the toggle" case (§32) |
| Bootstrap could leave a deployment with no Platform Owner | Closed by ADR-8: bootstrap is a separate command with a non-zero exit on missing/invalid config, and the deployment order in §7 requires verifying an owner exists before exposing Platform Admin functionality |
| `ModuleEnablementProvider` per-module adapters assume a discoverable "module master toggle" convention not yet confirmed for 4 of 5 modules (§13) | Explicit Tasks-phase verification step (§40) before implementation, not assumed away |
| Rollout (§34) bulk-assigns a Subscription to every existing tenant — a one-time, wide-blast-radius data operation | Staged, verified, reversible (a `Subscription` row is one row per tenant, trivially deletable/re-seedable if a defect is found before enforcement (step 6) activates) |
| Fail-closed audit (ADR-5) is stricter than Auth/Companies' existing patterns — a Platform Admin action can now fail purely due to an audit-infrastructure problem | Already explicitly accepted as a deliberate elevation in spec.md §28 Risk #6, confirmed final (not reopened, per this session's own prior correction) |
| Feature-toggle hardening (§14) adds a new permission requirement to 3 modules' existing endpoints — could unexpectedly lock out tenant admins who previously relied on membership-only access | New permission seeded and auto-granted to the existing `owner`/`admin` tenant roles as part of the same migration/seed step (mirrors how Accounting's own prior patch was rolled out, per §3.10's evidence) |

---

## 39. Complexity Tracking

*Fill only for Constitution Check violations — there are none (§1). Documented here instead per the calling brief's explicit request to justify every non-trivial new abstraction.*

| New abstraction | Why existing architecture is insufficient | Simpler alternative considered | Why rejected |
|---|---|---|---|
| Platform session/token boundary (separate table + `typ` claim) | Tenant `sessions`/JWT has no concept of "not scoped to any company," and reusing it would make BR-9A-003 (structural separation) unverifiable by inspection alone | A boolean flag on the existing tenant session | Rejected — a flag is convention, not structure; exactly the pattern the spec forbids |
| `PlatformEntitlementService` resolver | Five independent modules each re-implementing Plan × Toggle × Override logic would violate BR-9A-016's determinism guarantee (five slightly-different implementations drifting over time) | Let each module query `PlanCapability`/`EntitlementOverride` directly | Rejected — duplicates non-trivial resolution logic across 5 call sites, high drift risk |
| `ModuleEnablementProvider` adapter (5 small implementations) | Existing feature-flag tables have the same *shape* (`flag_key`/`is_enabled`) but not a confirmed uniform *master-key convention* — a generic query would guess wrong for at least one module | Hardcode a single flag-key lookup pattern for all 5 | Rejected — reconnaissance couldn't confirm this holds for 4 of 5 modules; guessing wrong silently breaks entitlement for that module |
| `AiCreditLedgerEntry` as one combined ledger (not separate usage + adjustment tables) | Spec requires both automatic future usage debits and manual admin adjustments to share one audit-linked, append-only structure | Two separate tables (`AiUsageRecord` + `AiCreditAdjustment`) | Rejected — an unnecessary split; a signed `delta` column with a nullable actor column cleanly serves both cases in one table, matching this project's general "don't add tables for cases a nullable column already covers" instinct evidenced elsewhere (e.g. `PlatformAuditEvent.support_access_grant_id` nullable rather than a second audit table) |

No speculative abstraction beyond what §12/§13/§16/§19/§20/§21's own spec requirements directly demand.

---

## 40. Technical Unknowns Resolved

| Unknown | Resolution |
|---|---|
| Does `get_current_user()` check session revocation today? | **No** — confirmed via reading `backend/core/auth/dependencies.py` in full (§3.1). Epic 9A does **not** change it (§10.4): tenant suspension is enforced company-scoped instead, and platform sessions use their own new dependency. Documented as an adjacent pre-existing defect (§41). |
| **Is a `Session` tenant-scoped? Can it be invalidated for one tenant without affecting another?** | **No and no — resolved by direct model inspection (§3.1).** `sessions` has no `company_id`; the JWT has no company claim; `User.company_id` is a documented nullable placeholder; company context arrives only as the `{company_id}` path parameter. Therefore session rows cannot express per-tenant invalidation at all, and ADR-6 replaces session revocation with company-scoped access invalidation (§10.2). |
| **Do the business modules currently block a suspended company?** | **No — resolved by inspecting `backend/api/v1/router.py` and `users_roles/dependencies.py` (§3.3).** All five mount `get_current_company_member`, which reads only `CompanyMember.status`, never `Company.status`. Closing this is mandatory Epic 9A work (§10.2 Layer 1). |
| Is "Better Auth" a real library dependency? | **No** — confirmed via `backend/core/auth/interfaces.py`'s own docstring; it's a naming placeholder over a custom JWT implementation (§3.1). |
| Best integration point for entitlement enforcement? | **Mount-level dependency on each entitled module's router** (`require_capability_entitled(...)`, §13.1) — the same place the repository already centralises per-module gating. Not middleware (no middleware convention exists, §3.17), not frontend-only, and **not** only at toggle-mutation time (corrected — that left a Plan-downgrade bypass). |
| **Can the existing frontend `apiClient` singleton safely serve both auth domains?** | **No — resolved by reading `lib/api/client.ts` in full (§3.16).** Transport is constructor-injectable, but the token accessor, refresh lock, token-clearing, and `session-expired` event are hardcoded module-scope tenant calls. Resolved via ADR-11's injected `AuthStrategy` + two configured instances (§23.1). |
| Current feature-toggle persistence model — one master flag or many per module? | **Confirmed heterogeneous**: CRM has exactly one (`feature.crm.enabled`); the other 4 use a generic multi-row `flag_key`/`is_enabled` shape with no single master key. Resolved via the adapter pattern (§13) **plus an explicit default rule, decided here rather than deferred**: if a module exposes no module-grain master toggle, its `ModuleEnablementProvider` returns `enabled = True`, meaning that module has no tenant-level opt-out at module grain and the **Plan ceiling alone governs** its availability. This is deterministic, fails safe for existing tenants (who keep current access, §34), and means no adapter needs to invent a master key that doesn't exist. Per-module fine-grained flags continue to work exactly as they do today, untouched. |
| Do usage counters need row locking/atomic increments? | **No** — §18's design is periodic/batch (one `UPDATE`-or-`INSERT` per company per period from a scheduled computation), not per-request atomic increments, so ordinary transactional writes suffice; no row-locking design is needed. |
| Existing audit transaction semantics? | **Confirmed heterogeneous across 3 tables** (§3.4) — Accounting's flush-then-caller-commits pattern is the only fail-closed precedent and is the one Epic 9A follows (ADR-5). |
| Existing DB-level scheduled-task mechanism for periodic usage computation (§18) or override-expiry sweeps (§16)? | **Not confirmed present** during reconnaissance — no cron/scheduler framework was found. Resolved conservatively: both designs (§16, §18) work correctly via at-read-time checks (`expires_at`, missing-period → `unavailable`) without requiring a scheduler at all for correctness; a scheduler remains an optional Tasks-phase convenience, not a blocking dependency. |
| Suspend/reactivate concurrency mechanism? | **Decided here, not deferred**: `SELECT ... FOR UPDATE` on the `Company` row at the start of both operations (§9.2 step 2, §26). Chosen over an optimistic version check because `Company` has no existing version column (adding one would alter a heavily-used table), because these are rare, low-contention administrative operations where a brief row lock costs nothing, and because pessimistic locking makes the "exactly one transition commits" guarantee (Acceptance Scenario 6) trivially provable in a test. |
| Where is the pre-suspension status stored so reactivation can restore it? | **Resolved**: `companies.pre_suspension_status`, a nullable column added in migration `057`, guarded by a CHECK constraint tying it to `status = 'suspended'` (§9.1, §26, ADR-12). Never inferred from audit history. |
| **Does the existing auth implementation distinguish an authentication event from a token refresh?** | **Yes — resolved by reading `AuthService.login()` and `AuthService.refresh()` (§3.1).** `login()` calls `create_session(...)` (new `Session` row, new `created_at`); `refresh()` calls `rotate_refresh_token(...)` then `create_access_token(session_id=new_record.session_id)`, reusing the existing session and never creating one. `Session.created_at` is therefore an authentication-freshness value that survives refresh unchanged. |
| **Does authentication-freshness need a new JWT claim, a new Session field, or both?** | **Neither.** `Session.created_at` already exists (`BaseModel`, `server_default=func.now()`, immutable after INSERT) and `sid` is already a signed claim surfaced as `CurrentUser.session_id`. One PK lookup at the company-access boundary suffices — no token-format change, no auth-schema migration, no change to `get_current_user()` (§10.2). |
| **Can migration 057 assume no company is already suspended?** | **No — and it must not.** `status='suspended'` records where a company *is*, never where it *was*, so a pre-existing suspended row's restore target is unrecoverable. Resolved via §33.1's preflight: detect and fail loudly with remediation guidance rather than backfill a guess. |

No unresolved unknown here blocks `/sp.tasks` — every item above either has a concrete resolution or an explicitly-scoped, non-blocking Tasks-phase verification step (never a silent assumption).

---

## 41. Out of Scope (Explicit Non-Goals)

Unchanged from, and fully consistent with, spec.md §5/§27 — this plan does not expand Epic 9A into: tenant business-logic redesign; CRM redesign; Installments/Reports implementation; payment gateway/SaaS invoicing/tax; AI provider/OpenClaw integration; unrestricted impersonation; tenant business-record support browsing; mobile apps; microservices/Kubernetes; unrelated ERP refactoring. Also explicitly not touched: the dead `/admin/companies` page/endpoint (§3.9 — documented, not fixed, per spec Risk #3); Accounting's and CRM's already-correct feature-toggle gates (§14 — extended with the ceiling check, never re-authored); the `SUPER_ADMIN`/`super_admin` casing inconsistency in `purchase/router.py` (spec Risk #4 — flagged, not fixed by this Epic).

**Adjacent finding, documented and deliberately not fixed here** (added by the correction pass): `get_current_user()` never checks `Session.is_revoked`, so ordinary tenant logout does not invalidate an in-flight access token before its ~15-minute natural expiry (§3.1). The first draft of this plan proposed fixing it as an Epic 9A prerequisite; the corrected suspension design (§10.2) does not depend on it, so changing that universal hot path is no longer in scope. It is a real pre-existing defect worth its own small remediation, recorded here in the same manner as the `/admin/companies` findings rather than silently absorbed.

**Frontend-wide migration to the canonical tenant-context accessor** (§15) is likewise out of scope: the accessor is introduced and used by new Epic 9A code, while existing modules keep their current direct reads unchanged.

---

## 42. Final Cross-Check / Planning Readiness

- [x] Epic 9A remains based on completed Epic 9 (§2 — `merge-base` verified).
- [x] Constitution v1.2.1 is authoritative (§1 Constitution Check, §2).
- [x] No Specification business decision was changed — every design choice traces to an existing FR/BR/spec section, never contradicts one.
- [x] Platform Admin identity is separate from tenant membership (§5).
- [x] Platform and tenant authorization contexts are separate (§6).
- [x] Platform RBAC is server-authoritative (§8).
- [x] First Platform Owner bootstrap is secure/out-of-band, **and cannot silently succeed without creating an owner** (§7, ADR-8 — non-zero exit on missing/invalid config; no bootstrap migration exists).
- [x] Suspension immediately and durably invalidates access to the suspended tenant, across all five business modules **and** the companies module (§10.2 — closes the §3.3 enforcement gap).
- [x] Suspension causes **no** collateral loss of access to other tenants for multi-tenant users (§10.1–§10.3, ADR-6, cross-tenant test suite §32).
- [x] Reactivation restores the **pre-suspension** status (`active→suspended→active`, `inactive→suspended→inactive`), from an explicitly persisted, CHECK-constrained column — never inferred (§9.1, §9.3, ADR-12).
- [x] Reactivation does not resurrect pre-suspension access, **including via an old refresh credential**: the watermark is compared against `Session.created_at`, which only a genuine login advances — refresh reuses the same session (§10.2, ADR-6, test case B in §32).
- [x] `iat` is never treated as proof of fresh authentication; authentication freshness is server-generated and not client-controllable (§10.2).
- [x] Multi-device behaviour is explicitly specified and per-session deterministic (§10.3.1, test case E).
- [x] Migration `057` refuses to proceed rather than fabricating a lifecycle state if any company is already suspended (§33.1, §26, ADR-12).
- [x] CRM uses the generic entitlement architecture, and `require_crm_enabled` alone is **not** treated as sufficient for runtime access (§35, §13.1).
- [x] Plan Entitlement remains the tenant-toggle ceiling (§13, resolution table).
- [x] Plan Entitlement is enforced at **point of use** on all five modules, not only at toggle mutation — a Plan downgrade takes effect without touching stored toggles (§13.1, §27, ADR-3).
- [x] Existing feature-toggle authorization hardening is planned, scoped to the 3 modules actually confirmed vulnerable (§14, §27), and retained as a secondary guard.
- [x] Canonical tenant context is an explicit accessor contract fronting the unchanged `erp_active_company_id` persistence; new Epic 9A code uses the accessor, existing modules are not refactored (§15, ADR-13).
- [x] Frontend token crossover is structurally impossible: two `ApiClient` instances with injected, domain-specific auth strategies and separate refresh locks (§23.1, ADR-11).
- [x] Platform selected-tenant context is separate (§15, §21, §23).
- [x] Administrative overrides are explicit/audited (§16).
- [x] Quotas and entitlements remain separate concepts (§17).
- [x] AI readiness remains provider-neutral (§19).
- [x] Billing integration remains future-only (§11).
- [x] Audit fail-closed has a concrete transaction design (§20, ADR-5).
- [x] Support access cannot read tenant business records (§21 — structurally, not just by convention).
- [x] No unrestricted impersonation exists anywhere in this design (§21).
- [x] Existing tenants have a safe migration strategy (§33–§34).
- [x] No unnecessary microservices/Kubernetes introduced (§1 Constitution Check, §4).
- [x] Security threat analysis is complete (§28).
- [x] Testing strategy includes real PostgreSQL/live verification, not SQLite-only (§32).
- [x] No unresolved technical blocker remains before `/sp.tasks` (§40 — every unknown now has a concrete resolution; the two previously-vague Tasks-phase deferrals, the module master-toggle rule and the lifecycle locking mechanism, are both decided here).

**Result: this Plan satisfies the repository's Definition of Ready for `/sp.tasks`.**
