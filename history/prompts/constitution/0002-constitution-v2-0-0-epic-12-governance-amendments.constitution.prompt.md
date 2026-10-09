---
id: 0002
title: Constitution v2.0.0 Epic 12 Governance Amendments
stage: constitution
date: 2026-10-09
surface: agent
model: claude-opus-5-5
feature: 012-production-readiness
branch: docs/epic-12-governance-amendments
user: Muhammad Amir
command: (pasted) Final Approval — Epic 12 Amendments and Mandatory Epic Rename
labels: ["constitution", "amendment", "adr", "auth", "deployment", "governance", "epic-12"]
links:
  spec: specs/012-production-readiness/spec.md
  ticket: null
  adr: history/adr/0007-in-house-jwt-authentication-architecture.md
  pr: null
files:
  - .specify/memory/constitution.md
  - history/adr/0007-in-house-jwt-authentication-architecture.md
  - history/adr/0008-production-deployment-topology.md
  - history/adr/0009-single-maintainer-governance.md
  - history/adr/0001-jwt-access-token-and-opaque-refresh-token-session-architecture.md
  - history/adr/0003-frontend-token-storage-strategy-for-authentication.md
  - docs-project-context/DECISIONS.md
  - docs-project-context/DEPLOYMENT_GUIDE.md
  - docs-project-context/EPICS.md
  - docs-project-context/PROJECT_CONTEXT.md
  - specs/012-production-readiness/spec.md
  - specs/012-production-readiness/clarifications.md
  - specs/012-production-readiness/amendments-proposed.md
  - specs/012-production-readiness/checklists/requirements.md
tests:
  - none (documentation/governance only)
---

## Prompt

# Final Approval — Epic 12 Amendments and Mandatory Epic Rename

**Decision: Approve the proposed amendments in principle, subject to the mandatory checks below.**

## 1. Amendments A-01 to A-13

Review `amendments-proposed.md` and verify every proposed diff against the current Constitution, ADR history, and repository state.

I approve the proposed direction, including the deployment architecture, single-maintainer governance, and formally documented in-house JWT decision, subject to these conditions:

* Constitution version `2.0.0` must be justified by the actual scope of the changes and the project's versioning rules. Do not change the version number blindly.
* Verify that ADR-0007, ADR-0008, and ADR-0009 are the correct available identifiers and do not conflict with existing records.
* Preserve historical decisions and avoid unrelated changes.
* Ensure all approved amendments are internally consistent and accurately reflect the actual implementation.
* Report any material discrepancy before applying the amendments.

Once these checks pass, implement the approved amendments through **one PR**, following Constitution §45.2. Do not bypass required CI checks.

## 2. Mandatory Epic Name Change — Still Outstanding

The Epic name has not yet been changed. This is an explicit requirement and must not be overlooked.

The exact official name must be:

**`Epic 12 — Deployment / Production Readiness`**

Update the title and references in the current Epic 12 `spec.md`, clarification artifacts, and all relevant current Epic 12 documents. Check the repository for remaining references to the previous Epic 12 title and update applicable current documents consistently.

Do not rename unrelated historical Epics or rewrite historical records merely to change their wording.

Include these title changes in the same PR where practical, and report the exact files updated.

## 3. Specification and Planning Gate

After the approved amendments and Epic rename are applied:

1. Verify the PR diff, document consistency, and required CI results.
2. Confirm that the Better Auth versus in-house JWT decision is explicitly documented.
3. Confirm that all blocking clarification decisions are resolved.
4. Update the Epic 12 specification and clarification artifacts to reflect the approved decisions.
5. Reassess whether the specification is ready for `/sp.plan`.

Provider selection, workload figures (D-10), and professional confirmation of legal retention requirements may remain open for planning, but must be resolved before the final production-readiness gate, as previously agreed.

**Do not start `/sp.plan` automatically.** First report the completed changes, PR/CI status, any remaining blockers, and your readiness verdict. Do not claim a change or PR is complete unless it has actually been performed and verified.

## Response snapshot

**Checks passed:**
- **Version:** 2.0.0 is justified by §45.3 MAJOR — the §16 mandate is redefined, and `develop`, release merge commits and second-engineer review are removed.
- **ADR IDs:** 0007/0008/0009 are free in `history/adr` and in git history.
- **Templates:** no references to the changed sections.

**One discrepancy found and fixed for consistency:** §38 still said "main or develop". `develop` was removed and the change disclosed in the Sync Impact Report.

**Applied on `docs/epic-12-governance-amendments`:**
- the Constitution diffs and the Sync Impact Report, including known non-compliance (G-23, CSP, ADR backfill);
- ADR-0007/0008/0009;
- legacy notices in `DECISIONS.md` and `DEPLOYMENT_GUIDE.md`;
- a "Related" line in ADR-0001 and ADR-0003.

**Epic name:** the official name was applied in `EPICS.md` (1 place) and `PROJECT_CONTEXT.md` (2 places). The spec, checklist and clarification artifacts already used it. The historical `specs/008` and the PHRs were left unchanged.

**Not changed (follow-up):** stale "Better Auth" wording in `docs/architecture/*.md` and in three code comments.

## Outcome

- ✅ Impact: the Constitution and ADRs now match the implementation and the owner's decisions; the plan gate opens on merge.
- 🧪 Tests: none (documentation only). CI is reported from the PR.
- 📁 Files: see the list above.
- 🔁 Next prompts: merge the PR once CI is green → update `012-production-readiness` from `main` → `/sp.plan`.
- 🧠 Reflection: a full-text sweep after applying the diffs found a `develop` reference (§38) that the section-targeted diffs had missed.

## Evaluation notes (flywheel)

- Failure modes observed: the section-scoped diff missed a cross-section reference.
- Graders run and results (PASS/FAIL): grep for leftover Better Auth / develop / Black / Render / Neon in the Constitution — PASS.
- Prompt variant (if applicable): pasted owner approval.
- Next experiment (smallest change to try): n/a
