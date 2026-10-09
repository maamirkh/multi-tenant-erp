# ADR-0009: Single-Maintainer Governance

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** Project owner (sole maintainer)
- **Feature:** 012-production-readiness
- **Context:** Constitution v1.2.1 assumed a team, through four rules:
  - a `develop` integration branch (§28);
  - "merge commits for releases" (§28);
  - review "by at least one other engineer" (§43 DoD);
  - no direct commits to `develop` (§44 #13).

  Actual practice differs:
  - one owner, assisted by Claude Code;
  - Spec-Kit epic branches `NNN-<feature>` merged into `main` through PRs;
  - a `main` ruleset that requires one approval, squash merges and resolved threads;
  - the owner, as the only collaborator, merges through an administrative bypass of the approval count — for example, PR #9 was squash-merged as `712a668`.

  The ruleset's `required_status_checks` list is currently empty (Epic 12 G-14). The owner approved a single-maintainer workflow as Epic 12 decision D-06.

<!-- Significance checklist: Impact ✅ (process/quality gates), Alternatives ✅, Scope ✅ (every change) -->

## Decision

**Single-maintainer mode** (Constitution §29) applies while the project has exactly one maintainer:

1. Short-lived branches only: `NNN-<feature>`, `fix/*`, `docs/*`, `ci/*`, `hotfix/*`. Every change goes to `main` through a PR, with squash merge only.
2. The maintainer records a **self-review on the PR** against the §29 checklist before merging.
3. **All required CI status checks MUST pass.** A failing check is never bypassed. Epic 12 FR-PRD-040 makes the checks required in the ruleset and proves it by attempting a merge that fails.
4. The administrative bypass may cover **only the approval-count requirement**. Each use is logged in the PR description, with the PR number and the reason.
5. Once a second contributor joins, independent review by someone other than the author is required again, and this mode ends.

## Consequences

### Positive

- The Constitution matches real, auditable practice.
- The CI gate becomes the main quality control, and it is enforced.

### Negative

- No independent human review exists. Defects that CI cannot detect rely on the self-review discipline and on the Spec-Kit artifacts (spec, plan, tasks, PHR).
- The bus factor is one. This is mitigated by the Epic 12 runbooks (NFR-PRD-08).

## Alternatives Considered

- **Keep the team rules unchanged:** they cannot be met, so every merge would be a documented violation.
- **Drop the PR requirement:** rejected. It loses the CI gate and the audit trail.
- **Use an external reviewer for every PR:** not available. This should be revisited when the team grows.

## Reasoning

The safeguards that matter — PRs, passing CI and recorded review — can all be kept by one person. Pretending that a second reviewer exists cannot.

## References

- Constitution v2.0.0 §28, §29, §43, §44 #13
- Spec: `specs/012-production-readiness/spec.md` (D-06, G-14, G-19, FR-PRD-040)
