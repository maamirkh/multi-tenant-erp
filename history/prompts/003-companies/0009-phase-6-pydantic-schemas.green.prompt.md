---
id: "0009"
title: Phase 6 Pydantic Schemas
stage: green
date: 2026-07-15
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: Muhammad Amir
command: /sp.implement
labels: ["phase-6","schemas","pydantic-v2","companies","validation","masking"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/companies/schemas/company.py
  - backend/modules/companies/schemas/address.py
  - backend/modules/companies/schemas/settings.py
  - backend/modules/companies/schemas/status.py
  - backend/modules/companies/schemas/audit.py
  - backend/modules/companies/schemas/__init__.py
  - specs/003-companies/tasks.md
tests:
  - Checkpoint verification script (5/5 PASS)
  - Full regression: 409 tests PASS
---

## Prompt

/sp.implement

Epic 3 - Companies, Phase 6: Pydantic Schemas

Implement ONLY Phase 6 tasks (T026–T030).

## Response snapshot

Implemented T026–T030 in parallel:

- **T026 `company.py`**: `CreateCompanyRequest` (required: legal_name 2-255, email; optional: trade_name, phone_primary E.164, country ISO 3166, default_currency ISO 4217 default USD, default_language BCP47 default en-US, default_timezone IANA default UTC, slug); `UpdateCompanyRequest` (all optional, adds phone_secondary, website, tax_number, registration_number, business_category, business_type, incorporation_date, fiscal_year_start_month, date_format, brand_color hex, tagline, confirm_currency_change bool); `CompanyResponse` (id, legal_name, trade_name, slug, status, owner_id, email, country, default_currency, default_language, default_timezone, created_at, updated_at); `CompanyDetailResponse` with `.for_role(role)` serialiser that masks tax_number/registration_number to `"****"` for non-owner/admin/accountant/super_admin roles; `CompanyListItem` (compact: id, legal_name, slug, status, country, default_currency, created_at).

- **T027 `address.py`**: `CreateAddressRequest`, `UpdateAddressRequest` (all fields optional for partial update), `CompanyAddressResponse` — all address fields with ISO 3166 country validation.

- **T028 `settings.py`**: `UpdateSettingsRequest` (dict payload; service validates keys), `CompanySettingsResponse` (company_id, settings dict, updated_at).

- **T029 `status.py`**: `DeactivateRequest` (reason str 1-1000), `DeleteCompanyRequest` (reason, force_delete=False, confirm_delete required must be True enforced via `@model_validator`), `ActivateResponse`, `DeactivateResponse`, `DeleteCompanyResponse` (id, status, deleted_at, message), `RestoreResponse`.

- **T030 `audit.py`**: `AuditLogEntryResponse` (all 10 audit log fields), `AuditLogListResponse = PaginatedResponse[AuditLogEntryResponse]`.

- **`__init__.py`**: Re-exports all 18 schema classes.

## Outcome

- ✅ Impact: Phase 6 complete — 5 schema files + updated __init__.py; 18 exported schema classes; all Phase 5 validators wired to field validators; sensitive field masking via for_role() method
- 🧪 Tests: All 5 checkpoints PASS; full regression 409/409 PASS; 0 lint errors
- 📁 Files: 6 files created/modified
- 🔁 Next prompts: Run `/sp.implement` for Phase 7 (Domain Services — T031–T038)
- 🧠 Reflection: The `for_role()` pattern on `CompanyDetailResponse` keeps masking logic in the schema layer rather than the HTTP layer — clean separation. `AuditLogListResponse = PaginatedResponse[AuditLogEntryResponse]` is a clean type alias that avoids a wrapper class.

## Evaluation notes (flywheel)

- Failure modes observed: ruff I001 (import sort in __init__.py), F401 (unused Literal import in company.py), UP037 (quoted annotation in status.py) — all auto-fixed with --fix
- Graders run and results (PASS/FAIL): ruff PASS, checkpoint verification 5/5 PASS, regression 409/409 PASS
- Prompt variant (if applicable): null
- Next experiment: Add a pytest parametrize test that calls for_role() with each role and verifies masking behaviour — catches regressions when role list changes
