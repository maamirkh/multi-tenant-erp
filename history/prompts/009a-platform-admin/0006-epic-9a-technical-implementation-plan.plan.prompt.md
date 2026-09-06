---
id: 0006
title: Epic 9A technical implementation plan
stage: plan
date: 2026-08-19
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.plan
labels: ["platform-admin", "plan", "architecture", "rbac", "audit", "entitlement"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/009a-platform-admin/plan.md
 - specs/009a-platform-admin/research.md
 - specs/009a-platform-admin/data-model.md
 - specs/009a-platform-admin/quickstart.md
 - specs/009a-platform-admin/contracts/platform-admin-v1.yaml
 - CLAUDE.md
 - history/prompts/009a-platform-admin/0006-epic-9a-technical-implementation-plan.plan.prompt.md
tests:
 - none (planning-only phase; no code, migrations, or tests written)
---

## Prompt

# Epic 9A — Platform Administration / Super Admin
# `/sp.plan` — Full & Final Technical Planning Prompt

[Full 46-section technical planning brief provided by the user, covering: mandatory source-of-truth review (constitution.md, spec.md, 13 categories of existing repository architecture); Git/Epic baseline verification; the Modular Monolith planning principle (no microservices/Kubernetes/second stack); exhaustive repository reconnaissance requirements across backend auth/RBAC/audit/feature-toggles/quota and frontend CompanyContext/routing/API-client conventions; detailed architectural requirements for Platform Domain Boundary, Platform Administrator Identity, Platform Session Boundary, Initial Platform Owner Bootstrap, Platform RBAC, Tenant Lifecycle Integration, Session Revocation Strategy, Plans/Subscriptions, Module Entitlement Architecture, Entitlement Resolution Service, Feature-Toggle Hardening, Canonical Tenant Context, Administrative Overrides, Quota Architecture, Usage Metering, AI Credits Readiness, Audit Architecture (fail-closed), Cross-Tenant Support Access, Platform Dashboard, Frontend Architecture, API Architecture, Data Model/Migrations, DB Integrity/Concurrency, Security Threat Review, Bulk Operations, Observability, Performance, Testing Strategy, Migration/Backward-Compatibility, Entitlement Rollout Strategy, CRM Integration, a 5-module Integration Matrix, ADRs, Technical Unknowns, Implementation Sequencing (Phases A-G), Explicit Non-Goals, Constitution Compliance, Complexity Tracking; a required 40-item `plan.md` table of contents; supporting artifact requirements (research.md, data-model.md, contracts/, quickstart.md); a 26-item final cross-check; and an 18-item final output report format. Full verbatim text preserved in the conversation transcript for this turn.]

Followed by the standard `/sp.plan` command outline: run `setup-plan.sh --json`, load spec.md + constitution.md, fill Technical Context/Constitution Check, Phase 0 research.md, Phase 1 data-model.md/contracts/quickstart.md, update agent context via `update-agent-context.sh claude`, re-check Constitution Check, stop before `/sp.tasks`.

## Response snapshot

**Tooling note**: `setup-plan.sh`'s branch-name regex (`^[0-9]{3}-`) rejected `009a-platform-admin` due to the trailing letter — a narrow pre-existing gap (the same file's own `find_feature_dir_by_prefix()` fallback logic resolves the path correctly for non-standard prefixes; only the stricter `check_feature_branch()` hard-fails). Per the explicit "do not change branches or Git history" instruction, manually replicated exactly what the script would have produced (computed `FEATURE_DIR=specs/009a-platform-admin`, copied `plan-template.md` via the same `cp` step) rather than touching the script or the branch.

**Repository reconnaissance**: dispatched three parallel Explore agents (backend auth/RBAC/audit/migrations; feature-toggle/module-pattern across all 5 modules; frontend CompanyContext/routing/API-client) to gather cited, verified facts rather than assumptions. Key findings: `CurrentUser.roles` is confirmed permanently `[]` (all `super_admin` checks are dead code); "Better Auth" is a naming placeholder over a hand-rolled JWT+session system; `get_current_user()` never checks session revocation on any request (critical gap for the suspension requirement); tenant RBAC's `Permission`/`RolePermission` tables exist but aren't enforced (rank-based checks are what's actually wired); three audit-log tables exist with three different commit semantics, only Accounting's is genuinely fail-closed; only 3 of 5 modules (Inventory, Sales, Purchase) actually have the feature-toggle authorization gap — Accounting and CRM are already patched; `CompanyContext.tsx`'s Provider is scoped only to the `(companies)` route group, while `erp_active_company_id` itself (the localStorage key) is the true canonical value read directly by every other module; the existing `/admin/companies` admin surface is doubly broken (dead backend guard + wrong frontend function) and explicitly not fixed by this Epic.

**Wrote `plan.md`** (42 numbered sections, following this project's own established deep-plan convention from `009-crm`/`008-accounting-finance` rather than the shallow generic template) covering: full Constitution Check (10/10 pass); complete cited Current-State Findings (§3, 17 subsections); Platform identity/session design (shared `User` credentials + separate `PlatformAdministrator`/`PlatformSession`/distinct JWT `typ` claim); genuinely-enforced Platform RBAC (deliberately not mirroring tenant RBAC's inert pattern); an idempotent Alembic-migration bootstrap mechanism; a resolved session-revocation design (adding an `is_revoked` check to `get_current_user()` — the plan's single most consequential technical decision, since without it "actively revoke sessions" would be data-correct but functionally inert); Plan/Subscription/Capability/Entitlement/Quota/Override architecture reusing the 5 existing feature-flag tables unmodified; a fail-closed audit design following the Accounting module's existing precedent; support-access scope structurally incapable of reaching business records; a full data model (18 new entities, none blindly created — explicit "not created" rationale for 3 candidate items); an evidence-based 5-module integration matrix; a security threat table; a staged entitlement-rollout strategy (seed → bulk-assign baseline plan to existing tenants → verify → only then activate enforcement, so no existing tenant loses access); 10 ADRs; and a 26-item final cross-check, all passing.

**Supporting artifacts**: `research.md` (5 Decision/Rationale/Alternatives entries for the plan's genuine technical unknowns), `data-model.md` (full field-level detail for all 18 entities across 6 migration groups), `contracts/platform-admin-v1.yaml` (lightweight OpenAPI contract — paths/methods/permissions fixed, request/response schemas deliberately deferred to Tasks-phase), `quickstart.md` (10-step verification walkthrough for once implementation exists, including the critical suspend-with-still-valid-token revocation proof).

Ran `.specify/scripts/bash/update-agent-context.sh claude` (Phase 1 step 3) — updated `CLAUDE.md`'s "Recent Changes"/"Active Technologies" sections mechanically, matching the exact unedited convention already used for every prior epic's entries.

## Outcome

- ✅ Impact: Epic 9A now has a complete, repository-grounded technical plan — every architectural decision traces to either a cited existing-code fact or an explicit rationale/alternatives-considered analysis, not invented architecture. Zero Specification business decisions were reopened or changed. The plan resolves the one architecturally load-bearing technical unknown (session revocation enforcement) that the Specification's own resolved OQ-3 decision depends on to be genuinely true rather than just data-correct.
- 🧪 Tests: N/A — planning-only phase, no code/migrations/tests written, per explicit instruction.
- 📁 Files: `specs/009a-platform-admin/{plan.md, research.md, data-model.md, quickstart.md, contracts/platform-admin-v1.yaml}` (all new), `CLAUDE.md` (mechanical agent-context update), this PHR.
- 🔁 Next prompts: `/sp.tasks` (not started, per explicit instruction) once the Product Owner reviews this plan.
- 🧠 Reflection: The three-parallel-Explore-agent reconnaissance pass was the highest-leverage step — several of the plan's most important decisions (session revocation is currently unenforced anywhere; only 3 of 5 modules have the toggle-auth gap, not all 5; "Better Auth" isn't a real dependency; CompanyContext's Provider is narrowly scoped) would have been wrong assumptions if planned from the spec text alone, and each directly changed a concrete design choice (ADR-6, §14's scope, §6's identity design, §15's context strategy) rather than being incidental color.

## Evaluation notes (flywheel)

- Failure modes observed: `setup-plan.sh`'s branch regex tooling gap (worked around without modifying the script or branch, per instruction); no other failures.
- Graders run and results (PASS/FAIL): self-graded 26-item final cross-check (plan.md §42) — 26/26 PASS; Constitution Check (§1) — 10/10 PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
