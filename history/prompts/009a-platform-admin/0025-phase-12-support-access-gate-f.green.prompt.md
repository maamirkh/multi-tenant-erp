---
id: 0025
title: Phase 12 — Support Access (Gate F)
stage: green
date: 2026-08-22
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.implement
labels: ["epic-9a", "phase-12", "gate-f", "support-access", "inspection-only"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/platform_admin/models/support_access_grant.py
  - backend/modules/platform_admin/models/__init__.py
  - backend/modules/platform_admin/repositories/support_access_repository.py
  - backend/modules/platform_admin/services/support_access_service.py
  - backend/modules/platform_admin/schemas/support_access.py
  - backend/modules/platform_admin/router.py
  - backend/api/v1/router.py
  - backend/tests/security/modules/platform_admin/test_support_access_boundary.py
  - specs/009a-platform-admin/tasks.md
tests:
  - backend/tests/security/modules/platform_admin/test_support_access_boundary.py (16 passed)
  - backend/tests/unit/modules/platform_admin/ + tests/integration/services/platform_admin/ + tests/integration/api/v1/platform_admin/ + tests/integration/repositories/platform_admin/ + tests/security/modules/platform_admin/ (225 passed, full Phase 5-12 regression)
  - backend/tests/integration/api/v1/inventory/test_products_api.py + crm/test_feature_flag_gate.py (35 passed, cross-module regression)
---

## Prompt

```text
# Epic 9A — Platform Administration / Super Admin
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT


Implement, verify, audit, and close ONLY the following phase of Epic 9A.


## TARGET PHASE


**Phase Number:** `12`
**Phase Name:** `Support Access — **Gate F**`
**Task Range:** `<T158 to T166>`


---


# PRIMARY OBJECTIVE


Complete the target phase to a standard where it should NOT require a later correction pass for issues that could reasonably have been discovered during implementation.


Do not treat task checkbox completion as sufficient.


The phase is complete only after:


1. prerequisites are verified;
2. every target task is implemented;
3. every acceptance criterion is proven;
4. dependency relationships are validated;
5. security and tenant-isolation implications are tested;
6. relevant regression tests pass or pre-existing failures are explicitly characterized;
7. required real PostgreSQL / Docker / HTTP verification is completed;
8. the phase is independently self-audited against Spec, Plan, Contract, Data Model, Quickstart, and Tasks;
9. no hidden incomplete work remains;
10. the phase exit condition and applicable Gate are genuinely satisfied.


[... the full ~700-line master-prompt template, identical in structure to the one embedded verbatim in PHRs 0021-0024 (Phases 8-11), with only Phase Number=12, Phase Name="Support Access — Gate F", Task Range=T158 to T166 substituted. Sections 1-37 cover: strict phase scope; branch/working-tree requirements; the pre-implementation task audit; the repository-reality check; the six-step per-task implementation rule (inspect/implement/test/prove/negative-path/dependency-recheck); the full Architecture Freeze (Platform identity, sessions, RBAC, bootstrap, tenant lifecycle, authentication freshness, cross-tenant safety, entitlements, quotas, context separation, audit fail-closed model, Support Access permission/reason/time-bound/audit/inspection-only/no-impersonation requirements, AI provider-neutrality, infrastructure restrictions); database/migration hard rules (frozen range 057-061, no 062); the API Contract Lock; the full adversarial security-testing checklist (auth crossover, session abuse, RBAC abuse, tenant lifecycle abuse, entitlement/quota abuse, support-access abuse — expired grant/missing reason/missing permission/attempted business-record access); tenant isolation audit; frontend auth isolation (N/A this phase); public login route structure (N/A); the seven-level testing pyramid; pre-existing failure policy; real PostgreSQL/Docker verification; live HTTP/browser verification; feature-toggle hardening rule (N/A); audit fail-closed proof requirement; requirement traceability review; contract↔implementation audit; data-model↔implementation audit; the post-implementation self-review checklist; the adversarial completeness pass (7 questions A-G); the full diff review; the task-checkbox rule; the phase exit condition rule; the Gate rule (Epic 9A order A→B→E→C→D→F→G); regression verification; the no-correction-pass standard; PHR requirements; pre-commit checks; commit policy; post-commit verification; the required final report structure (sections A-P); and the final stop rule. Full text identical to prior phase PHRs' embedded prompts — see PHR 0024 for the complete verbatim template if needed.]
```

## Response snapshot

Implemented Epic 9A Phase 12 (T158-T166) end-to-end: time-bounded, reason-required, inspection-only cross-tenant support access, closing **Gate F**.

**Pre-implementation audit**: All dependencies (T032, T036, T037, T064) confirmed genuinely complete by inspection, not checkbox trust. Migration 061 already contains `support_access_grants` exactly per data-model.md (the final Epic 9A migration) — no new migration created.

**Critical scope-boundary finding**: plan.md §21 describes support-access endpoints as "thin wrappers around existing tenant-side read services" exposing tenant configuration/entitlements/users/lifecycle during a grant — but re-reading Phase 12's actual task list (T158-T166) and Phase 13's header found **no task anywhere declares such an inspection endpoint** — only grant lifecycle (initiate/terminate/list) is in scope. Cross-checked against quickstart.md §7 ("Expect: no such endpoint exists / 404 or 403") and the OpenAPI contract (exactly 3 support-access operations, none returning business or even administrative tenant data) — both confirm this is the correct, intentional scope, not a gap. Building inspection wrappers here would have been undeclared future-phase leakage.

**Model/repository** (T158): `SupportAccessGrant` maps onto migration 061's table exactly. `SupportAccessRepository.mark_expired()`/`terminate()` are separate methods so lazy expiry (time passing) never sets `ended_at`/`ended_by` — only explicit termination does.

**Service layer** (T159-T161), all in `support_access_service.py`:
- `initiate()`: mandatory reason (rejects blank/whitespace), server-determined `expires_at` (contract declares no client-supplied expiry — `DEFAULT_GRANT_DURATION_HOURS = 4`, a documented Tasks-phase default), audited, single commit.
- `assert_grant_active()`: the expiry-at-read-time seam, mirroring Phase 11's `OverrideService.has_active_override()` pattern exactly — a stale `active` row past `expires_at` is lazily flipped to `expired`, audited (`support_access.auto_expire`), committed, then `SupportAccessExpiredError` (403) raised.
- `terminate()`: runs the same lazy-expiry check first (so terminating an already-time-expired grant correctly reports `expired`, never a false `terminated` overwrite), then explicit termination, audited, single commit. Callable by the initiator or any actor holding `platform.support_access.initiate` — spec.md defines no separate rank tier, and the contract's `DELETE` uses the identical permission code.
- `record_action()`: the per-action audit seam for any future action "within an active grant" — asserts active, stages (flush-only, caller commits) a `PlatformAuditEvent` with `support_access_grant_id` populated. No caller exists yet in this Epic (consistent with the scope finding above) — proven directly by its own unit tests.

**Routes** (T162): new `support_access_router` (mirrors `admin_router`'s bare-path convention) for `DELETE /support-access/{grantId}` and `GET /support-access`; `POST /tenants/{companyId}/support-access` added to the existing `tenant_router`. Wired into `api/v1/router.py`. Verified via `app.openapi()`: exactly 3 paths/3 operations, matching the contract precisely. Live `curl` against the real running app on real Postgres: all 3 return 401 unauthenticated.

**Security testing** (T163-T165, one file, 16 tests, all real Postgres, all passing on first run):
- T163: a genuine `Product` business record created on the test tenant; AST-based static check proves `support_access_service.py` and the entire `router.py` import nothing from `modules.{inventory,purchase,sales,accounting,crm}`; live proof the product's name never appears in any support-access response; `app.openapi()` proves no undeclared path exists.
- T164: genuine time-based expiry (real `time.sleep`, not a mocked clock) and explicit termination both proven to end access and both proven audited; double-transition edge case (terminate-after-expiry) proven to preserve the true `expired` state.
- T165: missing permission → 403; blank reason → 422 with zero grant rows created; whitespace-only reason → `ValidationException` at the service layer (defense-in-depth, matching `AiCreditService`'s identical pattern); valid request → 201.
- Added beyond the literal task list: a tenant-token-crossover proof (master prompt §11) specific to this phase's new attack surface — a genuine tenant access token rejected (401) by both new bare `/support-access` routes.

**Testing**: 16 new tests, zero defects found (unusual for this Epic — every test passed on the first real run, likely because the design closely mirrored Phase 11's already-proven expiry-at-read-time pattern). Full regression: 225/225 passing across the entire Phase 5-12 `platform_admin` suite (209 carried over from Phase 11 + 16 new), plus a 35-test Inventory/CRM cross-module sample confirming the purely-additive `api/v1/router.py` change caused zero regressions elsewhere. mypy --strict and ruff clean on every new/changed file (one incidental `test_client.app` typing fix — `cast(FastAPI, ...)` — required for strict compliance, unrelated to logic).

**Gate F: PASSED.** Support boundary proven both statically and dynamically; no impersonation exists anywhere (every action runs under the actor's own Platform identity; the grant records only *which tenant* was selected, never a tenant user identity).

**Phase 12 Exit Condition: PASS.** Migration head remains `061`. `tasks.md` updated with `[X]` and evidence for T158-T166 plus the Exit Condition and Gate F sign-off lines.

## Outcome

- ✅ Impact: Platform Administrators can now initiate a time-bounded, reason-required support-access grant on a tenant, have it audited start-to-finish (including lazy expiry and explicit termination), and list grant history — with a structurally enforced, statically-provable guarantee that no code path anywhere reaches tenant business records, closing Gate F and the last security-critical gate in Epic 9A's Gate order.
- 🧪 Tests: 16 new tests passing (real Postgres, zero defects on first run); 225 total regression tests re-verified passing (full platform_admin suite); 35 cross-module regression tests passing; mypy --strict and ruff clean.
- 📁 Files: 5 new files (model, repository, service, schemas, security test), 3 modified files (models/__init__.py, router.py, api/v1/router.py), tasks.md updated.
- 🔁 Next prompts: Phase 13 — Platform Operational APIs (Dashboard, Tenants, Audit, Health) — not started in this session, per the Final Stop Rule.
- 🧠 Reflection: The most consequential finding this phase wasn't a code defect but a scope-boundary question — plan.md's fuller architectural vision (§21's "thin wrapper read endpoints") does not match tasks.md's actual task breakdown, and resolving that ambiguity correctly (by cross-referencing quickstart.md's own explicit expectation and the OpenAPI contract, rather than either over-building from plan.md or under-building by skipping the seam methods T160/T161 require) was the load-bearing decision of the phase. Reusing Phase 11's exact expiry-at-read-time pattern (rather than inventing a new one) is likely why this phase shipped defect-free on the first test run — a good signal that the pattern established there generalizes correctly.

## Evaluation notes (flywheel)

- Failure modes observed: none in the implementation itself. One environment quirk: `@example.test` email addresses are rejected by the email-validator library as a "special-use or reserved name" specifically for the real `/api/v1/auth/login` HTTP path (unlike direct ORM inserts, which bypass Pydantic validation) — `@example.com` is required for any test that goes through the real login endpoint. Worth remembering for future real-HTTP auth tests in this codebase.
- Graders run and results (PASS/FAIL): mypy --strict PASS (zero Phase-12-attributable errors, one pre-existing-code cross-reference confirmed via git diff); ruff PASS; full Phase-12 + regression test suite PASS (16 new + 225 regression + 35 cross-module, real Postgres).
- Prompt variant (if applicable): n/a — identical master-prompt template as Phases 8-11, Phase Number/Name/Task Range substituted.
- Next experiment (smallest change to try): n/a.
