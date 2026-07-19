---
id: "0008"
title: Phase 5 Validators and Exceptions
stage: green
date: 2026-07-15
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: Muhammad Amir
command: /sp.implement
labels: ["phase-5","validators","exceptions","pure-python","unit-tests","companies"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/companies/exceptions.py
  - backend/modules/companies/validators.py
  - backend/tests/unit/modules/companies/__init__.py
  - backend/tests/unit/modules/companies/test_company_validators.py
  - specs/003-companies/tasks.md
tests:
  - tests/unit/modules/companies/test_company_validators.py (38 tests PASS)
  - Full regression: 409 tests PASS
---

## Prompt

/sp.implement

Epic 3 - Companies, Phase 5: Validators and Exceptions

Implement ONLY Phase 5 tasks (T023–T025).

## Response snapshot

Implemented T023–T025:

- **T023**: `exceptions.py` — 14 exception classes, all inheriting `ApplicationException` from `core.exceptions.base`. Grouped by HTTP status: 400 (LogoTooLargeError, LogoInvalidFormatError, LogoInvalidContentError), 403 (CompanySuspendedError), 404 (CompanyNotFoundError), 409 (CompanyNameConflictError, SlugConflictError, InvalidStatusTransitionError, ActiveSubscriptionError), 410 (CompanyPurgedError), 422 (CompanyIncompleteError, SlugImmutableError, ForceDeleteRequiredError, CurrencyChangeWarningError). All error codes match spec.md §12.2 exactly. `CompanyIncompleteError` carries `missing_fields: list[str]` in `details`. No SQLAlchemy/FastAPI imports.

- **T024**: `validators.py` — 7 pure validator functions: `validate_iso_4217_currency` (180 ISO 4217 codes, normalises to uppercase), `validate_iana_timezone` (uses `zoneinfo.available_timezones()`), `validate_iso_3166_country` (249 ISO 3166-1 alpha-2 codes, normalises to uppercase), `validate_hex_color` (accepts 3 or 6 hex digits ±`#`, normalises to `#RRGGBB` uppercase, expands 3-digit shorthand), `validate_e164_phone` (regex `^\+[1-9]\d{1,14}$`), `validate_slug_format` (regex + consecutive-hyphen check), `validate_bcp47_language` (set of ~160 supported base-language and language-region tags).

- **T025**: `test_company_validators.py` — 38 unit tests across 7 test classes. Each validator: 2–3 valid cases + 3–4 invalid cases (wrong format, boundary, wrong type). All pass.

## Outcome

- ✅ Impact: Phase 5 complete — 14 exception classes with spec-exact error codes; 7 pure validators with normalisation; 38 unit tests covering valid and invalid paths for all functions
- 🧪 Tests: 38/38 unit tests PASS; full regression 409/409 PASS; 0 lint errors
- 📁 Files: 4 new files created, 1 existing file modified (tasks.md)
- 🔁 Next prompts: Run `/sp.implement` for Phase 6 (Pydantic Schemas — T026–T031)
- 🧠 Reflection: Pure-Python phases are fast and clean — no SQLite compatibility issues, no ORM dependencies. The frozen-set approach for country/currency validation gives O(1) lookup and is self-contained. The `zoneinfo` stdlib approach for timezones avoids a pytz/babel dependency.

## Evaluation notes (flywheel)

- Failure modes observed: ruff I001 import sort on all 3 new files — auto-fixed with `--fix`
- Graders run and results (PASS/FAIL): ruff PASS, pytest 38/38 PASS, regression 409/409 PASS, exception attribute verification PASS
- Prompt variant (if applicable): null
- Next experiment: Consider adding a test that verifies no SQLAlchemy/FastAPI symbols appear in the exceptions/validators modules (import-boundary enforcement)
