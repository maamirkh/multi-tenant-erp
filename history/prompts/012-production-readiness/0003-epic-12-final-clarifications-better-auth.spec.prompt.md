---
id: 0003
title: Epic 12 Final Clarifications Better Auth
stage: spec
date: 2026-10-09
surface: agent
model: claude-opus-5-5
feature: 012-production-readiness
branch: 012-production-readiness
user: Muhammad Amir
command: (pasted) Epic 12 — Deployment / Production Readiness: Final Clarifications
labels: ["epic-12", "clarify", "better-auth", "governance", "constitution-amendment"]
links:
  spec: specs/012-production-readiness/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/012-production-readiness/spec.md
  - specs/012-production-readiness/clarifications.md
  - specs/012-production-readiness/checklists/requirements.md
tests:
  - none (clarification only)
---

## Prompt

# Epic 12 — Deployment / Production Readiness: Final Clarifications

You are working in the existing DevSphere ERP repository. Continue the current Spec-Kit Plus workflow. The Epic 12 clarification report has been generated, but owner decisions remain pending.

## CRITICAL RULES

* This is a specification/clarification task ONLY. Do not implement code, install packages, change authentication, run migrations, deploy, or start `/sp.plan`.
* Read the existing Constitution, ADRs, `DECISIONS.md`, `DEPLOYMENT_GUIDE.md`, Epic 11 final artifacts, Epic 12 `spec.md`, and the latest clarification report before editing.
* Preserve existing architecture and working features. Do not silently resolve contradictions.
* Every Claude Code Goal prompt must remain under 4000 characters.
* **The official Epic name MUST be exactly `Epic 12 — Deployment / Production Readiness`.** Update the Epic title and references in the Epic 12 spec, clarification artifacts, and relevant Epic 12 headings. Do not rename unrelated historical Epics or rewrite history.
* Do not mark any feature implemented without repository evidence and tests.

## 1. Resolve all decisions using these owner-approved directions

**D-01 — Deployment:** Choose Option B: Vercel frontend + Dockerized FastAPI backend on a VPS + managed PostgreSQL. In `/sp.plan`, compare suitable managed PostgreSQL providers and regions, including backup/PITR, TLS, latency, cost, and operational burden. Do not purchase services or assume a provider is selected.

**D-02 — RPO:** Set the initial target to a maximum of 1 hour of data loss, subject to confirming that the selected database and backup design can actually meet it.

**D-03 — Retention:** Separate operational backups (30 days initially) from business/accounting record retention (7 years as a planning requirement). Flag the seven-year period for confirmation against applicable Pakistani legal/tax requirements or professional advice; do not present it as verified legal advice. Define archive, restore, deletion, and audit implications separately.

**D-04 — File storage:** Choose private tenant-scoped object storage with short-lived signed URLs and authorization checks. Compare S3-compatible providers during planning; do not assume provider selection. Remove SVG from company-logo uploads unless a demonstrably safe sanitization approach is justified and tested. Fix the fake `/dev/exports/...` fallback and all production upload/storage failure paths.

**D-05 — Email:** Choose a real transactional email provider for verification and password reset. Provider and sender domain remain open until options are compared. Production must fail safely or disable flows explicitly if email is not configured; never pretend delivery succeeded.

**D-06 — Governance:** Approve a single-maintainer workflow amendment reflecting actual practice: short-lived branches, PR to `main`, owner self-review recorded against the Constitution checklist, required CI checks passing, no bypass of failing checks, and logged exceptions. When a second contributor is available, normal independent review applies. Amend Constitution/ADR only after checking the canonical document and existing governance rules.

**D-07 — Availability/RTO:** Use an initial planning target of 99.5% availability and 4-hour RTO, with planned maintenance permitted. Clearly label these as proposed service objectives, define measurement/exclusions, and verify feasibility and cost in the plan. Do not promise an SLA without owner approval.

**D-08 — CSP/auth:** Prefer retaining the existing token approach temporarily and implementing a strict, tested Content Security Policy, but first resolve the Better Auth issue below. Do not assume the current authentication design is approved merely because ADR-0003 describes it.

**D-09 — Runtime safety:** Approve the proposed safe defaults:

1. Production/staging migrations run once in a dedicated release job before rollout; app workers only verify schema-head compatibility and fail readiness on mismatch.
2. Scheduler runs in a dedicated process, not every API worker, with PostgreSQL advisory-lock protection.
3. Recurring-journal instance and GL posting are atomic; prove no duplicate postings with concurrent PostgreSQL tests and a staging drill.
4. Production/staging fail closed on DEBUG, weak/default secrets, default storage credentials, wildcard/localhost CORS, unknown environment, missing trusted hosts, enabled email without a provider, or remote DB connections without TLS.

**D-10 — Workload:** Do not invent tenant/user/invoice/export numbers. Mark these as owner-supplied inputs and propose a measurable baseline/benchmark approach for `/sp.plan`. Identify which performance thresholds must remain provisional until real workload figures are supplied.

## 2. NEW MANDATORY ISSUE — BETTER AUTH IMPLEMENTATION GAP

The Constitution explicitly names Better Auth, but repository implementation reportedly uses an in-house JWT authentication system and ADR-0001 records a deviation. Treat this as a potentially material architecture and security gap, not merely outdated wording.

Before finalizing the spec:

1. Inspect the actual authentication code, frontend auth client, backend token/session verification, password hashing, login/logout, refresh/revocation, password reset, email verification, RBAC integration, tenant isolation, and relevant tests.
2. Establish precisely which Better Auth requirements exist in the Constitution and which are missing from implementation. Cite exact repository paths and relevant Constitution/ADR sections in the report.
3. Present two explicit options:
   A. Implement/adopt Better Auth in a controlled, migration-safe manner, preserving existing users, passwords where safely compatible, sessions, roles, company membership, tenant isolation, and existing API contracts.
   B. Keep the in-house JWT implementation as a formally approved architectural deviation, with an explicit Constitution amendment and ADR documenting the rationale, security controls, limitations, and maintenance ownership.
4. Recommend the safest maintainable option based on repository evidence, migration risk, security, and compatibility. Do not choose silently. Ask the owner to approve A or B.
5. If A is selected, include authentication migration, rollback, session invalidation, password compatibility, tests, and staged rollout in the future plan. Do not implement them now.
6. If B is selected, do not claim Better Auth is implemented. Update the governing documents only after explicit approval.
7. Treat CSP as necessary regardless of which option is selected, but do not claim CSP alone resolves every token-storage risk.

## 3. Classify all 22 gaps and preserve existing controls

Revalidate G-01 through G-22 against the current repository. Retain MUST/SHOULD/DEFERRED/ALREADY SATISFIED classifications only where evidence supports them. Preserve all 14 verified existing controls; do not rebuild them. Keep production blockers explicit, including backup/restore drills, scheduler duplication, migrations, configuration guardrails, storage, email, CSP, CI/CD, monitoring, environments, and runbooks.

## 4. Governance and document consistency

Prepare the proposed Constitution/ADR amendments for owner review, including:

* Deployment topology and superseding ADR.
* Single-maintainer workflow and branch/merge rules.
* Better Auth versus in-house JWT decision.
* Any stale Constitution references that conflict with verified repository practice, including authentication, Ruff formatting, and canonical ADR locations.

Do not silently modify unrelated historical records. Identify the canonical ADR source using the Constitution's own rules.

## 5. Required output and stop condition

Update the clarification artifacts and Epic 12 spec with the exact official title and clearly distinguish:

* approved owner decisions;
* proposed objectives requiring confirmation;
* unresolved provider/domain/workload inputs;
* repository-verified facts versus assumptions;
* production blockers;
* Better Auth evidence and options;
* Constitution/ADR amendments awaiting approval.

Return a concise decision matrix with all questions that still genuinely require owner input. Do not ask again about choices explicitly approved above. Then list the proposed document changes and evidence needed before planning.

**STOP after clarification. Do not start `/sp.plan`, create implementation tasks, modify application code, or execute migrations.** Report whether the spec is ready for `/sp.plan` only after all required decisions are explicitly approved and the governing-document contradictions are resolved.

## Response snapshot

- Renamed the Epic to "Epic 12 — Deployment / Production Readiness" in the spec and checklist. PHR 0001 is left verbatim.
- Added a Clarifications section, integrating D-01…D-10 with an explicit status for each, plus new decisions D-11 (Better Auth) and D-12 (database row security).

Better Auth inspection (VERIFIED):
- no `better-auth` dependency;
- in-house PyJWT access tokens, opaque rotating refresh tokens and a `sessions` table;
- ADR-0001 never mentions Better Auth; the deviation appears only in Epic 9A plan §3.1.
- G-22 is reclassified from "accepted" to **unratified** — a correction of the earlier spec.

New gaps:
- **G-23:** `get_current_user` never checks `Session.is_revoked`, so access tokens survive logout for up to 15 minutes.
- **G-24:** two ADR series exist, and the mandatory initial ADRs are missing; Constitution §39 makes `history/adr` canonical.

Other changes:
- Options A and B are presented, with B recommended.
- The amendment package A-01…A-13 is drafted and **not applied**.

Verdict: NOT ready for `/sp.plan` — D-11 is pending and the amendments must be approved and applied first.

## Outcome

- ✅ Impact: the spec separates approved, proposed, open and pending decisions; one earlier factual error was corrected.
- 🧪 Tests: none.
- 📁 Files: spec.md, clarifications.md, checklists/requirements.md.
- 🔁 Next prompts: answer D-11 (A or B), approve the A-01…A-13 amendments, confirm SEC-24 and D-12. Then apply the amendments and run `/sp.plan`.
- 🧠 Reflection: "ADR-0001 records a deviation" was an inherited assumption; reading the ADR disproved it.

## Evaluation notes (flywheel)

- Failure modes observed: decision-ID drift between the spec (D-09 = row security) and the report (D-09 = runtime safety) — reconciled to the owner's numbering, with row security renumbered to D-12.
- Graders run and results (PASS/FAIL): checklist updated; plan readiness FAIL by design.
- Prompt variant (if applicable): pasted owner directive.
- Next experiment (smallest change to try): n/a
