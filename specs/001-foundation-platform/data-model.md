# Data Model: Foundation Platform (Phase 1 Output)

**Branch**: `001-foundation-platform`
**Date**: 2026-07-11

This document defines the data entities established in Epic 1. No business tables are created in this Epic. The data model defines the base class contracts that all future business entities inherit.

---

## Overview

Epic 1 does not create any business tables in PostgreSQL. The only database artifact from this Epic is the Alembic migration history table (`alembic_version`), created automatically by Alembic.

However, this Epic defines the **abstract base model contracts** that every future business table must follow. These contracts are enforced at the Python/SQLAlchemy level, not the database level (in this Epic).

---

## Abstract Entity: BaseModel

**Purpose**: Root base for all database entities. Provides identity and audit timestamps.
**SQLAlchemy**: `__abstract__ = True` — does not create a table.

| Field | Type | Nullable | Default | Notes |
|-------|------|----------|---------|-------|
| `id` | UUID | No | `gen_random_uuid()` | Primary key; server-generated |
| `created_at` | TIMESTAMPTZ | No | `NOW()` | UTC; server default; immutable after creation |
| `updated_at` | TIMESTAMPTZ | No | `NOW()` | UTC; auto-updated on every modification via SQLAlchemy `onupdate` |

**Validation Rules**:
- `id` is never supplied by the client; always generated server-side.
- `created_at` is immutable; the application never modifies it after insert.
- `updated_at` is maintained by the ORM `onupdate` hook; the application does not set it manually.

---

## Abstract Entity: TenantBaseModel

**Purpose**: Base for all business entities. Extends `BaseModel` with multi-tenant isolation and soft delete fields.
**SQLAlchemy**: `__abstract__ = True` — does not create a table.
**Extends**: `BaseModel`

| Field | Type | Nullable | Default | Notes |
|-------|------|----------|---------|-------|
| (all BaseModel fields) | — | — | — | Inherited |
| `company_id` | UUID | No | — | Required; identifies the owning tenant |
| `created_by` | UUID | Yes | `NULL` | References the creating user; nullable until User Management Epic |
| `is_deleted` | BOOLEAN | No | `False` | Soft delete flag; False = active |
| `deleted_at` | TIMESTAMPTZ | Yes | `NULL` | UTC timestamp of soft deletion |

**Validation Rules**:
- `company_id` is NEVER populated from client-supplied parameters; always from the authenticated session context.
- `company_id` cannot be null for any business entity.
- `is_deleted` and `deleted_at` must be consistent: if `is_deleted=True`, then `deleted_at` must be non-null; if `is_deleted=False`, then `deleted_at` must be null.
- Soft delete is performed by setting `is_deleted=True` and `deleted_at=utcnow()`.
- Hard delete is only permitted through explicitly authorized administrative operations.

**Future FK Constraints** (added in later Epics via Alembic migration):
- `company_id` → `companies.id` (added in Company Management Epic)
- `created_by` → `users.id` (added in User Management Epic)

---

## State Transitions: Soft Delete Lifecycle

```
Active (is_deleted=False, deleted_at=NULL)
        │
        │  soft_delete()
        ▼
Deleted (is_deleted=True, deleted_at=<timestamp>)
        │
        │  restore() [future, requires authorization]
        ▼
Active (is_deleted=False, deleted_at=NULL)
```

**Rules**:
- Standard list queries return only Active records.
- `BaseRepository.list(include_deleted=True)` returns all records (administrative use only).
- Deleted records are excluded from all foreign key lookups by default.
- Restoring a deleted record is an audited operation (future implementation).

---

## Query Scope Model

All data access in the platform is scoped by `company_id`. This is the fundamental multi-tenant isolation guarantee.

```
Every Query
    └── WHERE company_id = <authenticated_tenant_id>
         AND is_deleted = False  ← (unless include_deleted=True)
```

No query may retrieve records across different `company_id` values. The `BaseRepository` enforces this by making `company_id` a mandatory parameter on all data access methods.

---

## Alembic Migration Baseline

**Migration**: `001_initial_baseline`
**Purpose**: Establishes the Alembic migration history with an empty schema.
**Upgrade**: No-op (baseline only).
**Downgrade**: No-op.

This migration exists so that the migration history is clean from the start. Future migrations add business tables sequentially.

---

## Future Entity Previews (Out of Scope for Epic 1)

The following entities will be defined in future Epics. They are listed here to confirm that `TenantBaseModel` is designed to accommodate them correctly.

| Future Entity | Epic | Key FK Dependencies |
|---------------|------|---------------------|
| `Company` | Company Management | (no company_id FK — Company IS the tenant) |
| `User` | User Management | `company_id → companies.id` |
| `Branch` | Multi-Branch (future) | `company_id → companies.id` |
| `SubscriptionPlan` | SaaS (future) | Platform-level (no company_id) |
| `CompanyPlan` | SaaS (future) | `company_id → companies.id` |
| `Product` | Inventory | `company_id → companies.id` |
| `Customer` | CRM | `company_id → companies.id` |

All business entities follow `TenantBaseModel`. The FK constraints are added via Alembic migrations in their respective Epics.
