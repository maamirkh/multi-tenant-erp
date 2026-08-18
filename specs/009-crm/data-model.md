# Data Model: Epic 9 — CRM

**Status**: Written at Epic closure (Phase 10, T103), derived directly from the implemented models under `backend/modules/crm/models/` — not written ahead of implementation. Mirrors Epic 8's `data-model.md` structure.

## Table of Contents

1. [Overview](#1-overview)
2. [Aggregate Roots](#2-aggregate-roots)
3. [Entities & Tables](#3-entities--tables)
4. [Domain Events](#4-domain-events)
5. [State Machines](#5-state-machines)
6. [Entity Relationships](#6-entity-relationships)
7. [Constraints Summary](#7-constraints-summary)
8. [Migration Strategy](#8-migration-strategy)

---

## 1. Overview

CRM introduces 8 new tables, all prefixed `crm_`, all inheriting `TenantBaseModel` (`id`, `company_id`, `created_at`, `updated_at`, `created_by`, `is_deleted`, `deleted_at`). Zero existing Epic 1–8 tables are altered. Two same-module tables (`crm_leads` ↔ `crm_opportunities`) have a documented circular FK, resolved via `ForeignKey(..., use_alter=True)` on `Lead.converted_opportunity_id`.

## 2. Aggregate Roots

Per plan.md §35, CRM has 5 aggregate roots, each owning its own transaction boundary and repository:

| Aggregate Root | Table | Child Entities |
|---|---|---|
| `Lead` | `crm_leads` | none (flat) |
| `Pipeline` | `crm_pipelines` | `PipelineStage` (`crm_pipeline_stages`) |
| `Opportunity` | `crm_opportunities` | none (flat — line detail belongs to Sales Quotation) |
| `Activity` | `crm_activities` | none (flat) |
| `LeadSource` | `crm_lead_sources` | none (lookup table) |

`CrmAuditLog` and `CrmFeatureFlag` are infrastructure tables, not domain aggregates.

## 3. Entities & Tables

### 3.1 `crm_lead_sources`

Company-configurable lookup for how a Lead was acquired.

| Column | Type | Notes |
|---|---|---|
| `code` | VARCHAR(30) | e.g. `WEBSITE`, `REFERRAL` |
| `name` | VARCHAR(100) | Display name |
| `is_active` | BOOLEAN | default `true` |

Constraints: `UNIQUE(company_id, code)`; index `(company_id, is_active)`.

### 3.2 `crm_leads`

The aggregate root for an unqualified prospect.

| Column | Type | Notes |
|---|---|---|
| `first_name`, `last_name`, `lead_company_name` | VARCHAR | at least one required |
| `email`, `phone`, `mobile` | VARCHAR | at least one of email/phone required |
| address fields | VARCHAR | optional |
| `source_id` | UUID FK → `crm_lead_sources` | nullable |
| `status` | VARCHAR(20) | `NEW`/`CONTACTED`/`QUALIFIED`/`UNQUALIFIED`/`CONVERTED`/`LOST`, default `NEW` |
| `score` | INTEGER | 0–100, nullable |
| `owner_id` | UUID (plain) | nullable, assigned salesperson |
| `last_contact_date`, `next_follow_up_date` | DATE | nullable |
| `qualification_notes`, `disqualification_reason` | TEXT | nullable |
| `converted_customer_id` | UUID (plain) | references `sales.customers.id`, no enforced cross-module FK |
| `converted_opportunity_id` | UUID FK → `crm_opportunities` (`use_alter=True`) | nullable |
| `converted_at` | TIMESTAMPTZ | nullable |
| `version` | INTEGER | optimistic lock, default `1` |

Constraints: status enum CHECK; score-range CHECK; name-or-company CHECK; email-or-phone CHECK; version ≥ 1 CHECK. Indexes: `(company_id, status)`, `(company_id, owner_id)`, `(company_id, next_follow_up_date)`, `(company_id, email)`.

### 3.3 `crm_pipelines`

| Column | Type | Notes |
|---|---|---|
| `name` | VARCHAR(100) | |
| `is_default` | BOOLEAN | default `false` |
| `is_active` | BOOLEAN | default `true` |

Constraint: partial unique index on `company_id` WHERE `is_default = true AND is_deleted = false` — at most one default pipeline per company (BR-008).

### 3.4 `crm_pipeline_stages`

| Column | Type | Notes |
|---|---|---|
| `pipeline_id` | UUID FK → `crm_pipelines` | |
| `name` | VARCHAR(100) | |
| `sequence` | INTEGER | ≥ 1 |
| `probability` | INTEGER | 0–100 default win probability |
| `is_won_stage`, `is_lost_stage` | BOOLEAN | default `false` |
| `is_active` | BOOLEAN | default `true` |

Constraints: sequence CHECK; probability-range CHECK; partial unique index per-pipeline on `is_won_stage=true` and separately on `is_lost_stage=true`. Index `(company_id, pipeline_id, sequence)`.

### 3.5 `crm_opportunities`

| Column | Type | Notes |
|---|---|---|
| `name` | VARCHAR(200) | |
| `customer_id` | UUID (plain) | references `sales.customers.id`, required, immutable |
| `owner_id` | UUID (plain) | required |
| `pipeline_id`, `stage_id` | UUID FK | required |
| `value` | NUMERIC(15,2) | ≥ 0, default `0` |
| `currency_code` | VARCHAR(3) | |
| `probability` | INTEGER | 0–100, inherited from stage, independently overridable |
| `expected_close_date` | DATE | nullable |
| `source_lead_id` | UUID FK → `crm_leads` | nullable, set on Lead-conversion origin |
| `status` | VARCHAR(10) | `OPEN`/`WON`/`LOST`, default `OPEN` |
| `lost_reason` | TEXT | required when LOST |
| `won_at`, `lost_at` | TIMESTAMPTZ | nullable |
| `quotation_id` | UUID (plain) | references `sales.sales_quotations.id`, set once linked |

`weighted_value` (`value * probability / 100`) is **not** a column — computed at read time (ADR-13). Constraints: value/probability/status CHECKs. Indexes: `(company_id, status)`, `(company_id, owner_id)`, `(company_id, customer_id)`, `(company_id, pipeline_id, stage_id)`, `(company_id, expected_close_date)`.

### 3.6 `crm_activities`

Single unified entity for calls/emails/meetings/tasks/notes/follow-ups.

| Column | Type | Notes |
|---|---|---|
| `activity_type` | VARCHAR(15) | `CALL`/`EMAIL`/`MEETING`/`TASK`/`NOTE`/`FOLLOW_UP` |
| `subject` | VARCHAR(300) | required |
| `description` | TEXT | nullable |
| `status` | VARCHAR(15) | `PLANNED`/`COMPLETED`/`CANCELLED`, default `PLANNED` |
| `priority` | VARCHAR(10) | `LOW`/`MEDIUM`/`HIGH`, default `MEDIUM` |
| `due_date`, `completed_at` | TIMESTAMPTZ | nullable; `completed_at` server-set only |
| `assigned_to` | UUID (plain) | required |
| `lead_id`, `customer_id`, `opportunity_id` | UUID FK / plain | all nullable, **at least one required** |

Constraint: `lead_id IS NOT NULL OR customer_id IS NOT NULL OR opportunity_id IS NOT NULL` (BR-006). Indexes: `(company_id, assigned_to, status)`, `(company_id, due_date)`, `(company_id, lead_id)`, `(company_id, customer_id)`, `(company_id, opportunity_id)`.

### 3.7 `crm_audit_log`

Append-only, no `update`/`delete` repository method exists.

| Column | Type |
|---|---|
| `entity_type` | VARCHAR(20) — `LEAD`/`OPPORTUNITY`/`ACTIVITY` |
| `entity_id` | UUID |
| `action` | VARCHAR(50) |
| `actor_user_id` | UUID (plain), nullable |
| `before_state`, `after_state` | JSONB, nullable |

Index: `(company_id, entity_type, entity_id)`.

### 3.8 `crm_feature_flags`

| Column | Type |
|---|---|
| `flag_key` | VARCHAR(50) — currently only `feature.crm.enabled` |
| `is_enabled` | BOOLEAN, default `false` |
| `description` | VARCHAR(500), nullable |

Constraint: `UNIQUE(company_id, flag_key)`.

## 4. Domain Events

12 events across 3 aggregates — see [`contracts/events.md`](contracts/events.md) for full payload schemas.

## 5. State Machines

**Lead** (spec.md §14.2): `NEW → CONTACTED → QUALIFIED → CONVERTED`, with `UNQUALIFIED`/`LOST` as off-ramps from any non-terminal state and `UNQUALIFIED → NEW` as the one manager-only reopen exception.

**Opportunity** (spec.md §17.2): `OPEN → WON | LOST`, both terminal — no stage/value edits once WON/LOST (BR-003).

**Activity**: `PLANNED → COMPLETED | CANCELLED`, both terminal; completing an Activity linked to a Lead cascades `Lead.last_contact_date` and, per BR-012, may auto-advance `Lead.status` from `NEW`/`CONTACTED` to `CONTACTED`.

## 6. Entity Relationships

```
LeadSource 1───* Lead
Lead 1───1 Opportunity        (converted_opportunity_id / source_lead_id, both nullable, set together)
Pipeline 1───* PipelineStage
Pipeline 1───* Opportunity
PipelineStage 1───* Opportunity
Opportunity *───1 Customer    (sales.customers, no enforced FK — cross-module boundary)
Lead *───0..1 Customer        (converted_customer_id, no enforced FK)
Activity *───0..1 Lead
Activity *───0..1 Customer    (no enforced FK)
Activity *───0..1 Opportunity
```

## 7. Constraints Summary

- 5 CHECK constraints (Lead status enum, Lead name-or-company, Lead email-or-phone, Opportunity value/probability/status, Activity type/status/priority/has-relation — grouped; see individual model files for the exact 8 physical CHECK constraints).
- 4 partial unique indexes (default pipeline, won-stage, lost-stage — both per-pipeline, lead-source code-per-company is a plain unique constraint not partial).
- 2 circular-FK resolutions via `use_alter=True` (`Lead.converted_opportunity_id`).
- Zero FK constraints across the CRM/Sales or CRM/Accounting module boundary — all cross-module references are plain UUID columns validated at the service layer (SEC-06/SEC-08), matching ADR-2/ADR-3's explicit boundary design.

## 8. Migration Strategy

- `055_crm_foundation.py` — creates all 8 tables, indexes, and constraints in one migration (single linear Alembic chain, `down_revision` chains from the last Epic 8 migration).
- `056_crm_permission_backfill.py` — idempotent backfill of the 19 new `crm.*` permissions and role-permission mappings for companies that existed before this epic shipped (mirrors the Epic 8 permission-backfill precedent).
- Both migrations verified upgrade/downgrade/upgrade in earlier phases (Phase 2); full-chain verification against a live Postgres instance is part of the deferred Epic-9-closure live-verification pass (see quickstart.md).
