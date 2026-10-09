# Epic 12 — Deployment / Production Readiness: Proposed Constitution & ADR Amendments

**Status**: **APPROVED (2026-10-09) and APPLIED** in the governance PR (branch `docs/epic-12-governance-amendments`), effective on merge to `main`.
**Addition beyond the reviewed diffs (consistency only):** §38 "Claude Code MUST NOT: Commit directly to `main` or `develop`…" became "…to `main`…". It follows directly from A-06/A-08 and is recorded in the Sync Impact Report.
**Date**: 2026-10-09 · **Spec**: [spec.md](spec.md) · **Clarifications**: [clarifications.md](clarifications.md)
**Canonical sources checked**: `.specify/memory/constitution.md` (v1.2.1, last amended 2026-08-19), `history/adr/0001–0006`, `docs-project-context/DECISIONS.md` (ADR-001…019), `docs-project-context/DEPLOYMENT_GUIDE.md`.

Each block below shows the **exact current text** (`-`) and the **proposed text** (`+`).

The amendments are applied only after owner approval, and only as Constitution §45.2 requires:
- a PR containing the version bump;
- the Sync Impact Report;
- dependent document updates.

---

## 0. Identifier and version verification

### Constitution version

| Item | Finding |
|---|---|
| Current version | **1.2.1**. History: 1.0.0 → 1.1.0 → 1.2.0 → 1.2.1 (Sync Impact Report, lines 1–45). |
| Earlier proposal | 1.3.0 — **invalid** |
| Why | §45.3 defines MAJOR as "backward-incompatible governance changes, principle removals, or fundamental redefinitions". This package does both: it **redefines** the §16 authentication mandate ("MUST use Better Auth"), and it **removes governance rules** — the `develop` branch, "merge commits for releases", and "reviewed and approved by at least one other engineer". |
| Proposed version | **2.0.0 (MAJOR)** — not in use anywhere |

### ADR identifiers

| Item | Finding |
|---|---|
| Canonical store | `history/adr/` (§39) |
| Existing canonical ADRs | 0001–0006, files `NNNN-title.md`, headers `# ADR-NNNN:` |
| Proposed IDs | **ADR-0007, ADR-0008 and ADR-0009 are free**. No file, git history entry (`git log --all -- 'history/adr/0007*'` is empty) or document reference uses them outside Epic 12. |
| Naming conflict 1 | §39 itself prescribes `NNN-decision-title.md` and `ADR-NNN` (3 digits), but all six canonical files use 4 digits. A-10 aligns §39 to the existing practice; **no file is renamed**. |
| Naming conflict 2 | `DECISIONS.md` has its own 3-digit series. Its ADR-007 (ORM), ADR-008 (Migration Tool) and ADR-009 (Dependency Management) are textually distinct from ADR-0007/0008/0009, but easy to confuse. A-11 resolves this by labelling that file a non-canonical legacy series: any reference to it must say "`DECISIONS.md` ADR-0NN". Its IDs are not renumbered. |

**Verdict:** the IDs **ADR-0007/0008/0009 are valid and conflict-free in the canonical store**, provided A-10 and A-11 are applied with them. The Constitution version must be **2.0.0**, not 1.3.0.

---

## 1. Amendment summary

| # | Target | Change | Driver |
|---|---|---|---|
| A-01 | Constitution §6.3 | Better Auth → in-house authentication (ADR-0007) | D-11 = B |
| A-02 | Constitution §15 | "Better Auth middleware" → platform authentication dependency | D-11 = B |
| A-03 | Constitution §16 | Mandate, session and tenant wording aligned to the implementation; immediate revocation added | D-11 = B, SEC-24 |
| A-04 | Constitution §6.6 | Approved production topology | D-01 |
| A-05 | New ADR-0008; notes in `DEPLOYMENT_GUIDE.md` and `DECISIONS.md` ADR-018 | Production deployment topology | D-01 |
| A-06 | Constitution §28 | Branch and merge strategy matches practice | D-06 |
| A-07 | Constitution §29, §43 | Single-maintainer review mode | D-06 |
| A-08 | Constitution §44 #13 | Remove `develop` | D-06 |
| A-09 | New ADR-0009 | Single-maintainer governance | D-06 |
| A-10 | Constitution §24, §39 | Ruff format; 4-digit ADR naming; foundational ADR list status | Repository practice, G-24 |
| A-11 | `DECISIONS.md` header | Mark it as a non-canonical legacy index | G-24 |
| A-12 | New ADR-0007 | In-house authentication architecture | D-11 = B |
| A-13 | ADR-0001 and ADR-0003 | One "Related" line each, pointing to ADR-0007. Body text unchanged. | D-08, D-11 |
| — | Constitution header and footer | Sync Impact Report; version 2.0.0; "Last Amended" date set to the day of application | §45.2 |

---

## 2. Constitution diffs

### A-01 — §6.3 Authentication (line 364)

```diff
 ### 6.3 Authentication

 | Component | Technology |
 |-----------|------------|
-| Auth Framework | Better Auth |
+| Auth Framework | In-house: JWT access tokens + opaque rotating refresh tokens + server-side sessions (ADR-0007) |
+| Password Hashing | Argon2id (ADR-0002) |
```

### A-02 — §15 API Design (line 596)

```diff
-2. Authenticate the request (via Better Auth middleware)
+2. Authenticate the request (via the platform authentication dependency — ADR-0007)
```

### A-03 — §16 Authentication & Authorization (lines 613–632)

```diff
-**Authentication MUST use Better Auth.**
+**Authentication MUST use the approved in-house authentication architecture (ADR-0007).**
+Replacing it with a third-party framework is a major change under §40 and requires a new ADR
+and Constitution amendment.

 **Required capabilities**:

 - **RBAC** (Role-Based Access Control) with granular permissions
 - **Permission-based Authorization** — roles contain sets of named permissions
 - **Audit Logging** — all authentication events are logged
 - **Secure Sessions** — server-side session management
+- **Immediate Revocation** — revoking a session (logout, password reset or change, account
+  disablement, administrative revocation) MUST cause every token issued for that session to be
+  rejected on the next request, on every worker and instance
 - **Secure Cookie or Token Strategy** — appropriate per deployment context
-- **Multi-Tenant Awareness** — sessions are scoped to a specific company
+- **Multi-Tenant Awareness** — every tenant-scoped request is authorized against the user's
+  active membership in the requested company; sessions are user-scoped, and tenant scope is
+  never inferred from the session alone
```

The rules list (lines 626–632) is unchanged, including "MUST remain modular and replaceable" and "bcrypt or Argon2".

### A-04 — §6.6 Deployment (lines 383–407)

```diff
 ### 6.6 Deployment

-**Initial Deployment:**
+**Production Deployment (ADR-0008):**

 | Layer | Platform |
 |-------|----------|
 | Frontend | Vercel |
-| Backend | Render |
-| Database | Neon PostgreSQL (managed) |
+| Backend | Dockerized FastAPI on a VPS (provider and region selected in the Epic 12 plan) |
+| Database | Managed PostgreSQL (provider and region selected in the Epic 12 plan) |
+| File Storage | Private, S3-compatible object storage (provider selected in the Epic 12 plan) |
+| Email | Transactional email provider (provider selected in the Epic 12 plan) |

-**Future Production:**
+**Future Growth Path** (adopted only with measured evidence, per §5 and Epic 12 NFR-PRD-09):
```

The diagram and the `> **RULE**` line (line 407) are unchanged.

### A-06 — §28 Git Workflow (lines 859–882)

```diff
 **Branch Strategy**:

 | Branch | Purpose |
 |--------|---------|
 | `main` | Production-ready code only |
-| `develop` | Integration branch for completed features |
-| `feature/*` | New feature development |
-| `bugfix/*` | Non-critical bug fixes |
-| `hotfix/*` | Critical production bug fixes |
-| `release/*` | Release preparation and stabilization |
+| `NNN-<feature>` | Spec-Kit feature/epic branches (e.g. `012-production-readiness`) |
+| `fix/*`, `docs/*`, `ci/*` | Short-lived non-feature changes |
+| `hotfix/*` | Critical production fixes |

 **Rules**:

-- **Never commit directly to `main` or `develop`.**
+- **Never commit directly to `main`.**
 - All changes MUST go through **Pull Requests**.
 ...
-- Merge strategies: Squash merge for features; merge commits for releases.
+- Merge strategy: squash merge only (enforced by the `main` ruleset). Release identification
+  (immutable artifact tags) is defined by Epic 12 FR-PRD-041. No repository tags exist yet.
```

### A-07 — §29 Code Review Standards (after line 897) and §43 DoD (line 1214)

```diff
 Reviewers MUST NOT approve PRs that violate Non-Negotiable Rules, regardless of urgency.
+
+**Single-maintainer mode** (ADR-0009) — applies only while the project has exactly one
+maintainer:
+
+- The maintainer MUST record a self-review on the PR against the checklist above before
+  merging.
+- All required CI status checks MUST pass. A failing check MUST NEVER be bypassed.
+- An administrative bypass may cover only the approval-count requirement. Each use MUST be
+  logged with the PR number and reason.
+- Once a second contributor exists, an independent review by someone other than the author
+  is required again.
```

```diff
-- [ ] Code is reviewed and approved by at least one other engineer
+- [ ] Code is reviewed and approved by at least one other engineer, or, in single-maintainer
+      mode (§29), self-reviewed against the §29 checklist with all required CI checks passing
```

### A-08 — §44 Non-Negotiable Rules #13 (line 1244)

```diff
-| 13 | No direct commits to `main` or `develop` |
+| 13 | No direct commits to `main` |
```

### A-10 — §24 Backend Principles (line 819) and §39 ADRs (lines 1077–1113)

```diff
-- All Python code MUST be formatted with Black and linted with Ruff.
+- All Python code MUST be formatted and linted with Ruff.
```

```diff
 ADRs are stored in: `history/adr/`
-Naming convention: `NNN-decision-title.md`
+Naming convention: `NNNN-decision-title.md` (four digits, e.g. `0007-…`); header `# ADR-NNNN: [Title]`.
+`history/adr/` is the **only** canonical ADR store. `docs-project-context/DECISIONS.md` is a
+non-canonical legacy index; its `ADR-0NN` identifiers are a separate series and MUST be cited as
+"DECISIONS.md ADR-0NN".
 ...
-# ADR-NNN: [Title]
+# ADR-NNNN: [Title]

-**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-NNN
+**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-NNNN
 ...
-**Mandatory Initial ADRs** (to be created during initial platform design):
+**Foundational ADRs** (required; status as of v2.0.0):

-- ADR-001: Why Modular Monolith Architecture
-- ADR-002: Why Better Auth
-- ADR-003: Why PostgreSQL
-- ADR-004: Why Repository Pattern
-- ADR-005: Why FastAPI
-- ADR-006: Why Feature Toggles Approach
+- Authentication approach — **ADR-0007** (supersedes the planned "Why Better Auth")
+- Modular Monolith Architecture — not yet recorded (backfill required)
+- PostgreSQL — not yet recorded (backfill required)
+- Repository Pattern — not yet recorded (backfill required)
+- FastAPI — not yet recorded (backfill required)
+- Feature Toggles Approach — not yet recorded (backfill required)
```

This states the pre-existing gap openly instead of hiding it. The backfill is a documentation follow-up and not an Epic 12 blocker.

### Header and footer (§45.2 items 2 and 4)

```diff
 <!--
   SYNC IMPACT REPORT
   ==================
-  Version change: 1.2.0 → 1.2.1 (PATCH — clarification, no new rule)
+  Version change: 1.2.1 → 2.0.0 (MAJOR — authentication mandate redefined; governance rules
+  removed or changed)
+  Modified: §6.3, §6.6, §15, §16, §24, §28, §29, §39, §43, §44 #13
+  Added: ADR-0007 (authentication), ADR-0008 (deployment topology), ADR-0009 (governance)
+  Templates: plan, spec and tasks templates have no static references to the changed sections
+  (re-verify when applying)
+  Dependent documents: DEPLOYMENT_GUIDE.md and DECISIONS.md header notes; CLAUDE.md unchanged
+  Deferred: backfill of the five foundational ADRs (§39)
+  ---- Previously in v1.2.1 ----
+  Version change: 1.2.0 → 1.2.1 (PATCH — clarification, no new rule)
 ...
-**Version**: 1.2.1 | **Ratified**: 2026-07-10 | **Last Amended**: 2026-08-19
+**Version**: 2.0.0 | **Ratified**: 2026-07-10 | **Last Amended**: <date of application>
```

---

## 3. New ADR outlines (full text written on approval, using the §39 structure)

| ADR | Title | Context / Decision / Consequences (summary) |
|---|---|---|
| **0007** | In-House JWT Authentication Architecture (supersedes the planned "Why Better Auth") | **Context:** §16 named Better Auth; the platform was built in-house (ADR-0001/0002/0003, Epic 9A plan §3.1) and was never ratified.<br>**Decision:** approve the in-house design.<br>**Controls:** see `clarifications.md` §3.<br>**Conditions (Epic 12 MUST):** SEC-24 immediate revocation; SEC-04 CSP; real email (FR-PRD-032); shared rate limiting; SEC-26 latent role bypass.<br>**Known limitations:** HS256 shared secret (a rotation runbook is required); the refresh token stays in `localStorage` (ADR-0003) with residual risk after CSP; no MFA yet (§19 readiness).<br>**Ownership:** the maintainer, with a security review each release.<br>**Alternatives:** Better Auth (rejected, with evidence); cookie sessions (deferred, with a trigger). |
| **0008** | Production Deployment Topology | **Decision:** Vercel frontend + Dockerized FastAPI on a VPS + managed PostgreSQL + private S3-compatible storage + a transactional email provider; providers chosen in the plan.<br>**Supersedes:** Constitution §6.6 "Render/Neon" and `DECISIONS.md` ADR-018; the `DEPLOYMENT_GUIDE.md` Hetzner recommendation becomes one candidate among the providers compared. |
| **0009** | Single-Maintainer Governance | Records D-06: the self-review protocol, no bypass of failing checks, the bypass log, and the return to independent review once a second contributor exists. |

## 4. Non-Constitution document notes (A-05, A-11, A-13)

These are notes only; historical body text is not rewritten.
- `DECISIONS.md` top: "Legacy, non-canonical decision index. Canonical ADRs live in `history/adr/` (Constitution §39). ADR-018 is superseded by `history/adr/0008`."
- `DEPLOYMENT_GUIDE.md` top: "The production topology is defined by ADR-0008. Provider recommendations in this guide are candidates, not decisions."
- `history/adr/0001-*.md` and `0003-*.md` status block: add the line "**Related**: ADR-0007 (formal approval of this architecture and its conditions)".

## 5. Owner approval requested

Please answer one of:
- **Approve all** (A-01…A-13, version 2.0.0, ADR IDs 0007/0008/0009);
- **Approve with changes** (name the item and the change);
- **Reject** an item.

On approval, the amendments are applied as one PR from a `docs/*` branch, as §45.2 requires, and nothing else is touched.
