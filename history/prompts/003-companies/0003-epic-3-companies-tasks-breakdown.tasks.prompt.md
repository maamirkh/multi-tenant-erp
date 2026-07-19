---
id: "0003"
title: "epic-3-companies-tasks-breakdown"
stage: tasks
date: 2026-07-15
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: shehla83
command: /sp.tasks
labels: ["tasks", "companies", "epic-3", "implementation-roadmap", "multi-tenant"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/003-companies/tasks.md
tests:
  - "124 tasks across 17 phases"
  - "17 checkpoint gates with Go/No-Go criteria"
---

## Prompt

Create the complete `tasks.md` for Epic 3 – Companies. Generate a complete implementation roadmap organized into sequential phases that minimize implementation risk, maximize testability, minimize merge conflicts, and allow Claude Code to work phase-by-phase. Each phase must have Objective, Scope, Deliverables, Dependencies, Files Expected To Change, Files That Must NOT Change, Database Impact, API Impact, Frontend Impact, Testing Requirements, Definition of Done, Exit Criteria, Implementation Notes, and a DO NOT IMPLEMENT boundary section. Recommended phases: Project Preparation, Database Models, Database Migrations, Repositories, Domain Services, Validation Layer, API Layer, Authorization Integration, Audit Logging, Frontend Foundation, Company Management UI, Company Settings, Integration Testing, Documentation, Performance Validation, Security Review, Epic Finalization.

## Response snapshot

Created `specs/003-companies/tasks.md` with 124 tasks across 17 phases:

- Phase 1 (T001–T008): Project Preparation — MinIO Docker service, env vars, core/events/, core/storage/, module skeleton
- Phase 2 (T009–T013): Database Models — Company, CompanyAddress, CompanyAuditLog SQLAlchemy models with enums
- Phase 3 (T014–T017): Database Migration — 003_companies.py with all 13 indexes; bidirectional upgrade/downgrade verified
- Phase 4 (T018–T022): Repositories — CompanyRepository, CompanyAddressRepository, CompanyAuditLogRepository with append-only enforcement; integration tests
- Phase 5 (T023–T025): Validators and Exceptions — 7 field validators, 14 exception classes, unit tests
- Phase 6 (T026–T030): Pydantic Schemas — 5 schema files including sensitive field masking serializer
- Phase 7 (T031–T038): Domain Services — CompanyService (full lifecycle, BR-001–BR-029), CompanyAuditService, CompanyLogoService (magic bytes MIME), CompanySettingsService; 90% branch coverage required
- Phase 8 (T039–T041): Authorization Dependencies — get_current_company, require_owner(), require_super_admin(); Phase 1 RBAC stub with Epic 4 TODO comments
- Phase 9 (T042–T058): API Router — all 14 endpoints; 10 integration test files; all AC-001–AC-012 covered
- Phase 10 (T059–T072): Frontend Foundation — TypeScript types, API client functions, 13 React Query hooks, CompanyContext with localStorage persistence
- Phase 11 (T073–T085): Company Management UI — 5 pages, 6 components, CreateWizard (4-step, Zod), status actions with optimistic updates
- Phase 12 (T086–T096): Company Settings UI — settings tabs, profile/regional/branding/preferences forms, logo upload with drag-drop, audit log page
- Phase 13 (T097–T103): Integration Testing — full test suite execution; AC traceability; event outbox completeness test
- Phase 14 (T104–T106): Documentation — quickstart.md, CLAUDE.md update, module README
- Phase 15 (T107–T110): Performance Validation — 10K seed, benchmark tests, EXPLAIN ANALYZE index verification
- Phase 16 (T111–T116): Security Review — 5 security test files; tenant isolation, permission matrix, sensitive masking, logo security, rate limiting; DB role audit log immutability
- Phase 17 (T117–T124): Epic Finalization — full regression, architecture audit, DoD verification (25 criteria), branch cleanup

Each phase has: explicit DO NOT IMPLEMENT boundary, checkpoint with Go/No-Go criteria, parallelization opportunities marked [P], user story labels [US1]–[US6].

## Outcome

- ✅ Impact: 124 atomic tasks providing a complete implementation roadmap; each phase is a standalone Claude Code session target
- 🧪 Tests: All security tests, integration tests, performance benchmarks, and frontend tests included as named tasks with specific file paths
- 📁 Files: specs/003-companies/tasks.md
- 🔁 Next prompts: /sp.implement (execute Phase 1), or /sp.adr for 3 flagged architectural decisions
- 🧠 Reflection: 17 phases mirror the 13 plan phases plus testing, documentation, performance, security, and finalization. DO NOT IMPLEMENT sections are the key safety feature for AI-assisted development.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): Format validation — all 124 tasks follow checkbox + ID + optional [P] + optional [US] + description with file path format
- Prompt variant (if applicable): sp.tasks v1
- Next experiment: Execute Phase 1 with /sp.implement to validate phase isolation works correctly
