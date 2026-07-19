---
id: "0010"
title: Phase 7 Domain Services
stage: green
date: 2026-07-15
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: Muhammad Amir
command: /sp.implement
labels: ["phase-7","services","domain-events","outbox","logo","settings","audit"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/companies/events.py
  - backend/modules/companies/services/company_audit_service.py
  - backend/modules/companies/services/company_logo_service.py
  - backend/modules/companies/services/company_settings_service.py
  - backend/modules/companies/services/company_service.py
  - backend/modules/companies/services/__init__.py
  - backend/tests/unit/modules/companies/test_company_service.py
  - backend/tests/unit/modules/companies/test_company_logo_service.py
  - backend/tests/unit/modules/companies/test_company_settings_service.py
  - specs/003-companies/tasks.md
tests:
  - 78 new unit tests — 78/78 PASS
  - Full regression: 487 tests PASS
---

## Prompt

/sp.implement

Epic 3 - Companies, Phase 7: Domain Services

Implement ONLY Phase 7 tasks (T031–T038).

## Response snapshot

Implemented T031–T038:

- **T031 `events.py`**: 11 domain event dataclasses (`CompanyCreatedEvent`, `CompanyUpdatedEvent`, `CompanyActivatedEvent`, `CompanyDeactivatedEvent`, `CompanySuspendedEvent`, `CompanySuspensionLiftedEvent`, `CompanyDeletedEvent`, `CompanyRestoredEvent`, `CompanyPermanentlyPurgedEvent`, `CompanyLogoUploadedEvent`, `CompanyAdminChangedEvent`). Each implements `to_outbox_record(correlation_id, actor_id) -> OutboxRecord` (returns `OutboxRecord` object, not dict — the repository takes an object).

- **T032 `company_audit_service.py`**: `CompanyAuditService.record(*, company_id, actor_user_id, action, before_state, after_state, ip_address, request_id, user_agent) -> CompanyAuditLog` — thin wrapper that delegates to `CompanyAuditLogRepository.create()`.

- **T033 `company_logo_service.py`**: `CompanyLogoService` with `validate_file(file_bytes, filename) -> str` using raw magic-byte inspection (no python-magic dependency — not in pyproject.toml); `upload(file_bytes, company_id, mime_type) -> str`; `schedule_previous_cleanup(previous_url) -> None`. MIME detection covers PNG, JPEG, GIF, WebP, SVG. SVG content inspected for `<script>`, event handlers, `javascript:` URIs. Defined a local `_StorageProtocol` Protocol to avoid importing `core.storage.s3_client` at module load time (which would fail due to missing boto3).

- **T034 `company_settings_service.py`**: `CompanySettingsService` with `ALLOWED_SETTINGS` registry (15 keys), `validate_settings(updates) -> dict`, `merge_settings(existing, updates) -> dict`.

- **T035 `company_service.py`**: `CompanyService` with `create_company`, `update_company`, `activate_company`, `deactivate_company`, `soft_delete_company`, `restore_company`, `get_company`, `list_user_companies`, `list_all_companies`. All status transitions validated against spec §5.6 table. Slug derivation via `_derive_slug()` + auto-suffix on collision. Currency-change guard. 90-day restore window enforced. Required fields checked before activation.

- **T036–T038**: 78 unit tests across 3 files covering all business rules.

- **`__init__.py`**: Re-exports 4 service classes.

## Outcome

- ✅ Impact: Phase 7 complete — 5 service files + events.py + __init__.py; 78 new tests; all BR-001–BR-029 covered
- 🧪 Tests: 78/78 new tests PASS; full regression 487/487 PASS; 0 lint errors
- 📁 Files: 9 files created/modified + tasks.md updated
- 🔁 Next prompts: Run `/sp.implement` for Phase 8 (Authorization and Dependencies — T039–T041)
- 🧠 Reflection: Used `_StorageProtocol` Protocol to decouple logo service from boto3 import at module load time. Raw magic-byte MIME detection is actually more reliable than python-magic for testing because it has no OS library dependencies.

## Evaluation notes (flywheel)

- Failure modes observed: (1) F401 unused imports auto-fixed by ruff --fix; (2) slug suffix logic used double-check pattern consuming two exists_by_slug calls — fixed by setting slug to suffixed value before entering while loop; (3) boto3 ModuleNotFoundError from s3_client.py top-level import — fixed with local Protocol that avoids the import
- Graders run and results (PASS/FAIL): ruff PASS, 78/78 unit tests PASS, 487/487 full regression PASS
- Prompt variant (if applicable): null
- Next experiment: For T033, consider adding a GIF animation safety check (gilded GIFs with XSS via comment blocks) — low risk but worth noting
