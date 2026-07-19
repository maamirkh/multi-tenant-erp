---
id: "0011"
title: Phase 8 Authorization Dependencies
stage: green
date: 2026-07-15
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: Muhammad Amir
command: /sp.implement
labels: ["phase-8","authorization","dependencies","fastapi","rbac","di"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/companies/dependencies.py
  - backend/tests/unit/modules/companies/test_company_dependencies.py
  - specs/003-companies/tasks.md
tests:
  - 21 unit tests — 21/21 PASS
  - Full regression: 508 tests PASS
---

## Prompt

/sp.implement

Epic 3 - Companies, Phase 8: Authorization and Dependencies

Implement ONLY Phase 8 tasks (T039–T041).

## Response snapshot

Implemented T039–T041:

- **T039 `dependencies.py`**: `get_company_service()` (wires all repos + sub-services), `get_company_audit_service()`, `get_company_logo_service()` (returns `CompanyLogoService` with `_NullStorageClient` stub — boto3 not in pyproject.toml), `get_current_company(company_id, current_user, service)` (fetches raw company via `service._company_repo.get_by_id()` to distinguish suspended from not-found; raises `CompanyNotFoundError`/`CompanySuspendedError`; enforces membership), `require_role(allowed_roles)`, `require_owner()`, `require_admin_or_above()`, `require_super_admin()`.

- **T040 RBAC note**: Documented Phase 1 simplification with `# TODO Epic-4: replace with company_members table lookup` comments in two locations. SuperAdmin determined by `"super_admin" in current_user.roles`. Ownership check is `company.owner_id == current_user.user_id`. No `is_superadmin` field was added to User/CurrentUser (neither accepts modification per protected files rule) — roles list used instead.

- **T041 `test_company_dependencies.py`**: 21 unit tests covering all 7 checkpoint scenarios plus edge cases. All guards tested by calling inner `_guard` functions directly with mock `CurrentUser` and `Company` objects — no FastAPI TestClient needed.

## Outcome

- ✅ Impact: Phase 8 complete — 1 dependencies file + 1 test file; 21 new tests; all Checkpoint 8 scenarios pass
- 🧪 Tests: 21/21 PASS; full regression 508/508 PASS; 0 lint errors
- 📁 Files: 2 files created + tasks.md updated
- 🔁 Next prompts: Run `/sp.implement` for Phase 9 (API Router — T042–T050)
- 🧠 Reflection: `get_current_company` must use `service._company_repo.get_by_id()` (not `service.get_company()`) because `get_by_id_active` excludes BOTH deleted AND suspended — without raw access we can't return the correct 403 COMPANY_SUSPENDED vs 404 distinction. The `_NullStorageClient` pattern cleanly defers boto3 dependency to Phase 9 wiring.

## Evaluation notes (flywheel)

- Failure modes observed: none — all 21 tests passed on first run; lint clean
- Graders run and results (PASS/FAIL): ruff PASS, 21/21 unit PASS, 508/508 regression PASS
- Prompt variant (if applicable): null
- Next experiment: When Epic 4 adds company_members, replace the two `# TODO Epic-4` locations in dependencies.py and update tests to cover non-owner members with admin role
