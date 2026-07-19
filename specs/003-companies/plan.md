# Implementation Plan: Epic 3 — Companies

**Branch**: `003-companies` | **Date**: 2026-07-15 | **Spec**: [spec.md](./spec.md)
**Status**: Draft — Ready for `/sp.tasks`
**Version**: 1.0.0

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technical Context](#2-technical-context)
3. [Constitution Check](#3-constitution-check)
4. [Architecture Strategy](#4-architecture-strategy)
5. [Module Breakdown](#5-module-breakdown)
6. [Backend Folder Structure](#6-backend-folder-structure)
7. [Frontend Strategy](#7-frontend-strategy)
8. [Frontend Folder Structure](#8-frontend-folder-structure)
9. [Database Strategy](#9-database-strategy)
10. [API Strategy](#10-api-strategy)
11. [Security Strategy](#11-security-strategy)
12. [State Management Strategy](#12-state-management-strategy)
13. [Testing Strategy](#13-testing-strategy)
14. [Implementation Phases](#14-implementation-phases)
15. [Deployment Strategy](#15-deployment-strategy)
16. [Observability](#16-observability)
17. [Risk Assessment](#17-risk-assessment)
18. [Definition of Done](#18-definition-of-done)
19. [Appendix](#19-appendix)

---

## 1. Executive Summary

Epic 3 implements the **Companies module** — the foundational tenant boundary for the entire DevSphere ERP platform. Every future ERP module (Accounting, Inventory, Sales, CRM, HR) will depend on a valid `company_id` to scope its data. This epic establishes that boundary with full lifecycle management, multi-tenant isolation, audit logging, and domain event infrastructure.

The implementation follows the identical structural pattern established in Epic 2 (Auth module): a DDD-aligned, Clean Architecture module under `backend/modules/companies/` with the layers `models → repositories → services → schemas → router`. Frontend follows the Next.js App Router pattern established for Auth, adding a new route group and company context.

**Scope**: Backend API (FastAPI + SQLAlchemy + PostgreSQL), Alembic migration, frontend company pages (Next.js), React Query integration, audit logging, domain event outbox, and full test suite (unit, integration, security, performance).

**Key constraint**: `company_id` isolation is enforced at the service layer on every query. No cross-tenant data leakage is acceptable.

---

## 2. Technical Context

| Dimension | Value |
|-----------|-------|
| **Backend Language** | Python 3.12+ |
| **Backend Framework** | FastAPI |
| **ORM** | SQLAlchemy 2.x (async) |
| **Migrations** | Alembic |
| **Schema Validation** | Pydantic v2 |
| **Frontend Language** | TypeScript 5.x (strict mode) |
| **Frontend Framework** | Next.js (App Router) |
| **UI Library** | shadcn/ui + Tailwind CSS |
| **Server State** | TanStack Query v5 |
| **Form Handling** | React Hook Form + Zod |
| **Database** | PostgreSQL 16 LTS |
| **Auth Integration** | JWT access tokens from Epic 2 (`core/auth/dependencies.py`) |
| **Testing (Backend)** | pytest + pytest-asyncio + httpx |
| **Testing (Frontend)** | Jest + React Testing Library |
| **Containerization** | Docker + Docker Compose |
| **File Storage** | S3-compatible (MinIO in development; AWS S3 / Cloudflare R2 in production) |
| **Performance Targets** | GET company p95 < 200ms; POST company p95 < 1s; list p95 < 500ms |
| **Scale Target** | 1,000,000 company records; 500 concurrent API requests |
| **Deployment (Phase 1)** | Backend: Render; Frontend: Vercel; DB: Neon PostgreSQL |

---

## 3. Constitution Check

All gates reference the project Constitution at `.specify/memory/constitution.md`.

| Gate | Requirement | Status | Notes |
|------|-------------|--------|-------|
| Modular Monolith | Module lives under `backend/modules/companies/` | PASS | Mirrors `modules/auth/` pattern |
| Clean Architecture | API → Service → Repository → DB; no layer bypass | PASS | Enforced by design |
| Repository Pattern | All DB access through `CompanyRepository` / `CompanyAddressRepository` | PASS | No direct ORM calls in service |
| Service Layer | All business logic in `CompanyService` / `CompanyAuditService` | PASS | Router handlers are thin |
| Dependency Injection | `get_company_service()` FastAPI dependency | PASS | Consistent with auth pattern |
| DDD | Company, CompanyAddress as domain entities; domain events defined | PASS | |
| Multi-Tenant Isolation | `company_id` on every dependent table; service-layer WHERE enforcement | PASS | Core requirement |
| UUID Primary Keys | `company_id` is UUID v4 | PASS | Never auto-increment integer |
| Soft Delete | `deleted_at` + `status` field; no hard deletes via API | PASS | |
| Audit Trail | `company_audit_logs` table; immutable; every state change recorded | PASS | |
| Error Handling | Centralized error envelope; module-specific exception types | PASS | |
| Testing Standards | Unit + Integration + Security + Performance test layers | PASS | |
| API Versioning | `/api/v1/companies` | PASS | |
| No Secrets in Code | Logo storage config via environment variables | PASS | |
| SaaS Readiness | `subscription_id` FK placeholder; `COMPANY_LIMIT` config key | PASS | |
| Docker First | All services runnable via `docker compose up` | PASS | |
| Pydantic v2 | All schemas use Pydantic v2 model syntax | PASS | |
| SQLAlchemy 2.x | Mapped column syntax; async session | PASS | |

**Gate Result**: PASS — no violations. Implementation may proceed.

---

## 4. Architecture Strategy

### 4.1 Layered Architecture

The Companies module enforces a strict unidirectional dependency flow:

```
┌──────────────────────────────────────────────┐
│  API Layer (router.py)                        │
│  • HTTP request parsing                       │
│  • Pydantic schema validation                 │
│  • Authentication + Authorization check       │
│  • Delegates to service; formats response     │
└──────────────────┬───────────────────────────┘
                   ↓
┌──────────────────────────────────────────────┐
│  Service Layer (services/)                    │
│  • All business rules and domain logic        │
│  • Orchestrates repositories                  │
│  • Publishes domain events                    │
│  • Records audit log entries                  │
│  • No HTTP types; no SQLAlchemy types         │
└──────────────────┬───────────────────────────┘
                   ↓
┌──────────────────────────────────────────────┐
│  Repository Layer (repositories/)             │
│  • All database interaction via SQLAlchemy    │
│  • No business logic                          │
│  • Returns domain models or raises DataError  │
└──────────────────┬───────────────────────────┘
                   ↓
┌──────────────────────────────────────────────┐
│  Database (PostgreSQL via AsyncSession)        │
│  • companies, company_addresses               │
│  • company_audit_logs, event_outbox           │
└──────────────────────────────────────────────┘
```

**Rules**:
- The router MUST NOT contain business logic. It validates input, calls the service, and returns a Pydantic schema.
- The service MUST NOT import SQLAlchemy types directly. It operates on domain model objects.
- The repository MUST NOT apply business rules. It executes queries and returns model instances.
- Cross-layer imports are prohibited. `router → service → repository` is the only permitted direction.

### 4.2 Module Boundaries

The Companies module is self-contained. It exposes a public interface that other modules can consume:

```
backend/modules/companies/__init__.py
  → exports: CompanyService, get_current_company, require_company_member
```

Other modules MUST NOT import from `modules/companies/repositories/`, `modules/companies/models/`, or `modules/companies/schemas/` directly. They use only the public interface.

The Auth module integration point is `core/auth/dependencies.py`: `get_current_user()` provides the authenticated user. The Companies module builds `get_current_company_member()` on top of this.

### 4.3 Repository Pattern

Each repository inherits from `core/repositories/base.py` (`BaseRepository`). The Companies module defines:

- **`CompanyRepository`**: CRUD for the `companies` table. All tenant-scoped queries include `company_id` in the WHERE clause. The only queries that operate without `company_id` are uniqueness checks (legal name, slug) and SuperAdmin operations.
- **`CompanyAddressRepository`**: CRUD for `company_addresses`. Always scoped by `company_id`.
- **`CompanyAuditLogRepository`**: Append-only writes to `company_audit_logs`. No update or delete methods exist.
- **`EventOutboxRepository`**: Append-only writes to `event_outbox`. Used for domain event delivery.

### 4.4 Service Pattern

Services contain all business logic. The Companies module defines:

- **`CompanyService`**: Orchestrates the full company lifecycle. Creates, updates, activates, deactivates, deletes, restores companies. Enforces all business rules (BR-001 to BR-029). Calls `CompanyAuditService` and `EventService` after each state change.
- **`CompanyAuditService`**: Constructs and persists audit log records. Accepts a before-state and after-state snapshot. Always called within the same transaction as the originating operation.
- **`CompanyLogoService`**: Handles logo upload, MIME validation, S3 storage, URL generation, and previous logo retention scheduling.
- **`CompanySettingsService`**: Validates and persists company settings updates. Enforces the allowed-values registry for each setting key.

### 4.5 Dependency Injection

All services are injected via FastAPI's `Depends()` mechanism. No service instantiates another service or repository directly.

```
Dependency Graph:
  AsyncSession  (core/database/session.py)
       ↓
  CompanyRepository
  CompanyAddressRepository
  CompanyAuditLogRepository
  EventOutboxRepository
       ↓
  CompanyService(company_repo, address_repo, audit_repo, outbox_repo, logo_service)
  CompanyAuditService(audit_repo)
  CompanyLogoService(storage_client)
       ↓
  Router endpoints via get_company_service()
```

### 4.6 Transaction Boundaries

Every state-changing operation executes within a single database transaction. The transaction boundary is managed at the service layer.

**Pattern**:
1. Service method begins: `async with session.begin():`
2. Repository writes execute (company update + audit log + outbox event).
3. Transaction commits atomically.
4. If any step fails, the entire transaction rolls back.
5. No partial state is ever persisted.

The outbox event is written in the same transaction as the state change (Transactional Outbox Pattern). This guarantees that an event is never published for a change that did not persist.

### 4.7 Error Handling

Module-specific exceptions are defined in `modules/companies/exceptions.py`. All exceptions inherit from `core/exceptions/base.py` (`AppException`). The global exception handler in `core/exceptions/handler.py` maps exceptions to HTTP responses.

**Exception hierarchy**:

```
AppException
  └── CompanyException
        ├── CompanyNotFoundError         → 404
        ├── CompanyNameConflictError     → 409
        ├── SlugConflictError            → 409
        ├── SlugImmutableError           → 422
        ├── InvalidStatusTransitionError → 409
        ├── CompanySuspendedError        → 403
        ├── CompanyIncompleteError       → 422
        ├── CompanyPurgedError           → 410
        ├── ActiveSubscriptionError      → 409
        ├── ForceDeleteRequiredError     → 422
        ├── CurrencyChangeWarningError   → 422
        ├── LogoTooLargeError            → 400
        ├── LogoInvalidFormatError       → 400
        └── LogoInvalidContentError      → 400
```

### 4.8 Logging

Structured JSON logging follows the pattern established in `core/logging/setup.py`. Every log entry in the Companies module includes:
- `module: "companies"`
- `company_id`: when available
- `actor_user_id`: when available
- `request_id`: from middleware
- `action`: operation name

No sensitive data (tax numbers, registration numbers) is ever logged. Log at `INFO` for successful operations, `WARNING` for business rule rejections, `ERROR` for unexpected failures.

### 4.9 Validation

Two-stage validation:

1. **Schema validation** (Pydantic v2): Field types, formats, length constraints. Executed automatically by FastAPI before the router handler is called.
2. **Business validation** (Service layer): Uniqueness checks, status transition validity, currency change warnings, fiscal year change frequency. Executed within service methods.

Pydantic validators for specific field types (email, URL, hex color, ISO codes) are defined in `modules/companies/validators.py` and reused across all schemas.

---

## 5. Module Breakdown

### `modules/companies/models/`

| File | Responsibility |
|------|---------------|
| `company.py` | `Company` SQLAlchemy model. All columns from spec Section 10.1. Inherits `BaseModel` (id, created_at, updated_at). |
| `company_address.py` | `CompanyAddress` model. FK to `companies.id`. |
| `company_audit_log.py` | `CompanyAuditLog` model. Append-only. |
| `enums.py` | `CompanyStatus`, `AddressType`, `BusinessType` Python enums. |
| `__init__.py` | Re-exports all models for Alembic discovery. |

### `modules/companies/repositories/`

| File | Responsibility |
|------|---------------|
| `company_repository.py` | `CompanyRepository`. Methods: `create`, `get_by_id`, `get_by_slug`, `get_by_legal_name`, `update`, `soft_delete`, `restore`, `list_all` (SuperAdmin), `exists_by_name`, `exists_by_slug`. |
| `company_address_repository.py` | `CompanyAddressRepository`. Methods: `create`, `get_by_id`, `list_by_company`, `update`, `delete`. Always `WHERE company_id = :company_id`. |
| `company_audit_log_repository.py` | `CompanyAuditLogRepository`. Methods: `create` only. `list_by_company` for reads. No update or delete. |
| `event_outbox_repository.py` | `EventOutboxRepository` (shared with other modules; defined in `core/events/`). Methods: `append`. No delete from application layer. |

### `modules/companies/services/`

| File | Responsibility |
|------|---------------|
| `company_service.py` | `CompanyService`. Implements all lifecycle operations. Enforces business rules. Calls audit and event services. |
| `company_audit_service.py` | `CompanyAuditService`. Accepts operation name, actor, before/after snapshots. Writes to `company_audit_logs` within the same transaction. |
| `company_logo_service.py` | `CompanyLogoService`. Validates file MIME type by magic bytes. Uploads to S3-compatible storage. Returns URL. Schedules previous logo for cleanup. |
| `company_settings_service.py` | `CompanySettingsService`. Validates settings keys and values against the allowed-values registry. Performs partial merge updates. |

### `modules/companies/schemas/`

| File | Responsibility |
|------|---------------|
| `company.py` | `CreateCompanyRequest`, `UpdateCompanyRequest`, `CompanyResponse`, `CompanyDetailResponse`, `CompanyListItem`. |
| `address.py` | `CreateAddressRequest`, `UpdateAddressRequest`, `CompanyAddressResponse`. |
| `settings.py` | `UpdateSettingsRequest`, `CompanySettingsResponse`. |
| `status.py` | `ActivateRequest`, `DeactivateRequest`, `DeleteCompanyRequest`, `RestoreResponse`. |
| `audit.py` | `AuditLogEntryResponse`, `AuditLogListResponse`. |
| `__init__.py` | Re-exports all public schemas. |

### `modules/companies/router.py`

Single router file. Registers all endpoints under `/api/v1/companies`. Uses `APIRouter` with `prefix="/companies"` and `tags=["companies"]`. All endpoint functions are thin: validate (via Pydantic), authorize (via dependency), delegate to service, return response schema.

### `modules/companies/validators.py`

Custom Pydantic field validators:

- `validate_iso_4217_currency(value)` — checks against embedded currency table.
- `validate_iana_timezone(value)` — uses `zoneinfo` standard library.
- `validate_iso_3166_country(value)` — checks against embedded country table.
- `validate_hex_color(value)` — regex match.
- `validate_e164_phone(value)` — regex match.
- `validate_slug_format(value)` — regex match; prohibited patterns.
- `validate_bcp47_language(value)` — checks against supported locales list.

### `modules/companies/events.py`

Defines all domain event payload dataclasses:
`CompanyCreatedEvent`, `CompanyUpdatedEvent`, `CompanyActivatedEvent`, `CompanyDeactivatedEvent`, `CompanySuspendedEvent`, `CompanySuspensionLiftedEvent`, `CompanyDeletedEvent`, `CompanyRestoredEvent`, `CompanyPermanentlyPurgedEvent`, `CompanyLogoUploadedEvent`, `CompanyAdminChangedEvent`.

Each event has a `to_outbox_record()` method that returns an `OutboxRecord` for persistence.

### `modules/companies/exceptions.py`

All module-specific exception classes (see Section 4.7). Each carries an `error_code` string constant matching the error codes in spec Section 12.2.

### `modules/companies/dependencies.py`

FastAPI dependency functions:
- `get_company_service(session: AsyncSession) -> CompanyService`
- `get_current_company_member(user, company_id, service) -> CompanyMemberContext` — validates that the authenticated user is a member of the requested company.
- `require_company_role(roles: list[str])` — role-checking dependency factory.
- `require_company_owner()` — shorthand for Owner-only operations.
- `require_company_admin_or_above()` — shorthand for Owner + Admin.
- `require_super_admin()` — platform-level admin check.

---

## 6. Backend Folder Structure

```text
backend/
├── modules/
│   ├── auth/                          # Epic 2 (existing)
│   └── companies/                     # Epic 3 (new)
│       ├── __init__.py                # Public interface exports
│       ├── router.py                  # FastAPI APIRouter; all endpoints
│       ├── dependencies.py            # DI factories; auth guards
│       ├── exceptions.py              # CompanyException hierarchy
│       ├── validators.py              # Pydantic field validators
│       ├── events.py                  # Domain event payload dataclasses
│       ├── models/
│       │   ├── __init__.py
│       │   ├── company.py             # Company SQLAlchemy model
│       │   ├── company_address.py     # CompanyAddress model
│       │   ├── company_audit_log.py   # CompanyAuditLog model (append-only)
│       │   └── enums.py              # CompanyStatus, AddressType, BusinessType
│       ├── repositories/
│       │   ├── __init__.py
│       │   ├── company_repository.py
│       │   ├── company_address_repository.py
│       │   └── company_audit_log_repository.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── company_service.py
│       │   ├── company_audit_service.py
│       │   ├── company_logo_service.py
│       │   └── company_settings_service.py
│       └── schemas/
│           ├── __init__.py
│           ├── company.py             # CRUD schemas
│           ├── address.py             # Address schemas
│           ├── settings.py            # Settings schemas
│           ├── status.py              # Lifecycle action schemas
│           └── audit.py              # Audit log response schemas
│
├── core/
│   ├── auth/                          # Existing — provides get_current_user()
│   ├── config/
│   │   └── settings.py               # Add: STORAGE_BACKEND, S3_*, COMPANY_LIMIT
│   ├── database/
│   │   └── models/
│   │       └── base_model.py         # Existing BaseModel (id, created_at, updated_at)
│   ├── events/                        # NEW — shared event infrastructure
│   │   ├── __init__.py
│   │   ├── outbox.py                 # OutboxRecord model + EventOutboxRepository
│   │   └── relay.py                  # Background relay: outbox → event bus (stub)
│   ├── storage/                       # NEW — file storage abstraction
│   │   ├── __init__.py
│   │   └── s3_client.py              # S3-compatible storage client
│   ├── exceptions/
│   │   └── base.py                   # Existing AppException base
│   └── repositories/
│       └── base.py                   # Existing BaseRepository
│
├── api/
│   └── v1/
│       └── router.py                 # Register companies router here
│
├── migrations/
│   └── versions/
│       └── 003_companies.py          # Alembic migration: Epic 3 tables
│
└── tests/
    ├── conftest.py                    # Shared fixtures (db, client, factory)
    ├── fixtures/
    │   ├── auth_fixtures.py           # Existing
    │   └── company_fixtures.py        # NEW: Company, Address test factories
    ├── unit/
    │   └── modules/
    │       └── companies/
    │           ├── __init__.py
    │           ├── test_company_service.py
    │           ├── test_company_audit_service.py
    │           ├── test_company_logo_service.py
    │           ├── test_company_settings_service.py
    │           └── test_company_validators.py
    ├── integration/
    │   ├── repositories/
    │   │   └── companies/
    │   │       ├── __init__.py
    │   │       ├── test_company_repository.py
    │   │       └── test_company_address_repository.py
    │   └── api/
    │       └── v1/
    │           └── companies/
    │               ├── __init__.py
    │               ├── test_create_company.py
    │               ├── test_get_company.py
    │               ├── test_update_company.py
    │               ├── test_company_status.py
    │               ├── test_delete_restore.py
    │               ├── test_company_settings.py
    │               ├── test_company_logo.py
    │               ├── test_company_addresses.py
    │               ├── test_audit_log.py
    │               └── test_superadmin_list.py
    ├── security/
    │   └── companies/
    │       ├── test_tenant_isolation.py
    │       ├── test_company_permissions.py
    │       ├── test_sensitive_field_masking.py
    │       ├── test_logo_upload_security.py
    │       └── test_rate_limiting.py
    └── performance/
        └── companies/
            ├── test_company_read_performance.py
            └── test_company_list_performance.py
```

---

## 7. Frontend Strategy

### 7.1 Page Architecture

The Companies module adds a new route group `(companies)` under the existing `(protected)` group. All company pages require an authenticated user (enforced by the `(protected)` layout) and additionally require the user to have company context.

**Page inventory**:

| Route | Page | Purpose |
|-------|------|---------|
| `/companies` | CompanyListPage | List user's companies; create new |
| `/companies/new` | CreateCompanyPage | Multi-step creation wizard |
| `/companies/[id]` | CompanyDetailPage | Read-only company overview |
| `/companies/[id]/settings` | CompanySettingsPage | Tabbed settings management |
| `/companies/[id]/settings/profile` | ProfileTab | Legal name, contact, address |
| `/companies/[id]/settings/regional` | RegionalTab | Currency, timezone, language, fiscal year |
| `/companies/[id]/settings/branding` | BrandingTab | Logo, colors, tagline |
| `/companies/[id]/settings/preferences` | PreferencesTab | Date format, number format, document prefixes |
| `/companies/[id]/audit-log` | CompanyAuditLogPage | Paginated, filterable audit history |
| `/admin/companies` | AdminCompanyListPage | SuperAdmin global company list |

### 7.2 Company Context

A `CompanyContext` is established when the user navigates into a company scope. It holds the active company's summary (id, name, status, currency, timezone) and is used by sidebar navigation, page headers, and any module that needs company metadata.

**`CompanyContext` lifecycle**:
1. On initial page load within `(protected)`, the context is `null`.
2. User selects or is redirected to a company. `GET /api/v1/companies/{id}` is called.
3. Successful response hydrates `CompanyContext` via `setActiveCompany()`.
4. Context is stored in `React.createContext` and the active company ID is persisted in `localStorage` for page refresh continuity.
5. Context is cleared on logout (via `AuthContext` event subscription).

### 7.3 React Query Strategy

All company data operations use TanStack Query v5. Key query definitions:

| Query Key | Endpoint | Stale Time |
|-----------|----------|-----------|
| `['companies']` | `GET /companies` (user's companies) | 5 minutes |
| `['company', id]` | `GET /companies/{id}` | 5 minutes |
| `['company-settings', id]` | embedded in company detail | Invalidated on settings mutation |
| `['company-audit-log', id, filters]` | `GET /companies/{id}/audit-logs` | 1 minute |
| `['admin-companies', filters]` | `GET /admin/companies` | 1 minute |

**Mutation hooks**:
- `useCreateCompany()` → invalidates `['companies']`
- `useUpdateCompany(id)` → invalidates `['company', id]`
- `useUpdateCompanySettings(id)` → invalidates `['company', id]`
- `useActivateCompany(id)` → invalidates `['company', id]`; optimistic status update
- `useDeactivateCompany(id)` → invalidates `['company', id]`; optimistic status update
- `useDeleteCompany(id)` → invalidates `['companies']`; removes `['company', id]` from cache
- `useRestoreCompany(id)` → invalidates `['companies']`
- `useUploadCompanyLogo(id)` → invalidates `['company', id]`
- `useUpdateCompanyAddress(id)` → invalidates `['company', id]`

### 7.4 Company Forms

All forms use React Hook Form with Zod schemas for client-side validation. Zod schemas mirror the backend Pydantic schemas to ensure consistent validation messages.

**Key form components**:

- `CompanyProfileForm` — legal name, trade name, email, phone, website, business type, category.
- `CompanyAddressForm` — street, city, state, postal code, country (with country selector using ISO 3166 list).
- `CompanyRegionalSettingsForm` — currency selector (ISO 4217), timezone selector (IANA), language selector (BCP 47), fiscal year start month.
- `CompanyBrandingForm` — logo upload (with drag-and-drop, preview), hex color pickers, tagline.
- `CompanyPreferencesForm` — date format selector, number format (decimal/thousands separator), document prefix inputs.
- `CompanyCreateWizard` — multi-step form: Step 1 (basic info), Step 2 (regional), Step 3 (branding optional), Step 4 (review & activate).

### 7.5 Caching Strategy

- Company list is cached for 5 minutes. Creating or deleting a company invalidates the list.
- Company detail is cached for 5 minutes. Any mutation on the company invalidates it.
- Audit logs are cached for 1 minute (short TTL due to high write frequency).
- Logo URLs are served from CDN; URL changes trigger React Query invalidation which causes the UI to re-fetch with the new URL.

### 7.6 Optimistic Updates

Used for status toggle operations (activate/deactivate) to provide instant visual feedback:

1. `useActivateCompany` — immediately updates cached company `status` to `active`.
2. `useDeactivateCompany` — immediately updates cached company `status` to `inactive`.
3. If the mutation fails, the optimistic update is rolled back and an error toast is shown.

### 7.7 Error Handling

API errors are parsed from the backend's standard error envelope:

```typescript
// lib/api/errors.ts
interface ApiError {
  code: string;
  message: string;
  details?: FieldError[];
  request_id: string;
}
```

Error handling layers:
1. **Form-level**: `VALIDATION_ERROR` — field errors from `details[]` are mapped to React Hook Form's `setError()`.
2. **Toast notifications**: Non-field errors (`COMPANY_NAME_CONFLICT`, `COMPANY_SUSPENDED`, etc.) surface as toasts.
3. **Page-level error boundaries**: Catch unrecoverable errors and display a fallback UI.
4. **Global query error handler**: Configured in `QueryClient` to handle 401 (redirect to login) and 403 (show permission denied page).

---

## 8. Frontend Folder Structure

```text
frontend/src/
├── app/
│   ├── (protected)/
│   │   ├── layout.tsx                  # Existing auth guard
│   │   ├── dashboard/
│   │   └── (companies)/               # NEW route group
│   │       ├── layout.tsx             # CompanyContext provider; sidebar integration
│   │       ├── companies/
│   │       │   ├── page.tsx           # CompanyListPage
│   │       │   ├── new/
│   │       │   │   └── page.tsx       # CreateCompanyPage (wizard)
│   │       │   └── [id]/
│   │       │       ├── page.tsx       # CompanyDetailPage
│   │       │       ├── settings/
│   │       │       │   ├── page.tsx   # Redirect → /settings/profile
│   │       │       │   ├── profile/
│   │       │       │   │   └── page.tsx
│   │       │       │   ├── regional/
│   │       │       │   │   └── page.tsx
│   │       │       │   ├── branding/
│   │       │       │   │   └── page.tsx
│   │       │       │   └── preferences/
│   │       │       │       └── page.tsx
│   │       │       └── audit-log/
│   │       │           └── page.tsx   # CompanyAuditLogPage
│   │       └── admin/
│   │           └── companies/
│   │               └── page.tsx       # AdminCompanyListPage (SuperAdmin)
│
├── components/
│   └── companies/                     # NEW
│       ├── CompanyCard.tsx
│       ├── CompanyStatusBadge.tsx
│       ├── CompanyCreateWizard.tsx
│       ├── CompanyProfileForm.tsx
│       ├── CompanyAddressForm.tsx
│       ├── CompanyRegionalSettingsForm.tsx
│       ├── CompanyBrandingForm.tsx
│       ├── CompanyPreferencesForm.tsx
│       ├── CompanySettingsTabs.tsx
│       ├── CompanyAuditLogTable.tsx
│       ├── CompanyLogoUpload.tsx
│       ├── CompanyStatusActions.tsx   # Activate / Deactivate / Delete buttons
│       └── AdminCompanyTable.tsx
│
├── contexts/
│   ├── AuthContext.tsx                # Existing
│   └── CompanyContext.tsx             # NEW: active company state + actions
│
├── hooks/
│   ├── useAuth.ts                     # Existing
│   └── companies/                     # NEW
│       ├── useCompanies.ts            # Query: user's company list
│       ├── useCompany.ts              # Query: single company detail
│       ├── useCreateCompany.ts        # Mutation
│       ├── useUpdateCompany.ts        # Mutation
│       ├── useCompanyStatus.ts        # Mutations: activate, deactivate
│       ├── useDeleteCompany.ts        # Mutation: soft delete
│       ├── useRestoreCompany.ts       # Mutation
│       ├── useUploadLogo.ts           # Mutation: multipart upload
│       ├── useCompanySettings.ts      # Mutation: settings update
│       ├── useCompanyAddresses.ts     # Queries + mutations for addresses
│       └── useCompanyAuditLog.ts      # Paginated query
│
├── lib/
│   └── api/
│       ├── client.ts                  # Existing axios/fetch client
│       ├── auth.ts                    # Existing
│       └── companies.ts               # NEW: all company API call functions
│
├── types/
│   ├── auth.ts                        # Existing
│   └── companies.ts                   # NEW: Company, Address, AuditLog TS types
│
└── __tests__/
    └── companies/                     # NEW frontend tests
        ├── CompanyCreateWizard.test.tsx
        ├── CompanyProfileForm.test.tsx
        ├── CompanySettingsTabs.test.tsx
        ├── CompanyStatusActions.test.tsx
        └── hooks/
            ├── useCompany.test.ts
            └── useCreateCompany.test.ts
```

---

## 9. Database Strategy

### 9.1 Table Design

Three primary tables are created in this epic:

**`companies`**: Main entity table. All columns as specified in spec Section 10.1. See model `models/company.py`. Key design decisions:
- `id` is `UUID` generated client-side (Python `uuid.uuid4()`).
- `legal_name` has a case-insensitive unique index using `lower(legal_name)` expression index.
- `status` is a `VARCHAR(20)` with a `CHECK` constraint enforcing allowed values (not a DB-level enum, for forward compatibility with adding new statuses).
- `settings` and `number_format` are `JSONB` columns — no normalization needed for key-value settings at this scale.
- `deleted_at` is indexed for purge job queries.

**`company_addresses`**: Child table. FK to `companies.id` with `ON DELETE RESTRICT` (a company cannot be hard-deleted while it has address records — enforces referential integrity before any future hard-delete pathway).

**`company_audit_logs`**: Append-only audit table. The application database user has `INSERT` and `SELECT` privileges only on this table — no `UPDATE` or `DELETE`. This is enforced at PostgreSQL role level in production.

### 9.2 Event Outbox Table

A new shared `event_outbox` table is introduced in this epic under `core/events/`. This table is used by all future modules.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Event ID |
| `event_type` | VARCHAR(100) | e.g., `CompanyCreated` |
| `aggregate_id` | UUID | `company_id` |
| `aggregate_type` | VARCHAR(50) | `Company` |
| `payload` | JSONB | Full event payload |
| `metadata` | JSONB | correlation_id, actor_id, etc. |
| `published` | BOOLEAN | DEFAULT FALSE — relay sets to TRUE |
| `published_at` | TIMESTAMPTZ | NULL until published |
| `created_at` | TIMESTAMPTZ | NOT NULL |

The background relay process (stub in Phase 1) polls for `published = FALSE` records, delivers them, and marks `published = TRUE`. In production, this becomes a proper relay to a message queue.

### 9.3 UUID Strategy

All primary keys are UUID v4, generated in application code (`core/utils/uuid.py`), not in the database. This allows:
- Pre-generating IDs before insert (useful for event sourcing and idempotency).
- Consistent ID generation across database engines.
- No auto-increment leakage that would enable record enumeration.

### 9.4 Soft Delete Implementation

Soft delete is a dual-field strategy:
- `status = 'deleted'` — used for application-layer filtering.
- `deleted_at TIMESTAMPTZ` — used for purge job scheduling (90-day retention).

Standard repository queries include `WHERE status != 'deleted'` by default. SuperAdmin queries may pass `include_deleted=True` to bypass this filter.

The purge job (scheduled background task) queries `WHERE status = 'deleted' AND deleted_at < NOW() - INTERVAL '90 days'` and performs hard deletes, preceded by emitting `CompanyPermanentlyPurgedEvent`.

### 9.5 Index Strategy

| Index | Table | Columns | Type | Rationale |
|-------|-------|---------|------|-----------|
| PK | `companies` | `id` | BTREE UNIQUE | Primary lookup |
| UQ | `companies` | `lower(legal_name)` | EXPRESSION UNIQUE | Case-insensitive uniqueness |
| UQ | `companies` | `slug` | BTREE UNIQUE | Slug conflict detection |
| IDX | `companies` | `owner_id` | BTREE | Companies-by-owner queries |
| IDX | `companies` | `status` | BTREE | Status-filtered queries |
| IDX | `companies` | `deleted_at` | BTREE | Purge job queries |
| IDX | `companies` | `created_at` | BTREE | Time-ordered listing |
| IDX | `companies` | `subscription_id` | BTREE | Future billing queries |
| PARTIAL UQ | `companies` | `custom_domain` WHERE NOT NULL | BTREE UNIQUE | Future domain routing |
| IDX | `company_addresses` | `(company_id, address_type)` | COMPOSITE | Address lookup |
| IDX | `company_audit_logs` | `(company_id, created_at)` | COMPOSITE | Time-ordered audit queries |
| IDX | `company_audit_logs` | `actor_user_id` | BTREE | Actions-by-user queries |
| IDX | `event_outbox` | `(published, created_at)` | COMPOSITE | Relay polling |

### 9.6 Migration Strategy

Alembic migration file: `migrations/versions/003_companies.py`.

**Migration creates**:
1. `event_outbox` table (shared infrastructure, needed by companies module).
2. `companies` table with all columns, constraints, and indexes.
3. `company_addresses` table with FK to `companies`.
4. `company_audit_logs` table.

**Migration is non-destructive**: No existing tables are modified. The FK from `company_audit_logs` to `companies` uses `ON DELETE RESTRICT` (cannot delete a company with audit records — data integrity enforcement).

**Rollback**: The `downgrade()` function drops `company_audit_logs`, `company_addresses`, `companies`, `event_outbox` in reverse order, respecting FK dependencies.

---

## 10. API Strategy

### 10.1 Versioning

All endpoints are under `/api/v1/`. Version is part of the URL path. When breaking changes require a v2, v1 and v2 can coexist for a deprecation period.

The companies router is registered in `api/v1/router.py`:
```
router.include_router(companies_router, prefix="/companies")
```

### 10.2 Request Validation

FastAPI automatically validates Pydantic schemas. Additional validation:
- Custom Pydantic validators for ISO codes, IANA timezones, E.164 phones (see Section 5, `validators.py`).
- Maximum body size enforced by middleware: 10 MB for standard requests, 5 MB for logo upload.

### 10.3 Response Format

**Standard success response** (wrapped in consistent envelope):

```json
{
  "data": { ... },
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

**Paginated list response**:

```json
{
  "data": [ ... ],
  "meta": {
    "total": 1250,
    "page": 1,
    "page_size": 25,
    "total_pages": 50,
    "request_id": "...",
    "timestamp": "..."
  }
}
```

The `PaginatedResponse` generic is already defined in `core/schemas/pagination.py`. Companies list uses it directly.

### 10.4 Authorization Flow

Every endpoint follows this authorization sequence:

1. `get_current_user()` — validates JWT; returns `AuthenticatedUser`. Returns 401 if missing or invalid.
2. `get_current_company_member(company_id)` — validates the user is a member of the requested company. Returns 403 if not a member. Returns 403 with `COMPANY_SUSPENDED` if company is suspended.
3. `require_company_role([...roles])` — validates the user has the required role within the company. Returns 403 with `FORBIDDEN` if insufficient role.

SuperAdmin endpoints skip step 2 and use `require_super_admin()` instead.

### 10.5 Pagination

All list endpoints support:

| Parameter | Default | Max | Description |
|-----------|---------|-----|-------------|
| `page` | 1 | — | 1-based page number |
| `page_size` | 25 | 100 | Records per page |
| `sort_by` | `created_at` | — | Sortable columns |
| `sort_order` | `desc` | — | `asc` or `desc` |

### 10.6 Filtering and Searching

The SuperAdmin company list (`GET /admin/companies`) supports:

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status value |
| `country` | string | ISO 3166-1 alpha-2 |
| `search` | string | Case-insensitive search on `legal_name` and `slug` |
| `include_deleted` | boolean | Include `deleted` status records |

The audit log endpoint (`GET /companies/{id}/audit-logs`) supports:

| Parameter | Type | Description |
|-----------|------|-------------|
| `action` | string | Filter by action constant |
| `actor_id` | UUID | Filter by user |
| `date_from` | datetime | ISO 8601 UTC |
| `date_to` | datetime | ISO 8601 UTC |

---

## 11. Security Strategy

### 11.1 Authentication

All company endpoints require a valid JWT access token from Epic 2's auth system. The `get_current_user()` dependency validates the token signature, expiry, and user existence on every request. No company operation is possible without a valid session.

### 11.2 Authorization

Role-based authorization uses the company membership model. The user's role within the specific company is checked — not a global role. A user who is `admin` in Company A has no privileges in Company B.

Role hierarchy enforcement:
- Roles are stored in the `company_members` table (managed by Epic 4 — Users).
- In Phase 1 (before Epic 4), the company `owner_id` FK is used. The creating user is always the Owner. Until the Users/RBAC module is built, only Owner-level operations are enforced.
- The dependency system is designed to accept the full role list once the `company_members` table exists; no structural change to the Companies module is required.

### 11.3 Tenant Isolation

`company_id` enforcement is the single most critical security control in this module.

**Implementation rules**:
1. The `company_id` is NEVER accepted as a query parameter or request body field from the client in standard endpoints. It is always extracted from the authenticated JWT context or the URL path parameter (which is validated against the user's membership).
2. Every repository method that retrieves company-scoped data accepts `company_id` as a mandatory parameter.
3. A company member attempting to access a different company's data by manipulating the `company_id` in the URL will fail at the `get_current_company_member()` dependency — their membership in the requested company will not be found.
4. The SuperAdmin exception: global list and admin operations explicitly bypass the membership check. SuperAdmin status is validated independently via `require_super_admin()`.

**Defense in depth** (future):
- PostgreSQL Row Level Security (RLS) policies will be added as a secondary enforcement layer in Epic 7, after the application-layer enforcement is verified in security tests.

### 11.4 Input Validation

- Pydantic v2 validators reject malformed inputs before they reach the service layer.
- SQL injection is prevented by SQLAlchemy's parameterized queries — no raw SQL string interpolation.
- Logo upload: MIME type is validated by inspecting file magic bytes using the `python-magic` library. Extension-only validation is not sufficient and is not used.
- Logo filename is sanitized and replaced with a system-generated UUID-based name to prevent path traversal.

### 11.5 Audit Logging

Every state-changing operation writes an immutable audit record (see spec Section 13). The audit log table is protected at the database role level: the application user has `INSERT` and `SELECT` only — no `UPDATE` or `DELETE` on `company_audit_logs`.

### 11.6 Rate Limiting

Rate limiting is implemented using `slowapi` (existing from Epic 2). Limits for company endpoints:

| Endpoint Pattern | Limit | Window |
|-----------------|-------|--------|
| `POST /companies` | 10/hour | Per user |
| `PATCH /companies/{id}` | 60/hour | Per user |
| `POST /companies/{id}/logo` | 10/hour | Per user |
| `GET /companies*` | 300/minute | Per user |

### 11.7 Sensitive Data Handling

- Tax number and registration number are masked in API responses for roles other than `owner`, `admin`, and `accountant`. The masking is applied in the Pydantic response schema using a field serializer that checks the requester's role.
- No sensitive fields are written to application logs.
- Logo files are stored in object storage, not the database. URLs are pre-signed for time-limited access in production.
- The `settings` JSONB field MUST NOT store secrets. If future integration tokens are needed, they go in a separate encrypted secrets table.

---

## 12. State Management Strategy

### 12.1 React Query Configuration

A shared `QueryClient` is configured in `frontend/src/lib/api/queryClient.ts` with:
- `staleTime: 5 * 60 * 1000` (5 minutes default)
- `gcTime: 10 * 60 * 1000` (10 minutes garbage collection)
- `retry: 1` (one automatic retry on network errors)
- Global `onError` handler: 401 → logout; 403 → redirect to access denied page.

### 12.2 Company Context State

`CompanyContext` holds:

```typescript
interface CompanyContextValue {
  activeCompany: CompanySummary | null;
  setActiveCompany: (company: CompanySummary) => void;
  clearActiveCompany: () => void;
  isLoading: boolean;
}
```

`CompanySummary` is a lightweight type containing only the fields needed by the shell UI: `id`, `legal_name`, `slug`, `status`, `default_currency`, `default_timezone`, `logo_url`, `brand_color_primary`.

The full company detail (for settings pages) is fetched on demand via `useCompany(id)` and cached by TanStack Query.

### 12.3 Cache Invalidation

| Trigger | Invalidates |
|---------|------------|
| Company created | `['companies']` |
| Company updated (any field) | `['company', id]` |
| Company status changed | `['company', id]`, `['companies']` |
| Company deleted | `['companies']`, remove `['company', id]` |
| Logo uploaded | `['company', id]` |
| Address added/updated/removed | `['company', id]` |
| Settings updated | `['company', id]` |

### 12.4 Optimistic Updates

Implemented for status toggle operations using TanStack Query's `onMutate`, `onError`, `onSettled` callbacks:

1. `onMutate`: snapshot previous cache value; write optimistic new value.
2. `onError`: restore snapshot (rollback).
3. `onSettled`: invalidate query to ensure server state is reflected.

---

## 13. Testing Strategy

### 13.1 Unit Tests (Backend)

**Target**: Service layer and validators. All external dependencies (repositories, storage) are mocked.

| Test File | Coverage Focus |
|-----------|---------------|
| `test_company_service.py` | Create, update, activate, deactivate, delete, restore logic; BR enforcement |
| `test_company_audit_service.py` | Audit record construction; before/after state snapshot accuracy |
| `test_company_logo_service.py` | MIME type validation; S3 upload mocking; URL generation |
| `test_company_settings_service.py` | Settings validation; partial merge; allowed-values enforcement |
| `test_company_validators.py` | Each validator function with valid and invalid inputs |

**Coverage requirement**: 90% branch coverage on all service and validator code.

### 13.2 Repository Tests (Integration)

**Target**: Repository methods against a real test database (PostgreSQL in Docker).

| Test File | Coverage Focus |
|-----------|---------------|
| `test_company_repository.py` | CRUD, uniqueness constraints, soft delete filter, slug lookup |
| `test_company_address_repository.py` | CRUD, company scoping |

**Test database**: Spun up via `docker compose --profile test up` using a dedicated `test_db` service. Migrations applied via `alembic upgrade head` before test run.

### 13.3 API Integration Tests

**Target**: Full HTTP request/response cycle through FastAPI test client.

Coverage per test file:
- `test_create_company.py`: Valid creation, name conflict, slug conflict, rate limit, validation errors.
- `test_get_company.py`: Successful retrieval, 404, cross-tenant access rejected.
- `test_update_company.py`: Partial update, role-based rejection, currency change warning.
- `test_company_status.py`: All valid transitions, all invalid transitions, suspension rules.
- `test_delete_restore.py`: Soft delete, restore within window, restore after 90 days.
- `test_company_settings.py`: Settings update, invalid setting key, partial merge.
- `test_company_logo.py`: Valid upload, too large, invalid format, bad MIME content.
- `test_company_addresses.py`: CRUD for addresses, company scoping.
- `test_audit_log.py`: Audit records created for each action; pagination; filtering.
- `test_superadmin_list.py`: Global list, status filter, search, non-superadmin rejection.

### 13.4 Security Tests

| Test File | Coverage Focus |
|-----------|---------------|
| `test_tenant_isolation.py` | User from Company A cannot read/write Company B data |
| `test_company_permissions.py` | Each role vs each endpoint; correct allow/deny |
| `test_sensitive_field_masking.py` | Tax number, registration number masked for non-owner/admin |
| `test_logo_upload_security.py` | SVG with XSS payload; mismatched MIME; path traversal filename |
| `test_rate_limiting.py` | Creation rate limit; logo upload rate limit |

### 13.5 Performance Tests

| Test File | Coverage Focus |
|-----------|---------------|
| `test_company_read_performance.py` | GET company detail < 200ms p95 with 10,000 records |
| `test_company_list_performance.py` | List 25 records < 500ms p95 |

Performance tests use `pytest-benchmark` and run against the test database pre-seeded with 10,000 company records.

### 13.6 Frontend Tests

| Test File | Coverage Focus |
|-----------|---------------|
| `CompanyCreateWizard.test.tsx` | Step navigation, validation, submit |
| `CompanyProfileForm.test.tsx` | Field validation, error display, successful submit |
| `CompanySettingsTabs.test.tsx` | Tab navigation, form state isolation |
| `CompanyStatusActions.test.tsx` | Activate/deactivate confirmation dialogs |
| `useCompany.test.ts` | Query hook data fetching, caching, error states |
| `useCreateCompany.test.ts` | Mutation hook success, error, cache invalidation |

Framework: Jest + React Testing Library. API calls are mocked with `msw` (Mock Service Worker).

### 13.7 Regression Tests

A regression test suite in `tests/integration/api/v1/companies/` captures all known bug scenarios found during QA. Each regression test is tagged with a reference to the issue that caused it.

---

## 14. Implementation Phases

### Phase 1: Foundation and Infrastructure

**Purpose**: Establish all shared infrastructure needed by the companies module before writing any company-specific code.

**Deliverables**:
- `core/events/` package: `OutboxRecord` model, `EventOutboxRepository`, outbox relay stub.
- `core/storage/` package: `StorageClient` abstract base, `S3StorageClient` implementation, MinIO configuration for local development.
- `core/config/settings.py` updated with: `STORAGE_BACKEND`, `S3_BUCKET`, `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `COMPANY_LIMIT` config keys.
- `docker-compose.yml` updated with MinIO service for local logo storage.
- `.env.example` updated with new storage variables.

**Dependencies**: Epic 2 (Auth) completed. PostgreSQL + Docker Compose running.

**Checkpoint**: `core/events/outbox.py` and `core/storage/s3_client.py` pass unit tests. MinIO accessible from backend container.

**Parallelization**: Storage client and event outbox infrastructure can be developed in parallel.

---

### Phase 2: Database Models and Migration

**Purpose**: Define all SQLAlchemy models and create the Alembic migration.

**Deliverables**:
- `modules/companies/models/enums.py` — `CompanyStatus`, `AddressType`, `BusinessType`.
- `modules/companies/models/company.py` — `Company` SQLAlchemy model with all columns.
- `modules/companies/models/company_address.py` — `CompanyAddress` model.
- `modules/companies/models/company_audit_log.py` — `CompanyAuditLog` model.
- `migrations/versions/003_companies.py` — creates all four tables with indexes and constraints.
- Migration tested: `alembic upgrade head` and `alembic downgrade -1` complete without error.

**Dependencies**: Phase 1 complete. `event_outbox` model defined.

**Checkpoint**: `alembic upgrade head` succeeds on clean database. All tables, indexes, and constraints exist as specified. `alembic downgrade -1` cleanly removes all tables.

---

### Phase 3: Validators and Exceptions

**Purpose**: Define all validation logic and exception types before service layer.

**Deliverables**:
- `modules/companies/validators.py` — all 7 field validator functions.
- `modules/companies/exceptions.py` — full exception hierarchy (14 exception classes).
- Unit tests for all validators: valid and invalid input coverage.
- Unit tests for exception instantiation and `error_code` attributes.

**Dependencies**: Phase 2 complete.

**Checkpoint**: `pytest tests/unit/modules/companies/test_company_validators.py` passes with 100% coverage.

**Parallelization**: Validators and exceptions can be developed simultaneously.

---

### Phase 4: Schemas

**Purpose**: Define all Pydantic v2 request and response schemas.

**Deliverables**:
- `modules/companies/schemas/company.py` — `CreateCompanyRequest`, `UpdateCompanyRequest`, `CompanyResponse`, `CompanyDetailResponse`, `CompanyListItem`.
- `modules/companies/schemas/address.py` — address schemas.
- `modules/companies/schemas/settings.py` — settings schemas.
- `modules/companies/schemas/status.py` — lifecycle action schemas.
- `modules/companies/schemas/audit.py` — audit log response schemas.
- Pydantic validators reference `validators.py` functions.
- Schema-level unit tests for required field enforcement and validator invocation.

**Dependencies**: Phase 3 complete (validators, exceptions).

**Checkpoint**: All schemas instantiate correctly with valid data. Invalid data raises `ValidationError` with correct field names and messages.

---

### Phase 5: Repositories

**Purpose**: Implement all data access layer components.

**Deliverables**:
- `modules/companies/repositories/company_repository.py` — full `CompanyRepository`.
- `modules/companies/repositories/company_address_repository.py` — `CompanyAddressRepository`.
- `modules/companies/repositories/company_audit_log_repository.py` — `CompanyAuditLogRepository` (append-only).
- Integration tests against test database for all repository methods.

**Dependencies**: Phase 2 (models), Phase 3 (exceptions). Test database running.

**Checkpoint**: All repository integration tests pass. Uniqueness constraints verified (duplicate name raises `IntegrityError`). Soft-delete filter verified (deleted companies not returned by default).

---

### Phase 6: Services

**Purpose**: Implement all business logic.

**Deliverables**:
- `modules/companies/services/company_service.py` — full `CompanyService` with all lifecycle methods.
- `modules/companies/services/company_audit_service.py` — audit record creation.
- `modules/companies/services/company_logo_service.py` — logo upload and MIME validation.
- `modules/companies/services/company_settings_service.py` — settings management.
- `modules/companies/events.py` — all domain event payload classes.
- Unit tests for all service methods with mocked repositories.

**Dependencies**: Phase 4 (schemas), Phase 5 (repositories).

**Checkpoint**: All service unit tests pass with 90%+ branch coverage. Business rules BR-001 through BR-029 each have at least one test asserting correct enforcement.

---

### Phase 7: API Router and Dependencies

**Purpose**: Wire the HTTP layer.

**Deliverables**:
- `modules/companies/dependencies.py` — all DI factories and auth guard functions.
- `modules/companies/router.py` — all 14 endpoints wired to service methods.
- `modules/companies/__init__.py` — public interface exports.
- `api/v1/router.py` updated to include companies router.
- Full API integration test suite.

**Dependencies**: Phase 6 complete.

**Checkpoint**: All API integration tests pass. `GET /api/v1/companies/{id}` returns 404 for non-existent company, 403 for cross-tenant access, 200 for valid member. All CRUD operations end-to-end verified.

---

### Phase 8: Security and Rate Limiting

**Purpose**: Harden the module against security threats.

**Deliverables**:
- Rate limiting decorators applied to creation and logo upload endpoints.
- Sensitive field masking applied in response schemas (role-based field serialization).
- Logo MIME type validation confirmed against magic bytes (python-magic integration).
- Database role permissions verified: `INSERT`/`SELECT` only on `company_audit_logs`.
- Full security test suite passing.

**Dependencies**: Phase 7 complete.

**Checkpoint**: All security tests pass. `test_tenant_isolation.py` passes (Company A user cannot access Company B). `test_sensitive_field_masking.py` passes. `test_logo_upload_security.py` rejects SVG with script content.

---

### Phase 9: Frontend — API Client and Types

**Purpose**: Build the frontend data layer before UI components.

**Deliverables**:
- `frontend/src/types/companies.ts` — all TypeScript type definitions matching backend schemas.
- `frontend/src/lib/api/companies.ts` — all API call functions.
- `frontend/src/hooks/companies/` — all React Query hooks.
- `frontend/src/contexts/CompanyContext.tsx` — active company state management.
- Hook-level unit tests with msw mocking.

**Dependencies**: Phase 7 complete (API endpoints available).

**Checkpoint**: All hook tests pass. TypeScript compilation passes with strict mode. API function return types match backend response schemas.

**Parallelization**: Frontend work in Phases 9–11 can begin as soon as Phase 7 API is complete and can run in parallel with Phase 8.

---

### Phase 10: Frontend — Pages and Components

**Purpose**: Build all company UI pages and components.

**Deliverables**:
- All company route pages (list, create wizard, detail, settings tabs, audit log).
- All company form components.
- Company status badge and action components.
- `CompanyContext` wired into the `(companies)` route group layout.
- Sidebar navigation updated with Companies section.

**Dependencies**: Phase 9 complete.

**Checkpoint**: Manual walkthrough of full user flow: create company → complete settings → view audit log → deactivate → reactivate. No console errors. Forms validate correctly. Optimistic updates work on status toggle.

---

### Phase 11: Frontend Tests

**Purpose**: Automated frontend test coverage.

**Deliverables**:
- Component tests for all major components.
- Hook tests for all query and mutation hooks.
- Form validation tests.

**Dependencies**: Phase 10 complete.

**Checkpoint**: `npm test -- --coverage` passes with 80%+ coverage on company components and hooks.

---

### Phase 12: Performance Tests and Load Validation

**Purpose**: Validate performance against NFR targets with realistic data volumes.

**Deliverables**:
- Test database seeded with 10,000 company records.
- Performance tests pass: GET < 200ms, list < 500ms.
- Index usage verified via `EXPLAIN ANALYZE` on key queries.

**Dependencies**: Phase 7 complete.

**Checkpoint**: All performance benchmarks within spec NFR targets. No missing indexes on hot query paths.

---

### Phase 13: Documentation and Deployment Validation

**Purpose**: Complete all documentation and verify Docker deployment.

**Deliverables**:
- `specs/003-companies/quickstart.md` — how to run the companies module locally.
- `docs/api/companies.md` — developer-facing API reference.
- Docker Compose tested: `docker compose up` starts all services cleanly.
- Alembic migration runs cleanly in Docker container.
- Environment variable documentation in `.env.example`.
- CLAUDE.md updated with Epic 3 completion and new technologies.

**Dependencies**: Phases 8, 11 complete.

**Checkpoint**: Fresh `docker compose up` from clean state; `alembic upgrade head`; all integration tests pass inside containers. No hardcoded values; all configuration via environment variables.

---

## 15. Deployment Strategy

### 15.1 Docker Configuration

The companies module runs within the existing backend container. No new service is required. The following additions are made to `docker-compose.yml`:

- `minio` service: S3-compatible local object storage for logo files.
  - Image: `minio/minio:latest`
  - Port: `9000` (API), `9001` (console)
  - Volume: `minio_data:/data`
  - Startup command: `server /data --console-address :9001`

The `backend` service environment is updated with:
- `STORAGE_BACKEND=s3`
- `S3_ENDPOINT=http://minio:9000`
- `S3_BUCKET=company-assets`
- `S3_ACCESS_KEY=` (from `.env`)
- `S3_SECRET_KEY=` (from `.env`)

### 15.2 Environment Variables

New variables added to `.env.example`:

```
# Company Module — File Storage
STORAGE_BACKEND=s3
S3_ENDPOINT=http://minio:9000
S3_BUCKET=company-assets
S3_ACCESS_KEY=your_minio_access_key
S3_SECRET_KEY=your_minio_secret_key
S3_REGION=us-east-1

# Company Module — Business Configuration
COMPANY_LIMIT=unlimited
COMPANY_LOGO_MAX_BYTES=5242880
COMPANY_DELETION_RETENTION_DAYS=90
LOGO_RETENTION_DAYS=30
```

Production environment uses Cloudflare R2 or AWS S3 values for `S3_ENDPOINT` and credentials.

### 15.3 Database Migration

Migration deployment sequence:

1. Backend Docker container starts.
2. Entrypoint script runs: `alembic upgrade head` before starting FastAPI.
3. If migration fails, container exits with non-zero code; orchestrator does not start the app.
4. Migration is idempotent — running `alembic upgrade head` multiple times is safe (no-op if already applied).

### 15.4 Health Checks

The existing `/api/health` endpoint returns 200 when the database is reachable. No changes needed. The migration is complete before the health check is reachable.

Additional check: if `STORAGE_BACKEND=s3`, the health endpoint verifies connectivity to the S3 endpoint and logs a warning (not a failure) if unavailable, to prevent a storage outage from taking down the entire API.

### 15.5 Rollback Strategy

If Epic 3 deployment fails:

1. **Application rollback**: Redeploy the previous Docker image (Epic 2 tag).
2. **Database rollback**: Run `alembic downgrade -1` which drops `company_audit_logs`, `company_addresses`, `companies`, `event_outbox` in reverse dependency order.
3. **Storage rollback**: No action required — MinIO data is in a volume; it can be retained or cleared independently.

Rollback is only safe if no other modules have taken a FK dependency on `companies.id`. Since Epic 3 is the first module to create the companies table, rollback is clean.

---

## 16. Observability

### 16.1 Logging

All log entries use the structured JSON format from `core/logging/setup.py`. Companies module adds a `module: "companies"` field to all log records.

| Event | Level | Fields |
|-------|-------|--------|
| Company created | INFO | `company_id`, `legal_name`, `owner_id`, `slug` |
| Company updated | INFO | `company_id`, `changed_fields`, `actor_id` |
| Status transition | INFO | `company_id`, `from_status`, `to_status`, `actor_id` |
| Soft delete | WARNING | `company_id`, `reason`, `actor_id` |
| Restore | INFO | `company_id`, `actor_id` |
| Logo upload | INFO | `company_id`, `file_size`, `mime_type` |
| Authorization failure | WARNING | `company_id`, `actor_id`, `endpoint`, `required_role` |
| Business rule violation | WARNING | `company_id`, `rule`, `error_code` |
| Unexpected error | ERROR | Full exception + traceback |

### 16.2 Metrics

The following metrics are collected via the existing middleware and should be tracked in the production monitoring dashboard:

- `companies_created_total` — counter
- `companies_deleted_total` — counter
- `company_status_transition_total` — counter, labels: `from_status`, `to_status`
- `company_api_request_duration_seconds` — histogram by endpoint
- `company_logo_upload_bytes` — histogram
- `company_audit_log_entries_total` — counter

### 16.3 Audit

The `company_audit_logs` table is the authoritative audit record. It is:
- Queryable via `GET /api/v1/companies/{id}/audit-logs`.
- Retained for 7 years per spec NFR-024.
- Not included in standard log aggregation (it is a database table, not a log stream).

### 16.4 Tracing

Request ID middleware (`core/middleware/request_id.py`) assigns a UUID to every request. This `request_id` is:
- Included in every structured log entry.
- Returned in `X-Request-ID` response header.
- Stored in `company_audit_logs.request_id`.
- Stored in `event_outbox.metadata.request_id`.

This allows full traceability from an API call through logs, audit records, and domain events using a single ID.

---

## 17. Risk Assessment

### 17.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Concurrent company creation race condition (same legal name) | Medium | High | Database-level unique constraint is the final enforcement. `IntegrityError` is caught and re-raised as `CompanyNameConflictError`. Optimistic locking not required — DB constraint is sufficient. |
| S3-compatible storage unavailable in development | Medium | Medium | MinIO in Docker Compose is the local solution. If MinIO fails, logo upload returns a service unavailable error — it does not block company creation (logo is optional). |
| Alembic migration conflict with future epics | Low | High | Migration uses a sequential numbering convention (`003_`). All future migrations must reference Epic 3's revision as a parent. Clear documentation required. |
| company_id isolation bypass via URL manipulation | Low | Critical | Mitigated by `get_current_company_member()` dependency that validates membership. Security tests confirm this. RLS as future defense-in-depth layer. |
| JSONB `settings` field schema drift | Medium | Low | Settings updates go through `CompanySettingsService` which validates against an allowed-values registry. Unknown keys are rejected. |

### 17.2 Business Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Slug immutability causes branding mismatch | Low | Medium | Spec BR-008 clearly defines slug immutability. Company name changes do not affect slug. User documentation must explain this. |
| Currency change on existing transactions | Medium | High | `CURRENCY_CHANGE_WARNING` error requires explicit `confirm_currency_change: true`. Historical transactions are not retroactively changed. |
| 90-day purge deletes a company a user wanted to restore | Low | High | Recovery via database backup (PITR). The 90-day window is communicated clearly in the UI when deletion is initiated. |

### 17.3 Migration Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Future FK dependencies break downgrade | Medium | Medium | Epic 3 migration downgrade must run before any module that FKs to `companies.id` is deployed. Rollback window is limited to before Epic 4 deployment. |
| `event_outbox` table conflicts with future event infrastructure | Low | Medium | Outbox table design is generic and matches standard patterns. If a different event infrastructure is adopted (e.g., Kafka outbox pattern), the relay strategy changes but the table is unchanged. |

### 17.4 Security Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| SVG logo with XSS payload | Medium | High | `python-magic` validates file content type. SVG uploads are accepted only if content is valid SVG XML. Content Security Policy (CSP) headers prevent inline script execution even if a malicious SVG bypasses upload validation. |
| Sensitive field logging exposure | Low | High | No sensitive fields (tax number, registration number) appear in log statements. Code review checklist item. |
| Rate limit bypass via IP rotation | Medium | Low | Rate limiting is per-user (authenticated), not per-IP. Token required; IP rotation does not bypass limits. |

---

## 18. Definition of Done

Epic 3 is complete when ALL of the following criteria are met:

### Backend

- [ ] Alembic migration `003_companies.py` runs cleanly (`upgrade` and `downgrade`) on a fresh PostgreSQL instance.
- [ ] All 14 API endpoints return correct responses for happy-path and error-path scenarios.
- [ ] All acceptance criteria AC-001 through AC-012 pass as automated tests.
- [ ] Service layer unit tests: 90%+ branch coverage.
- [ ] All security tests pass (tenant isolation, permission matrix, sensitive masking, logo security, rate limiting).
- [ ] Performance tests pass: GET < 200ms p95, list < 500ms p95 with 10,000 records.
- [ ] Business rules BR-001 through BR-029 are each covered by at least one failing test that proves enforcement.
- [ ] All domain events (11 event types) are written to the outbox table on correct triggers.
- [ ] All audit log events (16 action types) are written with correct before/after state on correct triggers.
- [ ] Audit log table is confirmed immutable: no `UPDATE` or `DELETE` via API returns success.
- [ ] Logo upload rejects files > 5 MB, unsupported formats, and mismatched MIME content.
- [ ] No sensitive data (tax numbers, registration numbers) appears in application logs.
- [ ] No hard-coded secrets; all configuration via environment variables.

### Frontend

- [ ] All company pages render without errors in development and production builds.
- [ ] Company creation wizard completes end-to-end with a newly created company visible in the company list.
- [ ] All form validations match backend validation rules.
- [ ] Optimistic updates work correctly for status toggle operations.
- [ ] Error messages display correctly for all defined error codes.
- [ ] Frontend tests pass with 80%+ coverage on company components and hooks.
- [ ] TypeScript compiles with zero errors in strict mode.

### Infrastructure

- [ ] `docker compose up` starts all services cleanly from a fresh state.
- [ ] MinIO is accessible and logo upload works end-to-end in Docker environment.
- [ ] `.env.example` documents all new environment variables.

### Documentation

- [ ] `specs/003-companies/spec.md` is the approved, current SSOT.
- [ ] `specs/003-companies/plan.md` (this file) accurately reflects the implementation.
- [ ] `CLAUDE.md` updated to reflect Epic 3 completion.
- [ ] Audit log retention policy (7 years) documented in operational runbook.

---

## 19. Appendix

### 19.1 Coding Conventions

**Python (Backend)**:
- All files follow PEP 8. Enforced by `ruff` (linter) and `black` (formatter).
- Type hints are mandatory on all function signatures and return types.
- `async def` for all FastAPI route handlers and service methods that touch I/O.
- Class names: `PascalCase`. Function names: `snake_case`. Constants: `UPPER_SNAKE_CASE`.
- Pydantic v2 models use `model_config = ConfigDict(...)` syntax (not `class Config`).
- SQLAlchemy 2.x uses `Mapped[type]` and `mapped_column()` syntax.

**TypeScript (Frontend)**:
- `strict: true` in `tsconfig.json` — no implicit `any`.
- Named exports preferred over default exports for components and hooks.
- Interface names: `PascalCase` prefixed with `I` for interfaces, or just `PascalCase` for types.
- Hook names: `usePascalCase`.
- File names: `PascalCase.tsx` for components, `camelCase.ts` for utilities/hooks.
- No `console.log` in committed code; use structured logger for debug output.

### 19.2 Naming Conventions

| Layer | Naming Pattern | Example |
|-------|---------------|---------|
| SQLAlchemy Model | `PascalCase` | `Company`, `CompanyAddress` |
| Repository | `PascalCase + Repository` | `CompanyRepository` |
| Service | `PascalCase + Service` | `CompanyService` |
| Pydantic Schema (Request) | `PascalCase + Request` | `CreateCompanyRequest` |
| Pydantic Schema (Response) | `PascalCase + Response` | `CompanyDetailResponse` |
| Domain Event | `PascalCase + Event` | `CompanyCreatedEvent` |
| Exception | `PascalCase + Error` | `CompanyNotFoundError` |
| API Route Prefix | `/api/v1/{plural}` | `/api/v1/companies` |
| Alembic Migration | `{NNN}_{feature_name}.py` | `003_companies.py` |
| DB Table | `snake_case_plural` | `companies`, `company_addresses` |
| DB Index | `ix_{table}_{column}` | `ix_companies_status` |
| DB Unique Constraint | `uq_{table}_{column}` | `uq_companies_slug` |
| React Component | `PascalCase.tsx` | `CompanyProfileForm.tsx` |
| React Hook | `use{PascalCase}.ts` | `useCreateCompany.ts` |
| Query Key | `['{entity}', id?, filters?]` | `['company', id]` |

### 19.3 Reference Architecture Decisions

The following architectural decisions were made during planning. Document with `/sp.adr` if not already recorded:

| Decision | Rationale |
|----------|-----------|
| Shared DB + company_id row isolation (vs. schema-per-tenant) | Balances operational simplicity and cost. Schema-per-tenant adds migration complexity for thousands of tenants. RLS will be added as defense-in-depth in a future epic. |
| UUID v4 generated in application code (vs. DB-generated) | Enables event sourcing patterns, pre-generation before insert, and ID consistency across database engines. |
| `status` as VARCHAR with CHECK constraint (vs. DB enum type) | PostgreSQL enum types require DDL to add new values. VARCHAR + CHECK can be extended via migration without DDL on existing rows. |
| Transactional Outbox Pattern for domain events | Guarantees no event is published without a corresponding committed state change. Simpler than distributed transactions or eventual consistency mechanisms. |
| `settings` as JSONB (vs. separate settings table) | Company settings are read frequently as a single unit. JSONB avoids N+1 queries and simplifies partial updates. Schema is validated at the application layer. |
| Logo stored in S3-compatible storage (vs. DB BLOB) | Binary blobs in PostgreSQL degrade performance and backup complexity. S3 objects scale horizontally and integrate with CDN. |
| Audit log as a separate append-only table | Keeps audit data immutable and queryable independently of the main `companies` table. Future archival to cold storage is straightforward. |

📋 **Architectural decision detected**: Shared Database / company_id row isolation strategy — Document reasoning and tradeoffs? Run `/sp.adr shared-db-row-isolation`

📋 **Architectural decision detected**: Transactional Outbox Pattern for domain events — Document reasoning and tradeoffs? Run `/sp.adr transactional-outbox-pattern`

📋 **Architectural decision detected**: S3-compatible object storage for binary assets — Document reasoning and tradeoffs? Run `/sp.adr s3-object-storage`

---

### 19.4 Project Documentation Structure

```text
specs/003-companies/
├── spec.md                   # SSOT — business requirements (THIS EPIC)
├── plan.md                   # This file — implementation blueprint
├── research.md               # Phase 0 research findings (auto-generated by /sp.plan)
├── data-model.md             # Entity diagram and field reference
├── quickstart.md             # Developer setup guide
├── contracts/                # OpenAPI schema fragments
└── tasks.md                  # Atomic implementation tasks (generated by /sp.tasks)
```

---

*This plan is the authoritative implementation blueprint for Epic 3 — Companies. All implementation tasks generated by `/sp.tasks` MUST reference and comply with this document. Any deviation requires a formal plan update before implementation proceeds.*
