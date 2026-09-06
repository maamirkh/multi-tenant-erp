---
id: 0030
title: Phase 13 Frontend Implementation
stage: green
date: 2026-09-03
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: [installments, frontend, phase-13, nextjs, tanstack-query]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/router.py
 - backend/modules/installments/constants.py
 - backend/modules/installments/schemas/base.py
 - backend/modules/installments/schemas/audit.py
 - backend/modules/installments/services/contract_service.py
 - backend/tests/security/installments/test_my_permissions_http.py
 - backend/tests/security/installments/test_contract_audit_and_status_filter_http.py
 - specs/010-installments/contracts/installments-api.yaml
 - specs/010-installments/tasks.md
 - frontend/src/lib/api/client.ts
 - frontend/src/lib/api/installments.ts
 - frontend/src/schemas/installments.ts
 - frontend/src/components/installments/apiErrors.ts
 - frontend/src/components/installments/InstallmentsStateBanner.tsx
 - frontend/src/components/installments/StatusBadge.tsx
 - frontend/src/hooks/installments/useInstallmentsPermissions.ts
 - frontend/src/hooks/installments/useContract.ts
 - frontend/src/hooks/installments/useContracts.ts
 - frontend/src/hooks/installments/useCreateContract.ts
 - frontend/src/hooks/installments/useSchedule.ts
 - frontend/src/hooks/installments/useCollections.ts
 - frontend/src/hooks/installments/useRecordCollection.ts
 - frontend/src/hooks/installments/useReverseCollection.ts
 - frontend/src/hooks/installments/useAuditHistory.ts
 - frontend/src/hooks/installments/useDelinquency.ts
 - frontend/src/hooks/installments/useContractLifecycleActions.ts
 - frontend/src/hooks/installments/useRescheduleContract.ts
 - frontend/src/app/(protected)/(installments)/layout.tsx
 - frontend/src/app/(protected)/(installments)/contracts/page.tsx
 - frontend/src/app/(protected)/(installments)/contracts/new/page.tsx
 - frontend/src/app/(protected)/(installments)/contracts/[contractId]/page.tsx
 - frontend/src/app/(protected)/(installments)/contracts/[contractId]/collect/page.tsx
 - frontend/src/app/(protected)/(installments)/contracts/[contractId]/reschedule/page.tsx
 - frontend/src/app/(protected)/(installments)/approvals/page.tsx
 - frontend/src/app/(protected)/(installments)/plans/page.tsx
 - frontend/src/app/(protected)/(installments)/configuration/page.tsx
 - frontend/src/app/(protected)/(installments)/installments-dashboard/page.tsx
 - frontend/src/app/(protected)/(installments)/reports/page.tsx
 - frontend/src/__tests__/installments/hooks/*.test.ts (12 files)
 - frontend/src/__tests__/installments/InstallmentsStateBanner.test.tsx
 - frontend/src/__tests__/installments/ContractDetailPermissionGating.test.tsx
tests:
 - backend/tests/security/installments/test_my_permissions_http.py (5 tests, real PostgreSQL)
 - backend/tests/security/installments/test_contract_audit_and_status_filter_http.py (3 tests, real PostgreSQL)
 - backend/tests/security/installments/ full directory regression (112 passed)
 - frontend/src/__tests__/installments/ (14 suites, 33 tests)
 - npx tsc --noEmit (0 errors)
 - npx eslint (0 errors)
 - backend ruff check (0 errors, 1 auto-fixed import-order)
---

## Prompt

# Epic 10 — Installments
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT
Target Phase: 13 — Frontend. Task range T214–T235. Feature branch 010-installments.
(Full 47-section master prompt supplied verbatim by the user via /sp.implement command
args — implement/test/verify/adversarial-review/regression-check/close only this phase,
strict scope, no future-phase leakage, hard-gate verification, full self-audit, PHR
required. See command-args in the session transcript for the complete text.)

## Response snapshot

Implemented Phase 13 (Frontend) in full: T214–T235, all 22 tasks.

**Two genuine planning/repository contradictions discovered and resolved (user-approved
via AskUserQuestion before proceeding, per master prompt §2's STOP rule):**

1. `useInstallmentsPermissions.ts` (T216) is specified to mirror `useCrmPermissions.ts`
   exactly, which depends on a `GET /crm/my-permissions` backend endpoint. No equivalent
   `GET /installments/my-permissions` endpoint existed anywhere (router, OpenAPI contract,
   or any of tasks.md's T001–T213). Added it — mechanical mirror of CRM's implementation,
   backed by a new `ALL_INSTALLMENTS_PERMISSION_CODES` constant derived from the existing
   `INSTALLMENTS_PERMISSIONS` tuple (avoids duplicating the CRM anti-pattern of a second
   literal list) and a new `InstallmentsMyPermissions` schema.

2. Two further gaps surfaced auditing T224 (Contract Detail's Audit-History section) and
   T227 (Approvals queue): no `GET /contracts/{id}/audit` endpoint existed even though
   `InstallmentAuditService.list_for_entity()` was already built and tenant-scoped; and
   `GET /contracts` had no `status` filter anywhere in router/service/repository despite
   the OpenAPI contract already documenting one. Fixed both — thin router wrapper for the
   first; threaded an existing `status` kwarg through `InstallmentContractService.list()`
   into the repository's pre-existing `list_filtered()` for the second (zero repository
   changes needed).

All three fixes are additive, tenant-scoped, and covered by new real-PostgreSQL HTTP
tests (5 + 3 = 8 new tests, all passing) before frontend work proceeded.

**Frontend delivered:** `installments.ts` API client (full endpoint surface incl. the
3 new endpoints), zod schemas, `useInstallmentsPermissions`/`useHasInstallmentsPermission`
(fail-safe), `apiErrors.ts`/`InstallmentsStateBanner`, `StatusBadge`, module layout,
12 TanStack Query hooks (contract CRUD, schedule, collections/reversal, audit history,
delinquency via client-filtered overdue report, full lifecycle-action mutation bundle,
reschedule), and 10 pages: contracts list/new/detail/collect/reschedule, approvals queue,
plans CRUD, configuration, dashboard, reports. Contract Detail is the operational center:
permission-gated lifecycle buttons per status (submit/approve/reject/activate/cure/
cancel/default/writeoff, each individually permission-checked, never a blanket gate),
stacked bordered sections (Terms/Schedule/Payments/Delinquency/Audit-History/Documents),
`LoadingState`/`PermissionDeniedState`/`ErrorState` from `platform-admin/DataState.tsx`.
Idempotency-Key header support added to `ApiClient` via a new `postWithHeaders()` method
(additive, no existing call site touched) since no module needed client-supplied
idempotency keys before Installments; every idempotency-protected mutation hook generates
a fresh key per invocation via `crypto.randomUUID()`.

Entitlement-disabled UI behavior (T232): `contracts/new`, `plans`, `configuration` render
`InstallmentsStateBanner`'s `featureDisabled` variant in place of form/list content;
Contract Detail and its collection/reversal actions stay fully reachable regardless
(backend-authoritative — `installments.collection.create` is SERVICING per
FR-INST-356, never blocked by disabled entitlement).

**Tests:** 12 hook test files (renderHook + mocked api-client, mirrors
`useCompany.test.ts` — placed under `src/__tests__/installments/hooks/` matching the
actual repo convention rather than the task's literal suggested colocated path),
banner variant test (3 states), and a permission-gated-buttons-hide (not disable) test
against the real Contract Detail page component. 33/33 frontend tests pass, 112/112
backend `tests/security/installments/` pass (zero regressions), tsc/eslint/ruff all
clean.

## Outcome

- ✅ Impact: Phase 13 (Frontend) complete — full Installments operational UI shipped;
  3 backend read-endpoint gaps closed (all user-approved, all additive/tenant-scoped).
- 🧪 Tests: 8 new backend HTTP tests (real Postgres) + 112 pre-existing security suite
  (zero regressions) + 33 new frontend tests; tsc/eslint/ruff all clean.
- 📁 Files: 4 backend files modified, 3 new (1 schema, 2 test files); 1 OpenAPI contract
  update; 1 shared frontend infra file modified (`client.ts`, additive); ~30 new frontend
  files (API client, schemas, hooks, components, pages, tests).
- 🔁 Next prompts: Phase 14 — Concurrency / Idempotency Hardening (NOT started this
  session, per master prompt's final-stop rule).
- 🧠 Reflection: Two of the three backend gaps were only discoverable by actually trying
  to wire the frontend to the documented contract — plan.md's frontend mapping table and
  the OpenAPI contract both already specified capabilities (my-permissions mirroring CRM;
  a status-filterable /contracts, per the contract's own summary line) that no backend
  phase had actually implemented. Worth flagging in future phase planning: cross-check
  frontend-consumed capabilities against the actual router surface before starting the
  frontend phase, not after.

## Evaluation notes (flywheel)

- Failure modes observed: `exactOptionalPropertyTypes: true` in tsconfig rejected
  `|| undefined` on API fields typed `T | null` — five call sites needed `|| null`
  instead; caught by `tsc --noEmit`, not by eslint or tests.
- Graders run and results (PASS/FAIL): tsc PASS, eslint PASS, ruff PASS, jest PASS
  (33/33), pytest PASS (112/112 + 8/8 new).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
