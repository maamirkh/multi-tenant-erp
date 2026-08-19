---
id: 0007
title: Epic 9A plan correction pass
stage: plan
date: 2026-08-19
surface: agent
model: claude-opus-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.plan
labels: ["platform-admin", "plan", "correction", "tenant-isolation", "entitlement", "bootstrap"]
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
 - history/prompts/009a-platform-admin/0007-epic-9a-plan-correction-pass.plan.prompt.md
tests:
 - none (planning-only correction pass; no code, migrations, or tests written)
---

## Prompt

Perform a TARGETED CORRECTION PASS on the existing Epic 9A `plan.md`.

[Full brief covering four blocking corrections and two clarifications, with an explicit preserve-list and a mandated final consistency pass:
**Correction 1** — entitlement must be enforced at point-of-use, not only at toggle mutation (a Plan downgrade leaving a stale enabled toggle would otherwise let a tenant keep using a denied module, since `require_crm_enabled` reads only the feature flag). 11 sub-requirements including CRM §35 update and 5 specific test cases.
**Correction 2** — reactivation must restore the pre-suspension status (`active→suspended→active`, `inactive→suspended→inactive`), with a durable persistence mechanism, atomic suspend transaction, and 6 test cases; must not infer previous state from logs/UI.
**Correction 3** — tenant suspension must not revoke access to other tenants; explicit instruction to perform repository reconnaissance of the session/auth model (what a Session represents, whether sessions are tenant-scoped, whether the JWT carries company context, how membership is checked per request) and NOT to retain the `UPDATE sessions WHERE user_id IN (company members)` approach unless evidence proves it correct; 8 requirements including 6 cross-tenant test cases; no Redis unless evidence demands it.
**Correction 4** — Platform Owner bootstrap must not silently succeed without creating an owner (the `if credentials missing: return` migration can be stamped applied while leaving a permanently unbootstrapped deployment); preferred direction is separating credential provisioning from irreversible migration versioning; 10 requirements including 6 bootstrap test cases and migration renumbering.
**Clarification 5** — canonical tenant-context abstraction: a defined accessor/contract fronting `erp_active_company_id`, not raw localStorage as the architectural contract; explicitly not permission to refactor all existing frontend modules.
**Clarification 6** — Platform API client / token separation: clarify structurally how token crossover is prevented, based on the actual `apiClient` implementation rather than assumption; 9 requirements.
Plus a preserve-list of ~30 already-correct decisions, a mandated stale-statement sweep for 8 specific contradiction patterns, and a 7-item final report. Full verbatim text in the conversation transcript for this turn.]

## Response snapshot

**Did not run `setup-plan.sh`** — it performs `cp plan-template.md → plan.md`, which would have destroyed the existing plan. Flagged and skipped deliberately; this was a correction pass, not initial generation.

**Reconnaissance first** (Corrections 3 and 6 explicitly demanded evidence over assumption). Read `core/auth/dependencies.py`, `auth/models/session.py`, `auth/models/user.py`, `auth/services/jwt_service.py`, `companies/dependencies.py`, `users_roles/dependencies.py`, `api/v1/router.py`, and `frontend/src/lib/api/client.ts` directly. Three findings materially changed the design:

1. **A `Session` has no tenant dimension** — `sessions` carries `user_id` only, no `company_id`; its own docstring calls it a device login for a human. The JWT carries no company claim. `User.company_id` is a documented nullable placeholder. Company context reaches a request *only* via the `{company_id}` path parameter. This proves the first draft's `UPDATE sessions WHERE user_id IN (members)` would sign multi-tenant users out of unrelated active companies.
2. **The five business modules never check company status** — all mount `get_current_company_member`, which reads only `CompanyMember.status`; only the `companies` module uses `get_current_company` (which does check suspension). So suspending a tenant today would not block `/inventory`, `/sales`, `/purchase`, `/accounting`, or `/crm` at all. The first draft's claim that "`CompanySuspendedError` already gives block-on-next-request for free" was true only for one module.
3. **`ApiClient`'s transport is injectable but its auth is not** — `buildHeaders()`/`postMultipart()` hardcode the tenant `getAccessToken()`, and the 401 branch hardcodes the tenant `acquireRefreshLock()`/`clearTokens()`/`session-expired` event. Reusing the singleton would attach tenant tokens to Platform requests and drive Platform 401s into the tenant refresh flow.

**Corrections applied** — Correction 1: new §13.1 introducing a mount-level `require_capability_entitled(...)` dependency on all five module routers as the primary enforcement point, with §14's mutation check demoted to a secondary guard; §35 rewritten so `require_crm_enabled` is preserved but explicitly insufficient alone. Correction 2: §9 restructured into §9.1–§9.3 with `companies.pre_suspension_status` + a CHECK constraint tying it to `status='suspended'`, and a domain CHECK limiting it to `active`/`inactive`. Correction 3: §10 rewritten end-to-end as company-scoped access invalidation (Layer 1 status enforcement closing the newly-found gap, Layer 2 an `access_invalidated_at` watermark compared against the token's `iat`), with §10.4 explicitly recording that global session revocation is out of scope and why. Correction 4: §7 replaced with a separate `python -m modules.platform_admin.bootstrap` command with a defined exit-code contract (non-zero on missing/invalid config), migration `062` deleted, deployment order documented.

**Clarifications** — §15 reframed as an accessor contract fronting the unchanged localStorage key, with a four-way table distinguishing UI selection state / authenticated identity / server-authoritative membership / Platform selected-tenant context; new §23.1 specifying an injected `AuthStrategy` and two configured `ApiClient` instances sharing one transport.

**Also resolved the two vague Tasks-phase deferrals** the brief forbade leaving open: the module-master-toggle question now has an explicit default rule (no master toggle → `enabled=True`, Plan ceiling alone governs), and the lifecycle concurrency mechanism is decided (`SELECT ... FOR UPDATE`, with rationale).

**Consistency sweep** across all six stale patterns plus ADR/risk/threat/test/checklist propagation. Caught and fixed two genuine self-contradictions introduced mid-pass: §3.1 still described the discarded `get_current_user()` change as "the central resolved Technical Unknown," and §10.4 claimed Epic 9A "does not modify that universal hot path" while §10.2 adds a `token_issued_at` field there — resolved by precisely scoping the latter as a pure data-passing change with no query and no new failure mode. Also synced `research.md` (Decisions 1, 3, 4 rewritten; 5 and 6 added), `data-model.md` (new `companies` columns section), and `quickstart.md` (bootstrap negative checks, cross-tenant suspension walkthrough, downgrade-bypass verification, token-separation checks, migration-creates-no-owner assertion).

ADRs grew from 10 to 13: ADR-3/6/8 revised, ADR-11 (API client), ADR-12 (pre-suspension persistence), ADR-13 (tenant-context accessor) added.

## Outcome

- ✅ Impact: All four blockers resolved with repository-evidence-backed designs rather than prompt-suggested mechanisms. The two most consequential outcomes are that tenant suspension no longer carries cross-tenant blast radius (and now actually works on the five business modules, which it previously would not have), and that a Plan downgrade can no longer be bypassed by a stale enabled feature toggle. No approved business requirement changed.
- 🧪 Tests: N/A — planning-only. Test *strategy* expanded substantially: entitlement matrix (6 scenarios × 5 modules), lifecycle round-trips including `inactive→suspended→inactive`, a 7-case cross-tenant isolation suite, 6 bootstrap cases, and 5 token-crossover cases.
- 📁 Files: `plan.md` (872→1096 lines), `research.md` (53→84), `data-model.md` (243→258), `quickstart.md` (92→124). `spec.md` and `constitution.md` untouched, as instructed.
- 🔁 Next prompts: `/sp.tasks` (not started, per instruction), after Product Owner review of the corrected plan — noting §10.4's mechanism refinement is flagged for explicit PO visibility.
- 🧠 Reflection: The brief's instruction to inspect the repository before choosing a mechanism was decisive — three of the four corrections landed on a *different* design than the prompt's own suggested direction implied, and finding #2 (business modules never check company status) was something neither the spec, the first-draft plan, nor the correction brief had noticed. Had I implemented the literal instruction ("suspension revokes sessions"), the result would have been simultaneously harmful to multi-tenant users and non-functional on the modules that matter most.

## Evaluation notes (flywheel)

- Failure modes observed: two self-introduced contradictions during the pass (stale §3.1 framing; §10.4 vs §10.2 on whether `get_current_user()` is modified) — both caught by the mandated consistency sweep rather than surviving into the deliverable, which is a good argument for the sweep being an explicit required step rather than assumed.
- Graders run and results (PASS/FAIL): six-pattern stale-statement sweep — PASS (all remaining matches verified as intentional "rejected/removed" records); ADR numbering integrity — PASS (13, sequential); §42 cross-check — PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
