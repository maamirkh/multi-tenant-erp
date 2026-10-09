# Epic 12 — Deployment / Production Readiness: Official Specification

**Feature Branch**: `012-production-readiness`
**Epic Sequence**: Epic 0 ✅ → 1 ✅ → … → 9A ✅ → 10 ✅ → 11 ✅ (merged to `main` as `712a668`, 2026-10-01) → **Epic 12 ← Current** → AI Layer (separate future epic, out of scope here)
**Created**: 2026-10-08
**Status**: Draft — clarified 2026-10-09 (three rounds). All blocking decisions D-01…D-12 are resolved. The Constitution 2.0.0 and ADR-0007/0008/0009 amendments are applied in the governance PR (branch `docs/epic-12-governance-amendments`) and take effect when it merges to `main`. Specification only: no plan, tasks, code, migrations, deployment files or configuration have been produced.
**Official Epic name**: `Epic 12 — Deployment / Production Readiness`. The spec was first drafted under the working title "Production Readiness & Deployment"; that title is preserved verbatim only in PHR 0001.
**Input**: "Epic 12 — define what makes the ERP production-ready: secure, reliable, observable, recoverable. Not AI."

**Requirement keywords**: **MUST** = required for the Production-Readiness Gate (§17). **SHOULD** = expected; an approved, recorded waiver may defer it. **DEFERRED** = explicitly out of this epic, with the trigger that would bring it back (§21).

**Evidence rule (applies to every requirement)**: configuration alone is not evidence. A requirement is satisfied only by a reproducible artifact, such as:
- a test or CI run;
- a drill log with timings;
- a command transcript;
- a screenshot of an enforced setting with its API readback.

Each artifact must come from a production-like environment where the requirement says so.

---

## Clarifications

### Session 2026-10-09

Decision status vocabulary used in this spec:
- **APPROVED** — an owner-approved direction;
- **PROPOSED** — an objective awaiting owner confirmation or a feasibility check in the plan;
- **OPEN** — an input still to be supplied;
- **PENDING** — a choice not yet made.

Full detail is in `clarifications.md`.

- Q: D-01 production topology? → A: **APPROVED** — Vercel frontend + Dockerized FastAPI backend on a VPS + managed PostgreSQL. The provider and region are **OPEN**: the plan compares them on backup/PITR, TLS, latency, cost and ops burden. No service is purchased or assumed. A Constitution §6.6 amendment and a superseding ADR are pending approval.
- Q: D-02 RPO? → A: **PROPOSED** — at most 1 hour of data loss, valid only once the chosen database and backup design is shown to meet it.
- Q: D-03 retention? → A: **APPROVED** split into two policies:
  - operational backups: 30 days initially;
  - business/accounting records: 7 years, as a planning requirement. **OPEN**: the 7-year figure must be confirmed against applicable Pakistani legal and tax requirements or professional advice; it is not verified legal advice.
- Q: D-04 file storage? → A: **APPROVED** — private, tenant-scoped object storage with short-lived signed URLs and an authorization check:
  - SVG is removed from company-logo uploads unless a tested, safe sanitization approach is justified;
  - the fake `/dev/exports/...` fallback and every silent production storage failure path are fixed.
  The S3-compatible provider is **OPEN** (compared in the plan).
- Q: D-05 email? → A: **APPROVED** — a real transactional email provider for verification and password reset. Production MUST fail safely or explicitly disable the flows when email is not configured, and MUST never report a delivery that did not happen. The provider and sender domain are **OPEN**.
- Q: D-06 governance? → A: **APPROVED in direction** — a single-maintainer workflow:
  - short-lived branches → PR → `main`;
  - owner self-review recorded against the Constitution §29 checklist;
  - required CI checks must pass, with no bypass of failing checks and every exception logged;
  - independent review applies once a second contributor exists.
  The amendment text is **PENDING** owner approval (`clarifications.md` §5).
- Q: D-07 availability/RTO? → A: **PROPOSED** service objectives, not an SLA: 99.5% monthly availability and a 4-hour RTO, with planned maintenance permitted. Measurement and exclusions are in NFR-PRD-01; feasibility and cost are verified in the plan.
- Q: D-08 CSP/auth? → A: **APPROVED direction** — keep the existing token approach temporarily and implement a strict, tested CSP. This is **conditional on D-11**: the current auth design is not treated as approved merely because ADR-0003 describes it. CSP is required under every option, and it does not remove every token-storage risk.
- Q: D-09 runtime safety? → A: **APPROVED**:
  1. a dedicated, single-run migration release job, with workers checking only schema-head compatibility;
  2. a dedicated scheduler process with a PostgreSQL advisory lock;
  3. recurring-journal instance and GL posting written atomically, proven by concurrent PostgreSQL tests and a staging drill;
  4. fail-closed configuration guardrails (§9.4).
- Q: D-10 workload? → A: **OPEN** owner-supplied input. Numbers are not invented. The benchmark method is defined (§14), and the thresholds that remain provisional are listed (PERF-03).
- Q: D-11 Better Auth vs the in-house JWT? → A: Superseded by the owner decisions below (B).
- Q: D-12 database-level row security? → A: Superseded by the owner decisions below (defer, with PostgreSQL evidence required).

### Session 2026-10-09 (owner decisions, round 2)

- Q: D-11 authentication architecture? → A: **APPROVED — Option B**: keep and formally approve the in-house JWT authentication, subject to an evidence-based security review.
  - The review (`clarifications.md` §3.1) found **no critical gap that the existing design cannot safely address**.
  - Approval is conditional on these Epic 12 MUSTs: SEC-24, SEC-04/05, FR-PRD-032, SEC-20 (shared rate limiting) and SEC-26.
  - If a fix proves unsafe within the existing design, Option A is re-presented with evidence. No auth migration happens without explicit approval.
  - Better Auth is never claimed as implemented.
- Q: G-23/SEC-24 immediate revocation? → A: **APPROVED — MUST**. Access tokens of revoked sessions are rejected immediately after:
  - logout;
  - password reset or change;
  - account disablement (deactivate, suspend, lock, archive);
  - administrative or session revocation.
  The rule must hold across all workers and instances, fail closed when revocation state is unavailable, and be proven with real PostgreSQL multi-process tests. The mechanism is compared in the plan, and a dedicated extra DB lookup is not mandated.
- Q: D-12 database row security? → A: **APPROVED — defer**, conditional on the PostgreSQL negative isolation suite (SEC-10) passing. Any demonstrated cross-tenant leak is a **production blocker**. RLS stays a future hardening option, added to the plan only if risk assessment shows a clear need.
- Q: A-01…A-13 amendments? → A: **APPROVED in principle**; the exact diffs (`amendments-proposed.md`) are under review and nothing has been applied. Verification corrected the proposal to Constitution **2.0.0 (MAJOR, per §45.3)**; ADR-0007/0008/0009 are confirmed free.
- Q: 7-year retention? → A: a **planning assumption** only. Professional confirmation of the Pakistani tax and accounting obligations is required before the final production-readiness gate.
- Q: A-01…A-13 final approval (round 3)? → A: **APPROVED and applied** in one PR, as §45.2 requires:
  - Constitution **2.0.0** (MAJOR justified by §45.3);
  - ADR-0007 (authentication), ADR-0008 (deployment topology) and ADR-0009 (governance), all verified free;
  - legacy-index notices in `DECISIONS.md` and `DEPLOYMENT_GUIDE.md`;
  - "Related: ADR-0007" lines in ADR-0001 and ADR-0003.
  One consistency addition beyond the reviewed diffs: `develop` was removed from the §38 AI Development Rules, as a direct consequence of A-06/A-08. The official Epic name was also applied in `docs-project-context/EPICS.md` and `PROJECT_CONTEXT.md`.
- Q: D-10 workload? → A: no invented figures. The plan defines a baseline, measurable load tests and provisional thresholds. Expected tenants, users per company, concurrent users, invoices and export volumes are recorded before final capacity sign-off.

---

## 1. Status / Goal / Non-goals

### 1.1 Goal
Take DevSphere ERP from "all epics merged and CI-green" to **"safe to run real tenants' financial data in production"**:
- one defined production architecture and a staging environment that mirrors it;
- enforced release gates;
- a proven backup and restore with defined RPO/RTO;
- tenant isolation proven on PostgreSQL;
- production-safe configuration that fails fast when wrong;
- observability and alerting good enough to detect and diagnose incidents;
- written, rehearsed runbooks.

### 1.2 Non-goals
- No AI, LLM, agents, vector search, RAG or NL-to-SQL.
- No microservices split, Kubernetes, multi-region active/active, data warehouse or OLAP store.
- No rewrite of auth, ORM, framework or module boundaries.
- No new business features and no change to approved business behavior or API contracts, except where an evidenced production gap (§2.2) requires it. Each such change is listed explicitly in §7.
- No change to Epic 11 report, export, audit, saved-view, dashboard or Customer 360 contracts.
- No performance optimisation without a measured bottleneck (Constitution §25).

---

## 2. Existing-State Findings

Inspected 2026-10-08 on `main` @ `712a668`:
- Constitution v1.2.1;
- `docs/architecture/*`, `docs-project-context/{DEPLOYMENT_GUIDE,DECISIONS}.md`;
- Epic 0–11 specs, plans, tasks and reports;
- `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `.github/workflows/*`, the `main` ruleset;
- `backend/main.py`, `backend/core/{config,database,logging,middleware,storage,migrations}`;
- the `auth`, `platform_admin` and `accounting` scheduler modules, and the frontend token storage.

### 2.1 Controls already satisfied (do not rebuild — verify and reuse)

| ID | Control | Evidence |
|---|---|---|
| S-01 | Multi-stage production images. The backend runs as non-root `appuser` and production installs no dev dependencies. The frontend uses Next `standalone` output. | `backend/Dockerfile`, `frontend/Dockerfile`; CI "Docker Build (Backend)" green; frontend production image builds after the Epic 11 Dockerfile fix |
| S-02 | API security headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, CSP, HSTS and Permissions-Policy. | `core/middleware/security_headers.py`; `tests/security/test_security_headers_all_endpoints.py` |
| S-03 | Request ID propagation, and JSON logs in production carrying `timestamp`, `level`, `request_id` and `user_id`. | `core/middleware/request_id.py`, `core/logging/setup.py` |
| S-04 | Centralized exception handling with the standard error envelope. Internal errors are not exposed. | `main.py` handlers |
| S-05 | `/api/v1/health`, `/health/live` and `/health/ready` (a database check), plus a platform operational-health endpoint (Epic 9A). | `api/v1/router.py`, `platform_admin/router.py` |
| S-06 | OpenAPI/Swagger is disabled unless `DEBUG`. | `main.py` |
| S-07 | Auth hardening: startup rejects a missing or short `JWT_SECRET_KEY`; Argon2id; lockout; password history; refresh-token rotation and replay detection; rate limit on auth routes. | `main.py`; `tests/security/test_{account_lockout,password_history,replay_attack,token_entropy,rate_limits,anti_enumeration,sensitive_log}.py` |
| S-08 | Tenant isolation and RBAC tests: 76 security test files, 70 files covering cross-tenant/IDOR, and the Epic 11 entitlement, RBAC, tenant-isolation, platform-admin and support-access matrices (T261–T265). | `backend/tests/security/**` |
| S-09 | DB connection health: `pool_pre_ping`, `lock_timeout` on each connection, configurable pool. | `core/database/engine.py` |
| S-10 | Migration discipline: Alembic chain `001→078`, every migration with a downgrade; the full chain is verified up and down on real PostgreSQL (Epic 11 T266/T281); CI migrates the job database to head. | `migrations/versions/*`, `tests/integration/migrations/*` |
| S-11 | CI checks: Ruff and `mypy .`; the full backend suite on PostgreSQL 16 with coverage ≥80% (auth ≥90%); bandit and pip-audit; npm audit; Jest; Next build; backend Docker build; PR title, secret and TODO checks; GitGuardian. Actions run on Node 24. | `.github/workflows/*`; all 11 checks green on `41ecd39` |
| S-12 | Append-only module audit logs, and Reports export audit durability (the audit is committed before the file is delivered). | Epic 2–11 specs; Epic 11 T206 |
| S-13 | Measured performance evidence exists for: Epic 8 GL (500K lines, PostgreSQL; trial balance and statements within plan limits); Epic 11 T270 (10K contracts and tie-heavy pagination); Epic 11 T214 (export memory benchmark); login/refresh performance tests. | Epic 8 plan §Phase 13, Epic 11 tasks T214/T270 |
| S-14 | Platform-owner bootstrap is a one-time operator step from environment variables. It accepts only a pre-hashed Argon2id password, so plaintext never appears in source, environment dumps or logs. | `modules/platform_admin/bootstrap.py` |

### 2.2 Gaps found (each traced to evidence)

| ID | Gap | Evidence | Severity |
|---|---|---|---|
| G-01 | The **deployment target is inconsistent** across approved documents. | Constitution §6.6: initial deployment on Vercel + Render + Neon, future production on Cloudflare → Hetzner → Docker Compose → PostgreSQL + Redis. `DECISIONS.md` ADR-018 (Accepted): frontend on Vercel, backend Docker on a cloud VPS. `DEPLOYMENT_GUIDE.md`: Hetzner recommended. | Blocking decision (D-01) |
| G-02 | **No staging or production environment definition.** Only the dev `docker-compose.yml` exists. There is no production orchestration, infrastructure-as-code or staging, although Constitution §43 makes "deployed to staging and validated" part of Done. | Repository tree | High |
| G-03 | **Migrations run in-process at every app start.** `lifespan → run_migrations()` runs in each worker, and the production image runs `--workers 2`. There is no migration lock, and startup is coupled to schema changes. | `main.py:60`, `core/migrations.py`, `backend/Dockerfile` CMD | High |
| G-04 | **The in-process scheduler starts in every worker and replica.** APScheduler (recurring journals, AR overdue check, AP due reminders) is started per process. Recurring journals have a check-then-insert plus a unique-constraint backstop, but exactly-once execution across N processes is **unverified**. A duplicate GL posting window may exist between journal posting and instance insert. | `main.py:106`, `accounting/services/scheduler.py`, `recurring_journal_service.py` | High |
| G-05 | Rate limiting is **in-memory per process**, with no shared store, and applies to auth routes only. The effective limit multiplies with the number of workers and replicas. | `modules/auth/router.py:66` | Medium |
| G-06 | **No production configuration guardrails:**<br>• `ENVIRONMENT` is free-form;<br>• `DEBUG=true` and `LOG_LEVEL=DEBUG` are allowed in production — the email stub logs reset and verification tokens at DEBUG;<br>• `S3_ACCESS_KEY`/`S3_SECRET_KEY` default to `minioadmin`;<br>• `SECRET_KEY`'s documented minimum of 32 characters is not enforced;<br>• `CORS_ORIGINS` defaults to localhost;<br>• there is no trusted-host validation. | `core/config/settings.py`, `auth/services/email_service.py` | High |
| G-07 | `.env.example` is **incomplete** (Constitution §20 requires every key). Missing keys include `S3_*`, `ARGON2_*`, `DB_LOCK_TIMEOUT_SECONDS`, `COMPANY_MAX_MEMBERS`, `USER_AVATAR_MAX_BYTES`, `INVITATION_EXPIRY_DAYS` and others. | `.env.example` vs `settings.py` | Medium |
| G-08 | **Object storage is not wired in production:**<br>• `S3StorageClient` is never instantiated;<br>• company logo and user avatar services use stubs that raise `NotImplementedError`;<br>• Inventory export uses `storage=None`;<br>• the storage contract returns **public URLs** — with no private-bucket or signed-URL model, tenant files would become world-readable by URL once wired;<br>• company-logo uploads accept `image/svg+xml` (`companies/services/company_logo_service.py:34-35`), a script-capable format;<br>• Inventory export returns a fake `/dev/exports/<file>` URL when storage is absent, and an empty URL when upload fails (`inventory/services/export_service.py:167-178`). | `core/storage/s3_client.py`, `companies/dependencies.py:101`, `users_roles/dependencies.py:71`, `inventory/dependencies.py:415` | High (blocking decision D-04) |
| G-09 | **Transactional email is a stub.** Password reset and email verification are never delivered; tokens appear only in DEBUG logs. | `auth/services/email_service.py` | High (blocking decision D-05) |
| G-10 | **Frontend sends no security headers or CSP.** ADR-0003 accepted refresh tokens in `localStorage` *with CSP as the stated XSS mitigation*, but that mitigation is absent for the app origin (the API's CSP does not protect pages). | `frontend/next.config.ts`, `history/adr/0003-*.md` | High |
| G-11 | Logs lack `company_id` (required by Constitution §22), and there is **no request access log** (method, path, status, duration, tenant). | `core/logging/setup.py`, `core/middleware/request_id.py` | Medium |
| G-12 | **No metrics, error tracking, uptime monitoring or alerting.** Epic 8 deferred GL-posting and reconciliation monitoring to "Epic 12 — Deployment". | Repository; Epic 8 plan "Future Epic 12 — Deployment" | High |
| G-13 | **No backup or restore tooling or drill; RPO/RTO undefined** (Constitution §34 requires this before launch). Retention is inconsistent: `DEPLOYMENT_GUIDE` says ≥30 days; the Epic 8 plan says daily incremental, weekly full and 7-year retention for accounting data. | Repository; docs | Blocking (D-02, D-03) |
| G-14 | **CI is not enforced at merge, and there is no CD:**<br>• the `main` ruleset requires 1 approval and squash merge, but `required_status_checks` is **empty**;<br>• merges by the sole owner rely on an admin bypass;<br>• `pr-checks.yml` lists 10 intended required checks that are not configured;<br>• there is no deploy workflow, image registry or tagging, staging gate or rollback automation;<br>• a stale trigger branch `002-auth-identity` remains;<br>• "Migration Validation" checks only syntax and chain (the real up/down runs inside the test suite);<br>• the backend suite takes ~2h50m;<br>• wall-clock tests have caused false failures (one fixed in `41ecd39`; the Installments pagination wall-clock test remains). | `.github/workflows/*`; ruleset API readback 2026-10-01 | High |
| G-15 | **No query/statement timeout and no aligned request timeouts.** Epic 11 exports are synchronous (up to 50K CSV / 25K XLSX rows); proxy, app and database timeouts are undefined. | `core/database/engine.py`; Epic 11 constants | Medium |
| G-16 | The dev compose file is unsafe to reuse in production:<br>• it publishes ports `5432`, `9000` and `9001`;<br>• MinIO runs as `minio:latest` with default credentials;<br>• `DEBUG` defaults to true;<br>• `--reload` is on;<br>• source is bind-mounted. | `docker-compose.yml` | Medium (production must not reuse it) |
| G-17 | **Two backend lock files** (`poetry.lock` and `uv.lock`) — dependency drift risk. CI and Docker use Poetry. | `backend/` | Low |
| G-18 | **No runbooks** for deploy, rollback, restore, incidents, secret rotation or migration recovery. | Repository | High |
| G-19 | **Governance drift:**<br>• Constitution §28 prescribes `develop`/`feature/*` branches and §43 requires review by another engineer;<br>• actual practice is `NNN-feature → main` squash PRs by a sole owner using admin bypass. | Git history; ruleset | Decision (D-06) |
| G-20 | Tenant isolation is **application-level only**: there is no database-level row security, and most isolation tests run on SQLite rather than PostgreSQL. | Tests; models | Medium |
| G-21 | **Readiness checks only database connectivity**: not schema-at-head, storage reachability or scheduler state. | `api/v1/router.py` | Medium |
| G-22 | **Unratified authentication deviation** (corrected 2026-10-09 — earlier listed as "accepted"). Constitution §6.3, §15 step 2, §16 ("Authentication MUST use Better Auth") and §39 (mandatory ADR-002 "Why Better Auth") require Better Auth. The repository has no Better Auth dependency, and authentication is in-house:<br>• PyJWT HS256 access tokens;<br>• opaque rotating refresh tokens;<br>• a `sessions` table.<br>ADR-0001 records that architecture but **never mentions Better Auth or the Constitution**. The deviation is acknowledged only in Epic 9A *plan* §3.1, and a plan cannot override the Constitution (§4). **Resolved by Constitution v2.0.0 (§6.3, §15, §16) and ADR-0007 — governance PR, effective on merge.** The conformance conditions remain open as SEC-24/04/05/20/26 and FR-PRD-032. | `backend/modules/auth/services/{jwt_service,token_service,password_service,auth_service}.py`, `backend/core/auth/{dependencies,interfaces}.py`, `history/adr/0001-*.md`; no `better-auth` in `frontend/package.json` or `backend/pyproject.toml` | Resolved (governance) once the PR merges; conditions tracked |
| G-23 | **Session revocation is not checked per request.** `get_current_user()` decodes the JWT and checks only account status; it never checks `Session.is_revoked`. An access token stays valid after logout or session revocation until it expires (default 15 min). Locked, inactive and deleted accounts *are* blocked immediately. The logout test proves only that the refresh token is rejected (`tests/integration/api/v1/auth/test_logout.py:32`). By contrast, platform-admin auth *does* check revocation per request (`modules/platform_admin/dependencies.py:122`). | `backend/core/auth/dependencies.py:44-115`; Epic 9A plan §3.1 | Medium — **MUST (SEC-24)** |
| G-25 | **Latent role-based super-admin bypass on the tenant path.** `CurrentUser.roles` is hard-coded to `[]` (`core/auth/dependencies.py`), yet two tenant-path checks grant a bypass when it contains `super_admin`: `companies/dependencies.py:150` and `accounting/services/permission_check.py:48`. `require_role` (`companies/dependencies.py:160-190`) is used by no route. Today these are inert and fail closed. If `roles` were ever populated from a tenant-scoped token, they would expose platform-level authority through a tenant session, which Constitution §50 forbids. | files cited | Low (latent) |
| G-24 | **ADR governance gaps:**<br>• two ADR series exist — `history/adr/0001–0006` and `docs-project-context/DECISIONS.md` ADR-001…019;<br>• Constitution §39 makes `history/adr/` canonical;<br>• the six "Mandatory Initial ADRs" in §39 (including ADR-002 "Why Better Auth") were never created there;<br>• `DECISIONS.md` ADR-018 is therefore a non-canonical record. | Constitution §39; `history/adr/`; `docs-project-context/DECISIONS.md` | Decision (amendment package) |

---

## 3. Problem Statement

Every module is implemented, tested and merged, but the platform has never run outside development, and the gaps in §2.2 mean a first production deployment would face these risks:

| Gap | Risk |
|---|---|
| Concurrent migrations (G-03) | Schema corruption or a failed start |
| Scheduler running in every process (G-04) | Duplicated accounting jobs |
| No backup or restore (G-13) | Unrecoverable data loss |
| No storage or email (G-08, G-09) | Broken password reset and uploads |
| No frontend CSP alongside `localStorage` tokens (G-10) | Weakened token-theft protection |
| No monitoring (G-12) | Incidents go unnoticed |
| CI not enforced at merge (G-14) | Failing code can reach production |

Production readiness must be **proven with evidence**, not asserted through configuration.

---

## 4. Goals & Success Criteria

| ID | Success criterion (measurable, verified in staging unless stated) |
|---|---|
| SC-01 | A tagged release is deployed to staging and then production through the documented pipeline, with no manual file edits on servers. The deploy log records the commit SHA, image digests and the migration revision before and after. |
| SC-02 | A full restore of a production-like backup into an isolated environment meets the approved RPO and RTO (D-02). The restored data passes integrity checks: row counts per tenant for key tables, GL trial balance balanced, latest audit entries present. Measured timings are recorded. |
| SC-03 | The PostgreSQL-backed tenant-isolation negative suite (§9.2) reports 0 cross-tenant reads or writes across API, report, export, Customer 360, saved view, storage object and audit endpoints. |
| SC-04 | Booting with any forbidden production setting from §9.4 fails before serving traffic, with a clear error: 100% of guardrail cases are covered by tests. |
| SC-05 | A deliberately broken release is rolled back to the previous version within the approved rollback target, with the database left at a schema the previous code supports. This is rehearsed at least once in staging. |
| SC-06 | With N application processes, each scheduled job executes exactly once per scheduled occurrence: verified under concurrency, 0 duplicate GL postings. |
| SC-07 | An induced failure (API down, DB unreachable, error-rate spike, disk/backup failure) raises an alert to the operator within the approved detection window, and the alert links to a runbook. |
| SC-08 | Every merge to `main` requires all designated CI checks to pass: verified by an attempted merge with a failing check being refused. |
| SC-09 | Post-deploy smoke verification (§16.3) passes in under the approved time budget, with no manual steps. |
| SC-10 | A performance baseline for the agreed SME reference workload (§14) is measured on production-like infrastructure and recorded. Alert thresholds derive from it. |
| SC-11 | Every runbook in §12.4 is executed at least once (tabletop or live in staging) and the execution is logged. |

---

## 5. Scope / Out of Scope

### 5.1 In scope
- Production and staging architecture and environment separation.
- Runtime configuration and its guardrails.
- Deployment pipeline and release gates.
- Database operations: pooling, timeouts, migrations, backups, restore, RPO/RTO.
- Secrets management.
- HTTPS, CORS, trusted hosts and security headers (API and frontend).
- Auth, session, rate-limit and email-delivery gaps.
- Tenant-isolation and RBAC verification on PostgreSQL.
- Object storage security.
- Structured and access logging, metrics, error tracking, health/readiness, alerting.
- CI/CD and branch protection.
- Smoke verification and performance baseline.
- Rollback: code and database, as distinct procedures.
- Dependency, container and secret scanning.
- Runbooks.
- Epic 11 production safety.
- The readiness gate.

### 5.2 Out of scope
Everything in §1.2, plus:
- Product-level features, including new reports or async exports — Epic 11's deferred items stay deferred.
- Billing or payment integration.
- Compliance certifications (SOC 2, ISO 27001). Controls here are compatible with them but certification is not pursued.
- Mobile apps.

---

## 6. Actors / Operational Roles

| Role | Responsibility | Notes |
|---|---|---|
| **Platform Owner / Operator** | Owns infrastructure, deploys, rotates secrets, responds to alerts, runs restores. | Today one person (sole repo owner). Runbooks must be executable by one operator. |
| **Release Approver** | Approves promotion from staging to production and authorizes database rollback. | May be the same person as the Operator (see D-06). Approvals are still recorded. |
| **Platform Administrator** (Epic 9A) | Uses platform-admin features. Gains no infrastructure access through Epic 12. | Existing role; unchanged. |
| **Tenant Admin / Tenant User** | Use the ERP. Affected by downtime, data loss and isolation failures. | Indirect actors; their data is the protected asset. |
| **CI/CD System** | Runs gates, builds images, deploys, and records evidence. | Has least-privilege credentials only. |
| **Security Reviewer** | Reviews scan results, header, CSP and guardrail evidence. | May be the Operator; reviews are logged. |

### 6.1 Operational user stories (prioritized)

| ID | Priority | Story | Independent test |
|---|---|---|---|
| US-1 | P1 | As the Operator, I can restore the database to a recent point after a disaster, so tenants lose at most RPO of data. | Restore drill (SC-02). |
| US-2 | P1 | As the Operator, I can deploy a release safely and roll it back. | Staging rehearsal (SC-01, SC-05). |
| US-3 | P1 | As a tenant, I can never see another tenant's data, files, reports or exports. | PostgreSQL negative suite (SC-03). |
| US-4 | P1 | As the Operator, the system refuses to start with unsafe production configuration. | Guardrail tests (SC-04). |
| US-5 | P2 | As the Operator, I am alerted to outages and error spikes and can trace a failing request across logs. | Induced-failure test (SC-07). |
| US-6 | P2 | As a user, I can reset my password and verify my email in production. | Smoke test (§16.3), subject to D-05. |
| US-7 | P3 | As the Owner, I know the capacity limits of one deployment for SME tenants. | Baseline report (SC-10). |

---

## 7. Functional Requirements

### 7.1 Environments & deployment
- **FR-PRD-001 (MUST)** There MUST be exactly three named environments: `development`, `staging` and `production`. `ENVIRONMENT` MUST be restricted to these values (plus `testing` for automated tests), and an unknown value MUST fail startup.
- **FR-PRD-002 (MUST)** Staging MUST mirror production topology, configuration shape, image artifacts and PostgreSQL major version. It MUST use separate credentials, secrets, databases and storage, and MUST NOT contain production tenant data unless it has been anonymized (see FR-PRD-064).
- **FR-PRD-003 (MUST)** Production MUST be deployed from immutable, versioned artifacts built once by CI: image digests and a frontend build tied to a git SHA. The same artifact MUST be promoted from staging to production with no rebuild.
- **FR-PRD-004 (MUST)** Production orchestration MUST be defined in version control, separately from the development compose file:
  - no source bind-mounts;
  - no `--reload`;
  - no published database or storage-admin ports;
  - pinned image versions.
- **FR-PRD-005 (MUST)** Database migrations MUST run as **one explicit, single-run release step** (APPROVED, D-09: a dedicated release job) before new application processes take traffic, never concurrently from N app workers (G-03). Development may keep auto-migration at startup.
  - Application start MUST NOT perform schema changes in production.
  - Application start MUST verify that the schema is at the revision the code expects. On a mismatch it MUST refuse readiness and log the expected and actual revisions.
- **FR-PRD-006 (MUST)** Background scheduled jobs MUST execute **exactly once per occurrence** across all application processes and replicas (G-04). Mechanism (APPROVED, D-09): a **dedicated scheduler process** — API workers never start the scheduler — protected by a **PostgreSQL advisory lock**, so a second scheduler instance cannot run the same job concurrently. The recurring-journal instance record and its GL posting MUST be written **atomically, in one transaction**. A concurrency test with ≥2 processes on PostgreSQL MUST show 0 duplicate executions and 0 duplicate GL postings, and a staging drill MUST confirm it.
- **FR-PRD-007 (SHOULD)** Deploys SHOULD be zero- or minimal-downtime (rolling or blue/green, as the D-01 topology allows). The measured user-visible interruption MUST be recorded.

### 7.2 Configuration & secrets
- **FR-PRD-010 (MUST)** In `staging`/`production`, startup MUST fail if any rule in §9.4 is violated.
- **FR-PRD-011 (MUST)** Secrets MUST:
  - come only from the platform's secret manager or injected environment;
  - never be baked into images;
  - never be committed;
  - never be logged.
  CI MUST use the CI platform's secret store (Constitution §20).
- **FR-PRD-012 (MUST)** `.env.example` (or an equivalent documented manifest) MUST list every configuration key with its purpose, whether it is required, its safe default and whether it is secret. A test MUST fail when a settings field is undocumented (G-07).
- **FR-PRD-013 (MUST)** A **secret-rotation** procedure MUST exist and be rehearsed in staging for:
  - JWT signing secret — with defined behavior: active sessions are invalidated, and users re-login;
  - database credentials;
  - storage credentials;
  - email provider key.
- **FR-PRD-014 (SHOULD)** Only one dependency lock file per language SHOULD be authoritative. The unused one (G-17) SHOULD be removed or documented.

### 7.3 Database operations
- **FR-PRD-020 (MUST)** Connection pool size × processes × replicas MUST stay below the database's connection limit, with documented headroom for migrations and admin. The numbers are derived from the D-01 topology and recorded.
- **FR-PRD-021 (MUST)** Statement and request timeouts MUST be defined and aligned (proxy > app > database statement timeout), so a runaway query cannot hold a connection indefinitely. Exceptions — Epic 11 export and long-running report paths — MUST be explicitly sized and documented, not left unbounded.
- **FR-PRD-022 (MUST)** Every release containing migrations MUST pass, in CI or staging on PostgreSQL:
  - upgrade from the previous production revision;
  - a smoke test against the upgraded schema;
  - for reversible migrations, a downgrade-then-upgrade round trip.
- **FR-PRD-023 (MUST)** Migrations shipped together with code MUST be **backward-compatible with the previous release's code** (expand/contract, Constitution §18), so the code can roll back without a schema rollback. Any migration that cannot meet this MUST be flagged in the PR, with a documented, approved procedure.
- **FR-PRD-024 (MUST)** Automated backups MUST meet the RPO and retention (D-02, D-03). They MUST be encrypted at rest and in transit, and stored off the database host in a separate failure domain.
  - The proposed RPO of **1 hour** implies continuous WAL archiving / point-in-time recovery, or snapshots at least hourly. The chosen managed-database design MUST be shown to meet it before the RPO is confirmed.
  - **Operational backup retention: 30 days.**
- **FR-PRD-024a (MUST)** **Business/accounting record retention (7 years, planning requirement; legal confirmation OPEN)** is a separate policy from operational backups. The plan MUST define:
  - an archive mechanism and format (an immutable, encrypted, periodic archive of financial and audit records), independent of the 30-day backup rotation;
  - restore-from-archive procedure and a verification drill;
  - deletion: no business-record deletion before the retention period; any later deletion audited and approved;
  - interaction with tenant/company soft-delete retention (Epic 3);
  - who may access archives, with every access audited.
- **FR-PRD-025 (MUST)** A full **restore drill** MUST be performed before launch and then on the approved cadence (SHOULD be at least quarterly). The drill MUST measure RTO and RPO and MUST verify integrity: per-tenant row counts, a balanced trial balance and audit-log continuity.
- **FR-PRD-026 (MUST)** Backup failure or a missed backup MUST raise an alert (§12).
- **FR-PRD-027 (SHOULD)** Slow-query visibility SHOULD be enabled: the database's statement statistics or slow-query log, with a threshold derived from the §14 baseline.

### 7.4 Storage & email (evidenced functional gaps)
- **FR-PRD-030 (MUST)** Per D-04 (APPROVED: private storage), company logo, user avatar and Inventory export MUST work end-to-end in production:
  - no production path may raise `NotImplementedError`;
  - no path may return a fake URL (`/dev/exports/...`) or an empty URL after a failed upload;
  - a storage failure MUST surface as an explicit, user-safe error and an error log/metric, never a silent success (G-08).
- **FR-PRD-030a (MUST)** Allowed upload types stay content-verified (magic bytes).
  - `image/svg+xml` MUST be removed from company-logo uploads, unless a sanitization approach is justified in an ADR and covered by malicious-SVG tests.
  - Existing size limits stay unless evidence requires a change: logo `COMPANY_LOGO_MAX_BYTES` = 2 MiB, avatar `USER_AVATAR_MAX_BYTES` = 5 MiB.
- **FR-PRD-031 (MUST)** If object storage is enabled:
  - objects MUST be **private** by default;
  - tenant access MUST be through short-lived signed URLs, or through an authorized download endpoint that re-checks tenant and permission;
  - object keys MUST be tenant-prefixed;
  - a cross-tenant object access attempt MUST fail (part of the SC-03 suite).
  Converting the current public-URL contract (G-08) is part of this requirement.
- **FR-PRD-032 (MUST)** Per D-05 (APPROVED), password reset and email verification MUST be delivered in production through a real transactional email provider (the provider and sender domain are OPEN and compared in the plan).
  - If no provider is configured, staging/production MUST fail closed at startup (§9.4), or the flows MUST be explicitly disabled in the UI and API. They MUST never report delivery that did not happen.
  - Tokens MUST NEVER be logged at any level in staging/production.
  - Sender-domain authentication (SPF, DKIM, DMARC) MUST be configured and verified.
  - Development MAY keep a non-sending local mode, but MUST NOT log tokens above DEBUG.

### 7.5 CI/CD & release
- **FR-PRD-040 (MUST)** The `main` ruleset MUST require every designated status check to pass before merge, and that requirement MUST be verified by an attempted merge that fails (G-14, SC-08). The designated list starts from `pr-checks.yml`'s documented 10 checks plus GitGuardian, and is finalized in the plan.
- **FR-PRD-041 (MUST)** A deployment workflow MUST:
  1. build and scan the artifacts;
  2. publish them with immutable tags;
  3. deploy to staging;
  4. run smoke verification;
  5. require an explicit approval;
  6. promote the same artifacts to production;
  7. run production smoke verification;
  8. record evidence (SHA, digests, migration revisions, smoke result, approver).
- **FR-PRD-042 (MUST)** Production deploy MUST be blocked when any of these is true:
  - CI is red for the SHA;
  - the migration check fails;
  - container scanning finds an unwaived Critical or High;
  - staging smoke failed.
- **FR-PRD-043 (SHOULD)** CI feedback time SHOULD be reduced without lowering coverage, for example by parallelizing the backend suite. Tests that assert wall-clock time SHOULD become deterministic or be quarantined from merge gates, with a tracked follow-up (the Installments pagination test remains, G-14).
- **FR-PRD-044 (SHOULD)** Stale workflow triggers (`002-auth-identity`) SHOULD be removed, and the "Migration Validation" job SHOULD perform a real PostgreSQL upgrade/downgrade, or be renamed to describe what it checks.

### 7.6 Observability
- **FR-PRD-050 (MUST)** Every request MUST produce one structured access-log entry with:
  - `timestamp`;
  - `request_id`;
  - `company_id` (when resolved);
  - `user_id`;
  - method;
  - route template, not the raw path containing IDs;
  - status;
  - duration.
  No bodies, tokens or secrets may be logged (G-11, Constitution §22).
- **FR-PRD-051 (MUST)** Application logs MUST include `company_id` where a tenant context exists.
- **FR-PRD-052 (MUST)** Unhandled exceptions in staging/production MUST be captured with their stack trace, request ID, tenant and user. Captures MUST be routed to an error-tracking destination that is filtered for secrets and PII.
- **FR-PRD-053 (MUST)** Metrics MUST cover at least:
  - request rate, error rate and latency per route group;
  - DB pool saturation;
  - DB connections and size;
  - disk;
  - backup age;
  - scheduler job outcomes;
  - GL posting failures (Epic 8 deferral);
  - export count, duration and rejected-over-limit counts (Epic 11).
- **FR-PRD-054 (MUST)** Readiness MUST reflect the ability to serve: database reachable; schema at the expected revision; and, if enabled, storage reachable. Liveness MUST stay dependency-free (G-21).
- **FR-PRD-055 (MUST)** External uptime monitoring MUST probe the public frontend and API endpoints from outside the hosting network.

### 7.7 Epic 11 production safety (no contract changes)
- **FR-PRD-060 (MUST)** Every Epic 11 contract MUST remain byte-compatible:
  - report keys;
  - response schemas, including FR-RPT-152 per-currency shapes;
  - export formats and row caps (CSV 50,000 / XLSX 25,000);
  - audit-before-delivery;
  - saved-view semantics;
  - Customer 360 and Dashboard composition and authorization.
- **FR-PRD-061 (MUST)** Synchronous export and report paths MUST fit inside the timeouts of FR-PRD-021 at the cap sizes. They are measured on staging using the Epic 11 T214/T270 harnesses, and a breach blocks the gate.
- **FR-PRD-062 (MUST)** Export file contents, report rows and filter values containing PII MUST NOT appear in application logs. The audit log's `filter_scope` stays in the database audit trail only.
- **FR-PRD-063 (MUST)** The SC-03 isolation suite MUST include every Epic 11 endpoint family:
  - discovery;
  - execution;
  - export;
  - saved views;
  - dashboard;
  - Customer 360 (IDOR).
- **FR-PRD-064 (SHOULD)** Any copy of production data used outside production — for example a restore drill target — SHOULD be access-restricted and destroyed after use. Anonymization SHOULD be applied before any use beyond verification.

---

## 8. Non-Functional Requirements

| ID | Category | Requirement | Level |
|---|---|---|---|
| NFR-PRD-01 | Availability | **PROPOSED service objective (not an SLA)**: 99.5% monthly availability of the API and frontend.<br>• **Measurement:** external uptime probes (FR-PRD-055) at 1-minute intervals; a minute counts as down when both API readiness and the frontend fail.<br>• **Exclusions:** announced planned maintenance (permitted; window and notice defined in the plan), and failures of upstream providers outside the D-01 topology (recorded, not excluded silently).<br>• Feasibility and cost are verified in the plan. No external SLA is promised without owner approval. | MUST |
| NFR-PRD-02 | Recoverability | **PROPOSED**: RPO ≤ 1 hour (D-02) and RTO ≤ 4 hours (D-07), both proven by drill (SC-02). The rollback target for a bad release is defined in the plan and must fit inside the RTO. | MUST |
| NFR-PRD-03 | Security | TLS 1.2+ on every public endpoint, HTTP→HTTPS redirect, HSTS. No plaintext DB or storage traffic across hosts. | MUST |
| NFR-PRD-04 | Least privilege | Separate DB roles: app runtime (DML only), migrations (DDL), backup (read), read-only diagnostics. Least-privilege CI deploy credentials. | MUST |
| NFR-PRD-05 | Data protection | Backups, archives, exports at rest and logs are treated as sensitive. Retention is defined in D-03: operational backups 30 days; business/accounting records 7 years (planning value, legal confirmation OPEN); log retention set in the plan. Access is restricted and audited. | MUST |
| NFR-PRD-06 | Observability | Any user-reported failure is traceable end-to-end by `request_id` within the log retention window. | MUST |
| NFR-PRD-07 | Performance | Latency and throughput targets are set from the measured §14 baseline, not guessed. Regressions beyond the approved tolerance block release. | MUST |
| NFR-PRD-08 | Operability | A single operator can execute every runbook. No step requires undocumented knowledge. | MUST |
| NFR-PRD-09 | Simplicity | The smallest architecture that meets these NFRs for the SME target. Any added component (proxy, cache, queue) needs written evidence of need (Constitution §25, §26). | MUST |
| NFR-PRD-10 | Cost | Monthly infrastructure cost is estimated and recorded per environment for D-01. | SHOULD |

---

## 9. Security & Tenant Isolation

### 9.1 Transport, CORS, hosts, headers
- **SEC-01 (MUST)** HTTPS only, with automated certificate renewal. HSTS on API and frontend, and certificate expiry alerting.
- **SEC-02 (MUST)** In staging/production, CORS MUST be an explicit allow-list of the frontend origin(s) — no wildcard and no localhost. Credentials are allowed only for listed origins.
- **SEC-03 (MUST)** Trusted-host validation MUST reject requests whose `Host` is not configured.
- **SEC-04 (MUST)** The frontend MUST send:
  - a Content-Security-Policy, minimally restricting script sources and disallowing inline script except via nonce or hash;
  - `frame-ancestors 'none'`;
  - Referrer-Policy;
  - X-Content-Type-Options;
  - Permissions-Policy;
  - HSTS.
  This closes the ADR-0003 mitigation gap (G-10). Verified by header tests against the deployed staging frontend.
- **SEC-05 (MUST)** Per D-08 (APPROVED direction: keep the current token approach temporarily, plus a strict, tested CSP — **conditional on D-11**). Under any D-11 outcome the token-storage choice MUST be recorded in an ADR, with its residual risk stated: CSP reduces, but does not eliminate, the theft risk of a `localStorage` refresh token. The options were:
  - keep ADR-0003 (refresh token in `localStorage`) with SEC-04's CSP in place and recorded as the compensating control; or
  - adopt ADR-0003's documented upgrade path (HttpOnly Secure SameSite cookie plus CSRF protection) through a new ADR.
  The choice is recorded and its tests are listed.

### 9.2 Tenant isolation & RBAC verification (PostgreSQL)
- **SEC-10 (MUST)** A **PostgreSQL-backed** negative isolation suite MUST run in CI. It reuses the existing SQLite-based tests' scenarios where possible, and covers for two tenants and a user without membership:
  - read, list, update and delete by ID;
  - search and filters;
  - reports, exports and Customer 360;
  - saved views;
  - audit logs;
  - storage objects (if enabled);
  - platform-admin and support-access boundaries.
  It also covers (D-12, 2026-10-09):
  - company-context enforcement (a header or path for a company without membership);
  - RBAC (a member lacking the permission);
  - tenant-ID manipulation in path, query and body;
  - IDOR on every resource type above.
  Expected result: 404/403 with no data leakage, and no tenant ID enumeration (G-20). SQLite-only evidence is insufficient for this gate. **Any demonstrated cross-tenant leak is a production blocker**: launch is blocked until it is fixed and the suite passes.
- **SEC-11 (MUST)** The RBAC matrix (Epic 4 and Epic 11 T262) MUST pass against the staging deployment for a representative sample of role × endpoint × method, executed over real HTTP.
- **SEC-12 (DEFERRED — APPROVED by D-12)** Database-level row security (PostgreSQL RLS) stays a future hardening option. It is added to the plan only if the risk assessment, or a SEC-10 finding, shows a clear need.

### 9.3 Auth, sessions, abuse
- **SEC-20 (MUST)** Rate limiting MUST be consistent across processes and replicas, using a shared store or an edge/proxy limiter (G-05). It covers at least login, refresh, password reset, email verification and registration. Verified with ≥2 processes.
- **SEC-21 (MUST)** Session and token lifetimes, lockout, and password policy are confirmed against Epic 2 values in the production configuration, and recorded in the readiness report. No change unless evidenced.
- **SEC-22 (MUST)** The existing platform-owner bootstrap (S-14) MUST be covered by an operator runbook (#9). The run must be verified to leave no default credentials, and to record an audit entry for the bootstrap. Bootstrap variables MUST be removed from the runtime environment after use.
- **SEC-23 (SHOULD)** MFA readiness (Constitution §19) is preserved; implementing MFA is DEFERRED (§21).
- **SEC-24 (MUST — APPROVED 2026-10-09)** Tenant per-request authentication MUST reject an access token, on the next request, once its session has been revoked. This closes the ≤15-minute window (G-23).
  - **Revocation triggers:**
    - logout and "sign out all devices";
    - password reset and change;
    - account deactivation, suspension, lock and archive;
    - administrative session revocation;
    - any future security-sensitive credential change.
  - **Guarantee:** holds across every worker and instance, with no per-process state that can disagree.
  - **Failure mode:** fail closed. If the revocation state cannot be read, the request is rejected (401/503), never accepted.
  - **Mechanism:** compared in the plan (`clarifications.md` §3.2): session/version validation folded into the existing per-request user lookup, a user-level token-version epoch, or a revocation cache. A dedicated additional DB round-trip is not mandated; the latency impact (p50/p95) MUST be measured.
  - **Evidence:** real PostgreSQL integration tests with ≥2 worker processes — revoke on process A, then the token is rejected on process B — for every trigger, plus a fail-closed test.
- **SEC-25 (MUST)** Per D-11 = **B (APPROVED)**, the in-house authentication architecture is formally approved through Constitution amendments A-01…A-03 and ADR-0007, which record the rationale, controls, known limitations (ADR-0003 residual risk, HS256 shared-secret rotation, no MFA yet) and maintenance ownership.
  - No document may claim Better Auth is implemented.
  - The approval is conditional on SEC-24, SEC-04/05, SEC-20, SEC-26 and FR-PRD-032 passing.
  - If any of these cannot be met safely in the existing design, the evidence and the Option A trade-offs are re-presented to the owner. No auth migration happens without explicit approval.
- **SEC-26 (MUST)** No platform-level authority is reachable through a tenant-scoped token or session (Constitution §50; G-25).
  - The latent `super_admin` bypasses on the tenant path are removed, or proven unreachable.
  - A test asserts that a tenant token can never grant a platform bypass.
  - Platform-admin authority stays exclusively on the platform-admin session path.

### 9.4 Production configuration guardrails (startup MUST fail — APPROVED, D-09)
In `staging`/`production`, startup fails if any of the following holds:
- `DEBUG` is true;
- `LOG_LEVEL` is DEBUG;
- `SECRET_KEY` or `JWT_SECRET_KEY` is shorter than 32 characters or matches a known default or example value;
- `CORS_ORIGINS` contains `*` or `localhost`;
- storage credentials are default (`minioadmin`) or the storage endpoint is plain HTTP across hosts;
- `DATABASE_URL` has no TLS requirement when the database is on another host;
- an unknown `ENVIRONMENT`;
- the trusted-hosts list is empty;
- the email provider is unset while email flows are enabled (D-05).

Each rule has a test.

### 9.5 Scanning
- **SEC-30 (MUST)** Keep the existing dependency scans (pip-audit, npm audit, bandit; S-11).
- **SEC-31 (MUST)** Add a container-image vulnerability scan for both production images. Critical/High findings block deploy unless a waiver is recorded with an expiry.
- **SEC-32 (MUST)** Secret scanning on every PR (GitGuardian plus the existing diff check) stays required.
- **SEC-33 (SHOULD)** A scheduled weekly re-scan of `main` and deployed images SHOULD catch newly published advisories. The 2026-09-30 CI failures from newly published advisories show the need.

---

## 10. Deployment & Environment

- **DEP-01 (MUST)** The production topology MUST be decided and recorded (D-01) before planning. The rest of this specification is written to hold for any compliant option.
- **DEP-02 (MUST)** Topology constraints that hold for any D-01 option:
  - TLS-terminating entry point;
  - frontend and API reachable only via HTTPS;
  - database not publicly reachable (private network or allow-listed);
  - object storage private;
  - backups in a separate failure domain;
  - secrets from a manager.
- **DEP-03 (MUST)** Containers run as non-root, with read-only root filesystems where feasible, resource limits, restart policies and health checks wired to the platform.
- **DEP-04 (MUST)** Environment parity: staging uses the same images, PostgreSQL major version and configuration shape as production (FR-PRD-002).
- **DEP-05 (SHOULD)** Infrastructure SHOULD be reproducible from the repository (infrastructure-as-code or scripted provisioning) to the degree the D-01 option allows.
- **DEP-06 (MUST)** Any component not in Constitution §6 (for example Redis for SEC-20, a reverse proxy, an error tracker) requires a recorded justification. A technology-stack change requires an ADR and Constitution amendment (Constitution §6 RULE, §44 #7).

---

## 11. Database / Migration / Backup / Restore

- **DB-01** Single-run migration step (FR-PRD-005); startup schema-revision check.
- **DB-02** Backward-compatible migrations (FR-PRD-023).
  - **Code rollback** = redeploy release N-1 against schema N, the default path.
  - **Database rollback** = an Alembic downgrade or a restore. It is used only when the release's migration is reversible without data loss, needs Release Approver authorization, and requires a fresh backup first.
  - A migration that drops or rewrites data MUST NOT be "rolled back" by downgrade. Recovery is forward-fix or point-in-time restore.
- **DB-03** Pre-migration backup or snapshot MUST be taken automatically before every production migration, and verified as existing before the migration runs.
- **DB-04** Backup schedule, encryption, off-site copy, retention (D-02/D-03), restore drill (FR-PRD-025), and alerting (FR-PRD-026).
- **DB-05** Point-in-time recovery capability, if D-02's RPO requires it (for example an RPO under 24h implies continuous WAL archiving or a managed equivalent).
- **DB-06 (DEFERRED)** Partitioning `accounting_journal_lines` by fiscal year (deferred by Epic 8). Trigger: measured GL query latency over the §14 tolerance at the observed volume. The Epic 8 measurement at 500K lines on PostgreSQL showed no need.
- **DB-07** Migration-failure recovery runbook: what to do when a migration fails mid-way (transactional DDL rollback, partial non-transactional steps), and how to resume or restore.

---

## 12. Observability & Incident Response

### 12.1 Logs
FR-PRD-050, FR-PRD-051 and FR-PRD-062. Logs are centralized, retained per D-03, access-restricted, and PII/secret-filtered. Existing filtering is covered by `test_sensitive_log.py`; it is extended to access logs.

### 12.2 Metrics & errors
FR-PRD-052 and FR-PRD-053. Dashboards are recorded for API, database, scheduler, backups and Epic 11 exports.

### 12.3 Alerts (thresholds from the §14 baseline; owner = Operator)

| Alert | Condition (initial; tuned after baseline) | Runbook |
|---|---|---|
| API down | External probe fails for 2 consecutive intervals | Incident |
| Elevated 5xx | 5xx rate above the baseline-derived threshold for 5 min | Incident |
| Latency regression | p95 above the baseline-derived threshold for 10 min | Incident |
| DB unreachable / pool exhausted | Readiness fails, or pool waits above threshold | Incident |
| Disk / DB size | Above 80% of capacity | Capacity |
| Backup missing / failed | Age > schedule + grace, or job failed | Restore/Backup |
| Scheduler job failed | Any FAILED job outcome | Incident |
| GL posting failures | Any failed posting in the interval (Epic 8) | Incident |
| Certificate expiry | Under 14 days | Deploy |

### 12.4 Runbooks (MUST, version-controlled, each executed once — SC-11)
1. Deploy (staging → production promotion).
2. Code rollback.
3. Database rollback / restore (including point-in-time recovery).
4. Backup verification and restore drill.
5. Incident response: triage, `request_id` tracing, communication, post-incident review.
6. Secret rotation (FR-PRD-013).
7. Migration failure recovery (DB-07).
8. Tenant data request: export, or deletion after the retention policy (references existing company soft-delete retention, Epic 3).
9. Platform-owner bootstrap and access recovery (SEC-22).

---

## 13. CI/CD & Branch Protection

- **CI-01 (MUST)** Branch protection is enforced as FR-PRD-040, and evidenced by readback plus a refused failing merge.
- **CI-02 (MUST)** Per D-06, the approval requirement is reconciled with a sole owner: either a documented bypass policy (who, when, logged) or a second reviewer. The bypass is never used to skip failing required checks.
- **CI-03 (MUST)** CD pipeline per FR-PRD-041 and FR-PRD-042, with the evidence artifact retained per release.
- **CI-04 (MUST)** CI weaknesses from G-14 are documented. Only those required by this epic's gates are fixed here: required checks, the deploy pipeline, the image scan and migration verification. Others are tracked (FR-PRD-043/044) and not silently changed.
- **CI-05 (SHOULD)** Release versioning (semantic tags) and generated release notes from conventional commits.

---

## 14. Performance / Capacity

- **PERF-01 (MUST)** Define an **SME reference workload** (D-10) before measuring:
  - tenants per deployment;
  - concurrent users per tenant;
  - document volumes (invoices, GL lines, contracts) per tenant-year;
  - export frequency.
- **PERF-02 (MUST)** Measure on staging (production-like) and record:
  - p50/p95/p99 latency and error rate for the critical flows — login/refresh, invoice create and issue, GL posting, AR aging, dashboard, a paginated Epic 11 report, and a CSV export at the 50,000-row cap;
  - DB CPU, connections and pool saturation;
  - memory per process.
- **PERF-03 (MUST)** Targets and alert thresholds are set from PERF-02 with approved headroom, and documented as the release-regression baseline (NFR-PRD-07). Existing evidence (S-13) is reused where the workload matches.
  - Until the owner supplies the D-10 workload, these stay **PROVISIONAL**: the latency targets per flow, the alert thresholds for latency, 5xx and pool saturation, the capacity statement (PERF-04), the DB connection budget (FR-PRD-020), and the export timeout sizing (FR-PRD-061).
  - Benchmark method:
    1. measure on staging with a synthetic data generator, at 1×, 2× and 5× of the supplied (or, until then, a clearly labelled assumed) workload;
    2. record p50/p95/p99 latency, errors and resource saturation per step;
    3. derive thresholds from the measured value at 1× plus approved headroom.
- **PERF-04 (MUST)** Capacity statement: the maximum reference workload one deployment of the D-01 topology sustains within targets, and the first saturating resource.
- **PERF-05 (DEFERRED)** Horizontal scaling, caching layers, read replicas and async export queues. Trigger: PERF-04 shows saturation below the reference workload.

---

## 15. Rollback & Recovery

| Scenario | Primary recovery | Database action | Authorization |
|---|---|---|---|
| Bad code, compatible schema | Redeploy previous image digests | None | Operator |
| Bad code plus reversible additive migration | Redeploy N-1 (schema N stays, per FR-PRD-023) | Optional downgrade later | Release Approver |
| Destructive or irreversible migration defect | Forward-fix release | Point-in-time restore only if data is corrupted | Release Approver + fresh backup |
| Data corruption or deletion | Point-in-time restore to an isolated database, verify, then cut over | Restore | Release Approver |
| Infrastructure loss | Re-provision from IaC/runbook, restore latest backup | Restore | Operator |

- **RB-01 (MUST)** The rollback target time (D-02) is proven in staging (SC-05).
- **RB-02 (MUST)** Rollback never bypasses audit. Audit logs written by the bad release are preserved; they are append-only (Constitution §35).

---

## 16. Testing & Verification

### 16.1 Automated (CI)
- Guardrail tests (§9.4).
- `.env.example` completeness test (FR-PRD-012).
- Migration revision check at startup (FR-PRD-005).
- Scheduler exactly-once concurrency test (FR-PRD-006).
- Cross-process rate-limit test (SEC-20).
- PostgreSQL isolation suite (SEC-10).
- Access-log field and PII-filter tests (FR-PRD-050/062).
- Readiness semantics (FR-PRD-054).
- Storage privacy and cross-tenant object tests (FR-PRD-031, if enabled).
- Header tests for the frontend (SEC-04).

### 16.2 Staging (production-like)
- Deploy and rollback rehearsal (SC-01/05).
- Restore drill (SC-02).
- Performance baseline (SC-10).
- Induced-failure alerting (SC-07).
- RBAC sample over HTTP (SEC-11).
- Secret-rotation rehearsal (FR-PRD-013).
- Epic 11 export-at-cap timing (FR-PRD-061).

### 16.3 Post-deploy smoke (automated, staging and production)
Health/ready → login → company switch → create and read one non-financial record in a dedicated smoke tenant → one report page → one small export → password-reset request accepted (if enabled) → logout. The smoke tenant is isolated, marked as synthetic, and excluded from business metrics.

---

## 17. Readiness Gate / Acceptance Scenarios

### 17.1 Production-Readiness Gate (all MUST items, each with an evidence artifact)
- [ ] D-01 … D-12 decided and recorded (ADRs where architecture-significant); Constitution 2.0.0 amendments (`amendments-proposed.md`) approved and applied — applied in the governance PR; tick on merge.
- [ ] Professional confirmation of the business-record retention period recorded (D-03).
- [ ] D-10 workload figures recorded and the provisional thresholds (PERF-03) finalized.
- [ ] FR-PRD-001…064 (MUST) satisfied, with evidence links.
- [ ] SEC-01…32 (MUST) satisfied, with evidence links.
- [ ] SC-01…SC-11 met in staging; SC-01, SC-08 and SC-09 also met in production.
- [ ] Runbooks executed (SC-11).
- [ ] No unwaived Critical/High vulnerabilities; waivers have expiry dates.
- [ ] Readiness report signed by the Release Approver.

### 17.2 Acceptance scenarios
1. **Given** a release with a migration, **when** it is deployed with 2+ app processes, **then** the migration runs exactly once before traffic, and every process reports the expected schema revision.
2. **Given** an app process started against a database one revision behind, **when** it starts, **then** readiness stays failed and the log names both revisions.
3. **Given** 3 app processes, **when** the recurring-journal schedule fires, **then** exactly one execution occurs, with one GL posting per due template.
4. **Given** production settings with `DEBUG=true` (or default storage keys, wildcard CORS, a short secret), **when** the app starts, **then** it exits non-zero before serving.
5. **Given** tenant A's user, **when** they request tenant B's invoice, report export, Customer 360, saved view or stored file by ID, **then** they receive 404/403 and no B data. Verified on PostgreSQL.
6. **Given** a failing required check, **when** a PR merge into `main` is attempted, **then** GitHub refuses it.
7. **Given** a production-like backup, **when** the restore drill runs, **then** it meets the RPO and RTO, and integrity checks pass.
8. **Given** release N fails its smoke test after deploy, **when** code rollback runs, **then** N-1 serves within the rollback target, with schema N intact and no data loss.
9. **Given** the API is stopped, **when** the external probe runs, **then** an alert reaches the Operator within the detection window, and links to the incident runbook.
10. **Given** 2 app processes, **when** login is attempted beyond the limit across both, **then** the shared limit is enforced.
11. **Given** a request that fails with a 500, **when** the Operator searches by the `request_id` returned in the response header, **then** they find the access log, the error capture with stack trace, and the tenant/user context — and no secrets.
12. **Given** the 50,000-row CSV export, **when** it runs on staging, **then** it completes within the configured timeouts, writes its audit row first, and stays within the measured memory envelope.

### 17.3 Edge cases
- A migration fails half-way, especially non-transactional operations such as concurrent index creation.
- A backup job succeeds but produces an unrestorable file. The drill must catch this.
- The scheduler process dies mid-job; the restart must not duplicate the job.
- Clock skew between processes. Lock leases must tolerate it.
- Certificate renewal fails.
- The storage provider is unavailable: uploads fail gracefully and readiness reflects it.
- The email provider is down: the reset request is still accepted, delivery is retried or logged, and there is no token leak.
- A secret is rotated during active sessions (FR-PRD-013 behavior).

---

## 18. Dependencies / Sequencing

1. **Amendment package approved and applied** (`amendments-proposed.md`: Constitution 2.0.0 and ADR-0007/0008/0009, in the governance PR). D-11 is decided (B). The plan is blocked only until that PR merges. D-10 numbers and legal retention confirmation may follow the plan, but are required before the final gate.
2. Environment and configuration foundations: FR-PRD-001/010/012, §9.4 guardrails, single-run migration step, scheduler exactly-once.
3. Storage and email decisions implemented (FR-PRD-030…032), and frontend headers (SEC-04/05).
4. Observability: logs, metrics, errors, readiness, uptime.
5. CI/CD: branch protection, CD pipeline, image scan.
6. Staging provisioned. Then the PostgreSQL isolation suite, the performance baseline and the restore drill.
7. Runbooks written and rehearsed.
8. Production provisioned, first deploy, smoke test, and the readiness gate.

External dependencies, decided under D-01/D-04/D-05:
- hosting provider(s);
- domain and DNS;
- certificate authority;
- object storage provider;
- email provider;
- error tracking and uptime services.

---

## 19. Risks / Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Deploying before restore is proven | Unrecoverable data loss | The gate requires the SC-02 drill before the first production tenant |
| Duplicate scheduled jobs (G-04) | Duplicate GL postings | FR-PRD-006 concurrency proof before multi-process deploy |
| Wiring storage while keeping public URLs | Tenant file exposure | FR-PRD-031: private-by-default with signed or authorized access |
| Sole-operator bus factor | Prolonged outage | Single-operator runbooks (NFR-PRD-08); credential recovery runbook (#9) |
| New advisories breaking CI unexpectedly | Blocked releases | Scheduled re-scan (SEC-33); waiver process with expiry |
| Over-engineering for the SME target | Cost and complexity | NFR-PRD-09, plus a justification for each added component |
| Long CI cycle (~2h50m) slowing hotfixes | Slow recovery | FR-PRD-043; code rollback does not require a full CI rerun of the old SHA (artifact already validated) |
| Staging data leakage | Privacy breach | FR-PRD-064 restrictions and destruction after drills |

---

## 20. Open Questions / Decisions

Status as of the 2026-10-09 clarification. Full matrix and evidence: `clarifications.md`.

| ID | Decision | Status | Resolution / remaining input |
|---|---|---|---|
| D-01 | Production topology (G-01) | **APPROVED** | Vercel frontend + Dockerized FastAPI on a VPS + managed PostgreSQL. **OPEN:** the database provider and region (plan compares backup/PITR, TLS, latency, cost, ops burden). Constitution §6.6 amendment and a superseding ADR are pending. |
| D-02 | RPO | **PROPOSED** | ≤ 1 hour, subject to the selected database design meeting it |
| D-03 | Retention | **APPROVED (split)** | Operational backups 30 days; business/accounting records 7 years as a **planning assumption**. **OPEN:** professional confirmation before the final gate. |
| D-04 | Object storage (G-08) | **APPROVED** | Private, tenant-scoped storage with signed URLs and an authorization check; SVG removed; fake and silent fallbacks fixed. **OPEN:** provider. |
| D-05 | Transactional email (G-09) | **APPROVED** | A real provider; fail closed or explicitly disable when not configured. **OPEN:** provider and sender domain. |
| D-06 | Single-maintainer governance (G-19) | **APPROVED** | Constitution 2.0.0 §28/§29/§43/§44 and ADR-0009 (governance PR) |
| D-07 | Availability / RTO | **PROPOSED** | 99.5% monthly objective, RTO 4 h, planned maintenance permitted; not an SLA |
| D-08 | CSP / token storage (G-10) | **APPROVED direction** | Keep tokens temporarily, plus a strict tested CSP — conditional on D-11 |
| D-09 | Runtime safety (G-03, G-04, G-06) | **APPROVED** | Migration release job; dedicated scheduler with advisory lock; atomic journal posting; fail-closed guardrails |
| D-10 | SME workload | **OPEN** | Owner-supplied numbers; thresholds provisional (PERF-03) |
| D-11 | Better Auth vs in-house auth (G-22) | **APPROVED — B** | Documented in ADR-0007 and Constitution 2.0.0 §6.3/§15/§16 (governance PR). Conditional on SEC-24/04/05/20/26 and FR-PRD-032. |
| D-12 | Database-level row security | **APPROVED — defer** | PostgreSQL negative suite (SEC-10) MUST pass; any leak blocks production |

---

## 21. Deferred / Future Work

| Item | Trigger to revisit |
|---|---|
| Row-level security in the database (SEC-12) | An isolation defect found by SEC-10, or a compliance requirement |
| Journal-lines partitioning (DB-06) | Measured GL latency beyond tolerance |
| Horizontal scaling, caching, read replicas, async export queue (PERF-05) | PERF-04 saturation below the reference workload |
| MFA (SEC-23) | Customer or security requirement |
| HttpOnly cookie sessions (D-08 option) | Security audit or an XSS finding |
| Multi-region and high-availability database | Availability target beyond the D-01 topology |
| Compliance certification | Commercial requirement |
| AI layer | Separate future epic |

---

## 22. Traceability to Constitution and Epics 0–11

| Source | Requirement(s) here |
|---|---|
| Constitution §6.6 Deployment; §44 #7 | DEP-01, DEP-06, D-01 (inconsistency flagged, not resolved here) |
| §18 Migration Policy (downgrade, staging test, expand/contract) | FR-PRD-005, 022, 023; DB-01, 02, 07 |
| §19 Security; §16 Auth/Authorization | §9; SEC-01…33 |
| §6.3, §15 step 2, §16, §39 (v2.0.0: in-house auth, ADR-0007; foundational ADR list) | G-22, G-24; SEC-25; D-11 = B (amended) |
| §50 (no platform authority via a tenant session) | G-25; SEC-26 |
| §20 Configuration | FR-PRD-010…013; §9.4 |
| §21 Error Handling; §22 Logging & Observability | FR-PRD-050…055 |
| §25 Performance; §26 Dependencies | §14; NFR-PRD-09; FR-PRD-014 |
| §27 Docker | FR-PRD-004; DEP-03 |
| §28 Git Workflow; §29/§43 Review & DoD | CI-01, CI-02; D-06 |
| §33 File Storage | FR-PRD-030, 031 |
| §34 Backup & Recovery | FR-PRD-024…026; DB-03…05; SC-02 |
| §35 Audit Trail | RB-02; FR-PRD-062 |
| §44 #11 tenant isolation | SEC-10, 11; SC-03 |
| Epic 2 (auth, ADR-0001/0002/0003) | SEC-05, 20, 21, 24, 25, 26; D-08, D-11 |
| Epic 3 (companies, storage, retention) | FR-PRD-030, 031; runbook #8 |
| Epic 8 ("Future Epic 12 — Deployment": backups, partitioning, GL monitoring) | FR-PRD-024, 053; DB-06; D-03 |
| Epic 9A (platform admin, health, bootstrap) | SEC-22; FR-PRD-054 |
| Epic 11 (exports, audit, saved views, C360, dashboard, T214/T270 harnesses) | FR-PRD-060…063; PERF-02/03 |
| Earlier specs that labelled Reports or Inventory as "Epic 12" (Epic 3/5/7 roadmaps) | Superseded numbering: Reports shipped as Epic 11. No conflict with this epic's scope. |

---

## Findings / Decisions Requiring Approval

Superseded by the 2026-10-09 clarification: see `clarifications.md` for the decision matrix, the Better Auth evidence and options, the revalidated gap classification (G-01…G-24), production blockers, and the Constitution/ADR amendment package awaiting approval.
