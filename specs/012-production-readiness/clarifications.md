# Epic 12 — Deployment / Production Readiness: Clarifications

**Spec**: [spec.md](spec.md) · **Amendments**: [amendments-proposed.md](amendments-proposed.md) · **Branch**: `012-production-readiness` · **Sessions**: 2026-10-09 (round 1: D-01…D-10; round 2: D-11, SEC-24, D-12, amendments in principle)
**Scope of this document**: clarification only. No code, packages, auth changes, migrations, deployments or plan.
**Evidence base**: repository at `main` @ `712a668` (branch `012-production-readiness` has no code changes), Constitution v1.2.1, `history/adr/0001–0006`, `docs-project-context/{DECISIONS,DEPLOYMENT_GUIDE}.md`, Epic 9A plan §3.1, Epic 11 final artifacts.

**Labels used in this document**
- Decision status: **APPROVED** (owner-approved direction), **PROPOSED** (an objective awaiting confirmation or a feasibility check), **OPEN** (input still to be supplied), **PENDING** (a choice not yet made).
- Source of a claim: **VERIFIED** (checked in the repository, with a path) or **ASSUMPTION** (needs verification in the plan).

---

## 1. Decision matrix

| ID | Topic | Status | Resolution | Still needed |
|---|---|---|---|---|
| D-01 | Production topology | APPROVED | Vercel frontend + Dockerized FastAPI on a VPS + managed PostgreSQL | Provider and region (plan comparison). Approval of the §6.6 amendment and ADR-0008 (§5). |
| D-02 | RPO | PROPOSED | ≤ 1 h of data loss | Proof that the chosen database design meets it (plan) |
| D-03 | Retention | APPROVED (split) | Operational backups 30 days; business/accounting records 7 years as a **planning assumption** (not verified law) | Professional confirmation before the **final gate**. The archive design comes in the plan. |
| D-04 | Object storage | APPROVED | Private, tenant-scoped storage; short-lived signed URLs plus an authorization check; SVG removed (unless sanitization is justified and tested); fake and silent fallbacks fixed | S3-compatible provider (plan comparison) |
| D-05 | Transactional email | APPROVED | A real provider for verification and reset; fail closed or explicitly disable when unconfigured; never fake delivery | Provider and sender domain (plan comparison) |
| D-06 | Governance | APPROVED | Single-maintainer workflow (ADR-0009) | — |
| D-07 | Availability / RTO | PROPOSED | 99.5% monthly objective (not an SLA), RTO 4 h, planned maintenance permitted | Feasibility and cost (plan) |
| D-08 | CSP / token storage | APPROVED direction | Keep the current tokens temporarily, plus a strict, tested CSP. D-11 = B, so this holds. | CSP compatibility analysis (plan) |
| D-09 | Runtime safety | APPROVED | Migration release job; dedicated scheduler with advisory lock; atomic journal posting with concurrency proof; fail-closed guardrails | — |
| D-10 | SME workload | OPEN | No numbers invented; the plan defines a baseline, load tests and provisional thresholds | Expected tenants, users per company, concurrent users, invoices and exports, recorded before **capacity sign-off** |
| D-11 | Better Auth vs in-house auth | **APPROVED — B** | In-house JWT formally approved. Evidence review (§3.1): no critical gap that cannot be fixed within the design. | Documented in ADR-0007 (governance PR); conditions SEC-24/04/05/20/26 and FR-PRD-032 |
| SEC-24 | Immediate session revocation | **APPROVED — MUST** | Rejection on the next request on every instance; fail closed; real PostgreSQL multi-process proof | Mechanism choice in the plan (§3.2) |
| D-12 | Database-level row security | **APPROVED — defer** | Conditional on the SEC-10 PostgreSQL negative suite passing; any leak is a production blocker | — |
| A-01…A-13 | Constitution/ADR amendments | **APPROVED and APPLIED** (governance PR) | Constitution **2.0.0**; ADR-0007/0008/0009 | Merge of the PR |

---

## 2. Better Auth — what the governing documents require (VERIFIED)

| Constitution section | Text |
|---|---|
| §6.3 Authentication | "Auth Framework \| Better Auth" |
| §15 API Design, step 2 | "Authenticate the request (via Better Auth middleware)" |
| §16 Auth & Authorization | "**Authentication MUST use Better Auth.**" It also requires: RBAC with permissions; audit logging of auth events; "server-side session management"; secure cookie or token strategy; "sessions are scoped to a specific company"; bcrypt/Argon2; MFA readiness (§19). |
| §39 ADRs | Mandatory initial ADR-002 "Why Better Auth", stored in `history/adr/` |
| §6 RULE, §44 #7 | Changing the stack requires an ADR plus a Constitution amendment |

---

## 3. Better Auth — what the repository implements (VERIFIED)

| Area | Implementation | Path |
|---|---|---|
| Dependency | No `better-auth` package in the frontend or backend | `frontend/package.json`, `backend/pyproject.toml` |
| Placeholder | Interfaces say "Better Auth (or any future provider) must plug into these abstractions" | `backend/core/auth/interfaces.py` |
| Access token | PyJWT HS256, 15 min default, claims `sub`, `email`, `sid`, `jti`, `iss`, `aud` | `backend/modules/auth/services/jwt_service.py` |
| Refresh token | Opaque, SHA-256 hashed, rotated on use, replay detection | `backend/modules/auth/services/token_service.py`; `tests/security/test_replay_attack.py` |
| Sessions | `sessions` table: user-scoped, **no `company_id`**, `is_revoked` | `backend/modules/auth/models/session.py` |
| Per-request auth | Decodes JWT, checks lock/inactive/deleted; **does not check `Session.is_revoked`**; `roles=[]` | `backend/core/auth/dependencies.py:44-115` |
| Tenant scope | Per request, through company membership and permission checks (Epic 4), not through the session | `tests/security/test_company_membership_enforcement.py`; Epic 11 T261–T263 |
| Passwords | Argon2id, lockout, password history, min/max length | `backend/modules/auth/services/password_service.py`; `tests/security/test_{argon2_params,account_lockout,password_history}.py` |
| Endpoints | `/api/v1/auth/{login,refresh,logout,me,forgot-password,reset-password,change-password,verify-email}` | `backend/modules/auth/router.py` |
| Email | Stub; tokens logged at DEBUG only | `backend/modules/auth/services/email_service.py` |
| Audit | Auth audit events | `backend/modules/auth/services/audit_service.py`; `tests/security/test_audit_log_completeness.py` |
| Platform admin | Separate `PlatformSession`/refresh tokens (Epic 9A) | `backend/modules/platform_admin/*`; `frontend/src/lib/platform-auth/*` |
| Frontend client | Access token in memory; refresh token in `localStorage` (ADR-0003) | `frontend/src/lib/auth/{client,tokenStorage,tenantAuthStrategy}.ts`, `frontend/src/contexts/AuthContext.tsx` |
| Records | ADR-0001 documents the JWT design but **does not mention Better Auth or the Constitution**. The deviation is acknowledged only in Epic 9A *plan* §3.1, which cannot override the Constitution (§4). | `history/adr/0001-*.md`; `specs/009a-platform-admin/plan.md:113-122` |

**§16 requirements met:**
- RBAC with permissions;
- auth audit;
- Argon2;
- server-side session records (revocable refresh);
- token strategy (ADR-0003).

**§16 requirements not met, or met only partly:**
- the Better Auth mandate;
- "sessions scoped to a company" — sessions are user-scoped; tenant scope is enforced per request;
- immediate session revocation for access tokens (G-23);
- MFA (readiness only);
- the CSP mitigation for ADR-0003 (G-10).

### Options

**A — Adopt Better Auth (migration-safe)**

Better Auth is a TypeScript framework. In this stack it would run in a JS runtime (the Next.js server, or a new Node service) with its own tables in PostgreSQL, and FastAPI would have to trust its sessions or tokens. Whether Better Auth's mechanism for this (for example a JWT/JWKS plugin) fits FastAPI is an **ASSUMPTION** to be verified in the plan.

Work this option requires:
- migrate users, credentials and accounts;
- support Argon2id hash compatibility through a custom verify/hash hook (**ASSUMPTION**, to verify), or force password resets;
- invalidate every session at cutover;
- reconcile platform-admin auth;
- re-implement or configure lockout, password history, replay detection and audit;
- keep the `/api/v1/auth/*` contracts, or version them;
- rewrite most of the auth security test suite;
- give Vercel or a Node service database access, which changes the D-01 topology;
- stage the rollout, with a rollback that restores the old tables and sessions.

| Pros | Cons |
|---|---|
| Matches the Constitution as written; library-maintained features (MFA, OAuth) later | Highest risk and effort; touches every authenticated flow and tenant-isolation path just before the first production launch; adds a second backend runtime with DB credentials |

**B — Formally approve the in-house design (recommended)**

Work this option requires:
- Constitution amendments A-01…A-03 (§5) and **ADR-0007** "In-house JWT + opaque rotating refresh-token authentication", which supersedes the Better Auth mandate and records the rationale, the controls (§3 above), the limitations and maintenance ownership (the owner);
- closing the known gaps inside Epic 12: SEC-24 session revocation (G-23), SEC-04 CSP (G-10), email (G-09), the shared rate limit (G-05);
- keeping MFA readiness;
- never describing the system as Better Auth.

| Pros | Cons |
|---|---|
| No migration risk; preserves ~all existing auth and isolation tests (S-07, S-08) and API contracts; smallest change before launch | The team owns auth security maintenance; MFA/OAuth must be built later; needs a disciplined dependency (PyJWT) and security review cadence |

### 3.1 Security review of the in-house implementation (evidence for D-11 = B)

**Controls verified in the repository:**
- **JWT validation** pins the algorithm and verifies issuer and audience (`modules/auth/services/jwt_service.py:107-109`). The secret length must be ≥32, enforced at startup (`main.py` `_validate_auth_configuration`).
- **Refresh tokens** are opaque, SHA-256 hashed and rotated. Reuse revokes every token of the user (`token_service.py:138-145`).
- **Reset and verification tokens** are hashed, unique, expiring and single-use (`models/password_reset_token.py:36-58`, `email_verification_token.py:34-56`, `token_service.py` "already been used").
- **Password reset and change** revoke all refresh tokens and sessions (`auth_service.py:449-450`, `521-522`).
- **Member deactivate, suspend, lock and archive** revoke sessions (`users_roles/services/member_service.py:960, 1100, 1170, 1244`).
- **Company suspension** is enforced per request (`users_roles/dependencies.py:211`).
- **Argon2id, lockout and password history** are in place.
- **Per-endpoint rate limits** exist (`auth/router.py:117-415`).
- **Auth events are audited.**
- **Platform-admin sessions** are separate and checked for revocation per request (`platform_admin/dependencies.py:122`).
- **Tests:** 77 unit, 56 integration and 31 security tests for auth, plus 70 cross-tenant/IDOR test files (S-07, S-08).

**Gaps found.** Each one is fixable inside the existing design. Better Auth would not remove any of them by itself; it would add migration risk instead.

| Gap | Severity | Fix in the existing design | Would Option A remove it by itself? |
|---|---|---|---|
| G-23: access token valid ≤15 min after revocation | Medium | SEC-24 | No (needs equivalent server checks) |
| G-10: no CSP while the refresh token is in `localStorage` | High (production) | SEC-04/05; residual risk recorded | Partly (cookie mode), but CSP is still required |
| G-09: email stub | High (production) | FR-PRD-032 | No (still needs a provider) |
| G-05: per-process rate limits | Medium | SEC-20 | No |
| G-25: latent `super_admin` bypass on `CurrentUser.roles` (always `[]`) | Low (latent) | SEC-26 | N/A |
| HS256 shared secret | Low (single issuer and verifier) | Rotation runbook (FR-PRD runbooks) | N/A |
| No MFA | Deferred (§19 readiness) | Later epic | Library support, but still requires a migration |

**Review verdict:** the condition in the owner's decision is met — no critical gap needs Option A. B proceeds on condition that the fixes above pass. If any fix proves unsafe in the existing design, Option A is re-presented with that evidence.

### 3.2 SEC-24 mechanism comparison (choice made in the plan)

Fact: `get_current_user` **already performs one primary-key user lookup per request** (`core/auth/dependencies.py:83-84`).

| Mechanism | Guarantee | Latency | Cross-instance | Failure mode | Notes |
|---|---|---|---|---|---|
| M1: check session state by `sid`, **folded into the existing user query** (join on primary keys) | Exact, per session | No extra round-trip; one extra indexed PK join | Yes (shared database) | DB unavailable → request fails (fail closed) | Same pattern as platform admin (`platform_admin/dependencies.py:122`) |
| M2: user-level `tokens_valid_after` / token-version epoch compared with `iat` | Covers all-session triggers (password reset, disable); **not single-session logout** unless combined with M1 | Zero extra (same user row) | Yes | Same as M1 | Needs a schema column; a good complement to M1 |
| M3: revocation cache (shared store, e.g. Redis) | Exact if the cache is consistent | Lower DB load | Only with a shared store; **an in-process cache fails this test** | Must fail closed if the store is unavailable, which adds an outage mode | Adds a component (NFR-PRD-09); justified only by measured DB pressure |
| M4: shorter access-token lifetime only | Not immediate | — | — | — | Rejected: does not meet "immediately" |

**Preliminary recommendation for the plan:** M1, possibly with M2. Measure the p50/p95 latency delta under the PERF-02 benchmark, and adopt M3 only with measured evidence.

**Proof required:** real PostgreSQL integration tests across two worker processes, covering every trigger and a fail-closed case.

### 3.3 Original recommendation (round 1)

**Recommendation: B.** The repository evidence shows a mature, heavily tested in-house implementation. The real production risks (G-10, G-23, G-09, G-05) are fixable within it, while A would re-open authentication and tenant isolation at the riskiest moment. CSP is required under both options and does not by itself remove the `localStorage` refresh-token risk; the residual risk is recorded in ADR-0007 (B) or removed by cookie-based sessions (A or a later ADR).

---

## 4. Gap revalidation (G-01…G-24)

All 24 gaps were re-checked against the repository. The 14 existing controls S-01…S-14 stay as baseline and will not be rebuilt.

| Gap | Class | Production blocker | Depends on | Status |
|---|---|---|---|---|
| G-01 Topology conflict | MUST | Yes | D-01, A-04/A-05 | Direction approved; amendment pending |
| G-02 No staging/production environment | MUST | Yes | D-01 | Open |
| G-03 Migrations in every worker | MUST | Yes | D-09 | Rule approved |
| G-04 Scheduler in every process; duplicate GL risk | MUST | Yes | D-09 | Rule approved |
| G-05 In-memory rate limit | MUST | No | D-01 | Open |
| G-06 No config guardrails | MUST | Yes | D-09, D-05 | Rule approved |
| G-07 `.env.example` incomplete | MUST | No | — | Open |
| G-08 Storage unwired/public; SVG; fake export URL | MUST | Yes | D-04 | Direction approved |
| G-09 Email stub | MUST | Yes | D-05 | Direction approved |
| G-10 No frontend CSP | MUST | Yes | D-08, D-11 | Direction approved, conditional |
| G-11 No `company_id` / access log | MUST | No | D-03 (log retention) | Open |
| G-12 No monitoring/alerts | MUST | Yes | D-01, D-02, D-07 | Open |
| G-13 No backup/restore; RPO/RTO | MUST | Yes | D-01, D-02, D-03, D-07 | Values proposed |
| G-14 CI not enforced; no CD | MUST (checks, CD, image scan) + SHOULD (speed, stale trigger, wall-clock test) | Yes (MUST part) | D-06, D-01 | Open |
| G-15 No timeouts | MUST | No | D-01, D-10 | Open |
| G-16 Dev compose unsafe | MUST (production does not reuse it) + SHOULD (pin MinIO) | No | D-01 | Open |
| G-17 Two lock files | SHOULD | No | — | Open |
| G-18 No runbooks | MUST | Yes | D-01, D-02, D-07 | Open |
| G-19 Governance drift | MUST (amendment) | Blocks the plan | D-06 | Text pending |
| G-20 App-level isolation; SQLite tests | MUST (PostgreSQL negative suite) / DEFERRED (RLS, D-12) | **Yes, if any leak is found** | D-12 | Approved |
| G-21 Readiness checks only the DB | MUST | No | D-04, D-09 | Open |
| G-22 Unratified Better Auth deviation (**reclassified** from "accepted") | MUST (amendment + conformance) | **Yes** (blocks the plan until applied) | A-01…A-03, ADR-0007 | D-11 = B approved |
| G-23 Access token valid after session revocation (new) | **MUST (SEC-24)** | Yes (D-11 condition) | — | Approved |
| G-25 Latent `super_admin` bypass on the tenant path (new) | MUST (SEC-26) | No (latent, fails closed) | — | New |
| G-24 Two ADR series; mandatory initial ADRs missing (new) | MUST (amendment A-10/A-11) | Blocks the plan | — | Text pending |

**Production blockers:**
- G-01, G-02, G-03, G-04, G-06, G-08, G-09, G-10, G-12, G-13, G-14 (MUST part), G-18, G-22, G-23;
- plus any cross-tenant leak found by SEC-10 (G-20).

---

## 5. Constitution / ADR amendment package (**approved in principle; exact diffs under review; not applied**)

**Superseded by [`amendments-proposed.md`](amendments-proposed.md).** That file holds the exact diffs, the verification and the summary. The table below is the round-1 intent, kept for traceability.

Version correction: the round-1 draft said "1.2.1 → 1.3.0 (MINOR)". This was **wrong**. §45.3 classifies a redefinition of the authentication mandate and the removal of governance rules as **MAJOR**, so the version becomes **2.0.0**. Per §39, `history/adr/` is canonical; new ADRs are numbered from 0007.

| # | Section | Current | Proposed (if approved) |
|---|---|---|---|
| A-01 | §6.3 | "Auth Framework \| Better Auth" | **If D-11 = B:** "Authentication \| In-house JWT access tokens + opaque rotating refresh tokens (ADR-0007)". **If A:** unchanged. |
| A-02 | §15 step 2 | "via Better Auth middleware" | "via the platform authentication dependency (ADR-0007)" |
| A-03 | §16 | "Authentication MUST use Better Auth." / "sessions are scoped to a specific company" | **If B:** "Authentication MUST use the provider approved in ADR-0007." / "Every request is authorized against the user's membership in the requested company; sessions are user-scoped and tenant scope is enforced per request." |
| A-04 | §6.6 | "Initial: Vercel / Render / Neon" | "Production: Vercel (frontend), Dockerized FastAPI on a VPS (backend), managed PostgreSQL, private S3-compatible object storage, transactional email provider (ADR-0008)". The "Future Production" path is retained as a growth option triggered by Epic 12 PERF-04/SEC-20. |
| A-05 | ADR-0008 (new) | — | "Production deployment topology". Records that it supersedes `DECISIONS.md` ADR-018. |
| A-06 | §28 | `develop`/`feature/*`/`bugfix/*`/`hotfix/*`/`release/*`; "merge commits for releases" | "Epic branches `NNN-<name>` and short-lived `fix/*`, `docs/*`, `ci/*` → PR → `main`; squash merge only (matches the `main` ruleset)." |
| A-07 | §29 / §43 | "reviewed and approved by at least one other engineer" | "Single-maintainer mode: the owner records a self-review against the §29 checklist on the PR; all required CI checks MUST pass; a bypass may cover only the approval requirement, never a failing check, and is logged. With a second contributor, independent review is required." |
| A-08 | §44 #13 | "No direct commits to `main` or `develop`" | "No direct commits to `main`" |
| A-09 | ADR-0009 (new) | — | "Single-maintainer governance" |
| A-10 | §24 | "formatted with Black and linted with Ruff" | "formatted and linted with Ruff" (matches CI; Black removed in `577d370`) |
| A-11 | §39 / docs | Two ADR series; mandatory initial ADRs not present | Confirm `history/adr/` as the only canonical ADR store. Add a header to `docs-project-context/DECISIONS.md` marking it a non-canonical historical index. Replace mandatory ADR-002 with ADR-0007 (B) or create it (A). Backfilling ADR-001/003–006 is tracked as follow-up documentation (not an Epic 12 blocker). |
| A-12 | ADR-0007 (new) | — | Per D-11: the in-house auth decision (B), or the Better Auth adoption plan (A) |
| A-13 | ADR-0003 follow-up | Residual `localStorage` risk "mitigated by CSP" | A new ADR or an ADR-0007 section recording the CSP as implemented, the remaining risk, and the cookie-upgrade trigger |

---

## 6. Questions that still require owner input

None blocks planning. The amendments are approved and applied in the governance PR (round 3).

**Required before the final production-readiness gate, as agreed:**
- professional confirmation of record retention;
- D-10 workload figures;
- provider selections (through the plan's comparisons).

---

## 7. Evidence needed before or during planning

- **Before `/sp.plan`:** the governance PR merged to `main`, with its CI result reported. After the merge, `012-production-readiness` is updated from `main`.
- **In the plan:**
  - provider comparisons (database, storage, email);
  - RPO 1 h and RTO 4 h feasibility evidence;
  - 99.5% cost and feasibility;
  - the archive/retention design;
  - CSP compatibility with the ADR-0007 tokens;
  - the SEC-24 mechanism (§3.2) with latency measurement;
  - the SEC-10 PostgreSQL negative suite scope;
  - the SEC-26 bypass removal.

---

## 8. Readiness for `/sp.plan`

**Ready once the governance PR merges.** All blocking decisions D-01…D-12 are resolved. The Constitution contradictions (§6.3, §6.6, §15, §16, §24, §28, §29, §38, §39, §43, §44) are removed by Constitution 2.0.0 and ADR-0007/0008/0009 in that PR.

**Non-blocking follow-ups:**
- stale "Better Auth insertion point" wording in `docs/architecture/*.md` and in three code comments, recorded in the Sync Impact Report (none claims Better Auth is implemented);
- the five foundational ADRs still to be backfilled (§39).
