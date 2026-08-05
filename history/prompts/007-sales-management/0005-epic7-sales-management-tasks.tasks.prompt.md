---
id: "0005"
title: "Epic 7 Sales Management Tasks"
stage: tasks
date: 2026-07-30
surface: agent
model: claude-opus-4-6
feature: 007-sales-management
branch: 007-sales-management
user: shehla83
command: /sp.tasks
labels: ["sales-management", "o2c", "epic-7", "tasks", "implementation-roadmap"]
links:
  spec: specs/007-sales-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/007-sales-management/tasks.md
tests:
  - none
---

## Prompt

/sp.tasks Epic 7 – Sales Management: Generate the official enterprise implementation tasks (tasks.md) for the complete Order-to-Cash (O2C) domain. Must convert the approved specification and implementation plan into small, logical, independent, enterprise implementation tasks organized by phase and user story. Covers 19+ phases from Architecture Preparation through Customer Master, Pricing Engine, Quotations, Sales Orders, Approval Workflow, Inventory Reservation, Delivery Notes, Invoices, Returns, Intelligence, Integration, and Epic Closure. Every task must be independent, reviewable, testable, Docker-verifiable, and AI implementation-friendly.

## Response snapshot

Generated complete enterprise tasks.md for Epic 7 – Sales Management. Key deliverables:

- **244 tasks** across 11 phases (T001-T244)
- **11 User Stories** mapped to spec functional requirements and plan phases
- **Phase 0** (31 tasks): Module scaffold, feature flags, master data, sequence service
- **Phase 1** (30 tasks): Customer Master with full lifecycle, contacts, addresses, credit management, bulk import
- **Phase 2** (21 tasks): Pricing Engine with 7-level resolution, discount rules, margin guard
- **Phase 3** (22 tasks): Sales Quotations with revision history, validity, conversion to SO
- **Phase 4** (30 tasks): Sales Orders + Approval Workflow with credit check, auto-approval, self-approval prevention
- **Phase 5** (23 tasks): Delivery Notes with Epic 5 inventory integration (reservation, deduction, release)
- **Phase 6** (26 tasks): Sales Invoicing with gap-free sequencing, DN consolidation, PDF export
- **Phase 7** (20 tasks): Sales Returns with RMA workflow, inventory restock, credit notes
- **Phase 8** (18 tasks): Sales Intelligence with 25 reports, 12 KPIs, dashboard
- **Phase 9** (11 tasks): Integration contracts, event verification, OpenAPI, import/export
- **Phase 10** (12 tasks): Performance, security, RBAC matrix, E2E workflows, epic closure
- Every phase has exit criteria, Docker verification, and acceptance criteria
- Dependency graph and parallel execution opportunities documented
- MVP scope: Phase 0 + Phase 1 + Phase 2 (foundation before transactional documents)

## Outcome

- Impact: Complete O2C implementation roadmap ready for phase-by-phase execution
- Tests: N/A (planning document, no code)
- Files: 1 created (tasks.md)
- Next prompts: /sp.implement for Phase 0 execution
- Reflection: Consolidated user prompt's 19 phases into 11 aligned with plan.md; maintained Epic 6 task format (checkbox + ID + [P] + [US] + file path)

## Evaluation notes (flywheel)

- Failure modes observed: None — all design documents available and consistent
- Graders run and results (PASS/FAIL): Format validation PASS — all 244 tasks follow checklist format with checkbox, ID, file paths
- Prompt variant (if applicable): Standard /sp.tasks with enterprise prompt; user provided 19-phase breakdown consolidated to 11 phases matching plan.md
- Next experiment: Consider generating a separate checklists/tasks-validation.md for automated format checking
