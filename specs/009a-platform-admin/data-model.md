# Data Model: Epic 9A — Platform Administration / Super Admin

Full field-level detail for every entity introduced by `plan.md` §25. All tables inherit a lean `BaseModel` (`id: UUID` PK, `created_at`, `updated_at`) — **never** `TenantBaseModel`, since these are platform-scoped tables, not tenant-scoped ones. Tables that *reference* a tenant carry an explicit `company_id` FK, never implicit scoping via inheritance. Migration numbering per `plan.md` §33.

---

## Additive Columns on the Existing `companies` Table (migration 057)

Not new entities — two nullable scalar columns supporting tenant lifecycle and company-scoped access invalidation (`plan.md` §9.1, §10.2, ADR-12). Both are NULL for every existing row; no backfill.

| Field | Type | Notes |
|---|---|---|
| `pre_suspension_status` | varchar, nullable | The `CompanyStatus` held immediately before suspension. Set on suspend, read on reactivate, set back to NULL on successful reactivate. Never inferred from audit history. |
| `access_invalidated_at` | timestamptz, nullable | Company-scoped access watermark. Set on suspend; **deliberately never cleared**, so pre-suspension sessions stay refused for this company after reactivation (FR-9A-018). Compared at request time against **`Session.created_at`** (authentication time), *not* the access token's `iat` — a refresh reuses the same session and therefore cannot advance past the watermark (`plan.md` §10.2, ADR-6). |

**Constraints**:
- `CHECK ((status = 'suspended' AND pre_suspension_status IS NOT NULL) OR (status <> 'suspended' AND pre_suspension_status IS NULL))`
- `CHECK (pre_suspension_status IS NULL OR pre_suspension_status IN ('active','inactive'))`

**Migration preflight**: migration `057` must verify that **no** `companies.status = 'suspended'` row exists before creating the first constraint, and fail loudly with operator remediation guidance if any does — such a row's true prior status is unrecoverable and must never be fabricated (`plan.md` §33.1).

**No change to the existing auth schema**: authentication freshness reuses `Session.created_at`, which already exists via `BaseModel`. No new column on `sessions`/`refresh_tokens`, and no new JWT claim.

---

## Identity & Session (migration 057)

### `PlatformAdministrator` (table `platform_administrators`)
| Field | Type | Notes |
|---|---|---|
| `user_id` | UUID, FK → `users.id`, UNIQUE, NOT NULL | 1:1 with existing `User`; reuses credentials, never a second password system |
| `is_active` | bool, default `true` | Deactivation immediately invalidates sessions (BR-9A-011) |
| `last_login_at` | timestamptz, nullable | |
| `deactivated_at` | timestamptz, nullable | |
| `deactivated_by` | UUID, FK → `platform_administrators.id`, nullable | |

**Validation**: a `User` row may have at most one `PlatformAdministrator` row (UNIQUE on `user_id`). **Lifecycle**: created only via §7 bootstrap (first row) or `platform.admins.manage`-gated API (all subsequent rows) — never implicitly.

### `PlatformRole` (table `platform_roles`)
| Field | Type | Notes |
|---|---|---|
| `code` | string, UNIQUE, NOT NULL | e.g. `platform_owner`, `platform_operations_admin` |
| `name` | string, NOT NULL | Display name |
| `description` | text, nullable | |

**Validation**: `code` is configuration data, not an enum — new roles are addable without a migration (FR-9A-140 pattern, Constitution §46).

### `PlatformPermission` (table `platform_permissions`)
| Field | Type | Notes |
|---|---|---|
| `code` | string, PK | e.g. `platform.tenants.suspend` — mirrors tenant `Permission`'s code-as-PK convention |
| `label` | string, NOT NULL | |
| `area` | string, NOT NULL | Groups permissions per §8's permission-area table |
| `description` | text, nullable | |

### `PlatformRolePermission` (table `platform_role_permissions`)
| Field | Type | Notes |
|---|---|---|
| `role_id` | UUID, FK → `platform_roles.id`, CASCADE | |
| `permission_id` | string, FK → `platform_permissions.code`, RESTRICT | |

**Constraint**: UNIQUE(`role_id`, `permission_id`).

### `PlatformAdminRoleAssignment` (table `platform_admin_role_assignments`)
| Field | Type | Notes |
|---|---|---|
| `platform_administrator_id` | UUID, FK → `platform_administrators.id`, CASCADE | |
| `role_id` | UUID, FK → `platform_roles.id`, RESTRICT | |
| `assigned_by` | UUID, FK → `platform_administrators.id`, nullable | Null only for the bootstrap-created first assignment |
| `assigned_at` | timestamptz, NOT NULL | |

**Constraint**: UNIQUE(`platform_administrator_id`, `role_id`). Effective permissions = union across all assigned roles' permissions (FR-9A-142).

### `PlatformSession` (table `platform_sessions`)
| Field | Type | Notes |
|---|---|---|
| `platform_administrator_id` | UUID, FK → `platform_administrators.id`, CASCADE | |
| `is_revoked` | bool, default `false` | |
| `revoked_at` | timestamptz, nullable | |
| `ip_address` | inet, nullable | |
| `user_agent` | string, nullable | |
| `expires_at` | timestamptz, NOT NULL | |

**State transitions**: `active` → `revoked` (deactivation, logout, or admin-initiated revocation) — one-way, never un-revoked.

### `PlatformRefreshToken` (table `platform_refresh_tokens`)
| Field | Type | Notes |
|---|---|---|
| `session_id` | UUID, FK → `platform_sessions.id`, CASCADE | |
| `token_hash` | string, NOT NULL | SHA-256, raw token never persisted (mirrors tenant `refresh_tokens`) |
| `is_revoked` | bool, default `false` | |
| `revoked_at` | timestamptz, nullable | |
| `expires_at` | timestamptz, NOT NULL | |

### `PlatformAuditEvent` (table `platform_audit_events`)
| Field | Type | Notes |
|---|---|---|
| `actor_platform_administrator_id` | UUID, FK → `platform_administrators.id`, nullable | Null only for rare system-initiated events |
| `action` | string, NOT NULL, indexed | e.g. `tenant.suspend`, `plan.publish` |
| `target_type` | string, NOT NULL | |
| `target_id` | UUID, nullable | |
| `company_id` | UUID, FK → `companies.id`, nullable, indexed | Populated for tenant-scoped actions |
| `reason` | text, nullable | |
| `before_state` | jsonb, nullable | |
| `after_state` | jsonb, nullable | |
| `context` | jsonb, nullable | Includes `request_id` for correlation |
| `support_access_grant_id` | UUID, FK → `support_access_grants.id`, nullable | Links action-level entries to their owning support session (added migration 061) |
| `created_at` | timestamptz, NOT NULL, indexed | |

**Validation**: append-only — no `UPDATE`/`DELETE` route exists in the router (BR-9A-023). **Indexes**: `actor_platform_administrator_id`, `company_id`, `action`, `created_at` (FR-9A-200's filter set).

---

## Entitlement (migration 058)

### `Capability` (table `capabilities`)
| Field | Type | Notes |
|---|---|---|
| `key` | string, PK | e.g. `inventory`, `sales`, `purchase`, `accounting`, `crm` |
| `module` | string, NOT NULL | |
| `grain` | enum(`module`, `feature`), NOT NULL | Per Assumption A7 |
| `display_name` | string, NOT NULL | |
| `is_active` | bool, default `true` | |

### `Plan` (table `plans`)
| Field | Type | Notes |
|---|---|---|
| `code` | string, UNIQUE, NOT NULL | Configuration data, never hardcoded names (FR-9A-151) |
| `name` | string, NOT NULL | |
| `status` | string+CHECK(`draft`,`published`,`retired`), NOT NULL | Matches `Company.status`'s VARCHAR+CHECK convention, not a PG ENUM |
| `description` | text, nullable | |
| `is_commercially_available` | bool, default `false` | |
| `billing_cycle_metadata` | jsonb, nullable | Informational only (Assumption A5) |
| `pricing_metadata` | jsonb, nullable | Informational only |

### `PlanCapability` (table `plan_capabilities`)
| Field | Type | Notes |
|---|---|---|
| `plan_id` | UUID, FK → `plans.id`, CASCADE | |
| `capability_key` | string, FK → `capabilities.key`, RESTRICT | |
| `allowed` | bool, NOT NULL | The Plan Entitlement ceiling (§17.2's resolution table) |

**Constraint**: UNIQUE(`plan_id`, `capability_key`).

### `Subscription` (table `subscriptions`)
| Field | Type | Notes |
|---|---|---|
| `company_id` | UUID, FK → `companies.id`, RESTRICT, indexed | |
| `plan_id` | UUID, FK → `plans.id`, RESTRICT | |
| `status` | string+CHECK(`active`,`ended`), NOT NULL | `trial` deliberately excluded (resolved OQ-1); CHECK-only design means adding it later needs no schema redesign |
| `effective_date` | date, NOT NULL | |
| `ended_at` | timestamptz, nullable | |
| `actor_id` | UUID, FK → `platform_administrators.id`, NOT NULL | |
| `reason` | text, NOT NULL for administrative changes | |

**Constraint**: `CREATE UNIQUE INDEX ON subscriptions (company_id) WHERE status = 'active'` — enforces one active subscription per tenant at the DB level. Migration 058 also adds a real FK (`companies.subscription_id → subscriptions.id`) on the existing, currently-unused nullable column, used as a synced denormalized "current subscription" pointer (`plan.md` ADR-9).

---

## Quotas & Overrides (migration 059)

### `QuotaDefinition` (table `quota_definitions`)
| Field | Type | Notes |
|---|---|---|
| `key` | string, PK | `users`, `branches`, `transactions`, `storage`, `api_calls`, `ai_credits` |
| `display_name` | string, NOT NULL | |
| `unit` | string, NOT NULL | |
| `enforcement_style` | enum(`hard`,`soft`,`informational`), NOT NULL | BR-9A-030 — declared explicitly, never defaults silently |

### `PlanQuota` (table `plan_quotas`)
| Field | Type | Notes |
|---|---|---|
| `plan_id` | UUID, FK → `plans.id`, CASCADE | |
| `quota_key` | string, FK → `quota_definitions.key`, RESTRICT | |
| `limit_value` | numeric, nullable | **NULL means unlimited** (FR-9A-182) — never a large sentinel number |

**Constraint**: UNIQUE(`plan_id`, `quota_key`); `limit_value >= 0` CHECK where not null.

### `TenantQuotaOverride` (table `tenant_quota_overrides`)
| Field | Type | Notes |
|---|---|---|
| `company_id` | UUID, FK → `companies.id`, indexed | |
| `quota_key` | string, FK → `quota_definitions.key` | |
| `override_limit` | numeric, nullable | Null = unlimited override |
| `reason` | text, NOT NULL | |
| `actor_id` | UUID, FK → `platform_administrators.id`, NOT NULL | |
| `granted_at` | timestamptz, NOT NULL | |
| `expires_at` | timestamptz, nullable | Null = permanent, explicitly distinguishable (not implicit) |
| `revoked_at` | timestamptz, nullable | |
| `is_active` | bool, default `true` | |

**Constraint**: `CREATE UNIQUE INDEX ... ON tenant_quota_overrides (company_id, quota_key) WHERE is_active = true`; `expires_at > granted_at` CHECK where not null.

### `EntitlementOverride` (table `entitlement_overrides`)
| Field | Type | Notes |
|---|---|---|
| `company_id` | UUID, FK → `companies.id`, indexed | |
| `capability_key` | string, FK → `capabilities.key` | |
| `reason` | text, NOT NULL | |
| `actor_id` | UUID, FK → `platform_administrators.id`, NOT NULL | |
| `granted_at` | timestamptz, NOT NULL | |
| `expires_at` | timestamptz, nullable | |
| `revoked_at` | timestamptz, nullable | |
| `is_active` | bool, default `true` | |

**Constraint**: `CREATE UNIQUE INDEX ... ON entitlement_overrides (company_id, capability_key) WHERE is_active = true`.

---

## Usage & AI Readiness (migration 060)

### `UsageRecord` (table `usage_records`)
| Field | Type | Notes |
|---|---|---|
| `company_id` | UUID, FK → `companies.id`, indexed | |
| `metric_key` | string, FK → `quota_definitions.key` | |
| `quantity` | numeric, NOT NULL | |
| `period_start` | timestamptz, NOT NULL | |
| `period_end` | timestamptz, NOT NULL | |
| `source` | string, NOT NULL | Which computation produced this row |
| `recorded_at` | timestamptz, NOT NULL | |

**Note**: periodic/batch rows, not per-event streaming (`plan.md` §18). Absence of a current-period row is treated as `unavailable`, never silently zero.

### `AiCreditLedgerEntry` (table `ai_credit_ledger_entries`)
| Field | Type | Notes |
|---|---|---|
| `company_id` | UUID, FK → `companies.id`, indexed | |
| `delta` | numeric, NOT NULL | Signed — positive = credit grant, negative = usage debit |
| `reason` | text, nullable | Required when `actor_platform_administrator_id` is populated |
| `actor_platform_administrator_id` | UUID, FK → `platform_administrators.id`, nullable | Null = future automatic usage debit; populated = manual admin adjustment (FR-9A-233) |
| `platform_audit_event_id` | UUID, FK → `platform_audit_events.id`, nullable | Links manual adjustments to their audit record (BR-9A-027) |
| `provider` | string, nullable | Free-text/enum-ish — never structurally coupled (FR-9A-234) |
| `model` | string, nullable | |
| `input_tokens` | int, nullable | |
| `output_tokens` | int, nullable | |
| `total_tokens` | int, nullable | |
| `estimated_cost` | numeric, nullable | |
| `billable_cost` | numeric, nullable | |
| `occurred_at` | timestamptz, NOT NULL | |

**Derived**: current balance per company = `SUM(delta)`. Empty table until an AI capability epic exists (§19) — no zero-value placeholder rows.

---

## Support Access (migration 061)

### `SupportAccessGrant` (table `support_access_grants`)
| Field | Type | Notes |
|---|---|---|
| `platform_administrator_id` | UUID, FK → `platform_administrators.id`, indexed | |
| `company_id` | UUID, FK → `companies.id`, indexed | Exactly one target tenant per grant (FR-9A-191) |
| `reason` | text, NOT NULL | |
| `started_at` | timestamptz, NOT NULL | |
| `expires_at` | timestamptz, NOT NULL | No indefinite grant (FR-9A-193) |
| `ended_at` | timestamptz, nullable | |
| `ended_by` | UUID, FK → `platform_administrators.id`, nullable | |
| `status` | string+CHECK(`active`,`expired`,`terminated`), NOT NULL | |

**State transitions**: `active` → `expired` (lazy, checked at read time when `expires_at < now()`) or `active` → `terminated` (explicit action by initiator or a sufficiently-privileged admin). Both are terminal.

Migration 061 also adds `platform_audit_events.support_access_grant_id` (nullable FK) — see Identity & Session section above.
