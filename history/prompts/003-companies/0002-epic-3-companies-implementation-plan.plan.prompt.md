---
id: "0002"
title: "epic-3-companies-implementation-plan"
stage: plan
date: 2026-07-15
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: shehla83
command: /sp.plan
labels: ["plan", "companies", "multi-tenant", "epic-3", "architecture", "fastapi", "nextjs"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/003-companies/plan.md
tests:
  - "13 implementation phases defined with checkpoints"
  - "Testing strategy: unit, integration, security, performance, frontend"
---

## Prompt

Create the complete `plan.md` for Epic 3 – Companies. Generate a complete engineering implementation plan explaining HOW the specification will be implemented. Architecture: Clean Architecture, Modular Monolith, DDD, Repository Pattern, Service Layer, Dependency Injection. Stack: FastAPI, SQLAlchemy 2.x, PostgreSQL, Alembic (backend); Next.js, TypeScript, TanStack Query, React Hook Form, Zod (frontend). Docker First deployment. Sections required: Executive Summary, Technical Context, Architecture Strategy, Module Breakdown, Backend Folder Structure, Frontend Strategy, Frontend Folder Structure, Database Strategy, API Strategy, Security Strategy, State Management Strategy, Testing Strategy, Implementation Phases, Deployment Strategy, Observability, Risk Assessment, Definition of Done, Appendix.

## Response snapshot

Created `specs/003-companies/plan.md` — a comprehensive 17-section implementation blueprint:

- Constitution Check: All 18 gates PASS
- Architecture: 4-layer (API/Service/Repository/DB); 14-exception hierarchy; Transactional Outbox pattern; DI graph documented
- Module Breakdown: 9 packages (models, repositories, services, schemas, router, validators, events, exceptions, dependencies)
- Backend Folder Structure: Complete tree under `backend/modules/companies/`; new `core/events/` and `core/storage/` packages
- Frontend: 10 pages; CompanyContext; 14 React Query hooks; optimistic status updates; msw-mocked tests
- Database: 3 tables + event_outbox; UUID v4 app-generated; CI expression index; JSONB settings; 13 indexes
- Security: Tenant isolation via get_current_company_member(); sensitive field masking; MIME magic bytes validation; append-only audit at DB role level
- 13 Implementation Phases: sequential, dependency-ordered, with parallelization opportunities
- Definition of Done: 25 measurable criteria across backend, frontend, infrastructure, documentation
- 3 ADR suggestions surfaced

## Outcome

- ✅ Impact: Complete implementation blueprint for the Companies module — all 13 phases ready for /sp.tasks
- 🧪 Tests: 5 test layers defined; security tests include tenant isolation, permission matrix, sensitive masking, logo security, rate limiting
- 📁 Files: specs/003-companies/plan.md
- 🔁 Next prompts: /sp.tasks, /sp.adr shared-db-row-isolation, /sp.adr transactional-outbox-pattern, /sp.adr s3-object-storage
- 🧠 Reflection: Plan mirrors modules/auth/ pattern exactly for developer familiarity. Three significant ADRs flagged for stakeholder consent before tasks are generated.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): Constitution Check — all 18 gates PASS
- Prompt variant (if applicable): sp.plan v1
- Next experiment: Run /sp.tasks to generate atomic implementation tasks from this plan
