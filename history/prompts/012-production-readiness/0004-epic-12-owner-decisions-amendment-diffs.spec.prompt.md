---
id: 0004
title: Epic 12 Owner Decisions Amendment Diffs
stage: spec
date: 2026-10-09
surface: agent
model: claude-opus-5-5
feature: 012-production-readiness
branch: 012-production-readiness
user: Muhammad Amir
command: (pasted) Epic 12 — Deployment / Production Readiness: Owner Decisions
labels: ["epic-12", "clarify", "d-11", "sec-24", "rls", "constitution-amendment", "adr"]
links:
  spec: specs/012-production-readiness/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/012-production-readiness/spec.md
  - specs/012-production-readiness/clarifications.md
  - specs/012-production-readiness/amendments-proposed.md
  - specs/012-production-readiness/checklists/requirements.md
tests:
  - none (clarification only)
---

## Prompt

# Epic 12 — Deployment / Production Readiness: Owner Decisions

## D-11 — Authentication Architecture

**Decision: Option B — Retain and formally approve the existing in-house JWT authentication system, subject to repository evidence and a security review.**

Do not adopt Better Auth solely because it is mentioned in the Constitution. Compare the existing authentication implementation against Better Auth using evidence covering security controls, tests, user/session compatibility, migration risks, and long-term maintenance costs.

If the existing implementation meets the required security standards, formally amend the Constitution and relevant ADRs to approve in-house JWT as the intended architecture. Do not claim that Better Auth is implemented.

If critical security gaps cannot be safely addressed in the existing system, present the evidence and trade-offs for reconsidering Option A. Do not implement an authentication migration without my explicit approval.

## A-01 to A-13 — Constitution and ADR Amendments

**Decision: Approve the proposed amendments in principle, subject to reviewing the exact diffs before application.**

Verify each amendment against the existing Constitution, ADRs, and actual repository practices. Do not silently rewrite unrelated rules or historical decisions. Ensure that the authentication decision, deployment topology, single-maintainer governance, and canonical ADR location remain consistent.

Verify existing version history and ADR numbering before finalizing document names and versions. Use Constitution version 1.3.0 and ADR-0007/0008/0009 only if these identifiers are valid and conflict-free.

First present the proposed diffs and an amendment summary for review. Apply the amendments only after approval.

## G-23 / SEC-24 — Immediate Session Revocation

**Decision: YES — This is a MUST requirement in Epic 12.**

After logout, password reset, account disablement, session revocation, and security-sensitive credential changes, access tokens belonging to revoked sessions must also be rejected immediately.

Inspect the existing JWT design and propose an appropriate mechanism, such as session/version validation or server-side revocation state.

Do not automatically require a database lookup on every request. Compare security guarantees, latency, caching, and failure-mode trade-offs. Prove that revocation works across all workers and instances using real PostgreSQL integration tests.

If the revocation store becomes unavailable, define fail-closed behavior rather than accepting potentially revoked tokens unsafely.

## D-12 — PostgreSQL Row-Level Security

**Decision: YES — Deferring database-level RLS is acceptable, provided the required tenant-isolation evidence passes.**

Epic 12 MUST include real PostgreSQL negative tests covering cross-tenant access, company-context enforcement, RBAC, tenant-ID manipulation, and IDOR risks.

Any demonstrated cross-tenant data leak is a production blocker. The system must not launch until the issue is remediated and the tests pass.

Keep PostgreSQL RLS as a future hardening option. Add it to the implementation plan only if the risk assessment demonstrates a clear need.

## Legal Retention and D-10 Workload

Treat seven-year business/accounting record retention as a planning assumption, not as a verified Pakistani legal requirement. Professional confirmation of applicable tax and accounting obligations is required before the final production-readiness gate.

Do not invent D-10 workload figures. The plan must define an initial baseline, measurable load tests, and provisional performance thresholds. Before final production capacity sign-off, record expected tenants, users per company, concurrent users, invoices, and export volumes.

## Required Sequence Before `/sp.plan`

1. Resolve D-11 using evidence from the actual repository.
2. Present the exact proposed diffs for A-01 through A-13 for review.
3. After approval, apply only the relevant Constitution and ADR amendments.
4. Ensure the exact official name, **`Epic 12 — Deployment / Production Readiness`**, is used consistently across all relevant current Epic 12 artifacts.
5. Close all blocking decisions and governing-document contradictions before proceeding to `/sp.plan`.

The plan must assess:

* Managed PostgreSQL, storage, and transactional email provider options.
* Feasibility and evidence for the 1-hour RPO and 4-hour RTO targets.
* Cost and feasibility of the proposed 99.5% availability target.
* Business-record archiving and retention design.
* CSP compatibility with the selected authentication architecture.
* SEC-24 session-revocation security guarantees and latency impact.

## Strict Stop Conditions

Do not implement application code, migrate authentication, deploy infrastructure, or execute database migrations during this clarification task.

Finalize the clarification and governance documents first. Do not start `/sp.plan` until the required decisions and amendments have been resolved and the specification is ready for planning.

## Response snapshot

**D-11 evidence review.** The controls were verified and cited: pinned algorithm with issuer/audience checks; hashed rotating refresh tokens with replay revocation; hashed, single-use reset and verification tokens; revocation on reset/change and on member disable; Argon2id; lockout; per-endpoint limits; and 164 auth tests. No critical gap needs Option A, so **B was confirmed**, on condition that SEC-24, SEC-04/05, SEC-20, SEC-26 and FR-PRD-032 pass.

**New finding — G-25 (SEC-26):** a latent `super_admin` bypass on `CurrentUser.roles` (always `[]`), in `companies/dependencies.py:150` and `accounting/services/permission_check.py:48`.

**SEC-24 is a MUST.** Mechanisms M1–M4 were compared. Preliminary pick: M1, folded into the existing per-request user lookup (`dependencies.py:83-84`), so no new round-trip. It fails closed and must be proven with a PostgreSQL multi-process test.

**D-12:** deferral approved. SEC-10 was extended, and any leak is a production blocker.

**Version check:** §45.3 makes the package **MAJOR → 2.0.0**, not 1.3.0. ADR-0007/0008/0009 are free in `history/adr`. Risk of confusion with `DECISIONS.md` ADR-007/008/009 is handled by A-10/A-11. §39's `NNN` naming is aligned to the existing 4-digit practice, with no renames.

**Diffs:** exact diffs are in `amendments-proposed.md`. **Nothing has been applied.**

**Verdict:** not ready for `/sp.plan` until the diffs are approved and applied.

## Outcome

- ✅ Impact: all decisions D-01…D-12 have an owner direction. One version error (1.3.0) was caught and corrected before application.
- 🧪 Tests: none.
- 📁 Files: spec.md, clarifications.md, amendments-proposed.md (new), checklist.
- 🔁 Next prompts: owner approves the diffs → apply them through a PR (§45.2) → `/sp.plan`.
- 🧠 Reflection: checking §45.3 directly changed the version answer, and checking the `roles` usage found a latent §50 risk.

## Evaluation notes (flywheel)

- Failure modes observed: the round-1 draft assumed a MINOR bump without reading §45.3. A wrong requirement ID (SEC-07) was caught and corrected to SEC-20.
- Graders run and results (PASS/FAIL): plan readiness FAIL by design (amendments pending).
- Prompt variant (if applicable): pasted owner directive.
- Next experiment (smallest change to try): n/a
