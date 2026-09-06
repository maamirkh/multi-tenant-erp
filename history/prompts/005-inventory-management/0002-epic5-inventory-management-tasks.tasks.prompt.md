---
id: "004"
title: Epic 5 inventory management tasks
stage: tasks
date: 2026-07-20
surface: agent
model: claude-sonnet-4-6
feature: 005-inventory-management
branch: 005-inventory-management
user: shehla83
command: /sp.tasks
labels: ["inventory","tasks","epic-5","product-master","stock-ledger","warehouse","adjustments","transfers","alerts","reporting","events"]
links:
  spec: specs/005-inventory-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/005-inventory-management/tasks.md
tests:
  - none (tasks stage)
---

## Prompt

/sp.tasks — Generate OFFICIAL tasks.md for Epic 5 – Inventory Management. Convert the approved plan.md into a deterministic, phase-based execution roadmap. Every task must be small, independent, reviewable, testable, Docker-verifiable, and suitable for AI-assisted implementation. 13 implementation domains, 10 phases from spec. No code, no SQL, no folder structures — execution planning only. Tasks must be specific enough for LLM implementation without additional context.

## Response snapshot

Generated `specs/005-inventory-management/tasks.md` — a comprehensive 13-phase, 294-task execution roadmap for Epic 5.

**User Story Map**: 9 user stories extracted from spec functional requirements:
- US1: Product Master Core (P1) — FR-PM-001 to FR-PM-011
- US2: Product Master Enrichment (P2) — FR-PM-012 to FR-PM-018, bulk import/export
- US3: Warehouse Management — FR-WM-001 to FR-WM-008
- US4: Inventory Core & Stock Ledger — FR-IO-001 to FR-IO-011, FR-IO-015
- US5: Inventory Adjustments — FR-IO-012
- US6: Stock Transfers & Reservations — FR-WM-003, FR-WM-004
- US7: Inventory Intelligence & Alerts — FR-IO-013, FR-IO-014
- US8: Reporting Foundation — spec §32, §33
- US9: Integration Foundation & Domain Events — FR-CC-006, spec §31

**13 Phases**:
- Phase 0: Module Scaffold & Foundation (22 tasks) — EventBus, FeatureFlagService, base repository, audit integration, permission registry
- Phase 1: Master Data Foundation (31 tasks) — Category, Brand, UOM, Attributes, Tags, ReasonCode, CustomFieldDefinition
- Phase 2: Product Master Core P1 (34 tasks) — Product aggregate, Variants, Barcodes, lifecycle state machine, FTS search
- Phase 3: Product Master Enrichment P2 (24 tasks) — Images (S3), Tags, CustomFields, Notes, Keywords, Bulk Import/Export
- Phase 4: Warehouse Management (20 tasks) — Warehouse entity, Locations, Types, branch_id reserved
- Phase 5: Inventory Core & Stock Ledger (37 tasks) — StockPosition, StockMovement (immutable), WAC/FIFO strategies, Snapshots
- Phase 6: Inventory Adjustments (21 tasks) — State machine, approval workflow, feature flag bypass
- Phase 7: Stock Transfers & Reservations (24 tasks) — Two-step transfer, in-transit tracking, cancellation reversal, reservation API
- Phase 8: Inventory Intelligence (21 tasks) — ReorderRule, LowStockAlert, overstock flag, auto-resolve
- Phase 9: Reporting Foundation (25 tasks) — 14 reports, 10 KPIs, CSV/Excel export
- Phase 10: Integration Foundation (10 tasks) — 31 domain events, scanner API, OpenAPI contracts
- Phase 11: Performance & Optimisation (12 tasks) — Benchmarks, N+1 audit, index tuning, caching design
- Phase 12: Final Testing & Epic Closure (13 tasks) — E2E workflows, permission matrix, security review, 15 EC gates

**Total**: 294 tasks across 13 phases

## Outcome

- Impact: Official Epic 5 execution roadmap ready — all 294 tasks numbered T001–T294, dependency-ordered, with Phase exit criteria and quality gates
- Tests: none (tasks stage — test files are defined in task descriptions)
- Files: specs/005-inventory-management/tasks.md
- Next prompts: /sp.implement (Phase 0 first) or /sp.git.commit_pr to commit and push all Epic 5 design artifacts
- Reflection: Phase 5 (Inventory Core & Stock Ledger) is the highest-complexity phase with 37 tasks — correctly identified as the critical path. The dependency graph clearly shows that Phases 6–10 all block on Phase 5. The [P] markers identify significant parallel opportunities within each phase, particularly in frontend tasks which can run concurrent with backend tasks.

## Evaluation notes (flywheel)

- Failure modes observed: None — prerequisites check returned correct FEATURE_DIR; all design documents available; tasks.md written successfully on first attempt
- Graders run and results (PASS/FAIL): Format validation — all 294 tasks follow `- [ ] T### [P?] [US?] Description` format; dependency ordering verified; all phases have exit criteria; all phases have Docker verification task
- Prompt variant (if applicable): sp.tasks enterprise variant with 13 phases and 9 user stories
- Next experiment: Run Phase 0 via /sp.implement to validate that task granularity is correct for LLM execution — verify each task is completable as a single implementation prompt
