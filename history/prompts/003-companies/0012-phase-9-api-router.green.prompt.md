---
id: "0012"
title: Phase 9 API Router Integration Tests
stage: green
date: 2026-07-15
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: shehla83
command: /sp.implement
labels: ["phase-9","api-router","integration-tests","fastapi","companies"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - modules/companies/router.py
  - api/v1/router.py
  - modules/companies/__init__.py
  - modules/companies/services/company_audit_service.py
  - modules/companies/services/company_service.py
  - modules/companies/schemas/company.py
  - tests/integration/api/v1/companies/test_create_company.py
  - tests/integration/api/v1/companies/test_get_company.py
  - tests/integration/api/v1/companies/test_update_company.py
  - tests/integration/api/v1/companies/test_company_status.py
  - tests/integration/api/v1/companies/test_delete_restore.py
  - tests/integration/api/v1/companies/test_company_settings.py
  - tests/integration/api/v1/companies/test_company_logo.py
  - tests/integration/api/v1/companies/test_audit_log.py
  - tests/integration/api/v1/companies/test_superadmin_list.py
tests:
  - tests/integration/api/v1/companies/ (43/43 passed)
  - tests/ full regression (549/551 passed; 2 pre-existing failures in timezone validator)
---

## Prompt

/sp.implement — Epic 3 Companies, Phase 9: API Router (T042–T058)

## Response snapshot

Implemented Phase 9 in full:

**T042–T048** — Created `modules/companies/router.py` with 15 endpoints:
- POST "" (create), GET/{id}, PATCH/{id}, POST/{id}/activate, POST/{id}/deactivate
- DELETE/{id} (soft delete), POST/{id}/restore, PATCH/{id}/settings
- GET/{id}/addresses, POST/{id}/addresses, PUT/{id}/addresses/{addr_id}, DELETE/{id}/addresses/{addr_id}
- POST/{id}/logo, GET/{id}/audit-logs, GET /admin/companies

**T049** — Registered router in `api/v1/router.py`; updated `modules/companies/__init__.py`.

**T050–T058** — Created 9 integration test files (43 tests total).

**Bugs fixed during implementation:**
1. `company_audit_service.py`: `company_id` in both `data` dict and `repo.create()` kwarg → TypeError. Removed from dict.
2. `company_service.py`: `datetime.now(UTC) - company.deleted_at` failed when SQLite returns naive datetime. Added `.replace(tzinfo=UTC)` normalisation.
3. `company_service.py`: `update_company` missing BR-001 name uniqueness check. Added `exists_by_name(exclude_id=company_id)` guard.
4. `schemas/company.py`: `UpdateCompanyRequest` missing `slug` field → slug immutability test always returned 200. Added field + validator.
5. `router.py`: `POST "/"` caused 307 redirects → changed to `POST ""`.
6. `router.py`: `REQUEST_ID_CONTEXT.get(None)` returns string; SQLAlchemy UUID column rejects it → added UUID() conversion.
7. `router.py`: `body.model_dump(exclude_unset=True)` on create dropped Pydantic defaults (default_currency="USD") → changed to `model_dump()`.
8. `test_delete_restore.py`: `TestClient.delete(json=...)` not supported → used `client.request("DELETE", ...)`.
9. `test_delete_restore.py`: `pending_setup → deleted` is not a valid transition → added `_activate_company()` helper before each delete.
10. `test_company_settings.py`: `invoices_enabled`/`purchase_orders_enabled` not in ALLOWED_SETTINGS → replaced with `email_notifications_enabled`/`approval_workflow_enabled`.
11. `test_get_company.py`: name collision between `test_get_valid_company` and `test_no_auth_returns_401` (both defaulted to "Get Test Corp") → gave the second test a unique name "No Auth Corp".

## Outcome

- ✅ Impact: Phase 9 complete; 15 REST endpoints wired; all 43 integration tests green; 3 service/schema bugs fixed
- 🧪 Tests: 43/43 integration tests pass; 549/551 full suite (2 pre-existing timezone unit test failures unrelated to this phase)
- 📁 Files: 15 files created/modified
- 🔁 Next prompts: Phase 10 (T059–T073)
- 🧠 Reflection: SQLite naive-datetime vs UTC-aware subtraction is a recurring trap in test environments; the slug field omission from UpdateCompanyRequest was a silent data-loss bug (extra fields silently dropped by Pydantic v2 default)

## Evaluation notes (flywheel)

- Failure modes observed: SQLite timezone naivety, missing schema field, pending_setup→deleted invalid transition, TestClient.delete() missing json kwarg, request_id string→UUID type mismatch, model_dump(exclude_unset) dropping defaults, duplicate test data names causing cross-test contamination
- Graders run and results (PASS/FAIL): pytest integration 43/43 PASS; pytest full suite 549/551 PASS (2 pre-existing)
- Prompt variant (if applicable): null
- Next experiment: consider SQLAlchemy UTC type override for test DB to avoid naive-datetime bugs
