# Research: Epic 9A — Platform Administration / Super Admin

Written during `/sp.plan` (Phase 0), before any implementation. Documents the Technical Context decisions and Technical Unknowns resolved while planning — cross-referenced to `plan.md` rather than duplicated in full there. See `plan.md` §3 for the full, cited repository reconnaissance this research is grounded in.

## Decision 1: Tenant Suspension Enforcement — Company-Scoped Access Invalidation

> **Revised after a second reconnaissance pass.** The first version proposed adding a `Session.is_revoked` check to `get_current_user()` and revoking sessions by `user_id`. Direct model inspection disproved that approach; the corrected decision follows.

**Context**: The Specification (resolved OQ-3) requires tenant suspension to *actively* invalidate access, not merely block the next request. Two repository facts govern the design:

1. **A `Session` has no tenant dimension.** `sessions` carries `user_id` only — no `company_id` — and its own docstring describes it as a device login for a human ("browser + mobile"). The access-token payload likewise carries no company claim, and `User.company_id` is a documented nullable placeholder. Company context reaches a request **only** as the `{company_id}` path parameter.
2. **The five business modules never check company status.** They mount `get_current_company_member`, which validates `CompanyMember.status` but never reads `Company.status`; only the `companies` module uses `get_current_company`, which does.

A third pass added a decisive third fact:

3. **`login()` and `refresh()` differ exactly where it matters.** `AuthService.login()` calls `create_session(...)`, producing a **new `Session` row** with a new `created_at`. `AuthService.refresh()` calls `rotate_refresh_token(...)` then `create_access_token(session_id=new_record.session_id)` — reusing the existing session and **never creating one**. So `Session.created_at` is a genuine authentication-event timestamp that survives any number of refreshes unchanged, is server-generated (`server_default=func.now()`, immutable after INSERT), and is reachable via the already-signed `sid` claim (`CurrentUser.session_id`).

**Decision**: enforce at the company-access boundary, not on global sessions. A shared `assert_company_access_allowed(db, company_id, session_id)` helper is called from both company-access dependencies, rejecting when the company is `suspended`/`deleted` (Layer 1) or when **`Session.created_at <= Company.access_invalidated_at`** (Layer 2). No new JWT claim, no new session column, and no change to `get_current_user()`/`CurrentUser` — one primary-key lookup on `sessions` suffices.

**Rationale**: this is the only design satisfying every requirement simultaneously. It makes a suspended tenant inaccessible immediately across *all* modules (fact 2 shows nothing does that today), remains precisely tenant-scoped (fact 1 shows session-level revocation cannot be), and — crucially — makes reactivation require a **real login** (fact 3), because a refresh cannot advance authentication time.

**Alternatives considered**: (a) comparing the watermark to the access token's `iat` — **rejected**: a refresh mints a token with a fresh `iat`, so a pre-suspension refresh credential redeemed after reactivation would pass the check and restore access with no re-authentication at all, violating FR-9A-018. `iat` is token-issuance time, not authentication time. (b) Adding a dedicated `auth_time` JWT claim carried across refreshes — rejected as unnecessary: it would change the token format and require both login and refresh to populate it correctly, when `Session.created_at` already holds exactly this value with stronger tamper-resistance (it lives in the database, not the token). (c) `UPDATE sessions ... WHERE user_id IN (members of the suspended company)` — rejected: a user belonging to Company A *and* B holds one session covering both, so this would sign them out of still-active Company B, and it wouldn't block the business modules at all. (d) Company status check alone, no watermark — rejected, reactivation would silently resurrect pre-suspension tokens. (e) A Redis revocation list — rejected, no Redis exists in this stack. See `plan.md` §10, ADR-6.

## Decision 2: Audit Fail-Closed Transaction Pattern — Follow Accounting, Not Auth/Companies

**Context**: Three independent audit-logging implementations exist in this codebase today, with materially different commit semantics: `auth.audit_logs` is explicitly fail-open (catches and swallows write exceptions); `companies.company_audit_logs` commits independently of the caller's transaction; `accounting.accounting_audit_log` is the only genuinely fail-closed precedent (`flush()`-only, caller commits state-change + audit together).

**Decision**: Platform audit (`PlatformAuditEvent`) follows the Accounting pattern exactly — repositories `flush()`, never `commit()`, for audited mutations; the service layer owns one `db.commit()` per operation.

**Rationale**: BR-9A-024/FR-9A-204 require audit-write failure to roll back the whole mutation. Only one of the three existing patterns actually achieves this; the other two are structurally incompatible with the requirement regardless of intent.

**Alternatives considered**: Extending `BaseRepository.create()/.update()`'s default auto-commit behavior with a "fail-closed" flag — rejected as unnecessary complexity when a proven precedent (Accounting) already exists in this exact codebase to copy directly. See `plan.md` §20, ADR-5.

## Decision 3: Module-Grain Entitlement Lookup — Adapter, Not Assumed Convention

**Context**: The generic entitlement resolver (`plan.md` §13) needs to answer "is this module's Tenant Toggle currently enabled" for each of 5 modules. CRM confirmed a single master flag key (`feature.crm.enabled`); the other 4 modules (Inventory, Sales, Purchase, Accounting) use a generic multi-row `flag_key`/`is_enabled` shape with no confirmed single master key during this planning pass.

**Decision**: A small `ModuleEnablementProvider` adapter protocol, one ~15-line implementation per module, rather than one generic query assumed to work identically for all 5.

**Rationale**: Guessing a uniform convention and being wrong for even one module would silently break entitlement resolution for that module — a correctness bug with security implications (an incorrectly "always available" or "always unavailable" module).

**Default rule (decided here, not deferred)**: if a module exposes no module-grain master toggle, its provider returns `enabled = True`, meaning that module has no tenant-level opt-out at module grain and the **Plan ceiling alone governs** its availability. This is deterministic, fails safe for existing tenants (who retain current access through the rollout, `plan.md` §34), and means no adapter must invent a master key that does not exist. Per-module fine-grained flags continue working exactly as they do today.

**Alternatives considered**: A single generic `SELECT is_enabled FROM {module}_feature_flags WHERE company_id=:id AND flag_key=:master_key` — rejected because `:master_key` isn't confirmed to exist for 4 of 5 modules.

## Decision 4: Platform Owner Bootstrap — Explicit Operator Command, Decoupled from Migrations

> **Revised.** The first version of this decision used an idempotent Alembic data migration (`062_bootstrap_platform_owner.py`) that returned silently when bootstrap environment variables were absent. That is unsafe and has been replaced.

**Context**: FR-9A-036 requires an out-of-band mechanism because every in-app Platform-Administrator-creation path requires an already-authenticated Platform Admin — a bootstrap circularity for the very first account. No existing CLI-command framework (Click/Typer/`manage.py`) exists in this repository.

**Why the migration approach was rejected**: Alembic records a revision as applied once it completes, and never re-runs it. A migration that silently no-ops on missing configuration therefore produces a deployment that is permanently stamped "bootstrapped" while having **no Platform Owner** — and supplying the environment variables later has no effect, because the revision will not run again. Making the migration *fail* instead is equally wrong in the opposite direction: it would block unrelated schema upgrades for anyone who hasn't configured bootstrap credentials.

**Decision**: a separate, explicitly-invoked, idempotent module entry point — `python -m modules.platform_admin.bootstrap` — run **after** `alembic upgrade head`. It exits `0` on successful creation *or* when an owner already exists, and **non-zero with an explicit message** when configuration is missing or invalid. Credentials come from `PLATFORM_OWNER_BOOTSTRAP_EMAIL` / `PLATFORM_OWNER_BOOTSTRAP_PASSWORD_HASH` (pre-hashed). Schema versioning and credential provisioning are fully decoupled; migration `062` no longer exists.

**Rationale**: this is the only arrangement that is safe in both directions — a missing bootstrap config can never masquerade as success, and it can never block a schema upgrade. Re-running after fixing configuration simply works, since no revision gates it. No CLI framework is introduced; a bare `python -m` entry point suffices.

**Alternatives considered**: keeping the migration but hard-failing on missing config (rejected: couples unrelated deployment concerns); a public bootstrap HTTP endpoint (rejected outright — would expose Platform authority creation to the network). See `plan.md` §7, ADR-8.

## Decision 5: Plan Entitlement Enforced at Point of Use, Not Only at Toggle Mutation

**Context**: The first draft enforced the Plan ceiling primarily where a tenant mutates a feature toggle. That leaves a real bypass: if a Platform Admin moves a tenant to a Plan that denies a module, the tenant's previously-enabled toggle row is untouched, and a module-level gate that reads only the toggle (e.g. CRM's `require_crm_enabled`) keeps granting access.

**Decision**: a mount-level `require_capability_entitled("<capability>")` dependency on all five business-module routers, evaluated per request via the single shared resolver. The toggle-mutation check is retained as a secondary guard only.

**Rationale**: the router mount is where this repository already centralises per-module request gating, so every endpoint in a module is covered automatically with no per-endpoint annotation and no per-module reimplementation of the resolution logic. A Plan downgrade then takes effect on the tenant's next request without anyone having to hunt down and flip stale toggle rows — and stored toggle values are preserved, so a later re-upgrade restores the tenant's original preference automatically.

**Alternatives considered**: per-endpoint decorators (easy to forget on a new endpoint); middleware (no middleware convention exists in this codebase); a background job that rewrites tenant toggles on plan change (rejected — destroys the tenant's own preference and is eventually-consistent where the requirement is immediate). See `plan.md` §13.1, ADR-3.

## Decision 6: Frontend API Client — Injected Auth Strategy, Two Instances

**Context**: Platform and tenant traffic must never share tokens or refresh flows. Inspection of `frontend/src/lib/api/client.ts` shows `ApiClient`'s transport is already constructor-injectable (`baseUrl`), but its auth is hardcoded at module scope: `buildHeaders()` and `postMultipart()` call the tenant `getAccessToken()`, and the 401 branch calls the tenant `acquireRefreshLock()`, `clearTokens()`, and dispatches the tenant `session-expired` event.

**Decision**: introduce an `AuthStrategy` interface (`getToken`, `refresh`, `onAuthFailure`), inject it via the constructor, and export two configured instances — `apiClient` (tenant, behaviourally identical to today) and `platformApiClient` (platform).

**Rationale**: crossover becomes structurally impossible rather than merely discouraged — each instance can only reach its own domain's token and refresh lock. All shared transport logic (URL building, header assembly, error parsing, 401-retry-once, `StandardResponse<T>` unwrapping, verb helpers) stays in one class, so nothing is duplicated, and no existing domain file changes.

**Alternatives considered**: reusing the singleton unchanged (rejected — a Platform 401 would invoke the tenant refresh flow and Platform requests would carry the tenant token); a fully separate duplicated client (rejected — needless duplication). See `plan.md` §23.1, ADR-11.

## Decision 5: No New Datastore, No New Deployable Service

**Context**: The calling brief explicitly forbids introducing Redis, microservices, or a second application stack unless the repository already uses them or a strong justification exists.

**Decision**: Every new table lives in the existing PostgreSQL database; every new module lives inside the existing FastAPI monolith (`backend/modules/platform_admin/`); every new frontend surface lives inside the existing Next.js app (`(platform-admin)` route group).

**Rationale**: `docker-compose.yml` confirms no Redis exists; nothing in Epic 9A's actual access patterns (indexed point-lookups, bounded paginated lists, periodic batch usage aggregation) requires a cache or a separate service to perform adequately at this project's stated scale (no numeric SLA was even established, per resolved OQ-4).

**Alternatives considered**: None seriously — this decision follows directly and unambiguously from Constitution §5 and the repository's own confirmed infrastructure inventory.
