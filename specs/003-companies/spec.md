# Feature Specification: Epic 3 — Companies

**Feature Branch**: `003-companies`
**Created**: 2026-07-15
**Status**: Draft
**Epic**: 003
**Module**: Companies (Multi-Tenant Foundation)
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#1-overview)
2. [Terminology & Definitions](#2-terminology--definitions)
3. [Multi-Tenant Architecture](#3-multi-tenant-architecture)
4. [User Scenarios & Testing](#4-user-scenarios--testing)
5. [Functional Requirements](#5-functional-requirements)
6. [Non-Functional Requirements](#6-non-functional-requirements)
7. [Business Rules](#7-business-rules)
8. [Permissions Matrix](#8-permissions-matrix)
9. [Validation Rules](#9-validation-rules)
10. [Database Design](#10-database-design)
11. [API Design](#11-api-design)
12. [Error Handling](#12-error-handling)
13. [Audit Logging](#13-audit-logging)
14. [Domain Events](#14-domain-events)
15. [Reporting Requirements](#15-reporting-requirements)
16. [Out of Scope](#16-out-of-scope)
17. [Assumptions](#17-assumptions)
18. [Acceptance Criteria](#18-acceptance-criteria)
19. [Future Enhancements](#19-future-enhancements)
20. [Success Criteria](#20-success-criteria)

---

## 1. Overview

### 1.1 Purpose

The Companies module is the **foundational pillar** of DevSphere ERP's multi-tenant architecture. Every other ERP module — Accounting, Inventory, Sales, Purchasing, CRM, HR — operates within the boundary of a Company. This module defines how companies are created, managed, isolated, and governed.

### 1.2 Strategic Importance

- All ERP data is scoped to a `company_id`. No record in any future module exists without a parent Company.
- The Companies module establishes the **tenant isolation boundary**: one company's data is never visible to another company's users without explicit cross-company permissions.
- This module must support a trajectory from single-company desktop use to a SaaS platform serving thousands of tenants.

### 1.3 Scope

| In Scope | Out of Scope |
|----------|-------------|
| Company CRUD and lifecycle | Billing, subscriptions, payments |
| Company profile and settings | Branches, warehouses, cost centers |
| Multi-tenant isolation model | Inventory, sales, purchasing, CRM |
| Branding, regional, tax settings | User management (managed in Auth module) |
| Audit logging for company events | AI features, reporting dashboards |
| Permission enforcement at company level | Custom domain / subdomain routing (future) |
| Soft delete and restore | White-label platform configuration (future) |

---

## 2. Terminology & Definitions

| Term | Definition |
|------|-----------|
| **Tenant** | The top-level isolation unit. In the current phase, a Tenant maps 1:1 with a Company. In a future SaaS phase, one Subscription (Tenant) may own multiple Companies. |
| **Company** | A legal business entity registered in the ERP. It is the primary unit of data ownership and the boundary for all ERP transactions. |
| **Organization** | A logical grouping of Companies under a single business group (reserved for future multi-entity support). Currently, Organization = Company. |
| **Owner** | The user who created the Company and holds the highest privilege level. Each Company has exactly one Owner. |
| **Primary Administrator** | A user assigned by the Owner to manage the Company's operational settings. May differ from the Owner. |
| **Slug** | A URL-safe, lowercase, hyphenated identifier derived from the company name. Globally unique. Used for future subdomain routing. |
| **company_id** | A UUID (v4) assigned at company creation. Immutable. Used as the foreign key in every module's data table. |
| **Soft Delete** | A non-destructive deactivation that marks a company as deleted while retaining all historical data. |
| **Status** | The lifecycle state of a Company: `active`, `inactive`, `suspended`, `pending_setup`, `deleted`. |

---

## 3. Multi-Tenant Architecture

### 3.1 Isolation Strategy

DevSphere ERP uses **Shared Database, Shared Schema** multi-tenancy with **application-level row isolation** enforced via `company_id`.

| Approach | Decision |
|----------|---------|
| Database-per-tenant | Not used in Phase 1 (cost and operational complexity) |
| Schema-per-tenant | Not used in Phase 1 (migration complexity at scale) |
| Shared schema + company_id | **Selected** — balances cost, scalability, and operational simplicity |
| Future Row Level Security (RLS) | Architected to enable PostgreSQL RLS as a defense-in-depth layer in a future epic |

### 3.2 company_id Strategy

- Every Company is assigned a **UUID v4** as its `company_id` at creation time.
- `company_id` is **immutable** — it never changes after creation.
- All data tables in all ERP modules MUST include `company_id` as a non-nullable foreign key.
- All service-layer queries MUST include `company_id` in WHERE clauses — no query may return cross-company data without explicit authorization.
- The `company_id` is extracted from the authenticated user's JWT token context on every request. It is never accepted as a user-supplied parameter in standard endpoints.

### 3.3 Data Ownership Model

- A Company **owns** all records created within its boundary.
- Users belong to a Company via a membership record (managed by the Auth/Users module).
- A user may be a member of multiple Companies, but each session context is scoped to exactly one Company at a time.
- Cross-company data access (e.g., consolidated reports) is reserved for future `SuperAdmin` and `SaaSAdmin` roles.

### 3.4 Future Extensibility Hooks

The data model must include placeholder fields and design patterns to support:

| Future Feature | Design Hook Required |
|---------------|---------------------|
| Subdomain routing | `slug` field (unique, indexed, immutable after first set) |
| Custom domain | `custom_domain` field (nullable, unique, indexed) |
| White label | `branding` JSONB field for logo, colors, fonts |
| Row Level Security | `company_id` on every table; RLS policies preparable |
| Multiple branches | `Branch` entity FK to `company_id` |
| Multiple warehouses | `Warehouse` entity FK to `company_id` |
| Multiple fiscal years | `FiscalYear` entity FK to `company_id` |
| SaaS subscription | `subscription_id` FK on `companies` table (nullable) |

---

## 4. User Scenarios & Testing

### User Story 1 — Company Creation (Priority: P1)

As an authenticated user, I want to create a new Company in the ERP so that I can begin recording business transactions, managing settings, and inviting team members within an isolated workspace.

**Why this priority**: No other ERP function is possible without an existing Company. This is the entry point for all tenants.

**Independent Test**: Can be fully tested by registering a new user, creating a company, and verifying the company appears in the user's company list with status `active`.

**Acceptance Scenarios**:

1. **Given** a registered user with no existing company, **When** they submit a valid company creation request with required fields, **Then** a new Company is created with status `pending_setup`, the user is assigned as Owner, a unique `company_id` is generated, and a `CompanyCreated` event is emitted.
2. **Given** a company creation request, **When** the company name already exists globally (same legal name), **Then** the system rejects the request with `COMPANY_NAME_CONFLICT` error.
3. **Given** a company creation request, **When** the derived slug conflicts with an existing slug, **Then** the system auto-appends a numeric suffix to make the slug unique, or returns `SLUG_CONFLICT` if manual slug input is provided.
4. **Given** a user who already owns the maximum allowed number of companies, **When** they attempt to create another, **Then** the system returns `COMPANY_LIMIT_EXCEEDED` error.
5. **Given** an unauthenticated request, **When** the company creation endpoint is called, **Then** the system returns `401 Unauthorized`.

---

### User Story 2 — Company Profile Management (Priority: P1)

As a Company Owner or Administrator, I want to update the company's profile information (name, address, tax details, branding, regional settings) so that the ERP reflects accurate and current business information across all modules.

**Why this priority**: Accurate company profile data underpins compliance (tax IDs, legal names), localization (currency, timezone, language), and branding across documents.

**Independent Test**: Can be tested by updating each profile section independently and verifying persistence and reflection in subsequent GET calls.

**Acceptance Scenarios**:

1. **Given** an Owner or Admin of Company A, **When** they submit a partial update to the company profile, **Then** only the provided fields are updated, unchanged fields retain their values, and a `CompanyUpdated` audit event is recorded.
2. **Given** an update request changing the company name, **When** the new name is unique, **Then** the name is updated and the slug is NOT changed (slug is immutable after creation).
3. **Given** an update to tax information (VAT number, registration number), **When** the values pass format validation, **Then** they are persisted and visible in company details.
4. **Given** a user with role `Manager` or lower, **When** they attempt to update company profile, **Then** the system returns `403 Forbidden`.
5. **Given** an update to the company logo, **When** the file meets size and format constraints, **Then** the logo URL is persisted and the old logo is marked for cleanup.

---

### User Story 3 — Company Activation and Deactivation (Priority: P2)

As a Company Owner, I want to activate or deactivate my company so that I can control whether the company is operational within the ERP system.

**Why this priority**: Status management controls access for all users within the company and is essential for subscription lifecycle management.

**Independent Test**: Can be tested by deactivating a company and verifying that member users can no longer access company resources, then reactivating and confirming access is restored.

**Acceptance Scenarios**:

1. **Given** an active company with multiple users, **When** the Owner deactivates the company, **Then** the company status becomes `inactive`, all non-owner user sessions for that company are invalidated, and a `CompanyDeactivated` event is emitted.
2. **Given** an inactive company, **When** the Owner submits a reactivation request, **Then** the company status returns to `active` and a `CompanyActivated` event is emitted.
3. **Given** a company in `suspended` status (system-initiated), **When** the Owner attempts to reactivate, **Then** the system returns `COMPANY_SUSPENDED` error — only a SuperAdmin can lift suspension.
4. **Given** an Admin (non-owner), **When** they attempt to deactivate the company, **Then** the system returns `403 Forbidden`.

---

### User Story 4 — Company Soft Delete and Restore (Priority: P3)

As a Company Owner, I want to delete a company when it is no longer needed, with the assurance that historical data is retained and recoverable within a defined grace period.

**Why this priority**: Irreversible deletion is dangerous; soft delete protects data integrity while allowing lifecycle management.

**Independent Test**: Can be tested by deleting a company, confirming it no longer appears in active listings, then restoring it and confirming all data is intact.

**Acceptance Scenarios**:

1. **Given** an Owner of a company with no active transactions in the last 30 days, **When** they confirm deletion, **Then** the company status becomes `deleted`, `deleted_at` is set, all user sessions are invalidated, and a `CompanyDeleted` event is emitted.
2. **Given** a deleted company within the 90-day retention window, **When** the Owner submits a restore request, **Then** the company is restored to `inactive` status and all data relationships are intact.
3. **Given** a deleted company older than 90 days, **When** the system runs its purge job, **Then** the company and all its data are permanently removed and a `CompanyPermanentlyDeleted` event is emitted.
4. **Given** a company with active financial transactions in the current fiscal year, **When** deletion is attempted, **Then** the system requires a `force_delete` confirmation flag and records this acknowledgment in the audit log.

---

### User Story 5 — Company Settings Management (Priority: P2)

As a Company Owner or Administrator, I want to configure company-wide settings (currency, timezone, language, fiscal year, default document numbering) so that the ERP behaves correctly for our region and business practices.

**Why this priority**: Settings affect every transaction in every module — incorrect timezone or currency causes systemic data quality issues.

**Independent Test**: Can be tested by configuring each setting category independently and verifying that the settings are returned correctly in the company detail endpoint.

**Acceptance Scenarios**:

1. **Given** a newly created company, **When** the Owner sets the default currency to `USD` and timezone to `America/New_York`, **Then** all subsequent financial records default to USD and timestamps are localized to Eastern time.
2. **Given** a company with existing transactions in currency `EUR`, **When** an Admin attempts to change the default currency to `GBP`, **Then** the system issues a warning `CURRENCY_CHANGE_WARNING` and requires explicit confirmation; historical transactions retain their original currency.
3. **Given** a company setting the fiscal year, **When** start month is set to `April`, **Then** the fiscal year runs April to March and all future period-based reports reference this calendar.

---

### User Story 6 — Company Listing and Search (Priority: P2)

As a SuperAdmin (platform admin), I want to view, search, filter, and paginate all companies across the platform so that I can monitor tenant health and perform administrative actions.

**Why this priority**: Essential for SaaS operational management at scale.

**Independent Test**: Can be tested independently by seeding multiple companies with varying statuses and verifying filter and pagination behavior.

**Acceptance Scenarios**:

1. **Given** a SuperAdmin, **When** they request the companies list with filter `status=active`, **Then** only active companies are returned, paginated at 25 per page by default.
2. **Given** a regular company user, **When** they call the company listing endpoint without SuperAdmin privileges, **Then** they receive only their own company's data — never a global list.
3. **Given** a search query for company name containing `acme`, **When** the SuperAdmin submits the search, **Then** all companies with `acme` in the name (case-insensitive) are returned.

---

### Edge Cases

- A company creation request where the legal company name contains special characters (e.g., `&`, `'`, accented characters) — the system must handle unicode and sanitize slug derivation.
- Concurrent creation requests for companies with the same name submitted within milliseconds — the system must handle this via database-level unique constraint, returning exactly one success.
- A company update where both the name and slug are provided — the system must validate the slug format and uniqueness independently of the name.
- A user who is the Owner of Company A attempts to call Company B's API endpoints — request must be rejected at the authorization layer regardless of how `company_id` is supplied.
- A company restore request where the company's referenced users have since been permanently deleted — the system must restore the company without those user associations and notify the Owner.
- Setting a fiscal year start date that conflicts with existing financial period records — the system must warn and require confirmation.
- A logo upload with a file that passes extension check but contains non-image binary content — the system must validate file contents, not just extension.

---

## 5. Functional Requirements

### 5.1 Company Lifecycle

- **FR-001**: The system MUST allow an authenticated user to create a new Company by providing the required fields.
- **FR-002**: The system MUST generate a unique UUID v4 as `company_id` at creation time. This value is immutable.
- **FR-003**: The system MUST auto-derive a URL-safe `slug` from the company name at creation. The slug MUST be globally unique.
- **FR-004**: The system MUST set the initial company status to `pending_setup` upon creation.
- **FR-005**: The system MUST allow the Owner to transition the company to `active` status after completing required setup fields.
- **FR-006**: The system MUST allow the Owner to deactivate an `active` company, transitioning it to `inactive`.
- **FR-007**: The system MUST allow the Owner to reactivate an `inactive` company, transitioning it to `active`.
- **FR-008**: The system MUST enforce soft delete only — no company record MUST be hard-deleted via the application API.
- **FR-009**: The system MUST allow the Owner to initiate a soft delete, transitioning the company to `deleted` status and setting `deleted_at`.
- **FR-010**: The system MUST allow restoration of a `deleted` company within 90 days of `deleted_at`, returning it to `inactive` status.
- **FR-011**: The system MUST permanently purge companies whose `deleted_at` exceeds 90 days, via a scheduled background process.
- **FR-012**: The system MUST prevent any user from accessing a `deleted` or `suspended` company's resources.
- **FR-013**: A `suspended` company MUST only be reactivated by a SuperAdmin.

### 5.2 Company Profile

- **FR-014**: The system MUST store and allow updating of the company's legal name.
- **FR-015**: The system MUST store and allow updating of the company's trade name (doing-business-as), which may differ from the legal name.
- **FR-016**: The system MUST store and allow updating of the company's registered address (street line 1, street line 2, city, state/province, postal code, country).
- **FR-017**: The system MUST store and allow updating of the company's mailing address, which may differ from the registered address.
- **FR-018**: The system MUST store and allow updating of one primary phone number and one secondary phone number.
- **FR-019**: The system MUST store and allow updating of one primary email address (used for system notifications).
- **FR-020**: The system MUST store and allow updating of the company's website URL.
- **FR-021**: The system MUST store and allow updating of the company's tax identification number (VAT/GST/EIN, varies by country).
- **FR-022**: The system MUST store and allow updating of the company's business registration number.
- **FR-023**: The system MUST store and allow updating of the company's business category (e.g., Manufacturing, Retail, Services, Technology).
- **FR-024**: The system MUST store and allow updating of the company's business type (e.g., Sole Proprietor, Partnership, LLC, Corporation, Non-Profit).
- **FR-025**: The system MUST store and allow updating of the company's founding/incorporation date.

### 5.3 Regional Settings

- **FR-026**: The system MUST store and allow updating of the company's default currency (ISO 4217 code, e.g., USD, EUR, GBP).
- **FR-027**: The system MUST store and allow updating of the company's timezone (IANA timezone identifier, e.g., America/New_York).
- **FR-028**: The system MUST store and allow updating of the company's default language (IETF BCP 47 code, e.g., en-US, fr-FR, ar-SA).
- **FR-029**: The system MUST store and allow updating of the company's country of operation.
- **FR-030**: The system MUST store and allow updating of the company's fiscal year start month (1–12).
- **FR-031**: The system MUST store and allow updating of the company's date format preference (e.g., DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD).
- **FR-032**: The system MUST store and allow updating of the company's number format preference (decimal separator, thousands separator).

### 5.4 Branding

- **FR-033**: The system MUST allow upload and storage of the company's logo image.
- **FR-034**: The system MUST enforce logo image constraints: maximum 5 MB, accepted formats: PNG, JPG, SVG, WebP.
- **FR-035**: The system MUST validate logo file content (not just extension) to prevent malicious uploads.
- **FR-036**: The system MUST store the company's primary brand color (hex code).
- **FR-037**: The system MUST store the company's secondary brand color (hex code).
- **FR-038**: The system MUST store a company tagline or short description (max 255 characters).

### 5.5 Company Settings

- **FR-039**: The system MUST store company-level default settings as a structured, extensible settings object.
- **FR-040**: The system MUST allow the Owner or Admin to update individual setting keys without overwriting the entire settings object.
- **FR-041**: Default company settings MUST include: default currency, default language, default timezone, fiscal year start month, date format, number format, invoice prefix, PO prefix.
- **FR-042**: The system MUST validate all setting values against an allowed values registry before persisting.

### 5.6 Company Status Transitions

Valid status transitions are strictly defined:

| From | To | Allowed By |
|------|----|-----------|
| `pending_setup` | `active` | Owner |
| `active` | `inactive` | Owner |
| `inactive` | `active` | Owner |
| `active` | `suspended` | System / SuperAdmin |
| `inactive` | `suspended` | System / SuperAdmin |
| `suspended` | `active` | SuperAdmin only |
| `active` | `deleted` | Owner |
| `inactive` | `deleted` | Owner |
| `deleted` | `inactive` | Owner (within 90 days) |

Any transition not listed above MUST be rejected with `INVALID_STATUS_TRANSITION`.

---

## 6. Non-Functional Requirements

### 6.1 Performance

- **NFR-001**: Company detail retrieval (GET by ID) MUST return a response within 200ms at p95 under normal load.
- **NFR-002**: Company list retrieval (paginated, 25 records) MUST return within 500ms at p95.
- **NFR-003**: Company creation MUST complete within 1 second at p95, including slug uniqueness validation.
- **NFR-004**: Company profile update MUST complete within 500ms at p95.
- **NFR-005**: The system MUST support at least 500 concurrent company API requests without degradation.

### 6.2 Scalability

- **NFR-006**: The database schema MUST support up to 1,000,000 company records without schema changes.
- **NFR-007**: All queries against the `companies` table MUST use indexed columns in WHERE clauses.
- **NFR-008**: The Companies module MUST be stateless at the application layer to support horizontal scaling.

### 6.3 Security

- **NFR-009**: All company endpoints MUST require a valid JWT access token.
- **NFR-010**: The `company_id` in API responses MUST be the UUID — never an auto-increment integer that enables enumeration.
- **NFR-011**: All sensitive fields (tax number, registration number) MUST be masked in API responses for non-Owner, non-Admin roles.
- **NFR-012**: Company data MUST be encrypted at rest in the database.
- **NFR-013**: Logo upload endpoints MUST validate MIME type via file content inspection, not just Content-Type header.
- **NFR-014**: Rate limiting MUST be applied to company creation: maximum 10 company creation attempts per user per hour.
- **NFR-015**: The system MUST log all authorization failures for company endpoints to the security audit log.

### 6.4 Availability

- **NFR-016**: The Companies module MUST achieve 99.9% availability (less than 8.7 hours downtime per year).
- **NFR-017**: Read operations (GET company, list companies) MUST be served from a read replica in production to prevent write-load interference.

### 6.5 Maintainability

- **NFR-018**: All business logic MUST reside in the Service layer, not in API route handlers or repositories.
- **NFR-019**: Company domain entities MUST not contain database-specific annotations or ORM directives.
- **NFR-020**: All public service methods MUST have corresponding unit tests with minimum 90% branch coverage.
- **NFR-021**: The Companies module MUST be independently deployable within the modular monolith architecture.

### 6.6 Auditability

- **NFR-022**: Every state-changing operation on a Company MUST produce an immutable audit log record.
- **NFR-023**: Audit log records MUST capture: actor user ID, company ID, action type, before state snapshot, after state snapshot, IP address, timestamp (UTC), request ID.
- **NFR-024**: Audit logs MUST be retained for a minimum of 7 years to support compliance requirements.
- **NFR-025**: Audit logs MUST NOT be deletable via the application API.

### 6.7 Data Integrity

- **NFR-026**: Company name uniqueness MUST be enforced at the database level via a unique constraint (case-insensitive collation).
- **NFR-027**: Slug uniqueness MUST be enforced at the database level via a unique constraint.
- **NFR-028**: All foreign key relationships in dependent modules referencing `company_id` MUST use ON DELETE RESTRICT to prevent orphaned records.
- **NFR-029**: All database writes involving company data MUST be wrapped in transactions.

### 6.8 Disaster Recovery

- **NFR-030**: Company data MUST be included in daily automated database backups.
- **NFR-031**: The system MUST support point-in-time recovery (PITR) for company data up to the last 30 days.
- **NFR-032**: Recovery Time Objective (RTO): company data must be restorable within 4 hours of a disaster event.
- **NFR-033**: Recovery Point Objective (RPO): maximum 1 hour of data loss in a worst-case failure scenario.

---

## 7. Business Rules

### 7.1 Company Name Rules

- **BR-001**: Company legal name MUST be globally unique across all tenants (case-insensitive).
- **BR-002**: Company trade name (DBA) does NOT need to be globally unique.
- **BR-003**: Company name MUST be between 2 and 255 characters.
- **BR-004**: Company name MUST NOT consist entirely of whitespace or special characters.
- **BR-005**: Company name changes are allowed but are recorded in audit history.

### 7.2 Slug Rules

- **BR-006**: The slug is auto-derived from the legal name at creation: lowercase, spaces replaced with hyphens, special characters removed, max 100 characters.
- **BR-007**: The slug MUST be globally unique. If a conflict exists, the system appends `-{n}` (e.g., `acme-corp-2`).
- **BR-008**: The slug is immutable after the company's first `active` transition. It cannot be changed via the API.
- **BR-009**: The slug serves as the future subdomain identifier and URL segment for white-label routing.

### 7.3 Ownership Rules

- **BR-010**: Every Company MUST have exactly one Owner at all times.
- **BR-011**: The Owner is the user who created the company. Ownership cannot be transferred in Phase 1 (future enhancement).
- **BR-012**: The Owner cannot be removed from the company. The Owner cannot remove themselves.
- **BR-013**: The Owner's permissions within their company are absolute — they cannot be restricted by other admin users.

### 7.4 Primary Administrator Rules

- **BR-014**: The Owner may designate one Primary Administrator per company.
- **BR-015**: The Primary Administrator can manage all company settings and users except for changing the Owner or deleting the company.
- **BR-016**: If the Primary Administrator is removed from the company, the Primary Administrator designation returns to the Owner.

### 7.5 Company Limit Rules

- **BR-017**: In Phase 1, there is no enforced limit on the number of companies a user may own. This will be governed by subscription tiers in a future epic.
- **BR-018**: A `COMPANY_LIMIT` configuration key MUST exist in system settings, defaulting to `unlimited`, so that limits can be enforced without code changes when billing is introduced.

### 7.6 Deletion Policy

- **BR-019**: Company deletion is always soft — `deleted_at` is set and `status` becomes `deleted`.
- **BR-020**: Deleted companies are excluded from all standard API queries (unless explicitly requested by SuperAdmin with `include_deleted=true`).
- **BR-021**: Deleted company slugs are released for reuse after the 90-day retention period expires and the company is purged.
- **BR-022**: A company with active (non-cancelled) subscription records MUST NOT be deletable — the subscription must be cancelled first.
- **BR-023**: A company MUST provide a deletion reason when initiating soft delete. Reason is stored in the audit log.

### 7.7 Status Transition Rules

- **BR-024**: Only transitions defined in Section 5.6 are permitted. All others return `INVALID_STATUS_TRANSITION`.
- **BR-025**: When a company is `suspended`, all API calls by company members return `403 Forbidden` with reason `COMPANY_SUSPENDED`.
- **BR-026**: A company in `pending_setup` status cannot be used for any ERP operations until transitioned to `active`.

### 7.8 Currency and Fiscal Year Rules

- **BR-027**: Once a financial transaction has been recorded, the default currency MUST NOT be changed without explicit Owner confirmation and a warning that historical data is unaffected.
- **BR-028**: The fiscal year start month may be changed once per 12-month period to prevent data inconsistency in period-based reporting.
- **BR-029**: The fiscal year start month change takes effect from the next financial year; it does not retroactively change closed periods.

### 7.9 Logo Rules

- **BR-030**: Only one logo is stored per company at any time. Uploading a new logo replaces the previous one.
- **BR-031**: The previous logo file MUST be retained for 30 days before permanent deletion (to allow CDN cache invalidation and rollback).

---

## 8. Permissions Matrix

### 8.1 Role Definitions

| Role | Description |
|------|-------------|
| `super_admin` | Platform-level administrator. Can view and manage all companies. Future SaaS role. |
| `owner` | Creator of the Company. Absolute authority within their company. |
| `admin` | Company administrator designated by the Owner. |
| `manager` | Departmental manager with elevated read access and limited write access. |
| `accountant` | Financial data access. Read company settings; cannot modify profile. |
| `sales` | Sales operations. Very limited company profile access. |
| `inventory` | Inventory operations. Very limited company profile access. |

### 8.2 Company Endpoint Permissions

| Action | `super_admin` | `owner` | `admin` | `manager` | `accountant` | `sales` | `inventory` |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Create Company | Yes | Yes | No | No | No | No | No |
| View Own Company Detail | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| View All Companies (global) | Yes | No | No | No | No | No | No |
| Update Company Profile | Yes | Yes | Yes | No | No | No | No |
| Update Company Branding | Yes | Yes | Yes | No | No | No | No |
| Update Regional Settings | Yes | Yes | Yes | No | No | No | No |
| Update Company Settings | Yes | Yes | Yes | No | No | No | No |
| View Tax / Reg Numbers | Yes | Yes | Yes | No | Yes | No | No |
| Update Tax / Reg Numbers | Yes | Yes | Yes | No | No | No | No |
| Activate Company | Yes | Yes | No | No | No | No | No |
| Deactivate Company | Yes | Yes | No | No | No | No | No |
| Delete Company (soft) | Yes | Yes | No | No | No | No | No |
| Restore Deleted Company | Yes | Yes | No | No | No | No | No |
| Suspend Company | Yes | No | No | No | No | No | No |
| Lift Suspension | Yes | No | No | No | No | No | No |
| View Audit Log | Yes | Yes | Yes | No | No | No | No |
| Upload Company Logo | Yes | Yes | Yes | No | No | No | No |
| View Company Settings | Yes | Yes | Yes | Yes | Yes | No | No |

---

## 9. Validation Rules

### 9.1 Company Name

| Rule | Constraint |
|------|-----------|
| Required | Yes |
| Min length | 2 characters |
| Max length | 255 characters |
| Allowed characters | Unicode letters, digits, spaces, hyphens, ampersands, periods, commas, apostrophes |
| Prohibited | All whitespace only; control characters; HTML/script tags |
| Uniqueness | Case-insensitive global uniqueness (normalized NFC Unicode form) |
| Error code | `COMPANY_NAME_REQUIRED`, `COMPANY_NAME_TOO_SHORT`, `COMPANY_NAME_TOO_LONG`, `COMPANY_NAME_INVALID_CHARS`, `COMPANY_NAME_CONFLICT` |

### 9.2 Slug

| Rule | Constraint |
|------|-----------|
| Auto-generated | Yes (from name at creation) |
| Manual override | Allowed only at creation time |
| Pattern | `^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$` |
| Min length | 2 characters |
| Max length | 100 characters |
| Prohibited | Leading/trailing hyphens; consecutive hyphens |
| Uniqueness | Global uniqueness, exact match |
| Immutability | Cannot be changed after first `active` transition |
| Error code | `SLUG_INVALID`, `SLUG_CONFLICT`, `SLUG_IMMUTABLE` |

### 9.3 Email Address

| Rule | Constraint |
|------|-----------|
| Required | Yes (primary company email) |
| Format | RFC 5322 compliant |
| Max length | 254 characters |
| Uniqueness | Not required — multiple companies may share a contact email |
| Error code | `EMAIL_REQUIRED`, `EMAIL_INVALID` |

### 9.4 Phone Number

| Rule | Constraint |
|------|-----------|
| Required | No |
| Format | E.164 international format (e.g., +12125551234) |
| Max length | 20 characters |
| Error code | `PHONE_INVALID` |

### 9.5 Website URL

| Rule | Constraint |
|------|-----------|
| Required | No |
| Format | Must be a valid URL with `http://` or `https://` scheme |
| Max length | 2048 characters |
| Error code | `WEBSITE_INVALID` |

### 9.6 Tax Identification Number

| Rule | Constraint |
|------|-----------|
| Required | No (at creation); may be required before `active` transition depending on country |
| Format | Country-specific; validated per ISO country code when country is set |
| Max length | 50 characters |
| Uniqueness | Not enforced globally (same tax entity may appear in test/sandbox environments) |
| Error code | `TAX_NUMBER_INVALID_FORMAT` |

### 9.7 Currency

| Rule | Constraint |
|------|-----------|
| Required | Yes (must be set before `active` transition) |
| Format | ISO 4217 3-letter code (e.g., USD, EUR, GBP) |
| Allowed values | Validated against an embedded ISO 4217 currency table |
| Error code | `CURRENCY_REQUIRED`, `CURRENCY_INVALID` |

### 9.8 Timezone

| Rule | Constraint |
|------|-----------|
| Required | Yes (must be set before `active` transition) |
| Format | IANA timezone database identifier (e.g., `America/New_York`) |
| Allowed values | Validated against the IANA timezone table |
| Error code | `TIMEZONE_REQUIRED`, `TIMEZONE_INVALID` |

### 9.9 Language

| Rule | Constraint |
|------|-----------|
| Required | Yes (defaults to `en-US` if not provided) |
| Format | IETF BCP 47 language tag |
| Allowed values | Validated against supported locales list |
| Error code | `LANGUAGE_INVALID` |

### 9.10 Country

| Rule | Constraint |
|------|-----------|
| Required | Yes (must be set before `active` transition) |
| Format | ISO 3166-1 alpha-2 code (e.g., US, GB, FR) |
| Allowed values | Validated against ISO 3166-1 country table |
| Error code | `COUNTRY_REQUIRED`, `COUNTRY_INVALID` |

### 9.11 Fiscal Year Start Month

| Rule | Constraint |
|------|-----------|
| Required | Yes (defaults to `1` — January) |
| Type | Integer |
| Allowed values | 1–12 |
| Error code | `FISCAL_YEAR_MONTH_INVALID` |

### 9.12 Brand Colors

| Rule | Constraint |
|------|-----------|
| Required | No |
| Format | Hexadecimal color code (e.g., `#FF5733` or `FF5733`) |
| Pattern | `^#?([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$` |
| Error code | `COLOR_INVALID` |

### 9.13 Logo Upload

| Rule | Constraint |
|------|-----------|
| Required | No |
| Max file size | 5 MB |
| Accepted MIME types | `image/png`, `image/jpeg`, `image/svg+xml`, `image/webp` |
| Content validation | MIME type MUST be validated from file magic bytes |
| Recommended dimensions | Min 200×200px; Max 4000×4000px |
| Error code | `LOGO_TOO_LARGE`, `LOGO_INVALID_FORMAT`, `LOGO_INVALID_CONTENT` |

### 9.14 Tagline / Short Description

| Rule | Constraint |
|------|-----------|
| Required | No |
| Max length | 255 characters |
| Error code | `TAGLINE_TOO_LONG` |

---

## 10. Database Design

### 10.1 Entities and Attributes

#### `companies` (Primary Entity)

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| `id` | UUID v4 | PK, NOT NULL, IMMUTABLE | Tenant isolation key; used as FK in all modules |
| `legal_name` | VARCHAR(255) | NOT NULL, UNIQUE (CI) | Official registered company name |
| `trade_name` | VARCHAR(255) | NULLABLE | Doing-business-as name |
| `slug` | VARCHAR(100) | NOT NULL, UNIQUE | URL-safe identifier; immutable after first `active` |
| `status` | ENUM | NOT NULL, DEFAULT `pending_setup` | `pending_setup`, `active`, `inactive`, `suspended`, `deleted` |
| `owner_id` | UUID | NOT NULL, FK → users.id | The user who created the company |
| `primary_admin_id` | UUID | NULLABLE, FK → users.id | Designated primary administrator |
| `email` | VARCHAR(254) | NOT NULL | Primary company contact email |
| `phone_primary` | VARCHAR(20) | NULLABLE | E.164 format phone |
| `phone_secondary` | VARCHAR(20) | NULLABLE | E.164 format phone |
| `website` | VARCHAR(2048) | NULLABLE | Company website URL |
| `tax_number` | VARCHAR(50) | NULLABLE | VAT / EIN / GST number |
| `registration_number` | VARCHAR(50) | NULLABLE | Business registration number |
| `business_category` | VARCHAR(100) | NULLABLE | Industry category |
| `business_type` | ENUM | NULLABLE | `sole_proprietor`, `partnership`, `llc`, `corporation`, `non_profit`, `other` |
| `incorporation_date` | DATE | NULLABLE | Legal incorporation/founding date |
| `default_currency` | CHAR(3) | NULLABLE | ISO 4217 code |
| `default_timezone` | VARCHAR(100) | NULLABLE | IANA timezone ID |
| `default_language` | VARCHAR(10) | NULLABLE | IETF BCP 47 code |
| `country` | CHAR(2) | NULLABLE | ISO 3166-1 alpha-2 |
| `fiscal_year_start_month` | SMALLINT | NOT NULL, DEFAULT 1 | 1–12 |
| `date_format` | VARCHAR(20) | NOT NULL, DEFAULT `YYYY-MM-DD` | Date display format |
| `number_format` | JSONB | NOT NULL, DEFAULT `{}` | Decimal and thousands separators |
| `logo_url` | VARCHAR(2048) | NULLABLE | Stored object URL |
| `logo_previous_url` | VARCHAR(2048) | NULLABLE | Previous logo (retained 30 days) |
| `brand_color_primary` | CHAR(7) | NULLABLE | Hex color code |
| `brand_color_secondary` | CHAR(7) | NULLABLE | Hex color code |
| `tagline` | VARCHAR(255) | NULLABLE | Short description |
| `settings` | JSONB | NOT NULL, DEFAULT `{}` | Extensible key-value settings map |
| `metadata` | JSONB | NOT NULL, DEFAULT `{}` | Future extensibility (custom fields, integrations) |
| `subscription_id` | UUID | NULLABLE | FK → subscriptions.id (future) |
| `custom_domain` | VARCHAR(253) | NULLABLE, UNIQUE | Future custom domain routing |
| `deleted_at` | TIMESTAMPTZ | NULLABLE | Set when status = `deleted` |
| `deletion_reason` | TEXT | NULLABLE | Required when soft-deleting |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Record creation timestamp (UTC) |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | Last modification timestamp (UTC) |

#### `company_addresses` (Secondary Entity)

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| `id` | UUID v4 | PK | |
| `company_id` | UUID | NOT NULL, FK → companies.id | |
| `address_type` | ENUM | NOT NULL | `registered`, `mailing`, `billing`, `shipping` |
| `street_line_1` | VARCHAR(255) | NOT NULL | |
| `street_line_2` | VARCHAR(255) | NULLABLE | |
| `city` | VARCHAR(100) | NOT NULL | |
| `state_province` | VARCHAR(100) | NULLABLE | |
| `postal_code` | VARCHAR(20) | NULLABLE | |
| `country` | CHAR(2) | NOT NULL | ISO 3166-1 alpha-2 |
| `is_primary` | BOOLEAN | NOT NULL, DEFAULT FALSE | Only one address of each type may be primary |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |

#### `company_audit_logs` (Audit Entity)

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| `id` | UUID v4 | PK | |
| `company_id` | UUID | NOT NULL, FK → companies.id | |
| `actor_user_id` | UUID | NULLABLE | NULL if system-initiated |
| `action` | VARCHAR(100) | NOT NULL | Event type (see Section 13) |
| `before_state` | JSONB | NULLABLE | Company snapshot before change |
| `after_state` | JSONB | NULLABLE | Company snapshot after change |
| `ip_address` | INET | NULLABLE | Requester IP |
| `user_agent` | TEXT | NULLABLE | Requester User-Agent |
| `request_id` | UUID | NULLABLE | Correlation ID from request |
| `metadata` | JSONB | NULLABLE | Additional context |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | UTC timestamp |

### 10.2 Relationships

| Relationship | Type | Description |
|-------------|------|-------------|
| `companies` → `users` (owner) | Many-to-One | Each company has one owner user |
| `companies` → `users` (primary_admin) | Many-to-One | Optional primary admin |
| `companies` → `company_addresses` | One-to-Many | A company may have multiple addresses by type |
| `companies` → `company_audit_logs` | One-to-Many | All audit events for a company |
| `companies` → `subscriptions` (future) | Many-to-One | Future SaaS billing link |

### 10.3 Indexes

| Table | Index Columns | Index Type | Purpose |
|-------|-------------|-----------|---------|
| `companies` | `id` | PRIMARY | Unique lookup |
| `companies` | `slug` | UNIQUE | Slug conflict check, future routing |
| `companies` | `legal_name` (CI) | UNIQUE | Name conflict check |
| `companies` | `owner_id` | BTREE | Find companies by owner |
| `companies` | `status` | BTREE | Filter by status |
| `companies` | `status, deleted_at` | COMPOSITE | Active company queries |
| `companies` | `custom_domain` | UNIQUE PARTIAL (NOT NULL) | Future domain routing |
| `companies` | `subscription_id` | BTREE | Future subscription lookup |
| `companies` | `created_at` | BTREE | Time-series sorting |
| `company_addresses` | `company_id, address_type` | COMPOSITE | Address lookup per company |
| `company_audit_logs` | `company_id` | BTREE | Audit log retrieval |
| `company_audit_logs` | `company_id, created_at` | COMPOSITE | Time-ordered audit queries |
| `company_audit_logs` | `actor_user_id` | BTREE | Find actions by user |

### 10.4 Unique Constraints

- `companies.slug` — global uniqueness.
- `companies.legal_name` — case-insensitive global uniqueness.
- `companies.custom_domain` — global uniqueness where not NULL.
- `company_addresses.(company_id, address_type, is_primary)` — only one primary address of each type per company.

---

## 11. API Design

### 11.1 Base Path

```
/api/v1/companies
```

All endpoints require `Authorization: Bearer <access_token>` header.

---

### 11.2 Endpoints

#### POST /api/v1/companies
**Create a new Company**

Authorization: Any authenticated user.

**Request Body**:

```
CreateCompanyRequest:
  legal_name       string  REQUIRED  2–255 chars
  trade_name       string  OPTIONAL  max 255 chars
  email            string  REQUIRED  RFC 5322
  phone_primary    string  OPTIONAL  E.164
  country          string  OPTIONAL  ISO 3166-1 alpha-2
  default_currency string  OPTIONAL  ISO 4217 (default: USD)
  default_language string  OPTIONAL  BCP 47 (default: en-US)
  default_timezone string  OPTIONAL  IANA (default: UTC)
  slug             string  OPTIONAL  manually specified; auto-derived if omitted
```

**Response 201 Created**:

```
CompanyResponse:
  id               UUID
  legal_name       string
  trade_name       string | null
  slug             string
  status           string  (pending_setup)
  owner_id         UUID
  email            string
  country          string | null
  default_currency string
  default_language string
  default_timezone string
  created_at       datetime
  updated_at       datetime
```

**Error Responses**:

| Status | Error Code | Condition |
|--------|-----------|-----------|
| 400 | `VALIDATION_ERROR` | Invalid field values |
| 409 | `COMPANY_NAME_CONFLICT` | Legal name already exists |
| 409 | `SLUG_CONFLICT` | Provided slug already exists |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many creation attempts |

---

#### GET /api/v1/companies/{company_id}
**Get Company Detail**

Authorization: Members of the company; SuperAdmin.

**Path Parameters**: `company_id` — UUID.

**Response 200 OK**:

```
CompanyDetailResponse:
  id                      UUID
  legal_name              string
  trade_name              string | null
  slug                    string
  status                  string
  owner_id                UUID
  primary_admin_id        UUID | null
  email                   string
  phone_primary           string | null
  phone_secondary         string | null
  website                 string | null
  tax_number              string | null  (masked for non-owner/admin: ****)
  registration_number     string | null  (masked for non-owner/admin: ****)
  business_category       string | null
  business_type           string | null
  incorporation_date      date | null
  default_currency        string
  default_timezone        string
  default_language        string
  country                 string | null
  fiscal_year_start_month integer
  date_format             string
  number_format           object
  logo_url                string | null
  brand_color_primary     string | null
  brand_color_secondary   string | null
  tagline                 string | null
  settings                object
  addresses               CompanyAddress[]
  created_at              datetime
  updated_at              datetime
```

**Error Responses**:

| Status | Error Code | Condition |
|--------|-----------|-----------|
| 401 | `UNAUTHORIZED` | No valid token |
| 403 | `FORBIDDEN` | User not a member of this company |
| 404 | `COMPANY_NOT_FOUND` | Company does not exist or is deleted |

---

#### PATCH /api/v1/companies/{company_id}
**Update Company Profile (Partial Update)**

Authorization: Owner, Admin, SuperAdmin.

**Request Body** (all fields optional; only provided fields are updated):

```
UpdateCompanyRequest:
  legal_name              string
  trade_name              string | null
  email                   string
  phone_primary           string | null
  phone_secondary         string | null
  website                 string | null
  tax_number              string | null
  registration_number     string | null
  business_category       string | null
  business_type           string | null
  incorporation_date      date | null
  default_currency        string
  default_timezone        string
  default_language        string
  country                 string
  fiscal_year_start_month integer
  date_format             string
  number_format           object
  brand_color_primary     string | null
  brand_color_secondary   string | null
  tagline                 string | null
```

**Response 200 OK**: Full `CompanyDetailResponse`.

**Error Responses**:

| Status | Error Code | Condition |
|--------|-----------|-----------|
| 400 | `VALIDATION_ERROR` | Invalid field values |
| 403 | `FORBIDDEN` | Insufficient role |
| 404 | `COMPANY_NOT_FOUND` | |
| 409 | `COMPANY_NAME_CONFLICT` | New legal name conflicts |
| 422 | `CURRENCY_CHANGE_WARNING` | Currency change with existing transactions (requires `confirm_currency_change: true`) |

---

#### PATCH /api/v1/companies/{company_id}/settings
**Update Company Settings**

Authorization: Owner, Admin, SuperAdmin.

**Request Body**:

```
UpdateSettingsRequest:
  settings  object  Key-value map of setting keys to update
```

**Response 200 OK**:

```
CompanySettingsResponse:
  company_id  UUID
  settings    object
  updated_at  datetime
```

---

#### POST /api/v1/companies/{company_id}/activate
**Activate Company**

Authorization: Owner, SuperAdmin.

Transitions from `pending_setup` or `inactive` to `active`. Validates required fields are complete (currency, timezone, country, email).

**Response 200 OK**: `CompanyDetailResponse` with `status: active`.

**Error Responses**:

| Status | Error Code | Condition |
|--------|-----------|-----------|
| 403 | `FORBIDDEN` | Not Owner or SuperAdmin |
| 409 | `INVALID_STATUS_TRANSITION` | Current status does not allow activation |
| 422 | `COMPANY_INCOMPLETE` | Required fields not set (lists missing fields) |

---

#### POST /api/v1/companies/{company_id}/deactivate
**Deactivate Company**

Authorization: Owner, SuperAdmin.

**Request Body**:

```
DeactivateRequest:
  reason  string  REQUIRED  Max 1000 chars
```

**Response 200 OK**: `CompanyDetailResponse` with `status: inactive`.

---

#### DELETE /api/v1/companies/{company_id}
**Soft Delete Company**

Authorization: Owner, SuperAdmin.

**Request Body**:

```
DeleteCompanyRequest:
  reason                string   REQUIRED  Max 1000 chars
  force_delete          boolean  OPTIONAL  Required when active transactions exist
  confirm_delete        boolean  REQUIRED  Must be `true` to proceed
```

**Response 200 OK**:

```
DeleteCompanyResponse:
  id          UUID
  status      string  (deleted)
  deleted_at  datetime
  message     string
```

**Error Responses**:

| Status | Error Code | Condition |
|--------|-----------|-----------|
| 400 | `VALIDATION_ERROR` | Missing reason or confirm |
| 403 | `FORBIDDEN` | Not Owner or SuperAdmin |
| 409 | `ACTIVE_SUBSCRIPTION` | Cannot delete with active subscription |
| 422 | `FORCE_DELETE_REQUIRED` | Active transactions exist; `force_delete: true` required |

---

#### POST /api/v1/companies/{company_id}/restore
**Restore Soft-Deleted Company**

Authorization: Owner, SuperAdmin.

**Response 200 OK**: `CompanyDetailResponse` with `status: inactive`.

**Error Responses**:

| Status | Error Code | Condition |
|--------|-----------|-----------|
| 403 | `FORBIDDEN` | Not Owner or SuperAdmin |
| 404 | `COMPANY_NOT_FOUND` | Company not found or not in `deleted` status |
| 410 | `COMPANY_PURGED` | 90-day retention window has expired |

---

#### POST /api/v1/companies/{company_id}/logo
**Upload Company Logo**

Authorization: Owner, Admin, SuperAdmin.

**Request**: `multipart/form-data` with `logo` file field.

**Response 200 OK**:

```
LogoUploadResponse:
  logo_url    string
  updated_at  datetime
```

**Error Responses**:

| Status | Error Code | Condition |
|--------|-----------|-----------|
| 400 | `LOGO_TOO_LARGE` | File exceeds 5 MB |
| 400 | `LOGO_INVALID_FORMAT` | Unsupported file type |
| 400 | `LOGO_INVALID_CONTENT` | File content does not match declared type |

---

#### GET /api/v1/companies/{company_id}/addresses
**List Company Addresses**

Authorization: Members of the company, SuperAdmin.

**Response 200 OK**:

```
AddressListResponse:
  data  CompanyAddress[]
```

---

#### POST /api/v1/companies/{company_id}/addresses
**Add Company Address**

Authorization: Owner, Admin, SuperAdmin.

---

#### PUT /api/v1/companies/{company_id}/addresses/{address_id}
**Update Company Address**

Authorization: Owner, Admin, SuperAdmin.

---

#### DELETE /api/v1/companies/{company_id}/addresses/{address_id}
**Remove Company Address**

Authorization: Owner, Admin, SuperAdmin.

---

#### GET /api/v1/companies/{company_id}/audit-logs
**Get Audit Log for Company**

Authorization: Owner, Admin, SuperAdmin.

**Query Parameters**:

```
page         integer  DEFAULT 1
page_size    integer  DEFAULT 25, MAX 100
action       string   Filter by action type
actor_id     UUID     Filter by user
date_from    datetime
date_to      datetime
```

**Response 200 OK**:

```
AuditLogListResponse:
  data         AuditLogEntry[]
  total        integer
  page         integer
  page_size    integer
  total_pages  integer
```

---

#### GET /api/v1/admin/companies (SuperAdmin only)
**List All Companies (Global)**

Authorization: SuperAdmin only.

**Query Parameters**:

```
page            integer  DEFAULT 1
page_size       integer  DEFAULT 25, MAX 100
status          string   Filter by status
search          string   Search by legal_name or slug
country         string   Filter by country code
include_deleted boolean  DEFAULT false
sort_by         string   DEFAULT created_at
sort_order      string   DEFAULT desc
```

**Response 200 OK**:

```
CompanyListResponse:
  data         CompanyListItem[]
  total        integer
  page         integer
  page_size    integer
  total_pages  integer
```

---

### 11.3 Pagination Standard

All list endpoints follow the same pagination envelope:

```
{
  "data": [...],
  "meta": {
    "total": 1250,
    "page": 1,
    "page_size": 25,
    "total_pages": 50
  }
}
```

### 11.4 Common Response Headers

| Header | Description |
|--------|-------------|
| `X-Request-ID` | UUID correlation ID for request tracing |
| `X-RateLimit-Limit` | Rate limit ceiling |
| `X-RateLimit-Remaining` | Remaining requests in window |
| `X-RateLimit-Reset` | Unix timestamp when window resets |

---

## 12. Error Handling

### 12.1 Error Response Envelope

All errors return a consistent envelope:

```json
{
  "error": {
    "code": "COMPANY_NAME_CONFLICT",
    "message": "A company with this legal name already exists.",
    "details": [
      {
        "field": "legal_name",
        "message": "Legal name must be globally unique (case-insensitive)."
      }
    ],
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-07-15T10:30:00Z"
  }
}
```

### 12.2 Error Code Registry

| HTTP Status | Error Code | Description |
|-------------|-----------|-------------|
| 400 | `VALIDATION_ERROR` | One or more request fields fail validation |
| 400 | `LOGO_TOO_LARGE` | Logo file exceeds 5 MB |
| 400 | `LOGO_INVALID_FORMAT` | Unsupported logo file type |
| 400 | `LOGO_INVALID_CONTENT` | Logo file magic bytes do not match declared type |
| 401 | `UNAUTHORIZED` | No valid authentication token |
| 403 | `FORBIDDEN` | Authenticated but insufficient permissions |
| 403 | `COMPANY_SUSPENDED` | Company is suspended; contact support |
| 403 | `COMPANY_PENDING_SETUP` | Company not yet activated |
| 404 | `COMPANY_NOT_FOUND` | Company does not exist or is deleted |
| 404 | `ADDRESS_NOT_FOUND` | Address record not found |
| 409 | `COMPANY_NAME_CONFLICT` | Legal name already taken |
| 409 | `SLUG_CONFLICT` | Slug already taken |
| 409 | `INVALID_STATUS_TRANSITION` | Requested status change is not permitted |
| 409 | `ACTIVE_SUBSCRIPTION` | Cannot delete company with active subscription |
| 410 | `COMPANY_PURGED` | Company permanently deleted; data unrecoverable |
| 422 | `COMPANY_INCOMPLETE` | Required setup fields not completed |
| 422 | `FORCE_DELETE_REQUIRED` | Active transactions exist; explicit confirmation required |
| 422 | `CURRENCY_CHANGE_WARNING` | Currency change with existing transactions |
| 422 | `SLUG_IMMUTABLE` | Attempt to change slug after activation |
| 422 | `FISCAL_YEAR_CHANGE_TOO_SOON` | Fiscal year start already changed in the last 12 months |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests; see `X-RateLimit-Reset` header |
| 500 | `INTERNAL_SERVER_ERROR` | Unexpected server error |

### 12.3 Validation Error Format

When `VALIDATION_ERROR` is returned, the `details` array contains one entry per failing field:

```json
{
  "field": "default_currency",
  "message": "Currency code 'XYZ' is not a valid ISO 4217 code.",
  "code": "CURRENCY_INVALID"
}
```

### 12.4 Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /companies` | 10 requests | Per user per hour |
| `PATCH /companies/{id}` | 60 requests | Per user per hour |
| `POST /companies/{id}/logo` | 10 requests | Per user per hour |
| All other reads | 300 requests | Per user per minute |

---

## 13. Audit Logging

### 13.1 Audit Events

Every state-changing operation MUST produce a `company_audit_logs` record. Read operations are NOT audited at the database level (application-level access logs capture reads).

| Action Constant | Trigger | Before State | After State |
|----------------|---------|-------------|-------------|
| `COMPANY_CREATED` | Company creation | null | Full company snapshot |
| `COMPANY_UPDATED` | Profile/settings update | Changed fields only | Changed fields only |
| `COMPANY_ACTIVATED` | Status → active | `{status: previous}` | `{status: "active"}` |
| `COMPANY_DEACTIVATED` | Status → inactive | `{status: "active"}` | `{status: "inactive"}` |
| `COMPANY_SUSPENDED` | Status → suspended | `{status: previous}` | `{status: "suspended"}` |
| `COMPANY_SUSPENSION_LIFTED` | Status restored by SuperAdmin | `{status: "suspended"}` | `{status: "active"}` |
| `COMPANY_DELETED` | Soft delete | Full company snapshot | `{status: "deleted", deleted_at: ...}` |
| `COMPANY_RESTORED` | Restore from deleted | `{status: "deleted"}` | `{status: "inactive"}` |
| `COMPANY_SETTINGS_CHANGED` | Settings update | Previous settings | New settings |
| `COMPANY_BRANDING_CHANGED` | Logo or color update | Previous branding | New branding |
| `COMPANY_ADMIN_CHANGED` | Primary admin designation | Previous admin ID | New admin ID |
| `COMPANY_LOGO_UPLOADED` | Logo upload | Previous logo URL | New logo URL |
| `COMPANY_ADDRESS_ADDED` | Address creation | null | Address snapshot |
| `COMPANY_ADDRESS_UPDATED` | Address update | Previous address | New address |
| `COMPANY_ADDRESS_REMOVED` | Address deletion | Previous address | `{deleted: true}` |
| `COMPANY_OWNER_TRANSFER` | Future ownership transfer | Previous owner ID | New owner ID |

### 13.2 Audit Log Immutability

- Audit log records MUST NOT be updatable or deletable via the application API.
- The database user used by the application MUST NOT have `UPDATE` or `DELETE` privileges on `company_audit_logs`.
- An append-only write model MUST be enforced at the repository layer.

### 13.3 Audit Log Retention

- Audit logs MUST be retained for a minimum of 7 years.
- After 7 years, logs may be archived to cold storage but MUST remain queryable on request.
- Log purging requires SuperAdmin authorization and is recorded in the platform-level audit trail.

---

## 14. Domain Events

### 14.1 Event Definitions

Domain events are published after successful persistence to enable downstream module integration (future event bus / message queue).

| Event | Payload |
|-------|---------|
| `CompanyCreated` | `company_id`, `legal_name`, `slug`, `owner_id`, `status`, `created_at` |
| `CompanyUpdated` | `company_id`, `changed_fields[]`, `updated_by`, `updated_at` |
| `CompanyActivated` | `company_id`, `activated_by`, `activated_at` |
| `CompanyDeactivated` | `company_id`, `deactivated_by`, `reason`, `deactivated_at` |
| `CompanySuspended` | `company_id`, `suspended_by`, `reason`, `suspended_at` |
| `CompanySuspensionLifted` | `company_id`, `lifted_by`, `lifted_at` |
| `CompanyDeleted` | `company_id`, `deleted_by`, `reason`, `deleted_at`, `purge_scheduled_at` |
| `CompanyRestored` | `company_id`, `restored_by`, `restored_at` |
| `CompanyPermanentlyPurged` | `company_id`, `purged_at` |
| `CompanyLogoUploaded` | `company_id`, `logo_url`, `uploaded_by`, `uploaded_at` |
| `CompanyAdminChanged` | `company_id`, `previous_admin_id`, `new_admin_id`, `changed_by`, `changed_at` |

### 14.2 Event Envelope

All domain events MUST follow this envelope:

```
Event Envelope:
  event_id      UUID       Unique identifier for this event
  event_type    string     e.g., "CompanyCreated"
  aggregate_id  UUID       company_id
  aggregate_type string    "Company"
  occurred_at   datetime   UTC timestamp of occurrence
  version       integer    Schema version for forward compatibility
  payload       object     Event-specific data (see above)
  metadata      object     correlation_id, request_id, actor_id
```

### 14.3 Event Delivery Guarantee

- Phase 1: Events are written to an `outbox` table within the same database transaction as the state change (Transactional Outbox Pattern). A background relay process publishes them to the event bus.
- This guarantees at-least-once delivery with deduplication handled by consumers using `event_id`.

---

## 15. Reporting Requirements

The following reports are defined for future implementation (not in scope for Epic 3):

| Report | Description | Data Source |
|--------|-------------|-------------|
| Company Growth Report | New companies created per period | `companies.created_at` |
| Company Status Summary | Count of companies by status | `companies.status` |
| Geographic Distribution | Companies by country | `companies.country` |
| Tenant Health Dashboard | Company activity metrics per period | Cross-module data |
| Dormant Company Report | Companies inactive for 90+ days | `companies.updated_at`, `status` |
| Audit Activity Report | State changes per company over period | `company_audit_logs` |

---

## 16. Out of Scope

The following are explicitly **excluded** from Epic 3 and must not be designed or implemented in this epic:

| Excluded Area | Future Epic |
|--------------|-------------|
| Subscription management | Epic 8 – Billing |
| Payment processing | Epic 8 – Billing |
| Invoicing | Epic 9 – Accounting |
| Branch / Location management | Epic 10 – Branches |
| Warehouse management | Epic 11 – Warehouses |
| Inventory module | Epic 12 – Inventory |
| Sales orders | Epic 13 – Sales |
| Purchase orders | Epic 14 – Purchasing |
| Accounting / Chart of Accounts | Epic 9 – Accounting |
| CRM / Contacts | Epic 15 – CRM |
| HR / Payroll | Epic 16 – HR |
| AI features | Epic 20+ |
| Subdomain routing | Epic 7 – SaaS Platform |
| Custom domain provisioning | Epic 7 – SaaS Platform |
| White-label configuration | Epic 7 – SaaS Platform |
| Multi-entity consolidation | Epic 10 – Org Hierarchy |
| Role and permission management UI | Epic 5 – RBAC |
| User management | Epic 4 – Users |
| Dashboard and analytics | Epic 6 – Reports |
| Email notification templates | Epic 5 – Notifications |

---

## 17. Assumptions

The following assumptions were made in producing this specification:

| # | Assumption | Impact if Wrong |
|---|-----------|----------------|
| A-01 | The Auth module (Epic 2) provides a valid JWT containing `user_id`; the Companies module does not re-authenticate. | Companies module would need its own auth layer. |
| A-02 | A user is a member of a company via a separate `company_members` table managed by the Users/Auth module; this spec does not design that table. | Membership concept needs to be defined jointly with Epic 4. |
| A-03 | File storage for logos (S3-compatible object storage) is configured and available as an infrastructure dependency. | Logo upload feature requires infrastructure provisioning. |
| A-04 | An ISO 4217 currency table and IANA timezone table are maintained as embedded data (not fetched from external API) in Phase 1. | Would require external API integration for currency/timezone validation. |
| A-05 | In Phase 1, one user may be Owner of multiple companies; no upper limit is enforced in this epic. | If business decides to limit, a `COMPANY_LIMIT` config key is pre-architected. |
| A-06 | `super_admin` and `saas_admin` roles exist as defined role constants in the Auth/RBAC module and are available for authorization checks. | Companies module would need to define its own role hierarchy. |
| A-07 | The event bus / message queue infrastructure is not available in Phase 1; Transactional Outbox Pattern is used as the event delivery mechanism. | If event bus is available, direct publish can replace outbox. |
| A-08 | PostgreSQL is the database engine; JSONB, UUID, INET, and TIMESTAMPTZ types are available. | Schema changes required for other database engines. |

---

## 18. Acceptance Criteria

### AC-001 — Company Creation

- [ ] A POST request with valid required fields creates a company and returns 201 with a company object containing a UUID `id` and `status: pending_setup`.
- [ ] A duplicate legal name returns 409 with code `COMPANY_NAME_CONFLICT`.
- [ ] A `company_audit_logs` record with action `COMPANY_CREATED` is created.
- [ ] A `CompanyCreated` domain event is written to the outbox table.

### AC-002 — Company Uniqueness

- [ ] Two companies with identical legal names (regardless of case) cannot be created.
- [ ] Two companies with identical slugs cannot be created.
- [ ] The slug is automatically derived from the legal name and is globally unique.

### AC-003 — Company Profile Update

- [ ] A PATCH request from the Owner updates only the provided fields; unprovided fields are unchanged.
- [ ] A PATCH request from a `manager` role returns 403.
- [ ] Updating tax number or registration number by an Admin succeeds and persists correctly.
- [ ] A `COMPANY_UPDATED` audit log record captures changed fields (before and after).

### AC-004 — Status Transitions

- [ ] Owner can activate a `pending_setup` company once all required fields are set.
- [ ] Owner can deactivate an `active` company; a `reason` is required.
- [ ] Owner can reactivate an `inactive` company.
- [ ] A `suspended` company cannot be reactivated by the Owner; only SuperAdmin can lift suspension.
- [ ] Invalid status transitions return 409 with `INVALID_STATUS_TRANSITION`.
- [ ] Users cannot access resources of a `suspended` or `deleted` company.

### AC-005 — Soft Delete and Restore

- [ ] DELETE endpoint soft-deletes the company: sets `status: deleted` and `deleted_at`.
- [ ] Deleted company does not appear in standard GET or list queries.
- [ ] Company can be restored within 90 days; restored company has `status: inactive`.
- [ ] Company cannot be restored after 90 days; returns 410 `COMPANY_PURGED`.
- [ ] A `COMPANY_DELETED` audit log record is created with the deletion reason.
- [ ] A `COMPANY_RESTORED` audit log record is created upon restoration.

### AC-006 — Permissions

- [ ] `super_admin` can list all companies globally.
- [ ] Non-SuperAdmin users cannot access another company's data.
- [ ] `manager`, `accountant`, `sales`, `inventory` roles cannot update company profile.
- [ ] Tax number and registration number are masked (****) for non-owner, non-admin, non-accountant roles.

### AC-007 — Validation

- [ ] Legal name shorter than 2 characters returns 400 with `COMPANY_NAME_TOO_SHORT`.
- [ ] Legal name longer than 255 characters returns 400 with `COMPANY_NAME_TOO_LONG`.
- [ ] Invalid ISO 4217 currency code returns 400 with `CURRENCY_INVALID`.
- [ ] Invalid IANA timezone returns 400 with `TIMEZONE_INVALID`.
- [ ] Invalid ISO 3166-1 country code returns 400 with `COUNTRY_INVALID`.
- [ ] Logo file larger than 5 MB returns 400 with `LOGO_TOO_LARGE`.
- [ ] Logo file with mismatched content type returns 400 with `LOGO_INVALID_CONTENT`.

### AC-008 — Audit Logging

- [ ] Every state-changing operation produces a record in `company_audit_logs`.
- [ ] Audit log records are immutable — no UPDATE or DELETE is possible via the API.
- [ ] Audit log records include actor_user_id, ip_address, request_id, before_state, after_state.

### AC-009 — Domain Events

- [ ] Every state change produces a corresponding domain event in the outbox table.
- [ ] Each event contains the correct payload fields as defined in Section 14.

### AC-010 — Performance

- [ ] GET /companies/{id} returns within 200ms at p95 in a test environment with 10,000 company records.
- [ ] POST /companies returns within 1 second at p95 including uniqueness validation.
- [ ] Company list endpoint with 25 records returns within 500ms at p95.

### AC-011 — Security

- [ ] All endpoints return 401 when called without a valid access token.
- [ ] The `company_id` field in all responses is a UUID — never an auto-increment integer.
- [ ] Rate limit on company creation enforces max 10 per user per hour.

### AC-012 — Data Integrity

- [ ] Concurrent company creation with the same legal name results in exactly one success and one `COMPANY_NAME_CONFLICT` error.
- [ ] Slug is never updated after a company's first `active` transition; returns 422 `SLUG_IMMUTABLE` if attempted.

---

## 19. Future Enhancements

The following features are explicitly deferred to future epics. They are documented here to ensure the current design remains compatible:

| Enhancement | Deferred To | Design Note |
|------------|------------|-------------|
| Subdomain routing | Epic 7 | `slug` field is immutable and indexed; ready for DNS-based routing |
| Custom domain | Epic 7 | `custom_domain` field pre-added to schema; nullable |
| White-label branding | Epic 7 | `branding` expansion via `settings` JSONB |
| SaaS subscription tiers | Epic 8 | `subscription_id` FK pre-added to schema; nullable |
| Company limit per subscription | Epic 8 | `COMPANY_LIMIT` config key pre-architected |
| Ownership transfer | Epic 4 | `owner_id` is FK; transfer requires new audit event `COMPANY_OWNER_TRANSFER` |
| Multi-entity / Org hierarchy | Epic 10 | `organization_id` FK reserved in `settings.metadata` |
| Row Level Security (RLS) | Epic 7 | All tables have `company_id`; RLS policies can be added without schema changes |
| Multiple branches | Epic 10 | `Branch` entity uses FK `company_id` |
| Multiple warehouses | Epic 11 | `Warehouse` entity uses FK `company_id` |
| Multiple fiscal years | Epic 9 | `FiscalYear` entity uses FK `company_id` |
| Advanced audit search | Epic 6 | Audit log table is indexed; search layer can be added |
| Company merge | Future | Requires cross-module data migration tooling |
| Data export (GDPR) | Future | `company_id` scoping enables full tenant data export |
| Company-level feature flags | Future | Extensible via `settings` JSONB |

---

## 20. Success Criteria

### Measurable Outcomes

- **SC-001**: A business owner can create a fully configured Company and transition it to `active` status within 5 minutes.
- **SC-002**: Company detail pages load in under 200ms for 95% of requests under a load of 500 concurrent users.
- **SC-003**: 100% of state-changing company operations produce a corresponding audit log record — verified by automated test coverage.
- **SC-004**: Zero cross-tenant data leaks are detectable in security penetration testing of the Companies module API.
- **SC-005**: A SuperAdmin can locate any company by name within 3 seconds using the global company search.
- **SC-006**: All 12 acceptance criteria groups (AC-001 through AC-012) pass with zero failing assertions.
- **SC-007**: Company data remains fully intact and restorable after a simulated disaster recovery test within the 4-hour RTO.
- **SC-008**: The Companies module supports creation of 10,000 companies without schema changes or performance degradation beyond defined NFR thresholds.

---

*This specification is the Single Source of Truth (SSOT) for Epic 3 — Companies. All implementation, testing, and review work MUST reference this document. Any deviation requires an approved update to this specification before implementation proceeds.*
