# Implementation Plan: Epic 12 — Deployment / Production Readiness

**Branch**: `012-production-readiness` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/012-production-readiness/spec.md`, together with [clarifications.md](clarifications.md) and [amendments-proposed.md](amendments-proposed.md). The amendments are applied and merged as PR #10, commit `e0f45d4`.
**Governing documents**: Constitution **v2.0.0**; ADR-0001, ADR-0002, ADR-0003, ADR-0007 (in-house authentication), ADR-0008 (production topology) and ADR-0009 (single-maintainer governance).

> **Planning only.** This plan does not include application code, migrations, package installs, infrastructure, paid services, runtime configuration changes or `tasks.md`.
>
> **Output scope.** The owner asked for `plan.md` only (2026-10-09). The material the standard `/sp.plan` flow puts in separate files is therefore kept inside this plan:
> - research and provider comparisons: §6;
> - data-model deltas: §7;
> - interface and contract deltas: §8;
> - verification and quickstart: §11.
>
> `update-agent-context.sh` was **not** run, because it edits `CLAUDE.md`.

---

## 0. Preflight Gate

**Status: PASS.** Verified on 2026-10-09 against the repository.

| Check | Result | Evidence |
|---|---|---|
| Governance PR merged into `main` | PASS | `origin/main` = `e0f45d4` "docs(governance): Constitution v2.0.0 and ADR-0007/0008/0009 … (#10)"; `012-production-readiness` contains it (`git merge-base --is-ancestor e0f45d4 HEAD`) |
| Constitution version | PASS | `.specify/memory/constitution.md:1556`: `**Version**: 2.0.0` |
| Canonical ADRs present | PASS | `history/adr/0007-in-house-jwt-authentication-architecture.md`, `0008-production-deployment-topology.md`, `0009-single-maintainer-governance.md` |
| Official epic title | PASS | Used in `spec.md`, `clarifications.md`, `amendments-proposed.md`, the checklist, `docs-project-context/EPICS.md` and `PROJECT_CONTEXT.md` |
| Spec and governance agree on substance | PASS, with wording drift | See the note below |

**Wording drift (non-blocking; not edited here because of the plan-only scope).** Some `spec.md` lines were written before the merge and still describe the governance change as pending:
- the D-01 row in §20: "Constitution §6.6 amendment and a superseding ADR are pending";
- G-22: "effective on merge";
- DEP-01: "decided … before planning";
- §22 row 1: "inconsistency flagged, not resolved here".

The substance is resolved by Constitution 2.0.0 §6.6 and ADR-0008. These lines should be refreshed in a later documentation pass. They do not change any requirement.

---

## 1. Summary

Epic 12 takes the merged, CI-green modular monolith to a state where real tenants' financial data can be run in production, and **proves** it with evidence (spec §1.1). The approach reuses everything that already works (spec §2.1, S-01…S-14) and closes the gaps G-01…G-25 in a strict order:

1. **Fail-safe foundations.** Configuration guardrails; three runtime roles from one image (`api`, a one-shot `migrate`, a single `scheduler`); recurring-journal posting that is exactly once and atomic; Docker hardening.
2. **Security conditions of ADR-0007.**
   - immediate session revocation (SEC-24);
   - shared, proxy-aware authentication rate limiting (SEC-20);
   - no platform bypass through a tenant token (SEC-26);
   - frontend CSP (SEC-04/05);
   - real email (FR-PRD-032).
3. **Functional production gaps.**
   - private, tenant-scoped object storage with short-lived signed URLs;
   - SVG removed;
   - no fake or empty export URLs.
4. **Observability.**
   - access logs that carry `company_id`;
   - error tracking;
   - metrics;
   - truthful readiness checks;
   - external uptime probes;
   - alerts linked to runbooks.
5. **Enforced CI and CD.**
   - required checks that always report;
   - image scanning;
   - immutable artifacts;
   - staging, then an approval step, then production.
6. **Environments and data safety.**
   - staging that mirrors production;
   - least-privilege database roles;
   - PITR plus an independent off-provider backup;
   - a 7-year business-record archive (a planning assumption);
   - restore drills.
7. **Proof.**
   - the PostgreSQL tenant-isolation suite;
   - a performance baseline;
   - rehearsed runbooks;
   - the first production deploy;
   - the evidence-based readiness gate.

Providers are **compared, not chosen** in this plan (§6). Proposed objectives (RPO ≤1 h, RTO ≤4 h, 99.5%) are carried as targets to be proven, never as guarantees.

---

## 2. Technical Context

| Item | Value |
|---|---|
| **Language/Version** | Python 3.12 (backend); TypeScript 5.x on Next.js 16.3.x (`frontend/package.json`: `next ^16.3.8`, React 19.2.4) |
| **Primary Dependencies** | **Existing:** FastAPI, Pydantic v2, SQLAlchemy 2.x (sync), Alembic, PyJWT, argon2-cffi, slowapi, boto3, APScheduler, httpx; TanStack Query, Tailwind 4, shadcn/ui, Recharts, Playwright, Jest.<br>**New candidates** (each needs justification under §6 and DEP-06): an error-tracking SDK; a metrics client; a CI image scanner (CI-only). No new runtime datastore unless §6.3 evidence demands one. |
| **Storage** | PostgreSQL 16 (Alembic head `078`; requires the `pg_trgm` extension — `migrations/versions/005_inventory_phase0.py:37`); S3-compatible private object storage (D-04). |
| **Testing** | pytest (the default suite runs on in-memory SQLite, `tests/conftest.py:109`). Real-PostgreSQL tests use the existing throwaway-database fixtures `pg_test_db`, `alembic_upgrade` and `db_engine` (`tests/integration/migrations/conftest.py`), already reused by `tests/integration/api/v1/reports/postgres/conftest.py`. Jest and Playwright (`frontend/e2e/*`). CI runs PostgreSQL 16. |
| **Target Platform** | ADR-0008:<br>• Vercel for the frontend;<br>• a Linux VPS running Docker for the API, migrate and scheduler roles;<br>• managed PostgreSQL;<br>• S3-compatible storage;<br>• a transactional email provider.<br>Providers and regions are **OPEN** (§6). |
| **Project Type** | Web application (`backend/` + `frontend/`) and operations assets (new `deploy/`, `docs/operations/`) |
| **Performance Goals** | **PROVISIONAL** until D-10. Targets are derived from the measured baseline (PERF-01…04; §5 P11). No figure is invented here. |
| **Constraints** | Proposed objectives: RPO ≤ 1 h, RTO ≤ 4 h, 99.5% monthly availability (not an SLA).<br>Operational backups kept 30 days; business records kept 7 years (planning assumption).<br>Epic 11 contracts stay byte-compatible (FR-PRD-060).<br>Single maintainer (NFR-PRD-08); smallest architecture (NFR-PRD-09). |
| **Scale/Scope** | **OPEN** (D-10): tenants, users per company, concurrent users, invoices and exports are owner inputs. A synthetic, clearly labelled *assumed* workload is used until they arrive (PERF-03). |
| **Open inputs** | Each is permitted to stay open through planning (spec §18, owner decision 2026-10-09), and **must** close before the final gate (P13):<br>• provider and region selection;<br>• sender domain;<br>• professional confirmation of the 7-year retention;<br>• D-10 figures. |

None of these is a NEEDS CLARIFICATION that blocks design. Each open input has a defined method (§6) and a defined gate (§10).

---

## 3. Constitution Check (v2.0.0)

*GATE: evaluated before design and re-evaluated after design (§3.2).*

### 3.1 Pre-design

| Constitution rule | Plan compliance |
|---|---|
| §5 Modular monolith; no premature microservices (§50) | One backend image with three process roles. No new services, Kubernetes, queues or caches without measured evidence (§6.3, PERF-05 deferred). |
| §6 Stack and §6 RULE; §44 #7, #15 | The stack is unchanged. The proxy, error tracker, metrics client and image scanner each have a recorded justification (DEP-06). An ADR is suggested where the three-part test passes (§12). Redis is **not** adopted (§6.3 R2). |
| §6.6 Deployment (ADR-0008) | Followed exactly. Providers are selected only through the §6 comparison. |
| §9 / §44 #10–11 Tenant isolation | The PostgreSQL negative suite (P7); tenant-prefixed object keys; no change to `company_id` scoping. |
| §15 Thin handlers / §44 #2–4 | New behaviour goes into services, repositories and middleware. Handlers stay thin, and no SQL is added in routers. |
| §16 Auth (ADR-0007), including Immediate Revocation | SEC-24 (P3) brings the code into line with the new §16 capability. The Sync Impact Report lists this as known non-compliance until P3 is done. |
| §18 Migrations (downgrade, expand/contract) | Every new migration includes a downgrade and follows expand/contract. Migrations run as a single release job (P2). |
| §19 Security; §20 Configuration and secrets | Guardrails (P1); secrets from the environment or secret store only; `.env.example` completeness test. |
| §22 Logging and observability | `company_id` and access logs (P6). |
| §25 Performance | No optimization without a measured bottleneck (P11). |
| §27 Docker | Non-root containers, health checks, read-only filesystem where feasible, separate production orchestration (P2, P8). |
| §28/§29 (ADR-0009) | Squash PRs; required checks must pass; self-review recorded; a bypass may cover only the approval count. |
| §33 File storage; §34 Backup; §35 Audit | P4; P10; audit stays append-only and audit-before-delivery is preserved (RB-02, FR-PRD-060). |
| §43 DoD "deployed to staging and validated" | Satisfied for the first time by P9. |

**Result: PASS.** There are no unjustified violations, so Complexity Tracking stays empty (§14).

### 3.2 Post-design re-check

Re-run after §5 to §8 were written. **PASS.** Three design points need explicit justification. Each is recorded in §5 and is not a violation:
1. a reverse proxy on the VPS — required by DEP-02 for TLS termination;
2. new SDK dependencies for error tracking and metrics — §44 #15 justification in §6.4;
3. one small table for the shared rate limiter — an alternative to Redis that keeps the stack unchanged.

---

## 4. Project Structure

### 4.1 Documentation (this feature)

```text
specs/012-production-readiness/
├── spec.md                 # approved specification (3 clarification rounds)
├── clarifications.md       # decision matrix, Better Auth evidence, SEC-24 comparison
├── amendments-proposed.md  # applied in PR #10
├── plan.md                 # this file
├── checklists/requirements.md
└── tasks.md                # NOT created here (/sp.tasks)
```

### 4.2 Source and operations (expected changes, from inspection)

```text
backend/
├── main.py                              # lifespan: no migrations/scheduler in API role; TrustedHost; error-tracker init
├── Dockerfile                           # production CMD per role; proxy-header flags; healthcheck
├── core/
│   ├── config/settings.py               # ENVIRONMENT Literal; email/storage/observability keys; guardrail validator
│   ├── config/guardrails.py             # NEW — §9.4 rule set (pure functions, one test per rule)
│   ├── migrations.py                    # NEW fn: expected-head check (no upgrade in prod)
│   ├── scheduler/runner.py              # NEW — dedicated scheduler entrypoint + advisory-lock leadership
│   ├── auth/dependencies.py             # SEC-24 session check folded into user lookup
│   ├── logging/setup.py                 # COMPANY_ID_CONTEXT; access-log formatter fields
│   ├── middleware/access_log.py         # NEW — one entry per request (route template, status, duration)
│   ├── observability/{metrics,errors}.py # NEW — metrics registry; error-capture scrubbing
│   ├── ratelimit/                       # NEW — shared limiter storage (PostgreSQL-backed, §6.3 R1)
│   └── storage/s3_client.py (+ factory.py NEW)  # private objects, keys not URLs, presigned GET
├── api/v1/router.py                     # readiness: DB + schema revision + storage
├── modules/
│   ├── accounting/services/{scheduler,recurring_journal_service,posting_engine}.py  # atomic claim+post
│   ├── accounting/repositories/recurring.py
│   ├── accounting/services/permission_check.py   # SEC-26 remove tenant-path super_admin bypass
│   ├── auth/{router.py, services/email_service.py, services/auth_service.py}       # limiter store; real email
│   ├── auth/repositories/session_repository.py
│   ├── companies/{dependencies.py, router.py, services/company_logo_service.py, models/company.py}
│   ├── users_roles/{dependencies.py, services/profile_service.py}
│   ├── auth/models/user.py              # avatar object-key column (expand/contract)
│   ├── inventory/{dependencies.py, services/export_service.py}
│   └── reports/ (export path)           # metrics hooks only — no contract change
├── migrations/versions/079+_*.py        # object-key columns; rate-limit buckets (numbers assigned at implementation)
└── tests/
    ├── unit/core/test_guardrails.py, test_env_example_completeness.py
    ├── integration/postgres/            # NEW — scheduler multi-process, revocation multi-process, rate-limit multi-process
    └── security/postgres/               # NEW — SEC-10 negative isolation suite on real PostgreSQL
frontend/
├── next.config.ts                       # static security headers
├── src/proxy.ts (Next 16 request proxy; convention verified in P0) # per-request CSP nonce
├── src/app/layout.tsx                   # nonce propagation
└── e2e/security-headers.spec.ts, smoke.spec.ts  # NEW
deploy/                                  # NEW — production/staging orchestration (not the dev compose)
├── compose.production.yml               # api, scheduler, migrate (profile), proxy; pinned digests; no bind mounts
├── proxy/                               # TLS entry-point config (product per §6.2)
├── db/roles.sql                         # least-privilege role definitions (NFR-PRD-04)
└── backup/                              # independent dump, archive, verify scripts
.github/workflows/
├── backend.yml, frontend.yml, pr-checks.yml  # always-reporting required checks; image scan
├── deploy.yml                           # NEW — build once → staging → approval → production
└── security-rescan.yml                  # NEW — weekly (SEC-33)
docs/operations/                         # NEW — runbooks 1–9, environment matrix, readiness report template
.env.example                             # every key (FR-PRD-012)
```

**Structure decision:** the existing web-application layout is kept. Only `deploy/` and `docs/operations/` are new top-level folders, and both hold operations material, not application modules.

---

## 5. Key Design Decisions (with options and rationale)

Each decision lists the requirement IDs it serves. Items marked **P0-research** are confirmed by a short spike in Phase 0 before implementation.

### P-1 Three runtime roles from one image

The same backend image digest runs in three ways:
- `api` — uvicorn workers. It never migrates and never schedules.
- `migrate` — a one-shot `alembic upgrade head` that runs as the **migration DB role**, before rollout.
- `scheduler` — exactly one long-running process.

A setting (`RUN_MIGRATIONS_ON_STARTUP`, default false outside `development`) keeps the developer experience: dev compose still auto-migrates.

- Covers: FR-PRD-004, FR-PRD-005, FR-PRD-006, DB-01, G-03, G-04.
- Rejected: an init container per replica (it still runs N times) and a migration lock inside the app (it couples startup to DDL).

### P-2 Schema-revision readiness and the rollback-compatibility tension

FR-PRD-005 says readiness must fail when the database is not at the code's expected head. But FR-PRD-023 and spec §15 say rollback means running code N-1 against schema N, and N-1 does not know revision N.

**Resolution:**
- Readiness passes when the DB revision equals the code head.
- Otherwise it fails, unless the `SCHEMA_REVISION_ALLOW=<db_revision>` override is set (rules below).

**Override rules (`SCHEMA_REVISION_ALLOW`):**

1. **Authorized procedure only.**
   - It may be set only by executing code-rollback runbook #2, under the Release Approver's authorization (spec §15).
   - It is never set in a forward deploy, in a default configuration, in `.env.example` values, or by hand outside the runbook.
   - The runbook execution log records who authorized it, when, why, and the **exact database revision** the override names.
2. **Exact match only.**
   - The override applies only when its value equals the database's **actual** revision (exact-match validation).
   - Invalid values (empty, malformed, a wildcard or pattern, or an unknown revision format) and mismatched values (a well-formed revision that is not the database's actual revision) are **rejected**: the override is not applied, readiness stays failed, and an error is logged.
   - It never allows a database that is *behind* the code head.
3. **Logged on every use.**
   - At startup, and at each readiness evaluation while the override is active, a WARNING entry records the expected (code head) revision, the actual database revision, the override value and the release SHA.
   - The same values go into the rollback evidence artifact.
4. **Removed and verified after the next forward deploy.**
   - The deploy pipeline (P8) fails the forward deploy if the override is still present in the target environment.
   - After the deploy, a check confirms it is absent and that readiness passes on an exact revision match.
   - The result is recorded in that release's evidence artifact.
5. **Not a compatibility proof.**
   - The override only stops readiness from *blocking* N-1 code. It does **not** establish that N-1 code works against schema N.
   - Compatibility must already be guaranteed by FR-PRD-023: expand/contract migrations, flagged in the PR, plus the P12 rollback rehearsal that runs N-1 against schema N.
   - A successful rehearsal proves compatibility only for the release it exercised. It is **not** a general proof for other migrations.
   - When N-1 compatibility with schema N is unsafe or unproven, the override must **not** be used. Recovery is a forward fix, or the approved PITR / database recovery procedure (runbook #3, Release Approver authorization, fresh backup first; spec §15, DB-02).

Rejected alternative: a compatibility table written by each migration. It costs a schema change and still needs operator judgment.

- Covers: FR-PRD-005, FR-PRD-023, FR-PRD-054, RB-01, acceptance scenario 2.

### P-3 Exactly-once scheduler and atomic recurring posting

**Evidence of the current defect:**
- `PostingEngine.post_direct` commits on its own (`posting_engine.py:624`; the docstring at lines 25–29 says "exactly ONE db.commit()" per method).
- The `RecurringJournalInstance` row is then written by `BaseRepository.create`, which commits again (`core/repositories/base.py:84`).
- A crash between the two commits leaves a posted journal with no instance row. The next run re-posts it. This is the G-04 duplicate-GL window.

**Design:**

1. **Leadership.** The scheduler process takes `pg_try_advisory_lock(<scheduler key>)` on a dedicated connection and holds it for its lifetime. A second scheduler instance sees the lock taken and stays idle. If the process dies, the connection drops and the lock is released, so no lease clock is needed and clock skew is irrelevant (spec §17.3).
2. **Per-job transaction lock.** Each job also takes `pg_advisory_xact_lock(<job key>)`. This is defence in depth if leadership is ever misconfigured.
3. **Claim first, in one transaction.** For each due template:
   - insert the instance row with status `PENDING`, relying on the existing unique `(template_id, execution_date)` constraint;
   - post the journal using an **additive, caller-owned-transaction mode** of `PostingEngine`. The default behaviour is unchanged for every existing caller; the new mode flushes without committing;
   - set the instance to `SUCCESS` and advance `next_run_date`;
   - **commit once.**
4. **On failure:** roll back, then record a `FAILED` instance in a separate short transaction, as today.
5. **The other two jobs** (`ar_ap_overdue_check_job`, `ap_bill_due_reminder_job`) are verified idempotent under re-run during P2. If either is not, it gets the same claim-first treatment.

- Covers: FR-PRD-006, SC-06, acceptance scenario 3, and the §17.3 edge cases (a scheduler dying mid-job; clock skew).
- Rejected: APScheduler job stores with locking (still per process, not cross-host); a separate queue (NFR-PRD-09).

### P-4 Immediate session revocation (SEC-24) — mechanism M1

The candidates are compared in `clarifications.md` §3.2. `get_current_user` already loads the user by primary key on every request (`core/auth/dependencies.py:83-84`).

**M1:**
- Replace that lookup with one query that also selects the `sessions` row for the JWT `sid` (primary-key join).
- Reject the request when the session is missing or `is_revoked`.
- There is no extra round trip and no cache, so every worker and instance sees the same state.
- If the database is unavailable, the request already fails, so the check fails closed by construction. An explicit test asserts a 401/503 with no fallback.

**Trigger coverage** (each trigger already revokes session rows):

| Trigger | Where the session rows are revoked |
|---|---|
| Logout | `auth_service.py:267-268` |
| Password reset | `auth_service.py:449-450` |
| Password change | `auth_service.py:521-522` |
| Member deactivate, suspend, lock and archive | `member_service.py:960/1100/1170/1244` |

M1 needs no new trigger code. "Sign out all devices" has **no endpoint** today. It is **not** added, because there are no new features (spec §1.2); the rule applies when such a flow exists.

**M2** (a user token epoch) is held in reserve, and **M3** (a revocation cache) is rejected unless P11 measures database pressure.

**Latency:** p50/p95 are measured before and after on the P11 harness. The acceptance tolerance is set from that measurement (**PROVISIONAL**).

- Covers: SEC-24, G-23, Constitution §16.

### P-5 Shared, proxy-aware rate limiting (SEC-20)

**Evidence:**
- `slowapi` `Limiter(key_func=get_remote_address)` keeps its counters in memory (`modules/auth/router.py:66`), and the companies router also uses `limiter.limit`.
- Uvicorn runs **without proxy-header trust** (`backend/Dockerfile:102`).

**Critical finding:** behind the TLS proxy (P-6), every client would appear as the proxy's IP. All users would then share one login bucket, so one attacker could lock everyone out. The fix has two layers:
1. Run uvicorn with `--proxy-headers` and `--forwarded-allow-ips` restricted to the proxy address. The client IP then comes only from the trusted proxy's `X-Forwarded-For`.
2. Use a shared counter store.

| Option | Assessment |
|---|---|
| **R1 — PostgreSQL fixed-window counters (recommended)** | One small table, updated with a single UPSERT that also returns the count. Applied to auth and company routes only, which are low volume. Consistent across workers and hosts. No new component. |
| R2 — Redis | Adds a stateful service, its operation and its failure mode (NFR-PRD-09). Adopted only if P11 shows database pressure from R1. |
| R3 — Proxy `limit_req` | Per-host only, so its correctness depends on the topology. Kept optional as an edge DoS layer, not as the SEC-20 mechanism. |

The decision for R1 versus a `limits` storage backend is confirmed in P0. R1 is likely custom, because `limits` has no PostgreSQL backend (**P0-research** to confirm).

- Covers: SEC-20, G-05, acceptance scenario 10.

### P-6 TLS entry point on the VPS

A reverse proxy terminates TLS, redirects HTTP to HTTPS, sets HSTS and forwards to the API.

| Candidate | Assessment |
|---|---|
| Caddy | Built-in automatic ACME |
| nginx + certbot | Mature, more configuration |
| Provider load balancer | Removes host TLS work; adds cost and lock-in |

This is a **P0 decision** recorded in the justification log. In every case: the database is not public, the API is reachable only through the proxy, and certificate-expiry alerts are configured (SEC-01).

- Covers: DEP-02, NFR-PRD-03, SEC-01.

### P-7 Private, tenant-scoped storage

- The `StorageClient` contract changes from "upload returns a public URL" to **"upload returns an object key"**, plus a `presigned_get(key, ttl)` method. boto3 already provides presigning, so no new dependency is needed.
- **Keys:** `{company_id}/{purpose}/{uuid}.{ext}`.
- **Bucket:** private, with no public ACL.
- **Logo and avatar:** store the **object key** in new key columns, using expand/contract.
  - Existing `logo_url`/`avatar_url` values are expected to be NULL everywhere, because the storage path always raised `NotImplementedError`. This is **verified per environment** before the contract step.
  - API responses keep their field names (`logo_url`, `avatar_url`), now filled with a short-lived signed URL generated on read, **after** the existing authorization.
  - The TTL is configurable. Its value is set in P4 against frontend caching (**PROVISIONAL**).
- **Inventory export:**
  - uploads to the tenant prefix and returns a signed URL;
  - a missing or failed storage path raises a typed, user-safe error and emits a metric;
  - the `/dev/exports/...` and empty-URL paths are removed (`export_service.py:167-178`, `inventory/dependencies.py:415`).
- **SVG:** removed from `_ALLOWED_MIME_TYPES` (`company_logo_service.py:34-35`). Magic-byte checks and the size limits stay as they are.
- **Readiness** includes a storage `HEAD` on a canary key when storage is enabled.

- Covers: FR-PRD-030, FR-PRD-030a, FR-PRD-031, FR-PRD-054, G-08.

### P-8 Transactional email

**Transport:**
- **E-SMTP:** SMTP over TLS through the standard library. No dependency, and works with every candidate provider.
- **E-API:** the provider's HTTP API through the existing `httpx`.

This is a P0 decision after the provider comparison. Either way the transport sits behind an `EmailSender` interface that replaces the stub in `auth/services/email_service.py`.

**Delivery:**
- Sending happens after the response, as a background task, so the anti-enumeration response timing does not change.
- Retries are bounded, with backoff. The attempt count is **PROVISIONAL**, fixed in P4.
- On final failure: a log entry **without the token**, plus a metric and an alert.
- Reset and verification tokens are already single-use and expiring, so the user can safely ask again.
- Durable outbox-based delivery is **deferred**. Its trigger is a measured failed-delivery rate above the threshold set in P6. The outbox relay is a stub today (`core/events/relay.py`, labelled honestly in `platform_admin/router.py:1545`).

**Configuration:**
- In staging and production, `EMAIL_ENABLED=true` without provider configuration fails startup (§9.4).
- Development keeps a non-sending mode that logs **no token above DEBUG**.
- SPF, DKIM and DMARC are verified for the sender domain before P9's smoke test.

- Covers: FR-PRD-032, G-09, the §17.3 email-down edge case.

### P-9 Frontend CSP and headers (P0-research spike)

- **Static headers** go in `next.config.ts` `headers()`: `frame-ancestors 'none'` (and X-Frame-Options), Referrer-Policy, X-Content-Type-Options, Permissions-Policy and HSTS.
- **CSP:**
  - scripts are allowed through a per-request **nonce**, set in the Next 16 request proxy and middleware layer — the exact file convention for 16.3.x is confirmed in the spike;
  - `style-src` covers what Recharts and Tailwind actually need, measured in the spike;
  - `connect-src` is limited to the API origin and the error-tracker ingest;
  - `img-src` is limited to `'self'`, `data:`, `blob:` and the storage signed-URL origin.
- **Rollout:**
  1. `Content-Security-Policy-Report-Only` in staging, with Playwright collecting violations;
  2. enforce once there are zero violations on the e2e routes.
- **Recorded residual risk:** CSP does not remove the risk of a refresh token in `localStorage` (ADR-0003, ADR-0007). The HttpOnly-cookie upgrade stays deferred (spec §21).

- Covers: SEC-04, SEC-05, G-10.

### P-10 Observability (smallest viable set)

| Area | Design |
|---|---|
| **Logs** | JSON to stdout, with a new `COMPANY_ID_CONTEXT` set where tenant context is resolved. The new `access_log` middleware writes one entry per request using the **route template**. The existing redaction (`test_sensitive_log.py`) is extended to access logs. Logs are shipped to a centralized sink with retention (§6.4). |
| **Errors** | One SDK hooked into the exception handlers. Its `before_send` scrubber removes headers, tokens, bodies and PII. |
| **Metrics** | Request rate, errors and latency per route group; pool saturation; scheduler outcomes; GL posting failures (a hook at the `PostingEngine` failure path); Epic 11 export count, duration and rejections; backup age (a push or heartbeat from the backup job). `/metrics` is **not public**: it is bound to the internal network or token-protected. |
| **Uptime** | An external probe of the frontend and of `/api/v1/health/ready`, plus heartbeat monitors for the backup and scheduler jobs. |
| **Alerts** | Spec §12.3. Thresholds stay **PROVISIONAL** until P11, and each alert links to a runbook. |

- Covers: FR-PRD-050…055, FR-PRD-062, NFR-PRD-06, G-11, G-12, G-21.

### P-11 CI/CD

**Required checks that always report:**
- **Defect found:** `backend.yml` and `frontend.yml` trigger only on `backend/**` and `frontend/**` changes. A required check from those workflows would therefore stay "expected" forever on a docs-only PR. For example, PR #10 ran only "Summary" and GitGuardian.
- **Fix:** the workflows always start. A path-detection job then decides whether to run the heavy steps or report success as "skipped (no relevant changes)". Alternatively, a single always-on `ci-gate` aggregator job is the only required check. The choice is made in P8.

**Required set:** the checks documented in `pr-checks.yml` plus GitGuardian, finalized in P8 (FR-PRD-040). It is applied to the ruleset through the API and read back. A failing PR is then shown to be refused (SC-08).

**Deploy pipeline** (`deploy.yml`):
1. Build once on a `main` merge or a tag.
2. Scan the images (SEC-31), with a waiver file that carries expiry dates.
3. Push to a registry by digest.
4. Run the `migrate` job on staging, then deploy to staging.
5. Run the smoke test.
6. Approval through a GitHub Environment reviewer (ADR-0009 single-maintainer mode).
7. Promote the **same digest** to production: take a pre-migration backup, run `migrate`, deploy, smoke.
8. Store the evidence artifact: SHA, digests, revisions before and after, smoke result, approver.

The frontend promotes the same Vercel build tied to the SHA, for example a prebuilt deployment promoted between environments. The exact mechanism is confirmed in P0.

**Other changes:**
- CI time (SHOULD, FR-PRD-043): shard the backend suite with a job matrix by test directory. No new dependency is needed.
- Remove the stale `002-auth-identity` trigger (FR-PRD-044).

- Covers: FR-PRD-003, FR-PRD-022, FR-PRD-040…044, CI-01…05, SEC-30…33, G-14.

### P-12 Backups, PITR, archive

| Layer | Purpose | Design |
|---|---|---|
| **L1 — Provider PITR** | RPO ≤ 1 h | Continuous WAL / PITR on the managed database. The provider must offer it (§6 criterion), and the drill proves it (SC-02). |
| **L2 — Independent logical backup** | Separate failure domain, provider loss | A daily encrypted `pg_dump` from a backup DB role to object storage in a **different account or provider**, kept 30 days. Encryption is client-side; the tool is chosen in P0 from what the base image already has, otherwise justified. |
| **L3 — Business-record archive** | 7-year retention (planning assumption) | A periodic, encrypted, immutable export of financial and audit tables (journal entries and lines, AR/AP, invoices, audit logs), with object-lock or WORM retention set to the confirmed period. Every access is audited. Restore-from-archive has its own drill. |

**Honest RPO statement:**
- RPO ≤ 1 h holds while L1 is available.
- If the provider itself is lost, RPO equals the L2 interval. With a daily dump that is up to 24 h.
- This becomes an **owner decision** in §9: accept it, or pay for a more frequent L2.

**Other rules:**
- A pre-migration backup or snapshot is taken before each production `migrate` (DB-03).
- The backup age is exported as a metric, with an alert (FR-PRD-026).
- Archive deletion never happens before the retention period ends. Interaction with Epic 3 company soft-delete is defined in runbook #8.

- Covers: FR-PRD-024, FR-PRD-024a, FR-PRD-025, FR-PRD-026, DB-03…05, NFR-PRD-02, NFR-PRD-05, G-13.

### P-13 Least-privilege database roles

| Role | Rights |
|---|---|
| `erp_migrator` | Owns the schema; DDL |
| `erp_app` | DML on application tables. No DDL. No `UPDATE`/`DELETE` on append-only audit tables, if the existing tests confirm the app never needs them; otherwise documented. |
| `erp_backup` | Read only, for dumps |
| `erp_readonly` | Diagnostics |

- Default privileges are granted by `erp_migrator`, so new tables inherit the right grants.
- The definitions live in `deploy/db/roles.sql`.
- `pg_trgm` creation may need provider-specific rights, which is a §6 criterion.

- Covers: NFR-PRD-04, DEP-02.

### P-14 Aligned timeouts

The rule is proxy timeout > app request budget > database `statement_timeout`.

- A default `statement_timeout` applies per connection, next to the existing `lock_timeout` hook (`core/database/engine.py:54-79`).
- Epic 11 export and report paths use a **documented, larger** `SET LOCAL statement_timeout` sized from the T214/T270 measurements at the caps (CSV 50,000 / XLSX 25,000; `modules/reports/constants.py:24-25`).
- All values stay **PROVISIONAL** until P11.

- Covers: FR-PRD-021, FR-PRD-061, G-15.

### P-15 Configuration guardrails

- `ENVIRONMENT` becomes a `Literal["development", "testing", "staging", "production"]`.
- A pure `guardrails.evaluate(settings)` function returns every violated §9.4 rule.
- In staging and production, startup exits non-zero and lists **all** violations, never partial ones.
- There is one unit test per rule (SC-04).
- `TrustedHostMiddleware` is added, driven by `ALLOWED_HOSTS`.
- CORS is limited to the explicit origins (SEC-02/03).
- The `.env.example` completeness test diffs `Settings.model_fields` against the documented keys.

- Covers: FR-PRD-001, FR-PRD-010, FR-PRD-012, SEC-02, SEC-03, G-06, G-07.

---

## 6. Provider and Component Comparison Framework (P0 deliverable — no purchases)

**Rule:** no provider is selected, priced or assumed in this plan. P0 produces a dated **decision record** per category, filled from vendor documentation and quotes **captured at decision time**, plus latency **measured** from Pakistani networks (at least two ISPs) to each candidate region. Candidate names below are a starting list for evaluation, not recommendations.

### 6.1 Criteria (scored per candidate)

| Criterion | What is recorded |
|---|---|
| Fit with the required capabilities | Category-specific, see below |
| Regional latency | Measured RTT p50/p95 from Pakistan to the candidate region, and from the VPS region to the database region (same region required) |
| Backup / PITR / restore | Mechanism, retention, restore-to-new-instance time (feeds RTO), point-in-time granularity (feeds RPO) |
| Security | TLS enforcement, private networking or IP allow-lists, encryption at rest, access audit, MFA on the console |
| Reliability | Published availability commitment, maintenance windows, incident history |
| Cost | Monthly estimate per environment (staging and production), from quotes; NFR-PRD-10 |
| Lock-in and exit | Standard protocol (PostgreSQL wire, S3 API, SMTP), data export path |
| Operational burden | Single-maintainer effort for patching, upgrades and monitoring |
| Payment and account practicality | Billing availability for a Pakistan-based owner (recorded fact, not assumed) |

### 6.2 Categories and candidate lists

| Category | Required capabilities (pass/fail) | Candidates to evaluate |
|---|---|---|
| Managed PostgreSQL | PostgreSQL 16; `pg_trgm`; PITR covering the RPO; TLS; private or allow-listed access; enough connections for FR-PRD-020; roles creatable | e.g. AWS RDS, DigitalOcean Managed PostgreSQL, Aiven, Neon, Supabase, Azure Database for PostgreSQL. **Not** Hetzner, which has no managed PostgreSQL; it is listed only as a VPS candidate. |
| VPS | Docker; region co-located with the database; snapshots; firewall | e.g. Hetzner, DigitalOcean, AWS Lightsail/EC2, Vultr, Linode |
| Object storage (×2: primary, plus a separate account or provider for L2/L3) | S3 API; private buckets; presigned URLs; SSE; object lock or immutability for L3 | e.g. AWS S3, Cloudflare R2, Backblaze B2, DigitalOcean Spaces, Wasabi |
| Transactional email | SMTP or HTTPS API; SPF, DKIM and DMARC; bounce handling; deliverability to common Pakistani mailbox providers (tested) | e.g. Amazon SES, Postmark, Resend, Brevo, Mailgun, SendGrid |
| DNS / TLS | DNSSEC optional; API for ACME DNS-01 if needed | the registrar's DNS, Cloudflare DNS |
| Error tracking | Self-host or SaaS; PII scrubbing; Python and JS SDKs | e.g. Sentry (SaaS or self-hosted), GlitchTip (Sentry-compatible) |
| Metrics and logs | Prometheus-compatible ingestion; log retention configurable to NFR-PRD-05 | e.g. Grafana Cloud, Better Stack, the provider's native monitoring |
| Uptime and heartbeats | External probes at 1-minute intervals; heartbeat (cron) monitors | e.g. UptimeRobot, Better Stack, Healthchecks.io |
| Frontend region (Vercel) | A function region near the API region | Recorded from Vercel's region list at decision time |

### 6.3 Component justifications (DEP-06, §44 #15)

| Component | Need | Smallest option | Status |
|---|---|---|---|
| Reverse proxy | TLS termination (DEP-02) | One proxy container on the VPS (P-6) | Required |
| Shared rate-limit store | SEC-20 | **R1, PostgreSQL** (no new service) | Required; Redis rejected unless P11 evidence |
| Error-tracking SDK | FR-PRD-052 | One SDK, scrubbed | Required (new dependency; justification recorded at the PR) |
| Metrics client | FR-PRD-053 | A Prometheus client, or the provider agent | Decided in P0 |
| Image scanner | SEC-31 | A CI-only action, no runtime footprint | Required |

### 6.4 Data residency

Whether any Pakistani rule restricts hosting tenant financial data outside Pakistan is **not assumed either way**. It is added to the professional-confirmation request alongside the 7-year retention (§9, item 3). This is not legal advice.

---

## 7. Data-Model Deltas (planned; no migration is created by this plan)

| Change | Purpose | Expand / contract | Rollback |
|---|---|---|---|
| `companies.logo_object_key` (nullable text) | P-7 | Expand: add the column; the code writes the key and reads key-or-null. Contract (a later release): stop reading `logo_url` from the database once it is verified NULL in every environment. | Downgrade drops the column (no data loss while NULL) |
| `users.avatar_object_key` (and the previous-key column used for retention) | P-7 | Same pattern | Same |
| `auth_rate_limit_buckets` (`key`, `window_start`, `count`; primary key `(key, window_start)`; old windows pruned by the scheduler) | P-5 R1 | Additive table | Downgrade drops the table |
| `accounting_recurring_instances.status` gains `PENDING`, if the status is constrained | P-3 claim-first | Additive enum or check value | Downgrade only if no `PENDING` rows remain (runbook) |
| *None* for SEC-24 | M1 uses the existing `sessions.is_revoked` (indexed `ix_sessions_is_revoked`) | — | — |

**Rules:**
- Revision numbers are assigned at implementation, after `078`.
- Every change includes a downgrade (Constitution §18) and is covered by the real-PostgreSQL round-trip test (FR-PRD-022).

---

## 8. Interface and Contract Deltas

| Surface | Change | Compatibility |
|---|---|---|
| `GET /api/v1/health/ready` | Adds checks: schema revision and storage (if enabled). The body is extended additively. | Existing fields kept; 503 semantics unchanged |
| Company logo and user avatar responses | Same field names. The value becomes a short-lived signed URL. | Clients must not cache URLs beyond the TTL. The frontend is checked in P4. |
| Inventory export response (`download_url`) | Always a valid signed URL, or a typed error; never empty or fake | A bug fix to an evidenced gap (spec §1.2 permits it) |
| Logo upload | `image/svg+xml` → 415/422 with the existing error envelope | An intentional security restriction (FR-PRD-030a) |
| Auth endpoints | No path or schema change. Revoked-session tokens → 401 (already the documented behaviour for invalid tokens). Rate-limit 429 responses unchanged. | Compatible |
| `/metrics` | New; **internal only**, never routed publicly | Not part of the public API |
| Epic 11 (`/api/v1/reports/**`, dashboard, Customer 360, saved views, exports) | **No change.** Metrics hooks only. | Byte-compatible (FR-PRD-060), proven by the existing Epic 11 contract tests passing unchanged |
| Response header | `X-Request-ID` already exists (S-03), documented for incident tracing | Unchanged |

---

## 9. External Decisions and Owner Inputs

| # | Input | Needed by | Blocks |
|---|---|---|---|
| 1 | Provider and region per category (§6), plus monthly cost acceptance | End of P0, before P9 | P9 staging provisioning |
| 2 | Sender domain, and DNS access for SPF, DKIM and DMARC | P4 staging verification | Email smoke (P9) |
| 3 | Professional confirmation of business-record retention (7-year assumption), plus any data-residency rule | Before P13 | Final gate; L3 retention value |
| 4 | D-10 workload: tenants, users per company, concurrent users, invoices per month, exports per day, growth horizon | Before P11 final thresholds; must be recorded before P13 | Capacity sign-off |
| 5 | Accept or modify the L2 provider-loss RPO (P-12, daily → up to 24 h in that scenario) | End of P0 | Backup design; **P13** |
| 6 | Accept the availability arithmetic: 99.5% of a 30-day month allows **3.6 h** of unplanned downtime. One full-recovery incident at the 4 h RTO exceeds that month's budget. Options: accept as an objective (not an SLA); invest in faster recovery (a warm standby VPS image); or lower the objective. | End of P0 | NFR-PRD-01 wording in the readiness report |
| 7 | Planned-maintenance window and notice period | Before P13 | NFR-PRD-01 exclusions |
| 8 | Release Approver identity (expected: the owner, under ADR-0009) | P8 | Production approval gate |

---

## 10. Phases

Every phase lists its goal, the requirements it covers, the areas it changes, its dependencies, the evidence it needs, its rollback and risks, and its exit gate.

**Dependency overview** (no cycles):

```text
P0 Decisions/Research ─────────────────────────────┐
P1 Config guardrails ──┬─► P2 Runtime roles ───────┤
                       ├─► P3 Auth/session/ratelimit┤
                       ├─► P4 Storage & email ──────┤
                       └─► P6 Observability ◄─ P2 ──┤
P0 ─► P5 Frontend CSP ──────────────────────────────┤
P3,P4 ─► P7 PostgreSQL isolation suite ─────────────┤
P1..P7 ─► P8 CI/CD + branch protection* ────────────┤
P0,P2,P6,P8 ─► P9 Staging provisioning + first staging deploy
P9 ─► P10 Backup/restore/archive drills
P9,P6,P2 ─► P11 Performance baseline (final thresholds need D-10)
P9,P10,P11 ─► P12 Runbooks + rehearsals
ALL + owner inputs ─► P13 Production + readiness gate
```

\* The FR-PRD-040 required-check fix and ruleset change carry no code risk. They **may start immediately** after P0, in parallel with P1.

### P0 — Decisions, research spikes and baselines (documents only)

- **Goal:** close every **P0-research** item and produce the provider decision records, without buying anything.
- **Covers:** DEP-01 (topology already decided; providers now), DEP-06, NFR-PRD-09, NFR-PRD-10, D-01/D-04/D-05 open inputs, §9 items 1, 5 and 6.
- **Deliverables:**
  - `docs/operations/decisions/` records for each category in §6;
  - CSP spike notes (P-9): the Next 16 proxy file convention, nonce propagation, the Recharts style needs;
  - R1 limiter design confirmation (P-5);
  - an email transport choice (P-8);
  - the frontend promotion mechanism (P-11);
  - the backup encryption tool (P-12);
  - a SEC-24 latency **pre-baseline** measured locally.
- **ADR suggestions:** for any decision that passes the three-part test (§12).
- **Exit gate:** decision records exist and every §9 input is either received or explicitly scheduled. **No code changes in P0.**

### P1 — Configuration foundation and guardrails

- **Goal:** unsafe production configuration cannot start.
- **Covers:** FR-PRD-001, FR-PRD-010, FR-PRD-011, FR-PRD-012, SEC-02, SEC-03, SEC-21 (values recorded), the full §9.4 list, G-06, G-07, FR-PRD-014 (SHOULD: remove `backend/uv.lock` or document why it stays; CI and Docker use Poetry).
- **Changes:**
  - `core/config/settings.py`; new `core/config/guardrails.py`;
  - `main.py` (startup validation, `TrustedHostMiddleware`);
  - `.env.example` (repository root; the only copy);
  - email, storage, observability and `ALLOWED_HOSTS` keys (values from P0).
- **Tests:**
  - `tests/unit/core/test_guardrails.py`: one test per §9.4 rule, plus an "all violations reported" test;
  - an `.env.example` completeness test;
  - a trusted-host rejection test;
  - existing `tests/unit/core/test_settings.py` still green.
- **Rollback / risk:** pure configuration logic, and `development`/`testing` behaviour is unchanged. The risk is an over-strict rule blocking staging, mitigated by the actionable error messages.
- **Exit gate:**
  - SC-04: 100% of §9.4 rules have a passing test;
  - acceptance scenario 4 passes;
  - the full suite stays green.

### P2 — Runtime role separation, safe migrations, exactly-once scheduler, Docker hardening

- **Goal:** migrations run once; there is one scheduler; no duplicate GL postings; the production container shape is safe.
- **Covers:** FR-PRD-004, FR-PRD-005, FR-PRD-006, FR-PRD-022 (CI part), FR-PRD-023 (policy plus the PR checklist item), DB-01, DB-02, DB-07 (documented in P12), DEP-03, G-03, G-04, G-16, SC-06, acceptance scenarios 1–3.
- **Changes:**
  - `main.py` lifespan: no `run_migrations()` or `start_scheduler()` outside development;
  - `core/migrations.py`: expected-head check and the `SCHEMA_REVISION_ALLOW` override (P-2);
  - new `core/scheduler/runner.py`: advisory-lock leadership;
  - `modules/accounting/services/scheduler.py`;
  - `recurring_journal_service.py`, `posting_engine.py` (additive caller-owned-transaction mode; default unchanged) and `repositories/recurring.py` (P-3);
  - `api/v1/router.py` readiness;
  - `backend/Dockerfile`: per-role commands, healthcheck, proxy-header flags (P-5);
  - new `deploy/compose.production.yml`: pinned digests, no bind mounts, no `--reload`, no published database or storage-admin ports, resource limits, restart policies, read-only root filesystem where feasible, and a `migrate` one-shot profile.
- **Tests (real PostgreSQL** via `pg_test_db`, new `tests/integration/postgres/`):
  - 3 scheduler processes → exactly one execution per due template, and one GL entry each;
  - fault injection between the post and the commit → no journal without an instance, and no duplicate on re-run;
  - kill the leader mid-run → the standby takes over with no duplicates;
  - an app started one revision behind → readiness 503, with both revisions logged;
  - the override allows exactly the named revision, and only when it equals the actual DB revision;
  - an **invalid** override value (empty, malformed, wildcard or pattern) → rejected; readiness stays failed, with an error logged;
  - a **mismatched** override value (well-formed but not the actual DB revision) → rejected; readiness stays failed, with an error logged;
  - a DB revision **behind** the expected code head → readiness fails, with or without an override;
  - while the override is active, every readiness evaluation logs the expected revision, the actual database revision, the override value and the release SHA;
  - the migrate job run twice concurrently → the second is a no-op or fails safely; the schema is correct;
  - the existing accounting and recurring test suites unchanged and green;
  - the other two jobs re-run → idempotent.
- **Rollback / risk:**
  - The `PostingEngine` change is additive, but accounting integrity is the highest-risk area here. Every existing posting test must stay green, and no default behaviour changes.
  - Dev compose keeps auto-migration.
- **Exit gate:** SC-06 shown on PostgreSQL in CI, and acceptance scenarios 1–3 pass.

### P3 — Authentication, session and abuse hardening (ADR-0007 conditions)

- **Goal:** revoked sessions stop working immediately; rate limits are shared and proxy-aware; a tenant token can never carry platform authority.
- **Covers:** SEC-24, SEC-20, SEC-26, SEC-21, SEC-25 (conditions), G-23, G-05, G-25.
- **Changes:**
  - `core/auth/dependencies.py` (M1, P-4);
  - `modules/auth/repositories/session_repository.py`;
  - `modules/auth/router.py` and `modules/companies/router.py` (limiter storage, P-5);
  - new `core/ratelimit/` and a migration (§7);
  - `Dockerfile` / uvicorn proxy-header flags;
  - `modules/companies/dependencies.py:150` and `accounting/services/permission_check.py:48`: remove the tenant-path `super_admin` bypass, and the unused `require_role`, if confirmed unused.
- **Tests** (real PostgreSQL, ≥2 OS processes):
  - for **each** trigger (logout, reset, change, deactivate, suspend, lock, archive): revoke in process A, then the token is rejected in process B;
  - database unavailable → fail closed;
  - p50/p95 latency before and after, recorded;
  - login limit enforced across 2 processes (acceptance scenario 10);
  - a spoofed `X-Forwarded-For` from an untrusted source is ignored;
  - a tenant token carrying a `roles` claim gets no bypass;
  - the platform-admin path is unchanged (existing `tests/security/modules/platform_admin/*`);
  - the existing auth suites (77 unit, 56 integration, 31 security) stay green.
- **Rollback / risk:** M1 changes the hot path, so latency is measured. If a regression exceeds the provisional tolerance, M2 is evaluated. Proxy trust that is set too broadly would allow IP spoofing; the test covers that.
- **Exit gate:**
  - every trigger is proven across processes;
  - the fail-closed test passes;
  - the latency delta is recorded;
  - SEC-20 and SEC-26 tests pass.
  - If any condition **cannot** be met safely, stop and present the evidence to the owner under ADR-0007 (no authentication migration without approval).

### P4 — Private storage and transactional email

- **Goal:** uploads and exports work privately per tenant; reset and verification emails are really delivered; no silent or fake success.
- **Covers:** FR-PRD-030, FR-PRD-030a, FR-PRD-031, FR-PRD-032, FR-PRD-062 (no export contents or tokens in logs), G-08, G-09.
- **Changes:**
  - `core/storage/s3_client.py` and a new `factory.py`;
  - `companies/dependencies.py:111/264`, `users_roles/dependencies.py:61/291`, `inventory/dependencies.py:415`;
  - `company_logo_service.py` (SVG removal);
  - `profile_service.py`;
  - `inventory/services/export_service.py`;
  - the models listed in §7, plus migrations;
  - `auth/services/email_service.py` and its wiring in `auth_service.py:77`;
  - settings.
- **Tests:**
  - **Storage integration** runs against a MinIO service container in CI (the same S3 API; no new Python dependency): objects are private, the presigned URL expires, keys carry the tenant prefix, and **cross-tenant key access is denied**, both through the API and through a guessed key;
  - SVG is rejected;
  - a storage outage → a typed error and a metric, never an empty or fake URL;
  - email: a transport double in unit tests; background send with bounded retry; the provider-down path logs no token (extends `test_sensitive_log.py`); startup fails when enabled without a provider (P1 rule);
  - the frontend renders signed logo and avatar URLs (Jest or Playwright).
- **Rollback / risk:** the key columns are additive. Until the contract step, the old URL path stays readable. Provider credentials stay in the secret store only.
- **Exit gate:** all of the above pass. Real-provider delivery and SPF/DKIM/DMARC are verified in **P9** staging.

### P5 — Frontend security headers and CSP

- **Goal:** the ADR-0003 compensating control exists, and its residual risk is recorded.
- **Covers:** SEC-04, SEC-05, G-10.
- **Changes:** `frontend/next.config.ts`; the Next 16 request-proxy file (from the P0 spike); `src/app/layout.tsx` (nonce); new `frontend/e2e/security-headers.spec.ts`.
- **Tests:**
  - header assertions in Jest or Playwright;
  - Playwright runs the existing e2e routes (`reports-smoke`, `t219`–`t221`, installments) in **Report-Only** mode and collects violations, then repeats in enforce mode with 0 violations;
  - a check that no `'unsafe-inline'` appears in `script-src`.
- **Rollback / risk:** a CSP that is too strict breaks pages, which is why the Report-Only stage comes first. The CSP is a single configuration revert away.
- **Exit gate:** headers are present on every route, there are 0 violations in enforce mode across the e2e suite, and the residual risk is restated in the readiness report.

### P6 — Observability

- **Goal:** incidents are detected and traceable end to end, without leaking secrets or PII.
- **Covers:** FR-PRD-050…055, FR-PRD-027 (SHOULD), FR-PRD-062, NFR-PRD-06, G-11, G-12, G-21.
- **Changes:**
  - `core/logging/setup.py` (`COMPANY_ID_CONTEXT`);
  - the place where tenant context resolves (users_roles / companies dependencies);
  - new `core/middleware/access_log.py` and `core/observability/*`;
  - `main.py` (error-tracker initialization, `/metrics` exposure restricted);
  - the scheduler runner (outcome metrics and heartbeat);
  - `posting_engine.py` (failure counter only);
  - the Epic 11 export path (count, duration, rejection counters; no contract change).
- **Tests:**
  - every access-log field is present, the route template is used, and no body or token appears;
  - `company_id` is present when a tenant is resolved;
  - the error capture is scrubbed;
  - readiness semantics, including schema and storage;
  - the metrics registry exposes the required series;
  - Epic 11 contract tests are unchanged.
- **Rollback / risk:** the risks are log volume and cost, handled by sampling at the sink if needed, and a PII leak, which the tests guard.
- **Exit gate:** acceptance scenario 11 is shown locally, and all tests pass. The induced-failure alerting (SC-07) is proven in P12.

### P7 — PostgreSQL tenant-isolation, RBAC and IDOR suite

- **Goal:** no cross-tenant access, proven on real PostgreSQL.
- **Covers:** SEC-10, FR-PRD-063, D-12, SC-03, acceptance scenario 5. SEC-11 (over HTTP against staging) is executed in P9.
- **Changes:** new `tests/security/postgres/`, with a conftest that reuses `pg_test_db` and `alembic_upgrade`. It is parametrized over the endpoint families and scenarios below, reusing the existing SQLite-scenario builders where possible.

  Endpoint families:
  - CRUD by ID, list, search and filters;
  - reports, exports and Customer 360;
  - saved views;
  - audit logs;
  - storage objects;
  - platform-admin and support-access boundaries.

  Scenarios:
  - two tenants;
  - a user with no membership;
  - a member without the permission;
  - a company context for a company without membership;
  - tenant-ID manipulation in path, query and body.
- **CI:** a dedicated required job, so the suite cannot be silently skipped.
- **Rollback / risk:** tests only. **Any demonstrated leak is a production blocker**: it is fixed in the owning module with a regression test before P13. RLS (SEC-12) is reconsidered only if the risk assessment shows a clear need.
- **Exit gate:** 0 leaks and 0 tenant-ID enumeration; the job is green and required.

### P8 — CI/CD pipeline and enforced branch protection

- **Goal:** failing code cannot merge, and only scanned, immutable artifacts deploy.
- **Covers:** FR-PRD-003, FR-PRD-022, FR-PRD-040, FR-PRD-041, FR-PRD-042, FR-PRD-043 (SHOULD), FR-PRD-044 (SHOULD), CI-01…05, SEC-30, SEC-31, SEC-32, SEC-33, G-14.
- **Changes:**
  - `.github/workflows/backend.yml`, `frontend.yml` and `pr-checks.yml` (always-reporting gates, P-11);
  - new `deploy.yml` and `security-rescan.yml`;
  - the image-scan step;
  - registry publish by digest;
  - a migration check from the **previous production revision** (FR-PRD-022);
  - a forward-deploy guard for **staging and production**:
    - it fails the deploy when `SCHEMA_REVISION_ALLOW` is present in the target environment;
    - a post-deploy check confirms the override is absent and that readiness passes on an exact revision match;
    - the result, including the logged expected and actual revisions, is recorded in the release evidence artifact (P-2 rule 4);
  - a waiver file with expiry dates;
  - the ruleset updated through the API, with the configuration documented in `docs/operations/branch-protection.md`.
- **Tests and evidence:**
  - a ruleset readback;
  - a deliberately failing PR whose merge is refused (SC-08, acceptance scenario 6);
  - **override forward-deploy guard test:** with `SCHEMA_REVISION_ALLOW` set in the target environment, a forward deploy is blocked before `migrate` and rollout;
  - **post-deploy removal test:** after a forward deploy, the check fails if the override is present, and passes only when it is absent and the expected/actual revision check succeeds;
  - both results are recorded in the release evidence artifact;
  - the deploy workflow dry-run up to staging once P9 exists.
- **Rollback / risk:** an always-pending required check would block every merge, so the docs-only PR case is tested first. A bypass is never used for failing checks (ADR-0009).
- **Exit gate:** SC-08 is proven and the pipeline is defined. Its first real staging run happens in P9.

### P9 — Staging provisioning and first staging deployment

- **Goal:** a staging environment that mirrors production, deployed only through the pipeline.
- **Covers:** FR-PRD-002, FR-PRD-004, FR-PRD-020, FR-PRD-021, DEP-02, DEP-03, DEP-04, DEP-05 (SHOULD), NFR-PRD-03, NFR-PRD-04, SEC-01, SEC-11, FR-PRD-064 (SHOULD), SC-01 (staging), SC-09 (staging), §43 DoD.
- **Changes:** `deploy/` (proxy configuration, `db/roles.sql`, provisioning scripts); `docs/operations/environments.md` (environment matrix: hosts, roles, secrets locations, pool budget arithmetic); Vercel staging project configuration; GitHub Environments and secrets.
- **Evidence:**
  - TLS, HSTS and redirect checks, plus a certificate-expiry monitor;
  - the database is not publicly reachable (an external connection attempt fails);
  - DB roles verified: the app role cannot run DDL;
  - the pool budget is recorded, with the formula "pool × processes × replicas < limit" (FR-PRD-020) and **PROVISIONAL** values;
  - the smoke test (spec §16.3) runs automatically on the synthetic smoke tenant;
  - real email delivered, with SPF, DKIM and DMARC passing;
  - the SEC-11 RBAC sample over HTTP;
  - the deploy evidence artifact.
- **Rollback / risk:** staging holds no production data (FR-PRD-002). Credentials are separate from production.
- **Exit gate:** SC-01 and SC-09 pass in staging, and SEC-11 passes.

### P10 — Backup, restore and archive drills

- **Goal:** recovery is proven, not assumed.
- **Covers:** FR-PRD-024, FR-PRD-024a, FR-PRD-025, FR-PRD-026, DB-03, DB-04, DB-05, NFR-PRD-02, NFR-PRD-05, SC-02, acceptance scenario 7, the §17.3 "unrestorable backup" edge case.
- **Changes:** `deploy/backup/` (L2 dump, L3 archive, a verify script that checks per-tenant row counts, the trial balance and audit continuity), heartbeat and alerts, and runbooks #3 and #4.
- **Drills (staging, with production-like synthetic data):**
  1. **PITR** to a timestamp → measure the achieved RPO and the total RTO (provisioning, restore, verify, cut-over).
  2. **L2 restore** into an isolated database.
  3. **L3 archive** restore and verification.
  4. A **corrupted or missing backup** is detected by the verifier and alerting.
- **Rollback / risk:** drill targets are isolated and destroyed after use (FR-PRD-064).
- **Exit gate:** the measured RPO and RTO are recorded against the proposed targets.
  - If they are **not met**, stop and report to the owner, with the options from §9 items 5 and 6. Targets are never silently relaxed.

### P11 — Performance baseline and capacity

- **Goal:** measured thresholds instead of guessed ones.
- **Covers:** PERF-01…04, NFR-PRD-07, FR-PRD-021, FR-PRD-061, SC-10, acceptance scenario 12; the SEC-24 latency (P-4).
- **Method** (spec §14 PERF-03):
  - a synthetic data generator on staging;
  - runs at 1×, 2× and 5× of the **owner-supplied** D-10 workload. Until it arrives, a workload **labelled "ASSUMED — provisional"** is used and is never presented as the owner's figures;
  - flows: login and refresh, invoice create and issue, GL posting, AR aging, dashboard, a paginated Epic 11 report, and a 50,000-row CSV and a 25,000-row XLSX export. Exports reuse the T214/T270 harnesses (`tests/performance/accounting/*`, the Epic 11 harnesses);
  - recorded per step: p50/p95/p99, error rate, database CPU and connections, pool saturation, memory per process, and the time to the timeout ceiling.
- **Outputs:**
  - provisional thresholds: latency targets, alerts, pool budget, export timeouts;
  - the capacity statement (PERF-04), naming the first resource to saturate;
  - a regression baseline file.
- **Exit gate:**
  - the exports at the caps finish within the aligned timeouts and the audit row is written first (FR-PRD-061, acceptance scenario 12);
  - a breach blocks the gate;
  - the thresholds are **finalized** only after the D-10 figures are recorded.

### P12 — Runbooks and rehearsals

- **Goal:** one operator can run every procedure (NFR-PRD-08).
- **Covers:** spec §12.4 runbooks 1–9, SC-05, SC-07, SC-11, FR-PRD-013, SEC-22, DB-07, RB-01, RB-02, the §17.3 edge cases (failed certificate renewal, storage or email outage, rotation during active sessions).
- **Changes:** `docs/operations/runbooks/`, one file per runbook, plus an execution log.

| Runbook | Covers |
|---|---|
| Deploy | — |
| Code rollback | P-2 rules 1–5, step by step:<br>• `SCHEMA_REVISION_ALLOW` is set only through this runbook, under explicit Release Approver authorization recorded in the execution log (who, when, why, exact database revision);<br>• the value must exactly match the database's actual revision; invalid or mismatched values are rejected;<br>• it is used only for a release confirmed backward-compatible (FR-PRD-023). Otherwise, a forward fix or the approved PITR / database recovery procedure (runbook #3) — the override is not a compatibility proof;<br>• every readiness check while it is active logs the expected revision, the actual database revision, the override value and the release SHA;<br>• forward deployment is blocked while it is set, and its removal plus a successful expected/actual revision check are verified after the next forward deploy (P8 guard). |
| DB rollback / PITR | — |
| Backup verification | — |
| Incident response | `request_id` tracing |
| Secret rotation | JWT (active sessions are invalidated and users re-login), DB, storage, email |
| Migration failure recovery | Includes the non-transactional `CONCURRENTLY` index in `migrations/versions/007_inventory_products.py` |
| Tenant data request / deletion | Respects the D-03 split |
| Platform-owner bootstrap and access recovery | No default credentials; audit entry; bootstrap variables removed from runtime |
| Scheduler recovery | — |
| Storage outage | — |
| Email outage | — |

- **Rehearsals in staging:**
  - a deliberately broken release is rolled back within the rollback target (SC-05, acceptance scenario 8). The rehearsal exercises the full override procedure:
    1. explicit Release Approver authorization recorded (who, when, why, exact database revision);
    2. an invalid and a mismatched value are each shown to be rejected; then the exact-match value is set;
    3. every readiness check logs the expected revision, the actual database revision, the override value and the release SHA;
    4. N-1 code is verified working against schema N **for the rehearsed release only**. This does not prove compatibility for any other migration, which still relies on FR-PRD-023;
    5. the next forward deploy is blocked while the override is present, then accepted after its removal, with absence and a successful expected/actual revision check verified;
  - induced failures — API stopped, database unreachable, 5xx spike, backup job failed — alert within the detection window and link to the runbook (SC-07, acceptance scenario 9);
  - each runbook is executed once, live or as a tabletop, and logged (SC-11).
- **Exit gate:** the execution log covers every runbook, and SC-05 and SC-07 pass.

### P13 — Production provisioning, first deploy, readiness gate

- **Goal:** go-live only on evidence.
- **Preconditions:**
  - P0–P12 exit gates passed;
  - **every §9 input (#1–#8) is resolved**, or is covered by a **documented, owner-approved exception** recorded in the readiness report with five explicit fields: **scope, reason, approver (the owner, by name), approval date, and expiry date or review date**. An exception missing any field is invalid. No exception is assumed, implied or silently accepted. This explicitly includes:
    - #1 providers and regions, with monthly cost accepted;
    - #2 sender domain, with SPF, DKIM and DMARC verified;
    - #3 professional retention and data-residency confirmation;
    - #4 the D-10 workload recorded, and the PROVISIONAL thresholds finalized from it;
    - **#5 the provider-loss backup/RPO decision**;
    - #6 the availability decision;
    - #7 the maintenance window and notice period;
    - #8 the Release Approver;
  - **every §17 open input is resolved**, or is covered by an explicit, documented, owner-approved exception with the same five fields (scope, reason, approver, approval date, expiry date or review date); an exception missing any field is invalid. The §17 inputs are: providers, sender domain, legal retention and data residency, D-10 figures, and the RPO and availability decisions;
  - **`SCHEMA_REVISION_ALLOW` is absent in both staging and production before go-live**, verified by the P8 post-deploy check and recorded in the release evidence (P-2 rule 4);
  - no open P7 leak;
  - no unwaived Critical or High vulnerability.
- **Steps:**
  1. Provision production per the P0 decisions, mirroring staging.
  2. Promote the **same artifacts** through the pipeline (pre-migration backup, `migrate`, deploy).
  3. Run the production smoke test.
  4. Turn on monitoring and alerts.
  5. Write the readiness report (`docs/operations/readiness-report.md`) linking evidence for every MUST in §15.
  6. The Release Approver signs it.
- **Covers:** SC-01, SC-08 and SC-09 in production; the spec §17.1 gate; NFR-PRD-01 (measurement starts); NFR-PRD-10 (cost recorded).
- **Rollback:** runbook #2 or #3. There are no real tenants until the signed report exists.
- **Exit gate:** spec §17.1 fully checked, with evidence links.

---

## 11. Verification Strategy (quickstart for evidence)

| Layer | What runs | Where | Blocks |
|---|---|---|---|
| Unit | Guardrails, `.env.example` completeness, scrubbers, limiter logic | CI (every PR) | Merge |
| Real PostgreSQL integration | Scheduler multi-process, crash window, migration single-run, schema readiness, SEC-24 per trigger, SEC-20 multi-process, the P7 isolation suite, migration round-trip from the previous production revision | CI (`pg_test_db` fixtures, PostgreSQL 16 service) | Merge |
| Storage | MinIO container: privacy, expiry, prefix, cross-tenant denial | CI | Merge |
| Frontend | Jest headers; Playwright CSP Report-Only, then enforce; e2e suite | CI (+ staging) | Merge / deploy |
| Contract regression | The existing Epic 11 and all-module suites unchanged | CI | Merge |
| Pipeline | Image scan, migration check, staging smoke | `deploy.yml` | Production promotion |
| Staging drills | SC-01/02/05/07/09/10/11, SEC-11, FR-PRD-013, FR-PRD-061 | Staging | Readiness gate |
| Production | Smoke, monitoring live, readiness report | Production | Go-live |

**Evidence artifacts** go under `docs/operations/evidence/<date>-<item>.md`, each holding the command or output, the SHA and the timestamp. They are linked from the readiness report.

The full backend regression runs in CI on every PR (existing practice). Locally, phases run targeted suites, following the Epic 11 convention.

---

## 12. ADR Suggestions (not created — owner consent required)

These pass the three-part test (impact, alternatives, cross-cutting):

- 📋 Architectural decision detected: **runtime role separation and the schema-revision rollback override (P-1, P-2)** — Document reasoning and trade-offs? Run `/sp.adr runtime-roles-and-schema-revision-policy`
- 📋 Architectural decision detected: **an exactly-once scheduler through a PostgreSQL advisory lock, with claim-first atomic recurring posting (P-3)** — Document? Run `/sp.adr exactly-once-scheduler-and-atomic-recurring-posting`
- 📋 Architectural decision detected: **private object storage with keys and short-lived signed URLs (P-7)** — Document? Run `/sp.adr private-tenant-object-storage`
- 📋 Architectural decision detected: **a PostgreSQL-backed shared rate limiter with trusted proxy headers (P-5)** — Document? Run `/sp.adr shared-rate-limiting-without-redis`
- 📋 Architectural decision detected: **a three-layer backup design: PITR, an independent dump, and an immutable archive (P-12)** — Document? Run `/sp.adr backup-and-archive-layers`
- Provider choices from P0 are grouped into one ADR, per CLAUDE.md guidance: `/sp.adr production-provider-selection`.

---

## 13. Risk Register

| # | Risk | Likelihood / impact | Mitigation | Kill switch / guardrail |
|---|---|---|---|---|
| R1 | The `PostingEngine` transaction change regresses accounting | Medium / High | Additive mode, default unchanged; full accounting suites plus the new PostgreSQL crash-window test | The scheduler can be stopped (the single process); manual posting still works |
| R2 | SEC-24 adds hot-path latency | Low / Medium | One joined primary-key query; measured in P3 and P11 | M2 epoch fallback; never fail open |
| R3 | Proxy misconfiguration: shared IP lockout, or a spoofable `X-Forwarded-For` | Medium / High | Strict `--forwarded-allow-ips`; spoofing test | The rate-limit key is logged; the limiter can be disabled per route by configuration only in an incident (runbook) |
| R4 | The CSP breaks pages | Medium / Medium | Report-Only first; Playwright violation gate | A one-line configuration revert |
| R5 | Required checks stay pending on docs-only PRs | High (evidenced) / Medium | Always-report gate (P-11), tested first | Ruleset change is reversible |
| R6 | RPO or RTO not achievable on the chosen provider | Medium / High | Provider criteria; drills before launch | Stop at P10; owner decides (§9 items 5–6) |
| R7 | 99.5% conflicts with the single VPS and a 4 h RTO | High / Medium | Stated arithmetic; owner decision | Not an SLA |
| R8 | A cross-tenant leak is found | Low / Critical | P7 suite | **Production blocker** |
| R9 | Single maintainer (bus factor) | High / High | Runbooks for one operator; credential-recovery runbook | Readiness report lists access recovery |
| R10 | Over-engineering or cost creep | Medium / Medium | §6.3 justifications; no Redis, queue or Kubernetes without evidence | NFR-PRD-09 review at each PR |
| R11 | Email deliverability to local mailbox providers | Medium / Medium | Deliverability test in P0 and P9; SPF, DKIM and DMARC | Alert on delivery failures; user can re-request |
| R12 | Signed-URL TTL against browser caching causes broken images | Medium / Low | TTL tuned in P4; frontend refetch on 403 | Configuration value |
| R13 | Provider billing is impractical from Pakistan | Medium / Medium | §6.1 criterion | Alternative candidates |

---

## 14. Complexity Tracking

No Constitution violations. The three justified additions — a reverse proxy, two observability SDKs and one small rate-limit table — are recorded in §3.2 and §6.3, and the Constitution already permits each of them. This table is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| — | — | — |

---

## 15. Traceability Matrix (every MUST → phase → evidence)

### 15.1 Functional requirements

| Requirement | Phase | Evidence |
|---|---|---|
| FR-PRD-001 | P1 | Guardrail test: unknown `ENVIRONMENT` |
| FR-PRD-002 | P9 | Environment matrix; separate credentials |
| FR-PRD-003 | P8, P13 | Deploy evidence: same digest in staging and production |
| FR-PRD-004 | P2, P9 | `deploy/compose.production.yml` review checklist |
| FR-PRD-005 | P2 | PostgreSQL migrate single-run and schema-readiness tests |
| FR-PRD-006 | P2 | Multi-process scheduler and crash-window tests; staging drill (P12) |
| FR-PRD-010 | P1 | Guardrail tests |
| FR-PRD-011 | P1, P9 | Secret-store configuration; GitGuardian; no secrets in images (scan) |
| FR-PRD-012 | P1 | Completeness test |
| FR-PRD-013 | P12 | Rotation rehearsal log |
| FR-PRD-020 | P9, P11 | Pool budget record |
| FR-PRD-021 | P2, P11 | Timeout configuration plus measurements |
| FR-PRD-022 | P8 | CI migration check from the previous production revision |
| FR-PRD-023 | P2, P8 | PR checklist item; rollback rehearsal (P12) |
| FR-PRD-024 | P10 | PITR configuration plus drill |
| FR-PRD-024a | P10 | Archive design plus restore-from-archive drill |
| FR-PRD-025 | P10 | Drill report (RTO, RPO, integrity) |
| FR-PRD-026 | P6, P10 | Backup-age alert induced |
| FR-PRD-030 | P4 | Storage integration tests; no `NotImplementedError` or fake URL |
| FR-PRD-030a | P4 | SVG rejection test |
| FR-PRD-031 | P4, P7 | Privacy, expiry, prefix and cross-tenant tests |
| FR-PRD-032 | P1, P4, P9 | Transport tests; no-token log test; staging delivery; SPF, DKIM and DMARC |
| FR-PRD-040 | P8 | Ruleset readback; refused merge |
| FR-PRD-041 | P8, P9, P13 | `deploy.yml` run evidence |
| FR-PRD-042 | P8 | Blocking conditions tested (red CI, migration check, scan, smoke) |
| FR-PRD-050 | P6 | Access-log field test |
| FR-PRD-051 | P6 | `company_id` log test |
| FR-PRD-052 | P6 | Error-capture scrub test; staging capture |
| FR-PRD-053 | P6 | Metrics series test; dashboards |
| FR-PRD-054 | P2, P4, P6 | Readiness semantics tests |
| FR-PRD-055 | P6, P9 | External probe configured; induced outage (P12) |
| FR-PRD-060 | P4, P6, P11 | Epic 11 contract suites unchanged and green |
| FR-PRD-061 | P11 | Export-at-cap timing report |
| FR-PRD-062 | P4, P6 | Log PII tests |
| FR-PRD-063 | P7 | Isolation suite covers the Epic 11 families |

### 15.2 Non-functional, security, deployment and database requirements

| Requirement | Phase | Evidence |
|---|---|---|
| NFR-PRD-01 | P0, P13 | Feasibility arithmetic and owner decision; probe measurement starts |
| NFR-PRD-02 | P10, P12 | Drill timings |
| NFR-PRD-03 | P9 | TLS checks |
| NFR-PRD-04 | P9 | Role verification |
| NFR-PRD-05 | P6, P10 | Retention configuration; access audit |
| NFR-PRD-06 | P6, P12 | Scenario 11 trace |
| NFR-PRD-07 | P11 | Baseline file |
| NFR-PRD-08 | P12 | Execution log |
| NFR-PRD-09 | P0 | §6.3 justifications |
| SEC-01 | P9 | TLS, HSTS and expiry monitor |
| SEC-02 | P1 | CORS guardrail test |
| SEC-03 | P1 | Trusted-host test |
| SEC-04 | P5 | Header and CSP tests |
| SEC-05 | P5, P13 | Residual risk recorded (ADR-0007 plus readiness report) |
| SEC-10 | P7 | PostgreSQL suite green and required |
| SEC-11 | P9 | HTTP RBAC sample |
| SEC-20 | P3 | Multi-process limit test |
| SEC-21 | P1, P13 | Values recorded in the readiness report |
| SEC-22 | P12 | Bootstrap runbook execution |
| SEC-24 | P3, P11 | Per-trigger multi-process tests; fail-closed; latency |
| SEC-25 | P3–P5, P13 | All ADR-0007 conditions evidenced |
| SEC-26 | P3 | No-bypass test |
| SEC-30 | P8 | Existing scans retained |
| SEC-31 | P8 | Image-scan job; waivers with expiry |
| SEC-32 | P8 | Required secret scan |
| DEP-01 | P0 | ADR-0008 plus provider decision records |
| DEP-02 | P9 | Network exposure checks |
| DEP-03 | P2, P9 | Container configuration review |
| DEP-04 | P9 | Parity check (image digest, PostgreSQL major version) |
| DEP-06 | P0 | Justification log |
| DB-01 | P2 | Migrate tests |
| DB-02 | P2, P12 | Rollback rehearsal |
| DB-03 | P8, P10 | Pre-migration backup step evidence |
| DB-04 | P10 | Backup configuration plus alert |
| DB-05 | P10 | PITR drill |
| DB-07 | P12 | Migration-failure runbook |

### 15.3 CI, performance, rollback and success criteria

| Requirement | Phase | Evidence |
|---|---|---|
| CI-01 | P8 | Readback plus refused merge |
| CI-02 | P8 | ADR-0009 bypass log |
| CI-03 | P8 | Deploy evidence |
| CI-04 | P8 | G-14 list with fixed versus tracked items |
| PERF-01 | P11 | Workload record: owner-supplied, or labelled as assumed |
| PERF-02 | P11 | Measurements |
| PERF-03 | P11 | Thresholds (provisional until D-10) |
| PERF-04 | P11 | Capacity statement |
| RB-01 | P12 | SC-05 timing |
| RB-02 | P12 | Audit preserved after rollback |
| SC-01 | P9, P13 | Staging and production deploy evidence |
| SC-02 | P10 | Restore drill |
| SC-03 | P7 | Isolation suite |
| SC-04 | P1 | Guardrail tests |
| SC-05 | P12 | Rollback rehearsal |
| SC-06 | P2 | Scheduler tests and drill |
| SC-07 | P12 | Induced-failure alerts |
| SC-08 | P8, P13 | Refused merge |
| SC-09 | P9, P13 | Smoke timing |
| SC-10 | P11 | Baseline |
| SC-11 | P12 | Runbook log |

### 15.4 SHOULD items and deferred items

**SHOULD items, planned:**

| Item | Phase |
|---|---|
| FR-PRD-007 (downtime measured) | P9, P13 |
| FR-PRD-014 | P1 |
| FR-PRD-027 | P6 |
| FR-PRD-043 | P8 |
| FR-PRD-044 | P8 |
| FR-PRD-064 | P9, P10 |
| SEC-23 (MFA readiness preserved; nothing removed) | — |
| SEC-33 | P8 |
| DEP-05 | P9 |
| CI-05 | P8 |
| NFR-PRD-10 | P0, P13 |

**DEFERRED, not planned (spec §21):**

| Item | Trigger |
|---|---|
| SEC-12 RLS | Risk evidence |
| DB-06 partitioning | Measured latency |
| PERF-05 | PERF-04 saturation |
| MFA | — |
| HttpOnly cookies | — |
| Multi-region | — |
| Certification | — |

---

## 16. Plan Audit (performed after writing)

| Check | Result |
|---|---|
| Every spec MUST mapped to a phase and evidence | **PASS.** §15 covers:<br>• FR-PRD-001…063 (all MUST IDs);<br>• NFR-PRD-01…09;<br>• SEC-01…05, 10, 11, 20–22 and 24–26;<br>• SEC-30…32;<br>• DEP-01…04 and 06;<br>• DB-01…05 and 07;<br>• CI-01…04;<br>• PERF-01…04;<br>• RB-01/02;<br>• SC-01…11. |
| Dependency cycles | **None.** The graph in §10 is acyclic. P8's ruleset part may run early without creating a cycle. |
| Unjustified complexity | **None.** Every addition has a justification in §6.3. Redis, queues, Kubernetes and RLS are excluded or deferred with triggers. |
| Unsupported assumptions | Removed or labelled:<br>• no provider, price or latency figure is stated;<br>• workload is "ASSUMED — provisional" until D-10;<br>• thresholds are PROVISIONAL;<br>• 7 years is a planning assumption;<br>• the Next 16 proxy convention and the `limits` PostgreSQL backend are P0-research items, not facts. |
| Untestable acceptance criteria | **None found.** Each exit gate names a test, a drill or an artifact. The "within detection window" (SC-07) and "rollback target" (SC-05) values are set from P11 and P0 data **before** the rehearsals that measure them. |
| Spec tensions surfaced, not silently resolved | 1. FR-PRD-005 strict schema check vs FR-PRD-023 N-1 rollback → P-2 override, flagged for an ADR.<br>2. SEC-24 "sign out all devices" has no existing endpoint → not added (no new features); the rule applies if one is added later.<br>3. RPO ≤1 h does not hold in the provider-loss scenario → owner decision (§9 #5).<br>4. 99.5% vs a 4 h RTO → owner decision (§9 #6). |
| Newly evidenced defects carried into phases | 1. The recurring-posting crash window (two commits) → P2.<br>2. Missing proxy-header trust → P3.<br>3. Path-filtered workflows cannot serve as required checks → P8. |
| Epic 11 protection | FR-PRD-060 is verified by the existing contract suites passing unchanged in P4, P6 and P11. Export changes are metrics only. |

---

## 17. Readiness for `/sp.tasks`

**Ready.** Every MUST requirement has a phase, a dependency position and a measurable exit gate. No blocking clarification remains for task generation.

The open inputs are scheduled, not blocking task generation:
- providers;
- the sender domain;
- legal retention and data residency;
- the D-10 figures;
- the RPO and availability decisions in §9.

Each is gated before the phase that needs it. **All must be resolved, or covered by an explicit, documented, owner-approved exception that records scope, reason, approver, approval date, and expiry or review date, before P13** (see the P13 preconditions, which list §9 #1–#8, including #5 the provider-loss backup/RPO decision).

**Stopped here.** `tasks.md` has not been generated, and no code, migrations, infrastructure or configuration have been changed.
