# Epic 9A — Platform Administration / Super Admin: Official Business Specification

**Feature Branch**: `009a-platform-admin`
**Epic Sequence**: Inserted after completed **Epic 8 — Accounting & Finance**, alongside **Epic 9 — CRM** (in progress, not yet completed — see [§8 Assumptions](#8-assumptions)), and before **Epic 10 — Installments**. No existing Epic is renumbered.
**Created**: 2026-08-18
**Status**: Complete — all Open Questions resolved 2026-08-19, ready for `/sp.plan`
**Input**: User description — "Epic 9A — Platform Administration / Super Admin: create the complete Specification for the DevSphere ERP SaaS Platform Administration / SaaS Control Plane capability."

---

## Table of Contents

1. [Epic Title & Metadata](#1-epic-title--metadata)
2. [Purpose / Executive Summary](#2-purpose--executive-summary)
3. [Problem Statement](#3-problem-statement)
4. [Goals](#4-goals)
5. [Non-Goals](#5-non-goals)
6. [Actors & Trust Boundaries](#6-actors--trust-boundaries)
7. [Scope](#7-scope)
8. [Assumptions](#8-assumptions)
9. [Dependencies](#9-dependencies)
10. [User Stories with Priority](#10-user-stories-with-priority)
11. [Acceptance Scenarios](#11-acceptance-scenarios)
12. [Functional Requirements](#12-functional-requirements)
13. [Business Rules](#13-business-rules)
14. [Tenant Lifecycle Requirements](#14-tenant-lifecycle-requirements)
15. [Platform RBAC Requirements](#15-platform-rbac-requirements)
16. [Plan & Subscription Requirements](#16-plan--subscription-requirements)
17. [Entitlement & Quota Requirements](#17-entitlement--quota-requirements)
18. [Support/Cross-Tenant Access Requirements](#18-supportcross-tenant-access-requirements)
19. [Audit & Security Requirements](#19-audit--security-requirements)
20. [Usage & AI Readiness Requirements](#20-usage--ai-readiness-requirements)
21. [Operational Monitoring Requirements](#21-operational-monitoring-requirements)
22. [Edge Cases](#22-edge-cases)
23. [State Transitions](#23-state-transitions)
24. [Non-Functional Requirements](#24-non-functional-requirements)
25. [Success Criteria](#25-success-criteria)
26. [Integration Boundaries](#26-integration-boundaries)
27. [Out of Scope](#27-out-of-scope)
28. [Risks](#28-risks)
29. [Open Questions / Clarifications (Resolved 2026-08-19)](#29-open-questions--clarifications)
30. [Constitution Compliance / Traceability](#30-constitution-compliance--traceability)

---

## 1. Epic Title & Metadata

| Field | Value |
|---|---|
| Epic ID | 9A |
| Epic Title | Platform Administration / Super Admin |
| Epic Type | SaaS Control Plane (cross-cutting platform capability, not a tenant-facing business module) |
| Inserted Between | Epic 8 (Accounting & Finance, complete) and Epic 10 (Installments, not started) |
| Concurrent Epic | Epic 9 (CRM) — in progress on a separate branch; Epic 9A does not depend on Epic 9 and does not block it |
| Constitution Version | v1.2.1 |
| Primary Constitution Anchor | §50 Platform Administration & SaaS Control Plane Principles |
| Owning Layer | New platform-level module(s) within the existing Modular Monolith (§5) — not a separate system, not a microservice |

---

## 2. Purpose / Executive Summary

DevSphere ERP is architected from Day One as a multi-tenant SaaS platform (§9, §37 of the Constitution), but the codebase currently has **no functioning operator of that platform**. A `super_admin` string check exists in three independently-declared locations (`companies/dependencies.py`, `companies/router.py`, `accounting/services/permission_check.py`), and one real SuperAdmin-guarded endpoint exists (`GET /admin/companies`) — but the authenticated-user object that carries roles (`CurrentUser`) is hardcoded to `roles=[]` on every real request (`backend/core/auth/dependencies.py:112`). **In the shipped system today, it is not possible for any real user to become a super_admin.** Every test that exercises SuperAdmin behavior does so by overriding the FastAPI dependency injection with a fake user — never through the real authentication path.

Separately, the SaaS commercialization model required by Constitution §37 (subscription plans, company plans, entitlements, quotas, usage limits, billing hooks) has **zero implementation** beyond a single nullable `subscription_id` placeholder column on `Company` and one unused exception class (`ActiveSubscriptionError`). Tenant suspension — the one lifecycle capability the data model already reserves for a Platform Admin (`CompanyStatus.suspended`, documented as "(SuperAdmin only)" in `companies/models/enums.py`) — has no service method, no API endpoint, and its domain events (`CompanySuspendedEvent`, `CompanySuspensionLiftedEvent`) are defined but never fired.

**Epic 9A's purpose is to close this gap**: establish Platform Administration as a real, reachable, least-privilege, fully-audited actor — distinct from Company/Tenant Administration at every layer — and give it the operational control plane the Constitution already promises: tenant lifecycle governance, a genuine Platform RBAC model, SaaS plan and subscription administration, feature entitlements and quotas, explicit audited cross-tenant support access, platform audit/security oversight, and operational health visibility. Epic 9A also establishes provider-neutral readiness for future AI usage/credit tracking without implementing an AI provider.

This is a Specification only. No implementation, migration, or code change is performed as part of this document.

---

## 3. Problem Statement

1. **No reachable Platform Admin identity.** The only "super_admin" mechanism is a JWT-roles-list string check, and the roles list is never populated in production. There is no account lifecycle, no way to grant or revoke platform authority, and no dedicated Platform Admin session concept.
2. **No real Platform RBAC.** A single boolean-like "is super_admin or not" check is the entire authorization model. There is no least-privilege model, no granular permission areas, and no way to create a read-only analyst or a billing-only operator without granting full authority.
3. **Tenant lifecycle is incomplete and partially unreachable.** `CompanyStatus.suspended` is modeled, documented as Platform-Admin-only, and already enforced on the *read* side (`CompanySuspendedError` blocks a suspended tenant), but nothing can ever set that status — the write side does not exist.
4. **SaaS commercialization has no control plane.** Plans, entitlements, quotas, and subscriptions are constitutional aspiration only; there is no way to define a plan, assign it to a tenant, or determine what a tenant is entitled to.
5. **No audited cross-tenant support pathway.** Constitution §9 already requires that "admin access to tenant data uses separate, audited pathways," but no such pathway is implemented; the only cross-tenant capability today is a read-only company list.
6. **No consolidated platform-level audit or operational visibility.** Three separate, tenant/system-scoped audit tables exist (auth, companies, accounting) with no cross-tenant, actor-centric view suitable for a platform operator.
7. **Naming and scaffolding inconsistencies already exist** (e.g. `SUPER_ADMIN` uppercase in `purchase/router.py` vs. `super_admin` lowercase everywhere else; a frontend "admin" page that calls a non-existent endpoint) that a real Platform RBAC model must not perpetuate.

Epic 9A resolves these by specifying — at the business/requirements level — what Platform Administration must do, who may do it, and how it stays provably separate from tenant authority.

---

## 4. Goals

- G1: Establish Platform Administration as a distinct, reachable, least-privilege actor, never conflatable with Company/Tenant Administration.
- G2: Provide complete, auditable tenant lifecycle governance built on the already-modeled `CompanyStatus` values, closing the "suspend/reactivate" implementation gap.
- G3: Provide a genuine Platform RBAC model (granular permission areas, configurable role-to-permission bundles) replacing the single super_admin string check.
- G4: Provide the SaaS plan and subscription administration control plane required by Constitution §37, operationalizing what has so far been aspiration-only.
- G5: Provide deterministic feature entitlement and quota behavior, resolving conflicts between plan rules and the existing per-module tenant feature-toggle tables.
- G6: Provide an explicit, time-bounded, fully audited cross-tenant support access workflow — never silent impersonation.
- G7: Provide Platform Admin visibility into audit, security, and operational health, proportionate to the current Modular Monolith architecture.
- G8: Establish provider-neutral readiness for AI usage/credit tracking and future billing integration, without building either.
- G9: Make DevSphere ERP operationally ready for SaaS commercialization, clearly labeling what is in scope now vs. future-ready vs. explicitly out of scope.

---

## 5. Non-Goals

- Epic 9A does NOT implement a payment gateway, invoicing/billing system, or any real money movement for SaaS subscriptions.
- Epic 9A does NOT implement an AI provider, model, or OpenClaw/LLM integration.
- Epic 9A does NOT implement unrestricted user impersonation ("login as user").
- Epic 9A does NOT redesign tenant-level (Company/Tenant Admin) RBAC, authentication, or Better Auth/JWT infrastructure — it consumes and extends them.
- Epic 9A does NOT introduce microservices, Kubernetes, a separate identity server, or a data warehouse.
- Epic 9A does NOT grant Platform Admins unrestricted browsing/editing of tenant business transactions (invoices, journal entries, sales orders, etc.).
- Epic 9A does NOT fix pre-existing, unrelated defects discovered during research (e.g., the missing role/permission checks on the four modules' feature-flag endpoints, or the frontend admin page calling a non-existent endpoint) — these are flagged in [§28 Risks](#28-risks) as adjacent findings for separate remediation, not resolved by this Epic.

---

## 6. Actors & Trust Boundaries

### 6.1 Actor Definitions

| Actor | Authority Boundary | Identity Source |
|---|---|---|
| **Platform Admin** (any of the candidate roles in [§15](#15-platform-rbac-requirements)) | Operates the DevSphere ERP platform itself, across all tenants. Never scoped to a single `company_id`. | Platform Administrator Account ([§14.4](#144-platform-administrator-accounts)) — independent of any tenant membership. |
| **Company/Tenant Admin** (existing `owner`/`admin` tenant roles) | Operates only within their own company (`company_id`-scoped), per Constitution §9. | Tenant `CompanyMember` row + tenant role, exactly as today. |
| **Tenant User** (existing `manager`/`accountant`/…/`viewer` roles) | Operates only within their own company, further restricted by tenant permission grants. | Tenant `CompanyMember` row, exactly as today. |

### 6.2 Trust Boundary Diagram

```
                    DEVSPHERE ERP PLATFORM

                Platform Administration
                / SaaS Control Plane
                         │
          ┌──────────────┼──────────────┐
          │              │              │
       Tenant A       Tenant B       Tenant C
          │              │              │
     Company Admin   Company Admin   Company Admin
          │              │              │
       ERP Users      ERP Users      ERP Users
```

Platform Administration governs the platform. Company Administration governs the company. Tenant users operate the ERP. **These authority levels MUST NOT collapse into one RBAC/session model** (Constitution §50).

### 6.3 Trust Boundary Rules

- BR-9A-001 (see [§13](#13-business-rules)): A Company/Tenant Admin MUST NOT gain Platform Admin capability through tenant roles, tenant permissions, tenant sessions, tenant API endpoints, feature toggles, subscription plans, or manipulated tenant context.
- A Platform Admin account MUST NOT implicitly gain access to a tenant's business data merely by having platform authority — cross-tenant business-data access requires the explicit privileged pathway in [§18](#18-supportcross-tenant-access-requirements).
- A Platform Admin session/token MUST be structurally distinguishable from a tenant session/token (different claim namespace or token type), so that no tenant-scoped code path can accidentally honor platform authority, and no platform-scoped code path can accidentally honor a tenant session.

---

## 7. Scope

### 7.1 In Scope (This Epic)

1. Platform Dashboard (visibility only, read aggregates from existing/new platform data)
2. Tenant/Company lifecycle administration — specifically completing the Suspend/Reactivate pathway already reserved for SuperAdmin in the data model, plus read/inspect access to all `CompanyStatus` values
3. Tenant Detail / 360° administrative view (read-only aggregation, no business-record browsing)
4. Platform Administrator account management (create, assign role, deactivate, revoke)
5. Platform-level RBAC (granular permission areas, configurable roles)
6. SaaS Plan management (define, publish, retire plans)
7. Subscription administration (assign/change a tenant's plan, view subscription status/history)
8. Feature entitlements (plan-derived + tenant-toggle interaction rules, optional time-boxed override)
9. Quotas & usage limits (definition, current-usage visibility, threshold behavior)
10. Platform-level feature availability controls
11. Platform audit & security oversight (cross-tenant, actor-centric view)
12. Explicit, time-bounded, audited cross-tenant support access
13. Platform usage/metering visibility (tenant-scoped, billing-suitable, not real-time analytics infrastructure)
14. AI usage/credit readiness (schema/requirements-level only, provider-neutral, no provider integration)
15. Platform health & operational monitoring (built on the existing `/health`, `/health/live`, `/health/ready` endpoints)
16. Platform-wide configuration (distinct from tenant business configuration)
17. Administrative notifications/alerts (requirements and integration boundary only, not a full notification product)
18. Commercialization readiness labeling (in-scope-now vs. foundation vs. out-of-scope)

### 7.2 Out of Scope

See [§27](#27-out-of-scope) for the complete, itemized list.

---

## 8. Assumptions

- **A1 — Epic 9 (CRM) is not actually complete.** The instruction that Epic 9A is "inserted after completed Epic 9" reflects the intended epic *sequence*, not literal completion status: repository inspection confirms Epic 9 (CRM) is mid-development on a separate branch (uncommitted work), not merged or closed. Epic 9A has no functional dependency on CRM and does not need Epic 9 to be complete to proceed; the sequence numbering (9 → 9A → 10) is preserved regardless.
- **A2 — "Deactivated" maps to the existing `inactive` status, and remains Owner-controlled.** The existing `CompanyStatus` enum already models 5 states (`pending_setup`, `active`, `inactive`, `suspended`, `deleted`) with documented transition ownership: `active↔inactive` and `active/inactive→deleted` are Owner-only; `active/inactive↔suspended` are documented SuperAdmin-only. Epic 9A reuses this exactly — Platform Admin's tenant-lifecycle write authority is scoped to **Suspend** and **Reactivate (lift suspension)** only. Platform Admin does not gain new authority over `inactive` (owner deactivation) or `deleted` (owner soft-delete); it retains read/inspect visibility into those states. This is the "reasonable default" that avoids contradicting the already-implemented and documented model.
- **A3 — Trial tenants are confirmed future-ready only; not implemented in this Epic.** No trial concept exists in the codebase today. Per resolved [OQ-1](#29-open-questions--clarifications) (decided 2026-08-19), Epic 9A does not implement a trial subscription state now — only `active` and `ended` are mandatory-now subscription states ([§23.2](#232-subscription-lifecycle-new--minimal-model)). The Plan/Subscription data model MUST remain extensible enough to add `trial` later without a breaking redesign (FR-9A-130).
- **A4 — Platform Admin identity is a new, first-class concept**, not a repurposing of the existing (effectively dead) `super_admin` JWT-role-string check. The existing check is treated as legacy scaffolding to be superseded, not extended, because it is provably unreachable in production (`CurrentUser.roles` is always `[]`).
- **A8 — The very first Platform Owner account is bootstrapped out-of-band, never through the normal account-creation API.** Per resolved [OQ-5](#29-open-questions--clarifications), every in-app path to create a Platform Administrator account requires an already-authenticated Platform Admin holding `platform.admins.manage` (BR-9A-012) — a self-referential bootstrap problem for the very first account. Epic 9A resolves this by requiring a one-time, out-of-band seed/migration mechanism (outside the normal API) to provision the first Platform Owner. See [FR-9A-036](#124-platform-administrator-accounts) and [BR-9A-031](#13-business-rules).
- **A5 — Money/pricing metadata for plans is descriptive only in this Epic.** Since billing/payment processing is explicitly out of scope, any price fields on a Plan are informational metadata for future billing integration, not a chargeable contract.
- **A6 — Existing per-module feature-flag tables (`inventory_feature_flags`, `sales_feature_flags`, `purchase_feature_flags`, `accounting_feature_flags`) remain the tenant-toggle layer** referenced throughout this spec as "Tenant Feature Toggle" (Constitution §11); Epic 9A does not replace them, it adds the Plan Entitlement layer above them and defines the interaction rules between the two (see [§17](#17-entitlement--quota-requirements)).
- **A7 — "Module" and "feature" are treated as distinct granularities**: a *module* (e.g., CRM, Installments) is either entitled to a tenant or not (Plan Entitlement); a *feature* (e.g., `inventory.product_variants`) is a finer-grained tenant-toggle within an entitled module.

---

## 9. Dependencies

### 9.1 Existing Dependencies (Reused, Not Redefined)

| Dependency | Source | What Epic 9A Reuses |
|---|---|---|
| Multi-tenant isolation model | Companies module, Constitution §9 | `company_id` scoping pattern; Epic 9A's platform-level tables are the only tables in the system intentionally *not* `company_id`-scoped |
| `Company` model & `CompanyStatus` enum | `backend/modules/companies/models/company.py`, `enums.py` | The 5-state lifecycle, and its already-documented (but unimplemented) SuperAdmin-only suspend/reactivate transitions |
| `CompanySuspendedEvent` / `CompanySuspensionLiftedEvent` | `backend/modules/companies/events.py` | Existing, currently-unused domain event classes to be wired to real producers |
| `CompanySuspendedError` | `backend/modules/companies/exceptions.py` | Already enforced on tenant access; Epic 9A supplies the missing write path that sets the status this exception guards against |
| Users & Roles / RBAC infrastructure | `backend/modules/users_roles/` | The `SYSTEM_ROLES` / `Permission` / `RolePermission` modeling *pattern* is reused conceptually for Platform RBAC, kept as a structurally separate model per Constitution §50 |
| Authentication (JWT-based, Better-Auth-branded per Constitution §16/§6.3) | `backend/modules/auth/`, `backend/core/auth/` | Session model, session revocation (`is_revoked`/`revoked_at`), and the authentication boundary itself. Epic 9A does not replace authentication. |
| Audit trail infrastructure | `auth.audit_logs`, `companies.company_audit_logs`, `accounting.accounting_audit_log` | The append-only who/what/when/before/after/context schema pattern (Constitution §35) that platform-level audit must also follow — "no separate, parallel audit mechanism is introduced" (Constitution §50) |
| Feature toggle infrastructure | Per-module feature-flag tables (inventory, sales, purchase, accounting) | The Tenant Feature Toggle layer that Plan Entitlements must resolve against |
| Health endpoints | `GET /api/v1/health`, `/health/live`, `/health/ready` | The operational signal source for the Platform Health dashboard |
| Transactional outbox / event pattern | `backend/core/events/outbox.py`, `relay.py` | The durable-event pattern platform notifications should prefer, acknowledging the relay is currently a logging-only stub |
| SaaS Readiness principle | Constitution §37 | The plan/company-plan/quota/limit concept this Epic operationalizes |

### 9.2 New Requirements Introduced by Epic 9A

- A real, reachable Platform Administrator identity and account lifecycle (does not exist today in any reachable form).
- A dedicated Platform RBAC model (permission areas, roles) — today only a single string check exists, and it is unreachable.
- SaaS Plan and Subscription data concepts — today only a null placeholder column exists.
- Feature Entitlement resolution logic spanning Plan + Tenant Toggle + Override — does not exist today.
- Quota/usage-limit definition and enforcement-readiness — does not exist today.
- Explicit, audited, time-bounded cross-tenant support access workflow — does not exist today (only a read-only tenant list exists).
- A platform-level, cross-tenant, actor-centric audit view — does not exist today (three tenant/system-scoped audit tables exist independently).
- Platform-wide configuration governance, distinct from tenant business configuration — does not exist today.
- AI usage/credit readiness schema-level requirements — does not exist today.

---

## 10. User Stories with Priority

### US-1 (P1) — Platform Admin views the platform overview

**Actor**: Platform Admin (any role with `platform.dashboard.view`)
**Preconditions**: Actor holds an active Platform Administrator account with a valid platform session.
**Trigger**: Actor navigates to the Platform Dashboard.
**Main Flow**: System resolves the actor's platform permissions → aggregates tenant counts by status, plan distribution, subscription-status distribution, usage/limit warnings, recent tenant registrations, recent administrative actions, security-sensitive events, and a platform health summary → renders the dashboard.
**Alternative/Error Flows**: Any aggregate source unavailable (e.g., health check failing) → that widget shows an explicit "unavailable" state; the rest of the dashboard still renders. Actor has `platform.dashboard.view` but not, say, `platform.audit.read` → the "recent administrative actions" and "security-sensitive events" widgets are omitted (not shown empty, not shown erroring — omitted, consistent with least privilege).
**Authorization**: `platform.dashboard.view`.
**Audit**: Viewing the dashboard is not itself an audited mutation; the underlying widgets surface already-audited events.
**Acceptance Scenarios**:
1. **Given** an authenticated Platform Admin with `platform.dashboard.view`, **When** they load the dashboard, **Then** they see tenant counts (total/active/suspended/inactive/deleted), recent registrations, and a platform health summary, each attributed to real underlying data.
2. **Given** a Platform Admin with only `platform.dashboard.view` and no `platform.audit.read`, **When** they load the dashboard, **Then** audit/security widgets are omitted rather than shown with masked or empty data.
3. **Given** the database health check is degraded, **When** the dashboard loads, **Then** the health summary widget shows an explicit "degraded/unavailable" state rather than stale or default data.

---

### US-2 (P1) — Platform Admin searches and inspects tenants

**Actor**: Platform Admin with `platform.tenants.read`.
**Preconditions**: One or more companies exist in the system.
**Trigger**: Actor opens the Tenant list and searches/filters/sorts.
**Main Flow**: Actor searches by name/slug/status/plan → paginated results return, respecting search/filter/sort/pagination requirements in [§14](#14-tenant-lifecycle-requirements) → actor opens a tenant's 360° detail view.
**Alternative/Error Flows**: No matches → explicit empty state, not an error. Underlying usage-metering source unavailable for a given tenant → that section of the detail view shows "usage data unavailable," the rest of the view still renders.
**Authorization**: `platform.tenants.read`.
**Audit**: Read access to the tenant list/detail is logged only at a coarse (non-per-view) level consistent with Constitution §22 request logging; it is not treated as a "sensitive action" requiring the full audit schema, because it exposes only the same aggregate/summary fields already visible on the dashboard — not tenant business records.
**Acceptance Scenarios**:
1. **Given** a Platform Admin searches for a tenant by partial legal name, **When** results return, **Then** matching tenants are shown with status, plan, and creation date, paginated.
2. **Given** a Platform Admin opens a tenant's detail view, **When** the view renders, **Then** it shows company identity, status, plan, subscription status, entitlements, usage-against-limits, user count, lifecycle history, and platform administrative actions — and does NOT expose tenant business transactions (invoices, journal entries, sales orders, inventory records).
3. **Given** a tenant-scoped user attempts to call the tenant-detail platform endpoint using their tenant session, **When** the request is evaluated, **Then** it is rejected with an authorization error — the endpoint is unreachable from a tenant-scoped session regardless of the tenant role held.

---

### US-3 (P1) — Authorized Platform Admin changes tenant lifecycle status

**Actor**: Platform Admin with `platform.tenants.suspend` and/or `platform.tenants.reactivate`.
**Preconditions**: Target tenant exists; actor holds the specific permission for the requested transition.
**Trigger**: Actor initiates Suspend (from `active` or `inactive`) or Reactivate (from `suspended`).
**Main Flow**: Actor selects action → system requires confirmation + mandatory reason → system validates the transition is currently allowed → system updates `CompanyStatus`, fires the corresponding domain event (`CompanySuspendedEvent`/`CompanySuspensionLiftedEvent`), and writes a full audit record (who/what/when/before/after/context, including the reason) → tenant access is immediately affected per [§14.3](#143-effect-of-suspension-on-access-and-data).
**Alternative/Error Flows**: Reason omitted → rejected with a validation error before any state change. Transition not currently allowed (e.g., suspend an already-suspended tenant) → rejected with a specific, non-generic error (see [Edge Cases](#22-edge-cases)). Audit write fails → the state change MUST NOT be considered committed (see [BR-9A-024](#13-business-rules)).
**Authorization**: `platform.tenants.suspend` (for suspend), `platform.tenants.reactivate` (for reactivate) — modeled as separate permissions so an operator can hold one without the other.
**Audit**: Full audit record mandatory (Constitution §35 schema), including the mandatory reason as part of `context` or `metadata`.
**Acceptance Scenarios**:
1. **Given** an `active` tenant and a Platform Admin with `platform.tenants.suspend`, **When** they suspend it with a reason, **Then** the tenant's status becomes `suspended`, tenant users immediately lose access on their next request, and an audit record is written with before=`active`, after=`suspended`, and the reason.
2. **Given** a `suspended` tenant, **When** a Platform Admin without `platform.tenants.reactivate` attempts to reactivate it, **Then** the request is rejected with an authorization error and no state change occurs.
3. **Given** a Platform Admin submits a suspend request with no reason, **When** the request is validated, **Then** it is rejected before any state change, and no audit record (other than the rejected-attempt itself, per [§19](#19-audit--security-requirements)) is written.

---

### US-4 (P2) — Platform Admin manages SaaS plans

**Actor**: Platform Admin with `platform.plans.manage`.
**Trigger**: Actor creates, updates, publishes, or retires a Plan.
**Main Flow**: Actor defines plan name, description, commercial availability, enabled modules, user/branch/transaction/storage/API limits, and AI allowance readiness → system validates → plan is saved in Draft or Published state → audit record written. (Trial configuration is explicitly excluded from this Epic per resolved [OQ-1](#29-open-questions--clarifications) — future-ready only.)
**Alternative/Error Flows**: Attempt to retire a plan still assigned to active tenants → allowed, but existing assignments are unaffected until an explicit subscription change is made for each tenant (retirement blocks *new* assignments only — see [BR-9A-018](#13-business-rules)).
**Authorization**: `platform.plans.manage` for writes; `platform.plans.read` for read-only visibility (e.g., for a Billing/Subscription Admin who did not receive `.manage`).
**Audit**: Full audit record for create/update/publish/retire.
**Acceptance Scenarios**:
1. **Given** a Platform Admin with `platform.plans.manage`, **When** they publish a new plan with defined module entitlements and limits, **Then** the plan becomes assignable to tenants and is visible to actors with `platform.plans.read`.
2. **Given** a plan currently assigned to 12 active tenants, **When** a Platform Admin retires it, **Then** those 12 tenants keep their current entitlements unchanged, but the plan no longer appears as an option for new subscription assignments.

---

### US-5 (P2) — Platform Admin assigns/changes tenant subscriptions

**Actor**: Platform Admin with `platform.subscriptions.manage`.
**Trigger**: Actor assigns a plan to a tenant, or changes an existing assignment (upgrade/downgrade/cancel-readiness).
**Main Flow**: Actor selects tenant + target plan → system validates the tenant's current usage against the target plan's limits → if usage exceeds target limits, system surfaces the conflict (see [Edge Cases](#22-edge-cases)) and requires explicit administrative acknowledgment to proceed → subscription is updated, effective date recorded → audit record written → tenant's entitlements are re-resolved on next access.
**Authorization**: `platform.subscriptions.manage`.
**Audit**: Full audit record including before/after plan, effective date, and actor.
**Acceptance Scenarios**:
1. **Given** a tenant on Plan A with 40 users, **When** a Platform Admin assigns Plan B with a 25-user limit, **Then** the system surfaces the over-limit conflict and requires explicit acknowledgment before the change is applied; once applied, the tenant is flagged as over its new user quota (soft/informational per [§17](#17-entitlement--quota-requirements)), not silently truncated.
2. **Given** a tenant with no current subscription, **When** a Platform Admin assigns a plan for the first time, **Then** the subscription becomes `active` as of the effective date and the tenant's entitlements reflect the new plan immediately.

---

### US-6 (P2) — Platform Admin manages tenant entitlements/limits

**Actor**: Platform Admin with `platform.entitlements.override` or `platform.quotas.override`.
**Trigger**: Actor grants a temporary entitlement override or adjusts a quota for a specific tenant, outside the tenant's plan defaults.
**Main Flow**: Actor selects tenant + entitlement/quota + reason + optional expiry → system validates permission → override recorded and takes effect immediately → audit record written.
**Alternative/Error Flows**: Override expires → entitlement automatically reverts to plan-derived value; this reversion is itself logged.
**Authorization**: `platform.entitlements.override` / `platform.quotas.override` — distinct from `platform.plans.manage`/`platform.subscriptions.manage`, so overrides can be restricted to specific operators.
**Audit**: Full audit record on grant, and on automatic/manual revocation.
**Acceptance Scenarios**:
1. **Given** a tenant whose plan does not include a feature, **When** a Platform Admin grants a time-boxed override with a reason, **Then** the tenant gains access to the feature until the expiry, after which it automatically reverts, both events audited.

---

### US-7 (P2) — Authorized admin manages Platform Admin roles/permissions

**Actor**: Platform Admin with `platform.admins.manage` and/or `platform.rbac.manage`.
**Trigger**: Actor creates a new Platform Administrator account, assigns/changes their role, or revokes access.
**Main Flow**: Actor creates account (independent of any tenant membership, per [§14.4](#144-platform-administrator-accounts)) → assigns one or more platform roles → account becomes usable at next login → audit record written. Revocation: actor deactivates the account or removes role assignment → all active platform sessions for that account are invalidated.
**Alternative/Error Flows**: Actor attempts to grant themselves a higher-privilege role than they currently hold → rejected unless they hold `platform.rbac.manage` at the appropriate scope (see [BR-9A-013](#13-business-rules) on self-escalation).
**Authorization**: `platform.admins.manage` (account lifecycle), `platform.rbac.manage` (role/permission definitions).
**Audit**: Full audit record for every account and role change — this is explicitly listed as a mandatory audited action in Constitution §50 discussion.
**Acceptance Scenarios**:
1. **Given** a Platform Owner, **When** they create a new Support Admin account, **Then** the account exists independent of any tenant, can authenticate via a platform session, and is scoped only to the Support Admin permission bundle.
2. **Given** a Platform Admin's role is revoked mid-session, **When** they attempt their next privileged action, **Then** the action is rejected and their existing platform session is invalidated within the bound defined in [§24](#24-non-functional-requirements).

---

### US-8 (P2) — Security/Audit Admin reviews privileged actions

**Actor**: Platform Admin with `platform.audit.read`.
**Trigger**: Actor opens the platform audit view and filters by administrator, tenant, action, resource, date/time, result/status, or security relevance.
**Main Flow**: System returns matching audit entries drawn from the platform-level audit view described in [§19](#19-audit--security-requirements), append-only, filterable.
**Authorization**: `platform.audit.read`.
**Audit**: Read access to audit data is itself logged at the request-logging level (Constitution §22), not as a full sensitive-action audit entry.
**Acceptance Scenarios**:
1. **Given** a Security/Audit Admin filters by a specific Platform Admin actor and a date range, **When** results return, **Then** every platform-level privileged action performed by that actor in the range is shown, including tenant lifecycle changes, plan/subscription changes, entitlement/quota overrides, RBAC changes, and support-access sessions.

---

### US-9 (P3) — Support Admin obtains controlled tenant support access

**Actor**: Platform Admin with `platform.support_access.initiate`.
**Trigger**: Actor needs to inspect a specific tenant's context to resolve a support issue.
**Main Flow**: Actor selects target tenant, enters a mandatory reason, and requests a time-bounded support-access grant → system activates the privileged session with a clear visual indication of privileged mode, start timestamp, and automatic expiry → every action taken during the session is logged with full context → session ends at expiry or explicit termination → end timestamp recorded.
**Alternative/Error Flows**: Actor attempts an action outside the pre-approved scope of support access (e.g., editing tenant business transactions) → rejected; support access in this Epic is inspection-only (see [§18](#18-supportcross-tenant-access-requirements)).
**Authorization**: `platform.support_access.initiate`.
**Audit**: Full audit trail: actor identity, target tenant, reason, start/end timestamps, and every action performed during the session.
**Acceptance Scenarios**:
1. **Given** a Support Admin requests access to Tenant X with a reason, **When** the grant is approved, **Then** a time-bounded, clearly-marked privileged session begins, all actions within it are logged, and the session automatically terminates at its expiry even if the actor takes no explicit action to end it.
2. **Given** an active support-access session, **When** its expiry is reached, **Then** further tenant-context requests under that session are rejected and the session is marked ended in the audit trail.

---

### US-10 (P2) — Platform Admin reviews usage and quota status

**Actor**: Platform Admin with `platform.quotas.read` (or `platform.tenants.read` for tenant-scoped usage within the detail view).
**Trigger**: Actor reviews platform-wide or per-tenant usage against configured limits.
**Main Flow**: System surfaces current usage, limit, remaining allowance, and status (`ok`/`approaching`/`reached`/`unlimited`/`unavailable`) per quota category, per tenant.
**Authorization**: `platform.quotas.read`.
**Audit**: Read-only, not a sensitive action.
**Acceptance Scenarios**:
1. **Given** a tenant at 95% of its user quota, **When** a Platform Admin views usage, **Then** the tenant is flagged "approaching limit," distinct from a tenant at 100%+ ("limit reached") and a tenant on an unlimited plan ("unlimited").

---

### US-11 (P2) — Platform Admin reviews operational health

**Actor**: Platform Admin with `platform.monitoring.read`.
**Trigger**: Actor opens the operational health view.
**Main Flow**: System surfaces API availability, database connectivity, and the outbox/event relay's processing status, built on the existing `/health*` endpoints and outbox table, plus recent critical errors if a logging/error source is available.
**Authorization**: `platform.monitoring.read`.
**Acceptance Scenarios**:
1. **Given** the database health check reports degraded, **When** a Platform Admin views operational health, **Then** the degraded status is shown with the underlying check name (`database`), not a generic "something is wrong" message.

---

### US-12 (P3) — Platform Admin reviews AI usage/credit information when AI capabilities become active

**Actor**: Platform Admin with `platform.ai_usage.read`.
**Preconditions**: AI capability is active for at least one tenant (future state — no AI provider exists today).
**Trigger**: Actor reviews AI usage/credit consumption.
**Main Flow**: System surfaces, per tenant: allowance, consumed credits, remaining credits, and usage history, sourced from the provider-neutral schema defined in [§20](#20-usage--ai-readiness-requirements).
**Authorization**: `platform.ai_usage.read` (read), `platform.ai_credits.adjust` (manual adjustment).
**Acceptance Scenarios**:
1. **Given** AI capability is not yet active for any tenant, **When** a Platform Admin opens the AI usage view, **Then** it shows an explicit "AI capability not yet active" state rather than an empty table that could be mistaken for zero usage.

---

## 11. Acceptance Scenarios

Cross-cutting scenarios not tied to a single user story, proving tenant/platform boundary safety (Constitution §9, §50):

1. **Given** a tenant-scoped session (any tenant role, including `owner`), **When** it calls any `platform.*`-guarded endpoint, **Then** the request is rejected with an authorization error, regardless of the tenant role's rank.
2. **Given** a Company/Tenant Admin manipulates their tenant context or session claims client-side, **When** they attempt to reach a platform endpoint, **Then** the platform authorization boundary rejects the request — platform authority is never derivable from tenant-supplied context.
3. **Given** a Platform Admin account with no tenant membership anywhere in the system, **When** they authenticate, **Then** they can exercise their platform permissions without being blocked by any tenant-membership check.
4. **Given** a Platform Admin's platform session, **When** it is used against a tenant-scoped (`/api/v1/companies/{id}/...` non-admin) endpoint without an active, explicit support-access grant, **Then** it is treated as any other unauthenticated-for-that-tenant request — platform authority does not implicitly unlock tenant endpoints.
5. **Given** a suspended tenant, **When** any of its tenant users attempt any tenant-scoped action, **Then** every such action is rejected via the existing `CompanySuspendedError` pathway — suspension takes effect for all tenant users, not just new logins.
6. **Given** two Platform Admins concurrently attempt to suspend the same already-active tenant, **When** both requests are processed, **Then** exactly one succeeds and the other receives a specific "state already changed" error, not a silent duplicate audit entry (see [Edge Cases](#22-edge-cases)).
7. **Given** a Platform Admin without `platform.audit.read`, **When** they call the platform audit endpoint directly, **Then** the request is rejected regardless of what other platform permissions they hold — permission areas are independent, not implied by seniority alone (except for the Platform Owner bundle, which holds all permissions explicitly, not by inference).

---

## 12. Functional Requirements

Requirements are grouped by domain. Each is unambiguous, testable, and implementation-independent.

### 12.1 Platform Dashboard

- **FR-9A-001**: The system MUST provide a Platform Dashboard showing, at minimum: total/active/suspended/inactive/deleted tenant counts, tenant growth over a configurable period, total platform users, plan distribution, subscription-status distribution, usage/limit warnings, recent tenant registrations, recent administrative actions, security-sensitive events, and a platform health summary.
- **FR-9A-002**: Every dashboard metric MUST be traceable to a specific operational or commercial purpose documented alongside it; no metric may be added purely for visual completeness.
- **FR-9A-003**: The dashboard MUST define and visibly distinguish four states per widget: loading, populated, empty (zero underlying data), and unavailable (source failure) — never conflating empty with unavailable.
- **FR-9A-004**: Dashboard widgets requiring a permission the viewing Platform Admin does not hold MUST be omitted, not shown empty or erroring.
- **FR-9A-005**: AI usage/cost summary MUST appear on the dashboard only once AI capability is active for at least one tenant; until then it MUST NOT appear as a populated-but-empty widget.

### 12.2 Tenant Lifecycle (see also [§14](#14-tenant-lifecycle-requirements))

- **FR-9A-010**: The system MUST allow a Platform Admin with `platform.tenants.read` to view, search, filter, sort, and paginate the full tenant list across all `CompanyStatus` values.
- **FR-9A-011**: The system MUST allow a Platform Admin with `platform.tenants.suspend` to transition a tenant from `active` or `inactive` to `suspended`, requiring a mandatory reason and confirmation.
- **FR-9A-012**: The system MUST allow a Platform Admin with `platform.tenants.reactivate` to transition a tenant from `suspended` back to its pre-suspension status, requiring a mandatory reason and confirmation.
- **FR-9A-013**: The system MUST NOT allow Platform Admin lifecycle actions to modify `pending_setup`, `inactive` (as an owner-voluntary state), or `deleted` transitions — those remain Owner-controlled, per [Assumption A2](#8-assumptions).
- **FR-9A-014**: Every tenant lifecycle transition performed by a Platform Admin MUST produce a full audit record and fire the corresponding domain event.
- **FR-9A-015**: Suspending a tenant MUST NOT delete, truncate, or archive any tenant business data.
- **FR-9A-016**: The system MUST provide a lifecycle history view per tenant, showing every status transition with actor, timestamp, and reason.

### 12.3 Tenant Detail / 360° View

- **FR-9A-020**: The tenant detail view MUST show: company identity, status, creation/onboarding info, current plan, subscription status, enabled modules/entitlements, usage-against-limits, user count, lifecycle history, platform administrative actions, and relevant audit/security events for that tenant.
- **FR-9A-021**: The tenant detail view MUST NOT expose tenant business transaction records (invoices, journal entries, sales orders, purchase orders, inventory movements, CRM records, etc.).
- **FR-9A-022**: If a usage/metering data source is unavailable for a tenant, the affected section MUST show an explicit "unavailable" state; the rest of the view MUST still render.

### 12.4 Platform Administrator Accounts

- **FR-9A-030**: The system MUST support creating a Platform Administrator account independent of any tenant membership.
- **FR-9A-031**: The system MUST support activating/deactivating a Platform Administrator account, immediately invalidating active platform sessions on deactivation.
- **FR-9A-032**: The system MUST support assigning one or more Platform Roles to a Platform Administrator account.
- **FR-9A-033**: The system MUST record last-login and session-activity visibility for each Platform Administrator account, where the underlying session infrastructure supports it.
- **FR-9A-034**: Every create/deactivate/role-change on a Platform Administrator account MUST produce a full audit record.
- **FR-9A-035**: A Platform Administrator account MUST NOT be derivable from, or implicitly created by, a tenant `CompanyMember` record.
- **FR-9A-036**: The very first Platform Administrator (Platform Owner) account MUST be provisioned via a one-time, out-of-band seed/migration mechanism outside the normal `platform.admins.manage`-gated account-creation API (resolved [OQ-5](#29-open-questions--clarifications)) — because every in-app creation path requires an already-authenticated Platform Admin, which the very first account cannot satisfy. This bootstrap mechanism is a one-time operational action, not a repeatable admin-creation path, and MUST be traceable at the infrastructure level (e.g., migration history) even though it necessarily precedes the platform audit trail's own existence.

### 12.5 Platform RBAC

See [§15](#15-platform-rbac-requirements) for the full requirement set.

### 12.6 SaaS Plan Management

See [§16](#16-plan--subscription-requirements).

### 12.7 Subscription Administration

See [§16](#16-plan--subscription-requirements).

### 12.8 Feature Entitlements & Quotas

See [§17](#17-entitlement--quota-requirements).

### 12.9 Usage Metering

- **FR-9A-060**: The system MUST provide tenant-scoped, attributable usage data per configured quota category (users, branches, transactions, storage, API calls, and future categories), suitable as a foundation for future billing.
- **FR-9A-061**: Usage metering MUST NOT require real-time analytics infrastructure beyond the existing Modular Monolith and PostgreSQL — periodic/batch computation is acceptable unless a future ADR changes this.
- **FR-9A-062**: If a usage measurement source fails, the system MUST surface "measurement unavailable" rather than defaulting to zero or the last-known value silently.

### 12.10 AI Usage/Credit Readiness

See [§20](#20-usage--ai-readiness-requirements).

### 12.11 Cross-Tenant Support Access

See [§18](#18-supportcross-tenant-access-requirements).

### 12.12 Audit & Security Oversight

See [§19](#19-audit--security-requirements).

### 12.13 Platform Health & Operational Monitoring

See [§21](#21-operational-monitoring-requirements).

### 12.14 Platform Configuration

- **FR-9A-090**: The system MUST provide a platform-wide configuration surface for genuinely global SaaS settings (plan/entitlement definitions, platform feature availability, SaaS-level defaults, maintenance/admin configuration), distinct from tenant business configuration (`company_settings` or equivalent).
- **FR-9A-091**: Platform-wide configuration MUST NOT be capable of silently overriding a tenant's business-specific configuration; any interaction between the two MUST be explicit and documented.
- **FR-9A-092**: Every security-sensitive platform configuration change MUST produce a full audit record.

### 12.15 Administrative Notifications & Alerts

- **FR-9A-100**: The system MUST define requirements for Platform Admin alerts covering: tenant approaching quota, subscription/plan issues, failed operational processes, security-sensitive events, provider/integration failures, and platform health degradation.
- **FR-9A-101**: Administrative notifications MUST be delivered through the existing Plugin/Adapter notification-provider boundary (Constitution §47) when a concrete provider is later integrated; this Epic defines the requirement and integration boundary only, not a notification product.

### 12.16 Search, Filtering, Pagination & Bulk Operations

- **FR-9A-110**: Tenant, plan, subscription, and audit list views MUST support search, filter, sort, and pagination proportionate to platform scale.
- **FR-9A-111**: Any bulk administrative action (e.g., bulk suspend) MUST require the same mandatory-reason, confirmation, and audit guarantees as its single-tenant equivalent, applied per affected tenant (one audit record per tenant, not one blended record), and MUST be gated behind an explicit, separate permission from the single-tenant action.

### 12.17 Data Export / Administrative Reporting

- **FR-9A-120**: The system MUST support exporting the tenant directory, subscription summary, usage summary, and audit data, scoped to what the requesting Platform Admin's permissions already allow them to view online.
- **FR-9A-121**: Exports MUST NOT include tenant business transaction records; that reporting belongs to a future dedicated reporting module/Epic.

### 12.18 Commercialization Readiness

- **FR-9A-130**: Plan and subscription data structures MUST accommodate future paid billing cycles, a future trial subscription state (resolved [OQ-1](#29-open-questions--clarifications): future-ready only, not implemented in this Epic), and enterprise/custom plans without a breaking redesign.
- **FR-9A-131**: The system MUST NOT implement actual payment processing, invoicing, or usage-based billing calculation in this Epic.

---

## 13. Business Rules

| ID | Rule |
|---|---|
| BR-9A-001 | A Company/Tenant Admin MUST NEVER gain Platform Admin capability through tenant roles, permissions, sessions, API endpoints, feature toggles, subscription plans, or manipulated tenant context. |
| BR-9A-002 | Platform Admin authority MUST be evaluated exclusively from a Platform Administrator Account and its assigned Platform Roles — never from `CurrentUser.roles` populated by a tenant-scoped JWT, and never from tenant `CompanyMember` rank. |
| BR-9A-003 | A Platform Admin session MUST be structurally distinguishable from a tenant session at the token/claim level. |
| BR-9A-004 | Platform Admin's direct tenant-lifecycle write authority is limited to Suspend and Reactivate; Deactivation (`inactive`) and Deletion (`deleted`) transitions remain Owner-controlled. |
| BR-9A-005 | A tenant lifecycle action MUST require: the specific permission for that transition, explicit confirmation, a mandatory reason, and a full audit record — all four, not a subset. |
| BR-9A-006 | Suspending or deactivating a tenant MUST NOT delete or destroy tenant business data. |
| BR-9A-007 | Hard deletion of a tenant is never a normal lifecycle operation reachable through this Epic's requirements. |
| BR-9A-008 | Every Platform RBAC permission is independently checked; holding one platform permission never implies another, except for the explicit "all permissions" bundle held by the Platform Owner role. |
| BR-9A-009 | Destructive or highly privileged platform operations (tenant suspension, RBAC changes, entitlement/quota overrides, support-access initiation) MUST each require their own explicit permission, distinct from read permissions in the same domain. |
| BR-9A-010 | A Platform Administrator account MUST exist and function independent of membership in any customer tenant. |
| BR-9A-011 | Deactivating a Platform Administrator account MUST immediately invalidate that account's active platform sessions. |
| BR-9A-012 | A Platform Admin MUST NOT be able to escalate their own privileges by self-assigning a higher-privilege role unless they already hold `platform.rbac.manage` at a scope that legitimately covers that role. |
| BR-9A-013 | Role/permission changes to a Platform Administrator account, including self-service changes by a sufficiently privileged actor, MUST be fully audited. |
| BR-9A-014 | A SaaS Plan definition and a tenant's Subscription (plan assignment) are distinct concepts; changing a Plan's definition never silently changes what a Subscription's snapshot entitles unless the tenant's subscription is explicitly re-evaluated per [§16](#16-plan--subscription-requirements). |
| BR-9A-015 | Plan entitlement (what a tenant's plan allows) and Tenant Feature Toggle (what a tenant has chosen to enable within what's allowed) are evaluated together per the resolution table in [§17.2](#172-resolution-rules). |
| BR-9A-016 | A tenant can never use a feature that the resolution in §17.2 disallows, regardless of the tenant's own feature-toggle setting. |
| BR-9A-017 | A temporary entitlement/quota override requires explicit permission, a reason, and is auditable; it SHOULD support an expiry, and it automatically reverts to the plan-derived value at expiry. |
| BR-9A-018 | Retiring a Plan blocks only *new* subscription assignments to that plan; tenants already subscribed keep their current entitlements until an explicit subscription change is made for them individually. |
| BR-9A-019 | Cross-tenant support access is never silent; it always requires explicit permission, explicit tenant selection, a mandatory reason, and is time-bounded. |
| BR-9A-020 | Every action performed during an active cross-tenant support-access session is logged with full context, in addition to the session's own start/end audit record. |
| BR-9A-021 | Cross-tenant support access in this Epic is inspection-only and limited to tenant configuration, entitlements, and user data; it does not grant the ability to create, update, or delete tenant business records, and — per resolved [OQ-2](#29-open-questions--clarifications) — does not grant read access to tenant business records (invoices, journal entries, sales orders, etc.) either (see [§18.4](#184-in-scope-vs-future-ready)). |
| BR-9A-022 | Platform audit records use the same who/what/when/before/after/context schema already defined by Constitution §35; no parallel or divergent audit schema is introduced. |
| BR-9A-023 | Platform audit records are append-only; no update or delete path exists for them. |
| BR-9A-024 | If the audit write for a privileged platform action fails, the action itself MUST NOT be considered successfully committed — audit failure blocks the mutation (fail-closed), consistent with Constitution §35's non-negotiable audit requirement for critical operations. |
| BR-9A-025 | Normal Company/Tenant users and Company/Tenant Admins MUST NEVER be able to reach any Platform Administration capability, under any tenant role or rank. |
| BR-9A-026 | AI usage/credit tracking, when implemented, MUST remain provider-neutral at the schema and requirements level — no coupling to a specific AI vendor. |
| BR-9A-027 | Manual AI credit adjustments, when implemented, MUST require explicit permission, a reason, and a full audit record, matching the pattern for entitlement/quota overrides. |
| BR-9A-028 | Platform-wide configuration MUST NEVER silently override tenant-specific business configuration; any override capability MUST be explicit, scoped, and justified. |
| BR-9A-029 | Bulk lifecycle or entitlement actions MUST produce one audit record per affected tenant, never a single blended record covering multiple tenants. |
| BR-9A-030 | A quota's enforcement style (hard limit, soft/warning limit, or informational-only) MUST be explicitly declared per quota category — no quota category defaults silently to hard enforcement without that being a deliberate configuration choice. |
| BR-9A-031 | The first Platform Owner account MUST be created via a one-time, out-of-band seed/migration mechanism, never via the normal in-app account-creation API — because every in-app creation path requires an already-authenticated Platform Admin (self-referential bootstrap problem), resolved per [OQ-5](#29-open-questions--clarifications). |

---

## 14. Tenant Lifecycle Requirements

### 14.1 Status Model (Reused, Not Redefined)

Epic 9A reuses the existing `CompanyStatus` enum exactly as implemented (`backend/modules/companies/models/enums.py`):

| Status | Business Meaning | Who Can Set It |
|---|---|---|
| `pending_setup` | Tenant created, onboarding not yet complete | Owner (system, on tenant creation) |
| `active` | Tenant fully operational | Owner (from `pending_setup`/`inactive`), Platform Admin (from `suspended`, via Reactivate) |
| `inactive` | Tenant voluntarily paused by its own Owner | Owner only |
| `suspended` | Tenant access blocked by platform sanction (e.g., policy violation, non-payment readiness) | **Platform Admin only** |
| `deleted` | Tenant soft-deleted | Owner only (with retention-window restore also Owner-only) |

### 14.2 Platform Admin Authority Boundary

- Platform Admin MAY: view all tenants in all statuses; suspend an `active` or `inactive` tenant; reactivate a `suspended` tenant back to its pre-suspension status.
- Platform Admin MAY NOT (in this Epic): set `inactive`, set `deleted`, restore from `deleted`, or force `pending_setup→active` — these remain Owner actions Platform Admin can only observe.

### 14.3 Effect of Suspension on Access and Data

- Suspension MUST block all tenant-scoped API access for every user of that tenant, immediately (already enforced today via `CompanySuspendedError` at the read boundary — Epic 9A supplies the missing write path).
- Suspension MUST NOT delete, archive, or modify any tenant business data.
- Suspension is NOT required to actively force-terminate already-established tenant sessions (resolved [OQ-3](#29-open-questions--clarifications), decided 2026-08-19) — blocking the *next* request from any tenant session, via the existing `CompanySuspendedError` pathway, satisfies this requirement. Active session force-termination at the moment of suspension remains a documented possible future security-posture enhancement (see [§19.4](#194-session-and-access-revocation) for the distinct, already-required case of *account deactivation*, which MUST invalidate active sessions immediately), not an in-scope requirement of this Epic.
- Reactivation MUST restore full access without requiring any tenant data migration or re-onboarding.

### 14.4 Platform Administrator Accounts

- A Platform Administrator account is a first-class identity, structurally independent of `CompanyMember`.
- Fields required at the business level: identity (name/email), active/inactive status, assigned Platform Role(s), creation metadata, last-login visibility (where session infrastructure supports it), and revocation metadata.
- Deactivating the account immediately invalidates its active platform sessions (see [BR-9A-011](#13-business-rules)).
- The very first Platform Owner account is provisioned out-of-band via a one-time seed/migration mechanism (resolved [OQ-5](#29-open-questions--clarifications)) — the only Platform Administrator account creation path that does not go through the normal `platform.admins.manage`-gated API, existing solely to break the bootstrap circularity (every in-app creation path requires an already-authenticated Platform Admin). See [FR-9A-036](#124-platform-administrator-accounts), [BR-9A-031](#13-business-rules).

---

## 15. Platform RBAC Requirements

### 15.1 Permission Areas (Granular, Independent)

| Area | Example Permission Codes |
|---|---|
| Dashboard | `platform.dashboard.view` |
| Tenant inspection | `platform.tenants.read`, `platform.tenants.export` |
| Tenant lifecycle | `platform.tenants.suspend`, `platform.tenants.reactivate`, `platform.tenants.bulk_suspend` |
| Plans | `platform.plans.read`, `platform.plans.manage` |
| Subscriptions | `platform.subscriptions.read`, `platform.subscriptions.manage` |
| Entitlements | `platform.entitlements.read`, `platform.entitlements.override` |
| Quotas | `platform.quotas.read`, `platform.quotas.override` |
| Platform Administrators | `platform.admins.read`, `platform.admins.manage` |
| Platform RBAC | `platform.rbac.read`, `platform.rbac.manage` |
| Support access | `platform.support_access.initiate`, `platform.support_access.read` |
| Audit logs | `platform.audit.read` |
| Operational monitoring | `platform.monitoring.read` |
| Platform configuration | `platform.configuration.read`, `platform.configuration.manage` |
| Notifications | `platform.notifications.read`, `platform.notifications.manage` |
| AI usage/cost | `platform.ai_usage.read`, `platform.ai_credits.adjust` |
| Export/reporting | `platform.export.generate` |

Exact permission-code naming is an implementation detail for the Plan phase; the *granularity* (one permission per sensitive capability, read/write split per domain) is the specification requirement.

### 15.2 Candidate Platform Roles (Configurable, Not Hardcoded)

| Candidate Role | Intended Bundle |
|---|---|
| Platform Owner / Super Admin | All permissions, including `platform.admins.manage` and `platform.rbac.manage` (bootstrap authority) |
| Platform Operations Admin | Tenant, plan, subscription, entitlement, quota, configuration, monitoring permissions — excludes `platform.admins.manage`, `platform.rbac.manage`, `platform.ai_credits.adjust` |
| Support Admin | `platform.tenants.read`, `platform.support_access.initiate`, `platform.support_access.read`, `platform.audit.read` (scoped to support-access history) |
| Billing/Subscription Admin | `platform.plans.*`, `platform.subscriptions.*`, `platform.entitlements.*`, `platform.quotas.*`, `platform.ai_credits.adjust` |
| Security/Audit Admin | `platform.audit.read`, `platform.monitoring.read`, `platform.admins.read`, `platform.rbac.read`, `platform.support_access.read` |
| Read-Only Platform Analyst | `*.read` across all domains; no write permissions |

These are candidates to be confirmed during Plan/product review, not mandatory hardcoded roles — Platform RBAC MUST be configurable so new roles/bundles can be defined without a code change (mirroring the Constitution §46 configuration-over-hardcoding philosophy, applied at the platform layer).

### 15.3 Rules

- FR-9A-140: Platform RBAC MUST be modeled as a structurally separate model from tenant RBAC (`SYSTEM_ROLES`/`Permission`/`RolePermission` in `users_roles`) — reusing the *pattern*, not the *tables*.
- FR-9A-141: A platform permission MUST NEVER be reachable through a tenant-scoped session or token (Constitution §50, verbatim requirement).
- FR-9A-142: The system MUST support assigning multiple Platform Roles to one Platform Administrator account, with the account's effective permissions being the union of its roles' permissions.
- FR-9A-143: Removing a Platform Admin's last role effectively deactivates their platform capability without requiring a separate "deactivate account" action, though the account record itself remains for audit history.

---

## 16. Plan & Subscription Requirements

### 16.1 Plan Definition (Platform-Owned, Not Tenant-Owned)

- FR-9A-150: A Plan MUST support: name, status (draft/published/retired), description, commercial availability flag, enabled modules, feature entitlements, user limit, branch limit, transaction/usage limits, storage limit, API limit (where applicable), AI allowance readiness field, billing-cycle readiness metadata, pricing metadata (informational only, see [Assumption A5](#8-assumptions)), and upgrade/downgrade eligibility rules.
- FR-9A-151: Plan names and structures MUST be configuration-driven; this specification does not hardcode "Basic/Pro/Enterprise" or any other specific plan names as a requirement.
- FR-9A-152: A retired Plan MUST remain visible (read-only) for tenants still assigned to it, and MUST NOT be offered for new assignments (BR-9A-018).

### 16.2 Subscription (Tenant Plan Assignment)

- FR-9A-160: A Subscription is a distinct record from a Plan: it links one tenant to one Plan as of an effective date, with its own status.
- FR-9A-161: The system MUST support assigning a plan to a tenant for the first time, changing (upgrade/downgrade) an existing assignment, and recording subscription history.
- FR-9A-162: Every subscription assignment/change MUST record: tenant, plan, effective date, actor, and reason (reason mandatory for administrative — i.e., not self-service — changes).
- FR-9A-163: The system MUST support cancellation/end-of-service readiness (a subscription state indicating the tenant's paid service is ending) without requiring actual payment-provider integration.
- FR-9A-164: The system MUST establish a clean extension point for a future billing provider via the existing Plugin/Adapter pattern (Constitution §47); this Epic does not implement that adapter.

### 16.3 Downgrade / Usage-Conflict Handling

- FR-9A-165: When a subscription change would place a tenant's current usage above the target plan's limits, the system MUST surface the conflict and require explicit administrative acknowledgment before applying the change (see [US-5](#us-5-p2--platform-admin-assigns--changes-tenant-subscriptions) scenario 1).
- FR-9A-166: After such a change is applied, the tenant is flagged as over its new quota (informational/soft, per the quota's declared enforcement style in [§17](#17-entitlement--quota-requirements)) rather than having existing users/data silently removed or truncated.

---

## 17. Entitlement & Quota Requirements

### 17.1 Three Distinct Sources

| Source | Owner | Grain |
|---|---|---|
| **Plan Entitlement** | Platform (via the tenant's current Plan) | Module/feature-level: is this module/feature available to this tenant at all |
| **Tenant Feature Toggle** | Tenant (existing per-module feature-flag tables) | Fine-grained behavior within an already-entitled module (e.g., `inventory.product_variants`) |
| **Administrative Override** | Platform (explicit, time-boxed) | Temporary exception to either of the above, for a specific tenant |

### 17.2 Resolution Rules

| Plan Entitlement | Tenant Toggle | Effective Result |
|---|---|---|
| Allowed | Enabled | **Available** |
| Allowed | Disabled | **Unavailable** (tenant's own choice) |
| Not Allowed | Enabled | **Unavailable** — plan entitlement is the ceiling; a tenant toggle cannot exceed what the plan allows |
| Not Allowed | Disabled | **Unavailable** |
| Not Allowed, but Active Override | (irrelevant) | **Available** for the override's duration |
| Tenant moves to a plan lacking a previously-entitled module | (was Enabled) | **Unavailable** immediately upon the subscription change taking effect; the tenant's toggle setting is preserved (not deleted) so the feature resumes automatically if the tenant later regains entitlement |

- FR-9A-170: The resolution in §17.2 MUST be evaluated at the point of use (API boundary), not cached indefinitely — a plan/entitlement/override change MUST take effect without requiring a tenant-side action.
- FR-9A-171: An administrative override MUST record: tenant, entitlement/quota affected, reason, granting actor, and optional expiry.
- FR-9A-172: An expired override MUST automatically revert to the plan-derived value, and that reversion MUST itself be audited.

### 17.3 Quota Categories & Behavior

| Category | Notes |
|---|---|
| Users | Count of active tenant members against plan's user limit |
| Branches | Readiness-aligned with Constitution §10 Multi-Branch Readiness |
| Transactions | Business-transaction volume (definition of "transaction" deferred to Plan phase per module) |
| Storage | File storage usage (Constitution §33) |
| API calls | Where API-level metering exists |
| AI usage/credits | See [§20](#20-usage--ai-readiness-requirements) |

- FR-9A-180: Each quota category MUST declare its enforcement style: hard limit (blocks the action), soft/warning limit (allows but flags), or informational metering only (no enforcement) — per BR-9A-030.
- FR-9A-181: The system MUST distinguish and clearly render five usage states per quota: `ok`, `approaching` (configurable threshold), `reached`, `unlimited` (plan grants no cap), and `unavailable` (measurement failure).
- FR-9A-182: "Unlimited" MUST be a distinct, explicit plan/entitlement value — never represented by an implausibly large number.

---

## 18. Support/Cross-Tenant Access Requirements

### 18.1 Principle

Normal Platform Admin screens (dashboard, tenant list/detail, plans, subscriptions, entitlements, quotas, audit, monitoring) expose only aggregate/summary data, never tenant business records. Any need to inspect tenant-specific business context requires the explicit workflow below.

### 18.2 Workflow Requirements

- FR-9A-190: Support access MUST require the `platform.support_access.initiate` permission, distinct from all other platform permissions.
- FR-9A-191: Support access MUST require explicit selection of exactly one target tenant per session.
- FR-9A-192: Support access MUST require a mandatory, freeform reason before the session activates.
- FR-9A-193: Support access MUST be time-bounded, with an explicit, visible expiry; there is no indefinite support-access session.
- FR-9A-194: While active, support access MUST be clearly and persistently indicated as a privileged mode (never a silent or ambiguous state).
- FR-9A-195: Every action taken during a support-access session MUST be logged with full context, in addition to the session-level start/end audit record.
- FR-9A-196: A support-access session MUST be immediately terminable by the initiating actor, by a sufficiently privileged Platform Admin, or automatically at its expiry.
- FR-9A-197: Session termination (explicit or automatic) MUST record an end timestamp in the audit trail.

### 18.3 What Support Access Grants (This Epic)

- Read/inspect access to the target tenant's configuration, entitlements, users, and lifecycle/audit history already visible via the Tenant Detail view — i.e., nothing beyond what a Platform Admin can already see about a tenant in aggregate, but now including the specific tenant's own configuration values rather than just aggregates.
- Per resolved [OQ-2](#29-open-questions--clarifications), support access explicitly does NOT extend to the target tenant's business records (invoices, journal entries, sales orders, inventory movements, etc.), read or write — a support session broadens *what tenant-specific data* a Platform Admin can see, not *what category* of data (business records remain permanently outside Platform Admin visibility, in or out of a support session).

### 18.4 In-Scope vs. Future-Ready

| Capability | Status |
|---|---|
| Time-bounded, audited, reason-required inspection access to tenant configuration/entitlements | **In scope now** |
| Read access to a tenant's own business records (invoices, journal entries, etc.) during a support session | **Resolved [OQ-2](#29-open-questions--clarifications): out of scope.** Support access remains strictly limited to configuration, entitlements, and user inspection per BR-9A-021. If a genuine need for read-only business-record access during support sessions is confirmed later, it requires its own explicit specification update — never an implicit extension of this Epic. |
| Full user impersonation ("login as user") | **Explicitly out of scope** (never silent, never unrestricted; if ever pursued, requires its own controlled, audited specification) |
| Write access to tenant business records during support access | **Out of scope** for this Epic |

---

## 19. Audit & Security Requirements

### 19.1 Platform Audit Visibility

- FR-9A-200: The system MUST provide a platform-level, cross-tenant, actor-centric audit view, filterable by platform administrator, tenant, action, resource, date/time, result/status, and security relevance.
- FR-9A-201: The platform audit view MUST draw on the same append-only, who/what/when/before/after/context schema already established by Constitution §35 — no separate, parallel audit mechanism is introduced (Constitution §50).
- FR-9A-202: At minimum, the following MUST be audited: tenant lifecycle changes, plan/subscription changes, entitlement/quota changes (including overrides), platform role/permission changes, privileged support access (session-level and action-level), security-sensitive platform configuration changes, and AI credit adjustments (once implemented).

### 19.2 Append-Only Guarantee

- FR-9A-203: Platform audit records MUST NOT be updatable or deletable through any API surface.
- FR-9A-204: If a privileged platform action's audit write fails, the action itself MUST be rejected/rolled back (fail-closed) per BR-9A-024 — this is stricter than "log and continue," and is a deliberate choice given the elevated sensitivity of platform-level actions relative to ordinary tenant operations.

### 19.3 Platform Security Requirements

- FR-9A-210: Platform Administration MUST enforce a separate authorization boundary from tenant RBAC (BR-9A-002, FR-9A-141).
- FR-9A-211: Platform Administration MUST enforce least privilege — no platform capability is granted by default; every permission is explicit.
- FR-9A-212: Platform endpoints MUST be protected against IDOR/BOLA — a Platform Admin's access to a specific tenant's data is never inferable from a client-supplied tenant identifier alone; it is always evaluated against the actor's actual permissions and (for support access) an active grant.
- FR-9A-213: State-changing platform operations MUST be protected against CSRF, consistent with Constitution §19.
- FR-9A-214: Sensitive platform endpoints (tenant suspend/reactivate, RBAC changes, support-access initiation) SHOULD support re-validation (e.g., re-confirmation) beyond the base session check, given their elevated blast radius.
- FR-9A-215: Platform Admin UI/API responses MUST NEVER expose secrets, credentials, or internal error details, consistent with Constitution §19/§21.
- FR-9A-216: Platform Admin session revocation and account-access revocation MUST be immediate and MUST invalidate already-issued tokens/sessions for that account (not merely block new logins).
- FR-9A-217: The Platform Admin surface MUST be architecturally ready for future MFA enforcement; MFA is not implemented anywhere in the codebase today (confirmed: zero existing MFA infrastructure), so this is a readiness requirement, not an in-scope implementation.

### 19.4 Session and Access Revocation

- FR-9A-220: Deactivating a Platform Administrator account MUST invalidate all of that account's active platform sessions within the bound defined in [§24](#24-non-functional-requirements).
- FR-9A-221: Revoking a specific platform permission MUST take effect on the account's next privileged action at the latest — a long-lived session MUST NOT be able to continue exercising a revoked permission indefinitely.

---

## 20. Usage & AI Readiness Requirements

### 20.1 Principle

No AI provider exists in this codebase today, and none is implemented by this Epic. The requirement is a provider-neutral schema/behavior readiness so a future AI capability can plug in without a control-plane redesign.

### 20.2 Requirements

- FR-9A-230: The system MUST define readiness for tracking, per tenant: AI allowance/credits, consumed credits, remaining credits, model/provider attribution, input/output/token usage where applicable, estimated/provider cost, billable usage, and usage history.
- FR-9A-231: AI feature entitlement MUST follow the same Plan Entitlement + Tenant Toggle + Override resolution model defined in [§17.2](#172-resolution-rules) — AI is not a special case.
- FR-9A-232: AI quota enforcement MUST follow the same enforcement-style declaration (hard/soft/informational) as other quota categories (BR-9A-030).
- FR-9A-233: Manual AI credit adjustments MUST require explicit permission (`platform.ai_credits.adjust`), a reason, and produce a full audit record (BR-9A-027).
- FR-9A-234: The AI readiness model MUST NOT name or structurally couple to any specific provider (OpenAI, Anthropic, Gemini, OpenClaw, or otherwise) — provider identity, where tracked, is a free-text/enum attribution field, not a structural dependency.
- FR-9A-235: Until AI capability is active for any tenant, all AI usage/credit views MUST show an explicit "not yet active" state, not a populated-but-empty or zero-value table (consistent with FR-9A-005 and US-12 scenario 1).

---

## 21. Operational Monitoring Requirements

### 21.1 Scope

Built on existing infrastructure only — no new observability platform is introduced.

### 21.2 Requirements

- FR-9A-240: The Platform Health view MUST surface, at minimum, the same checks already exposed by `GET /api/v1/health` (database connectivity, auth configuration validity) and the liveness/readiness distinction already exposed by `/health/live` and `/health/ready`.
- FR-9A-241: The Platform Health view MUST surface the transactional outbox's processing status (pending vs. published record counts), acknowledging today's relay is a logging-only stub — this view MUST make that stub-vs-real-delivery distinction visible rather than implying real message-bus delivery is occurring.
- FR-9A-242: The Platform Health view SHOULD surface recent critical errors where a logging source is available, without requiring new distributed-tracing infrastructure.
- FR-9A-243: Health/monitoring data sources that are unavailable MUST be shown as explicitly "unavailable," never silently omitted from the view in a way that could be mistaken for "all healthy."
- FR-9A-244: This Epic MUST NOT require Kubernetes, distributed tracing, or a microservices split to satisfy operational monitoring requirements (Constitution §5, §50 architectural discipline).

---

## 22. Edge Cases

| # | Scenario | Expected Business Behavior |
|---|---|---|
| 1 | Suspend an already-suspended tenant | Reject with a specific "tenant is already suspended" error; no duplicate audit entry, no-op on state. |
| 2 | Reactivate an already-active tenant | Reject with a specific "tenant is not currently suspended" error (reactivate is only valid from `suspended`). |
| 3 | Deactivate a tenant with an active subscription | Platform Admin cannot deactivate (§14.2 — deactivation is Owner-only); if the Owner deactivates, the subscription itself is unaffected (remains active/billable per its own state) — deactivation and subscription status are independent concerns. |
| 4 | Tenant exceeds its plan's limit through normal usage growth (not a plan change) | Quota status shows `reached`; behavior (block vs. warn) follows that quota category's declared enforcement style (FR-9A-180) — no universal rule. |
| 5 | Plan downgrade below current usage | Surfaced as an explicit conflict requiring administrative acknowledgment before applying (FR-9A-165); never a silent truncation. |
| 6 | Retired plan still assigned to existing tenants | Those tenants keep current entitlements; plan is unavailable for new assignments (BR-9A-018). |
| 7 | Removing an entitlement currently in use by a tenant | Feature becomes unavailable to that tenant going forward per §17.2; existing tenant data created while the feature was available is NOT deleted or hidden — only new use of the feature is blocked. |
| 8 | Platform Admin loses their permission mid-session | Next privileged action is rejected (FR-9A-221); already-completed actions are unaffected. |
| 9 | Platform Admin attempts an operation without permission | Rejected with a clear authorization error; attempt itself is logged as a security-relevant event per §19. |
| 10 | Tenant Admin attempts a Platform Admin endpoint | Rejected regardless of tenant rank (Acceptance Scenario 1 in §11). |
| 11 | A tenant-scoped token attempts a platform operation | Rejected — platform authority is never derivable from a tenant token (BR-9A-002, BR-9A-003). |
| 12 | Cross-tenant support session expires mid-task | Session and further tenant-context access under it are terminated at expiry (FR-9A-193, FR-9A-197); actor must initiate a new session with a new reason to continue. |
| 13 | Duplicate administrative request (e.g., double-click submit) | System MUST be idempotent for the same request within a short window, or the second request MUST fail cleanly against the now-changed state (e.g., edge case #1) rather than producing two audit records for one logical action. |
| 14 | Concurrent tenant lifecycle changes by two Platform Admins | Exactly one transition succeeds; the other receives a specific conflict error reflecting the tenant's actual current state (Acceptance Scenario 6 in §11). |
| 15 | Usage counter unavailable/stale | Shown as `unavailable`, never silently treated as zero or as the last-known value without a staleness indicator (FR-9A-062, FR-9A-181). |
| 16 | Subscription dates invalid (e.g., end date before effective date) | Rejected at validation time before the subscription record is created/changed. |
| 17 | Plan change partially fails (e.g., entitlement update succeeds, audit write fails) | Entire operation MUST be transactional; a partial failure MUST leave the tenant's subscription/entitlements in their pre-change state, not a half-applied state (BR-9A-024 extended to subscription changes). |
| 18 | Audit write failure during a privileged operation | The privileged operation itself fails (fail-closed, BR-9A-024) — this is a deliberate, stricter-than-default choice for platform-level actions. |
| 19 | Tenant is suspended while its users have active sessions | Suspension blocks the *next* request from any of those sessions, via the existing `CompanySuspendedError` pathway (§14.3). Per resolved [OQ-3](#29-open-questions--clarifications), active force-termination of already-open sessions at the moment of suspension is NOT required by this Epic — blocking on next request is sufficient. |
| 20 | AI credits adjusted concurrently (future) | Same concurrency-safety expectation as edge case #14 — exactly one adjustment applies per logical request; the model MUST NOT be implemented in a way that allows a lost-update race, once AI credits exist. |
| 21 | Platform dependency/health source unavailable | Health view shows that specific check as `unavailable`/`degraded` with the check name, never a blanket "unknown" that hides which dependency failed (FR-9A-243). |
| 22 | *(Discovered during research, not in the original list)* A Platform Admin account is created but never assigned a role | Account exists but is effectively non-functional (holds zero permissions) — this is a valid, intentional intermediate state (e.g., during onboarding), not an error; FR-9A-143 governs the reverse case (last role removed). |
| 23 | *(Discovered during research)* Legacy `SUPER_ADMIN` (uppercase) string check in `purchase/router.py`, inconsistent with the `super_admin` (lowercase) convention used elsewhere | Not resolved by this Epic (pre-existing, unrelated module); the new Platform RBAC model defined here supersedes *all* ad hoc string-role checks going forward, including this one, at implementation time — flagged in [§28 Risks](#28-risks) for the Plan phase to address as part of migrating off the legacy pattern. |

---

## 23. State Transitions

### 23.1 Tenant Lifecycle

```
pending_setup ──(Owner: complete onboarding)──▶ active
active ──(Owner: pause)──▶ inactive ──(Owner: resume)──▶ active
active ──(Platform Admin: suspend, reason required)──▶ suspended
inactive ──(Platform Admin: suspend, reason required)──▶ suspended
suspended ──(Platform Admin: reactivate, reason required)──▶ active
active ──(Owner: delete)──▶ deleted
inactive ──(Owner: delete)──▶ deleted
deleted ──(Owner: restore, within retention window)──▶ inactive
```

| Transition | Actor/Permission | Reason Required | Audit Required | Resulting Access |
|---|---|---|---|---|
| `pending_setup → active` | Owner | No | Yes (existing) | Full access begins |
| `active ↔ inactive` | Owner | No (existing behavior) | Yes (existing) | Owner-paused: existing behavior unchanged by this Epic |
| `active/inactive → suspended` | Platform Admin, `platform.tenants.suspend` | **Yes** | **Yes** | All tenant users blocked |
| `suspended → active` | Platform Admin, `platform.tenants.reactivate` | **Yes** | **Yes** | Full access restored |
| `active/inactive → deleted` | Owner | Yes (existing, `deletion_reason` field) | Yes (existing) | Existing soft-delete behavior unchanged |
| `deleted → inactive` | Owner, within retention window | — | Yes (existing) | Existing restore behavior unchanged |

**Prohibited transitions**: `suspended → deleted` directly, `suspended → inactive` directly, `pending_setup → suspended`, and any transition attempted by an actor lacking the specific required permission — all MUST be rejected with a specific error, not a generic 403.

### 23.2 Subscription Lifecycle (New — Minimal Model)

Given billing/payment integration is explicitly out of scope, the minimal subscription states required to satisfy [§16](#16-plan--subscription-requirements) are:

```
(none) ──(Platform Admin: assign plan)──▶ active
active ──(Platform Admin: change plan)──▶ active (new plan, same state, new effective date)
active ──(Platform Admin: cancel/end-of-service)──▶ ended
```

An intermediate `trial` state and a `past_due`/`grace_period` state (relevant once real billing exists) are confirmed future-ready only, not required now (resolved [OQ-1](#29-open-questions--clarifications), decided 2026-08-19). Only `active` and `ended` are mandatory-now states; the data model MUST NOT preclude adding `trial` or a billing-driven state later without a breaking redesign.

| Transition | Actor/Permission | Reason Required | Audit Required | Resulting Access |
|---|---|---|---|---|
| `(none) → active` | Platform Admin, `platform.subscriptions.manage` | Yes (administrative assignment) | Yes | Tenant entitlements reflect new plan immediately |
| `active → active` (plan change) | Platform Admin, `platform.subscriptions.manage` | Yes | Yes | Entitlements re-resolved; usage-conflict handling per FR-9A-165 |
| `active → ended` | Platform Admin, `platform.subscriptions.manage` | Yes | Yes | Tenant's plan-derived entitlements are withdrawn; tenant is not automatically suspended or deleted — that remains a separate, explicit lifecycle decision |

---

## 24. Non-Functional Requirements

### Security
- All platform endpoints require authentication via a Platform Administrator Account and platform session; least privilege is enforced per permission, not per role bundle alone.
- All state-changing platform operations require CSRF protection, consistent with Constitution §19.

### Performance
- Dashboard aggregate queries and tenant list/search MUST remain responsive at a scale proportionate to the platform's current tenant count. Per resolved [OQ-4](#29-open-questions--clarifications) (decided 2026-08-19), this Epic deliberately does NOT commit to specific numeric latency/throughput targets — no existing project benchmark was found, and fabricating a number would misrepresent an unvalidated target as a requirement. Numeric SLOs MAY be established later via a dedicated ADR once real usage data exists, without requiring a revision to this Epic's functional scope.

### Scalability
- The tenant list, audit view, and plan/subscription administration MUST support pagination from the outset (no "load all tenants" pattern), so behavior remains correct as tenant count grows, without committing to a specific numeric scale target here.

### Reliability
- Platform lifecycle and subscription state changes MUST be transactional (edge case #17); partial application is not acceptable.
- The platform MUST remain safe under failure — a failed dependency (e.g., health check source) degrades visibility, never tenant isolation or audit integrity.

### Auditability
- Every privileged platform action is audited per [§19](#19-audit--security-requirements), fail-closed on audit-write failure (BR-9A-024).

### Accessibility
- Platform Admin UI surfaces MUST meet the same WCAG 2.1 AA baseline already required for tenant-facing UI (Constitution §23) — no lower bar for internal tooling.

### Observability
- Platform Admin actions are logged consistent with Constitution §22 (structured logs, request logging), in addition to the dedicated audit trail.

### Maintainability
- Platform Administration is implemented as platform-level module(s) within the existing Modular Monolith (Constitution §5, §50) — not a separate service, not a fork of tenant RBAC tables.

### Multi-Tenant Isolation
- No platform-level table introduced by this Epic is tenant-scoped by `company_id` in the sense of belonging to a tenant; platform data (Plans, Platform Admin accounts, Platform Roles, platform audit records) is intentionally outside the tenant isolation boundary, while every reference *from* platform data *to* a tenant (e.g., a Subscription's tenant reference) MUST be explicit and auditable, never implicit.

---

## 25. Success Criteria

- SC-1: An authorized Platform Admin can suspend and reactivate a tenant, with the action fully audited and immediately effective on tenant access — without any code path allowing a Company/Tenant Admin to perform the same action.
- SC-2: A Platform Admin account can be created, assigned a least-privilege role bundle (e.g., Read-Only Analyst), and confirmed to be unable to perform any write action outside that bundle.
- SC-3: A tenant's effective feature availability (Plan Entitlement × Tenant Toggle × Override) is deterministic and independently verifiable against the resolution table in [§17.2](#172-resolution-rules) for every combination.
- SC-4: Every privileged cross-tenant action (lifecycle change, plan/subscription change, entitlement/quota override, RBAC change, support-access session) is attributable to a specific Platform Admin actor and retrievable via the platform audit view.
- SC-5: A Platform Admin can determine any tenant's status, plan, subscription, and entitlement state from the Tenant Detail view without accessing that tenant's business transaction records.
- SC-6: A tenant-scoped session or token — under any tenant role, including Owner — cannot reach any platform-level capability, verified by explicit negative test scenarios (§11 Acceptance Scenarios).
- SC-7: Platform operations remain tenant-safe under a simulated dependency failure (e.g., health-check source down): tenant isolation and audit integrity are unaffected even when a monitoring widget shows "unavailable."
- SC-8: Cross-tenant support access is never obtainable without an explicit reason and a visible time bound, verified by attempting to bypass each requirement individually and observing rejection.

---

## 26. Integration Boundaries

| Boundary | Nature of Interaction |
|---|---|
| **Authentication** | Platform Administration consumes the existing session/authentication infrastructure (session model, revocation) — it does not replace or fork authentication. A Platform Admin session is a distinct session *type* issued through the same underlying mechanism. |
| **Companies** | Platform Administration reads and writes `CompanyStatus` transitions (suspend/reactivate only) and reads company identity/settings for the Tenant Detail view; it does not own the `Company` model. |
| **Users/Roles** | Platform Administration's RBAC model is structurally separate but conceptually mirrors the existing `SYSTEM_ROLES`/`Permission` pattern; no shared tables. |
| **Feature Toggles** | Platform Administration's Plan Entitlement layer sits above the existing per-module tenant feature-toggle tables and resolves against them per §17.2; it does not replace them. |
| **Audit** | Platform-level audit records follow the existing Constitution §35 schema; whether they live in a new platform-scoped table or a cross-cutting view over existing tables is a Plan-phase decision, not specified here. |
| **Existing ERP modules** (Inventory, Purchase, Sales, Accounting, future CRM) | Consulted only for usage metering (e.g., transaction counts) and entitlement enforcement; Platform Administration never directly manipulates their business records. |
| **Future Billing Provider** | Integrated via the existing Plugin/Adapter pattern (Constitution §47); Epic 9A defines the Subscription/Plan data concepts the adapter will eventually act on, not the adapter itself. |
| **Future AI Provider** | Integrated via the existing Plugin/Adapter pattern (Constitution §47); Epic 9A defines the provider-neutral usage/credit schema requirements only. |
| **Future Notification Provider** | Integrated via the existing Plugin/Adapter pattern (Constitution §47); Epic 9A defines administrative alert *requirements*, not a notification product. |
| **Observability** | Platform Health consumes the existing `/health*` endpoints and the outbox's published/pending state; it does not introduce a new observability platform. |

---

## 27. Out of Scope

- Full payment gateway implementation.
- Full SaaS invoicing/accounting system for platform billing.
- AI assistant implementation, OpenClaw integration, or any LLM provider implementation.
- Full customer self-service billing portal.
- Mobile Platform Admin application.
- Kubernetes, microservices migration, or a separate analytics/data warehouse.
- Full BI platform.
- Arbitrary browsing or editing of tenant business transactions by Platform Admins.
- Unrestricted user impersonation ("login as user").
- Production infrastructure redesign.
- Features belonging to future ERP Epics (e.g., CRM's own business logic, Installments, Reports).
- Fixing pre-existing, unrelated defects surfaced during research (missing role checks on feature-flag endpoints across four modules; the frontend admin page calling a non-existent `listCompanies()` endpoint instead of `listAdminCompanies()`; the `SUPER_ADMIN`/`super_admin` casing inconsistency in `purchase/router.py`) — these are flagged in [§28 Risks](#28-risks) for separate remediation.

---

## 28. Risks

1. **Legacy `super_admin` scaffolding is dead code that must be superseded, not extended.** Three independent redeclarations of `_ROLE_SUPER_ADMIN` exist, and the underlying `CurrentUser.roles` is always empty in production. Risk: an implementation could be tempted to "just populate `roles=["super_admin"]`" as a shortcut instead of building the real Platform Administrator Account model this spec requires, reintroducing a single-flag authorization model instead of genuine RBAC. Mitigation: this spec explicitly requires (BR-9A-002) that platform authority never derives from `CurrentUser.roles`.
2. **Adjacent, pre-existing security gap**: the four modules' feature-flag update endpoints (`inventory`, `sales`, `purchase`, `accounting`) currently have no role/permission check beyond active tenant membership — any authenticated tenant member can toggle any feature flag for their company. This is not caused by, or fixed by, Epic 9A, but Epic 9A's Plan Entitlement layer sits directly above this gap; the Plan phase should flag this to the owning modules for separate remediation.
3. **Frontend admin page does not reach the real backend endpoint** (`AdminCompanyListPage` calls `listCompanies()`, not `listAdminCompanies()`, and no bare `GET /companies` route exists). Building on top of this without noticing could cause the new Platform Dashboard to inherit the same disconnect. Mitigation: flagged explicitly here for the Plan/implementation phase.
4. **Naming inconsistency** (`SUPER_ADMIN` vs. `super_admin`) if not deliberately resolved during the Plan phase could propagate into the new Platform RBAC permission-code naming.
5. **Epic 9 (CRM) concurrency**: Epic 9A and Epic 9 are being developed on separate, divergent branches. If Epic 9A introduces module-entitlement concepts that assume CRM's eventual feature-flag table shape, there is a risk of rework once CRM merges. Mitigation: this spec treats "module" entitlement generically (any module, not CRM-specific), minimizing coupling.
6. **Audit fail-closed design (BR-9A-024)** is stricter than the existing pattern in Accounting/Companies modules (which log-and-continue on audit issues in some paths). This is a deliberate elevation given platform-level blast radius, but it must be explicitly confirmed with the product owner during Plan review since it changes operational behavior (a Platform Admin action can now fail due to an audit-infrastructure problem, not just a business-rule violation).

---

## 29. Open Questions / Clarifications

All five clarifications originally raised during specification were resolved with the product owner on **2026-08-19**. Each entry below preserves the original question and reasoning for traceability, followed by the resolved decision. No open questions remain; this Epic is ready for `/sp.plan`.

- **OQ-1 — Are trial tenants/trial subscriptions a required capability now, or future-ready only?** No trial concept exists in the codebase today. The calling prompt conditioned trial requirements on "if trials are supported by the final specification," making this a genuine product decision, not a default.
  **Resolved: Future-ready only.** Epic 9A does NOT implement a trial subscription state now. Only `active` and `ended` are mandatory-now subscription states ([§23.2](#232-subscription-lifecycle-new--minimal-model)); the Plan/Subscription data model MUST remain extensible enough to add `trial` later without a breaking redesign (FR-9A-130, Assumption A3). This matches the specification's own recommended default and Constitution §2 (Simplicity) / Do-Not-Over-Engineer guidance.
- **OQ-2 — During an active cross-tenant support-access session, may a Platform Admin view (read-only) the target tenant's own business records (e.g., a specific invoice a customer is complaining about), or is support access strictly limited to configuration/entitlement/user inspection?** BR-9A-021 defaulted to inspection-only in the narrow sense (configuration/entitlements/users), but real support scenarios could plausibly require seeing an actual business record.
  **Resolved: Strictly inspection-only — no business-record access, read or write, ever, in or out of a support session.** BR-9A-021 and §18.3/§18.4 are updated accordingly. If a genuine future need for read-only business-record access during support sessions is confirmed, it requires its own explicit specification update, not an implicit extension of this Epic.
- **OQ-3 — When a tenant is suspended, must already-established tenant-user sessions be actively force-terminated at the moment of suspension, or is "blocked on next request" sufficient?** The existing `CompanySuspendedError` pathway already blocks the next request; whether Epic 9A must add active session termination was a security-posture decision affecting NFR scope.
  **Resolved: "Blocked on next request" is sufficient.** No new active session-termination mechanism is required for suspension in this Epic ([§14.3](#143-effect-of-suspension-on-access-and-data), Edge Case #19). This reuses existing behavior and keeps scope minimal; active force-termination on suspension remains a possible future security-posture enhancement, not a requirement.
- **OQ-4 — Are there specific performance/scale targets (tenant count, concurrent Platform Admin users, dashboard load time) that Platform Administration must meet?** No existing project standard was found for this.
  **Resolved: No specific numeric targets in this Epic.** Non-functional requirements stay qualitative ("responsive," "paginated from the outset," per [§24](#24-non-functional-requirements)). Fabricating a number would misrepresent an unvalidated target as a requirement; numeric SLOs MAY be established later via a dedicated ADR once real usage data exists.
- **OQ-5 — Should Platform Admin account creation itself require an existing Platform Owner to approve it (bootstrap problem), or is the very first Platform Owner account provisioned out-of-band (e.g., a seed/migration script)?** This affects Epic 9A's own "Definition of Done" — there must be some non-circular way to create the first Platform Admin.
  **Resolved: Out-of-band seed/migration script.** The very first Platform Owner account is provisioned by a one-time seed/migration mechanism outside the normal `platform.admins.manage`-gated API (FR-9A-036, BR-9A-031, Assumption A8, [§14.4](#144-platform-administrator-accounts)). This is a standard, auditable bootstrap pattern that cleanly breaks the circularity.

---

## 30. Constitution Compliance / Traceability

| Constitution Section | How Epic 9A Complies |
|---|---|
| §5 Modular Monolith | Platform Administration is specified as platform-level module(s) within the existing architecture ([§7.1](#71-in-scope-this-epic), [§24](#24-non-functional-requirements) Maintainability) — no microservice, no separate deployable system. |
| §9 Multi-Tenant Principles | Tenant isolation is never weakened; all cross-tenant capability is explicit, privileged, and audited ([§6](#6-actors--trust-boundaries), [§18](#18-supportcross-tenant-access-requirements)), fulfilling §9's existing requirement that "admin access to tenant data uses separate, audited pathways." |
| §11 Feature Toggles | Epic 9A does not replace tenant feature toggles; it adds the Plan Entitlement layer above them and defines their interaction deterministically ([§17](#17-entitlement--quota-requirements)). |
| §16 Authentication & Authorization | Platform Administration consumes existing authentication infrastructure; it adds a distinct Platform RBAC layer, never bypassing or replacing tenant authorization ([§15](#15-platform-rbac-requirements), [§26](#26-integration-boundaries)). |
| §19 Security Principles | Least privilege, IDOR/BOLA protection, CSRF protection, safe error responses, and session revocation are all specified explicitly ([§19.3](#193-platform-security-requirements)). |
| §22 Logging & Observability | Platform Health builds on existing structured logging and health-check infrastructure; no new observability platform is introduced ([§21](#21-operational-monitoring-requirements)). |
| §35 Audit Trail | Platform audit reuses the existing who/what/when/before/after/context schema, append-only, with no parallel mechanism ([§19.1](#191-platform-audit-visibility)–[§19.2](#192-append-only-guarantee)). |
| §37 SaaS Readiness | Epic 9A is the operationalization of §37's plan/company-plan/quota/limit/billing-hook requirements, which had zero implementation prior to this Epic ([§16](#16-plan--subscription-requirements), [§17](#17-entitlement--quota-requirements)). |
| §46 Business Configuration Philosophy | Platform-wide configuration is explicitly kept separate from, and non-overriding of, tenant business configuration ([§12.14](#1214-platform-configuration)). |
| §47 Plugin Architecture | Future billing, AI, and notification providers are explicitly scoped to integrate via the existing adapter pattern, never as a direct dependency of this Epic's core logic ([§26](#26-integration-boundaries)). |
| §49 Event-Driven Communication | Suspend/reactivate reuse the already-defined (currently unused) `CompanySuspendedEvent`/`CompanySuspensionLiftedEvent` domain events rather than inventing a parallel notification path ([§9.1](#91-existing-dependencies-reused-not-redefined)). |
| §50 Platform Administration & SaaS Control Plane Principles | This Epic is the direct specification-level realization of §50 in its entirety — distinct actor, central control plane, platform RBAC, audited cross-tenant pathways, tenant lifecycle governance, and AI/billing readiness, all without introducing unnecessary infrastructure complexity. |

**Self-Review Confirmation** (per calling prompt §41): This specification does not renumber any existing Epic; does not modify `constitution.md`; does not design database tables, API routes, or UI components (implementation is deferred to Plan); did not invent business rules where genuine product ambiguity existed — instead surfaced five Open Questions and resolved all of them with the product owner on 2026-08-19 (see [§29](#29-open-questions--clarifications)); and every requirement is traceable to either an existing, researched codebase fact or an explicit new-capability decision documented in [§9.2](#92-new-requirements-introduced-by-epic-9a). No open questions remain; this specification is ready for `/sp.plan`.
