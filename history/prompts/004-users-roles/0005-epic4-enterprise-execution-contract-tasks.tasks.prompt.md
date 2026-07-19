---
id: "0005"
title: Epic 4 enterprise execution contract tasks
stage: tasks
date: 2026-07-17
surface: agent
model: claude-opus-4-6
feature: 004-users-roles
branch: 004-users-roles
user: shehla83
command: /sp.tasks
labels: ["tasks","enterprise","users-roles","execution-contract","implementation-roadmap","17-phases","148-tasks"]
links:
  spec: specs/004-users-roles/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/004-users-roles/tasks.md
tests:
  - "All 148 tasks follow checklist format (checkbox, ID, labels, file paths)"
  - "All 8 user stories mapped to phases with correct priorities"
  - "Dependency graph validated — no circular dependencies"
  - "All tasks have single responsibility"
---

## Prompt

Epic 4 Tasks Generation — Generate a production-grade enterprise execution contract (tasks.md) for Epic 4 Users & Roles. The document must be detailed enough that Claude Code can implement the entire Epic phase-by-phase without additional planning. Every task must be small, independent, reviewable, testable, and production-ready. Include: phase structure with business/technical objectives, task checklists with IDs and file paths, dependency management, testing strategy, quality gates, risk management, progress tracker, epic completion checklist, success metrics, and handoff criteria. Enterprise quality comparable to Microsoft, SAP, Oracle, Atlassian, Odoo Enterprise.

## Response snapshot

Generated comprehensive tasks.md with 148 tasks across 17 phases:

**Phase Structure**:
- Phase 1: Setup (6 tasks) — Module scaffolding and router registration
- Phase 2: Foundation (14 tasks) — Database migration, models, enums, constants, config, exceptions, events
- Phase 3: US1 Add Member P1 (19 tasks) — Repositories, MemberService, InvitationService, RoleSeedService, API
- Phase 4: US2 Manage Roles P1 (8 tasks) — Role assignment, rank enforcement
- Phase 5: US3 Custom Roles P2 (9 tasks) — Custom role CRUD, permission registry
- Phase 6: US4 Profile P2 (11 tasks) — ProfileService, PreferenceService, avatar upload
- Phase 7: US5 Lifecycle P2 (7 tasks) — State machine, session revocation
- Phase 8: US6 Search/List P2 (5 tasks) — Pagination, filters, search
- Phase 9: US7 Employee Info P3 (4 tasks) — Employee metadata
- Phase 10: US8 Role Details P3 (3 tasks) — Role/permission viewing
- Phase 11: FE Members (15 tasks) — 4 pages, 6 components, hooks
- Phase 12: FE Roles (12 tasks) — 4 pages, 4 components, hooks
- Phase 13: FE Profile (8 tasks) — 2 pages, 3 components, hooks
- Phase 14: FE Ownership (4 tasks) — Transfer page and dialog
- Phase 15: Integration (8 tasks) — Company integration, audit, events
- Phase 16: Security/Perf (6 tasks) — Isolation, rank, performance tests
- Phase 17: Polish (9 tasks) — Cleanup, docs, Docker, final verification

**Key Features**:
- Mermaid dependency diagrams (implementation flow + phase dependencies)
- Per-phase detail: purpose, objectives, scope, risks, deliverables, validation, testing, review checklist, completion criteria
- User story mapping table with backend/frontend phase cross-references
- Parallel execution opportunities identified per phase
- MVP strategy (US1 + US2 only), incremental delivery, and parallel team strategies
- Enterprise progress tracker with status legend
- Comprehensive epic completion checklist (19 categories)
- Success metrics table with 13 measurable targets
- Handoff criteria (13 conditions for Epic 5 readiness)

## Outcome

- Impact: Production-grade enterprise execution contract — 148 tasks across 17 phases covering all 8 user stories
- Tests: Format validation PASS (all tasks follow checklist format with ID, labels, file paths)
- Files: specs/004-users-roles/tasks.md
- Next prompts: /sp.analyze or /sp.implement
- Reflection: The tasks.md maintains strict alignment with spec.md (8 user stories, 74 FRs, 72 BRs) and plan.md (12 implementation phases expanded to 17 for granularity). Each phase ends in a working state with explicit completion criteria. The dependency graph ensures no task requires unfinished work.

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): Format validation PASS; dependency check PASS; spec alignment PASS
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): none
