# Specification Quality Checklist: Epic 12 — Deployment / Production Readiness

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-08
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — see Note 1
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders — see Note 1
- [x] All mandatory sections completed: user scenarios (§6.1, §17.2), requirements (§7–§15) and success criteria (§4), mapped to the user-requested 22-section structure

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain. Open business choices are captured as decisions D-01…D-10 (§20), each with a recommended default.
- [x] Requirements are testable and unambiguous. Each MUST names its verification (§16) or evidence artifact.
- [x] Success criteria are measurable (SC-01…SC-11). Numeric targets that only the business can set (RPO/RTO, availability, workload) are bound to D-02/D-07/D-10 rather than invented.
- [x] Success criteria are technology-agnostic — see Note 1
- [x] All acceptance scenarios are defined (§17.2, 12 scenarios)
- [x] Edge cases are identified (§17.3)
- [x] Scope is clearly bounded (§1.2, §5)
- [x] Dependencies and assumptions identified (§18, §19, §20)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows (US-1…US-7)
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification — see Note 1

## Notes

1. **Accepted exception for an infrastructure epic.** Production readiness is about the operating platform itself, so the spec names existing, Constitution-mandated components:
   - PostgreSQL, Alembic and Docker (Constitution §6, §18, §27);
   - concrete security headers such as CSP and HSTS (Constitution §19);
   - concrete evidence locations: files and tests in the repository.

   It does **not** choose new tools. The hosting, email, storage, error-tracking and rate-limit store choices are left to D-01/D-04/D-05 and the plan. Success criteria are stated as observable outcomes.
2. **Blocking before `/sp.plan`:** decisions D-01 (a deployment-target contradiction between Constitution §6.6, `DECISIONS.md` ADR-018 and `DEPLOYMENT_GUIDE.md`) and D-06 (governance drift) need approval and probably a Constitution amendment.
3. Validation iterations: 1. Two corrections were made after re-verifying against the code: platform-owner bootstrap reclassified as an existing control (S-14), and the IDOR/cross-tenant test file count corrected to 70.
4. **Clarification session 2026-10-09 (iteration 2).**
   - Owner decisions were integrated, each with its status (APPROVED / PROPOSED / OPEN / PENDING).
   - The Epic was renamed to "Epic 12 — Deployment / Production Readiness".
   - G-22 was corrected: the Better Auth deviation is **unratified** (ADR-0001 never mentions Better Auth), not "accepted".
   - G-23 (session revocation) and G-24 (ADR governance) were added.
   - D-11 (Better Auth) and D-12 (database row security) were added.
   - The spec still conflicts with Constitution §6.3, §6.6, §15, §16, §24, §28, §29, §39, §43 and §44 until the amendment package in `clarifications.md` §5 is approved and applied. "All mandatory sections completed" remains true, but **plan readiness is NOT met** (see `clarifications.md` §8).
5. **Clarification round 2 (2026-10-09).**
   - D-11 = B was approved after an evidence review (`clarifications.md` §3.1).
   - SEC-24 is now a MUST, and SEC-26 / G-25 were added for the latent role bypass.
   - D-12 is deferred, with PostgreSQL negative tests; any leak blocks production.
   - The amendment diffs are in `amendments-proposed.md`. The version was corrected to **2.0.0** (MAJOR, per §45.3), and ADR-0007/0008/0009 were verified free.
   - Plan readiness is still **NOT met** until the diffs are approved and applied.
6. **Round 3 (2026-10-09): amendments applied.**
   - Constitution 2.0.0 and ADR-0007/0008/0009 are applied in the governance PR.
   - The official Epic name is applied in the current documents (`EPICS.md`, `PROJECT_CONTEXT.md`). Historical Epic 8 records and the PHRs are unchanged.
   - Plan readiness is met once that PR merges.
