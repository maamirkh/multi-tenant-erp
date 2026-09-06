---
id: "0002"
title: "Epic 8 Accounting Finance Implementation Plan"
stage: plan
date: 2026-08-05
surface: agent
model: claude-sonnet-4-6
feature: 008-accounting-finance
branch: 008-accounting-finance
user: architext
command: /sp.plan
labels: ["accounting","finance","plan","general-ledger","posting-engine","ar","ap","banking","payments","tax","multi-currency","epic-8"]
links:
  spec: specs/008-accounting-finance/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/008-accounting-finance/plan.md
  - specs/008-accounting-finance/research.md
  - specs/008-accounting-finance/data-model.md
  - specs/008-accounting-finance/quickstart.md
  - specs/008-accounting-finance/contracts/events.md
  - CLAUDE.md
tests:
  - "N/A — planning stage; no tests generated"
---

## Prompt

Generate the OFFICIAL Technical Implementation Plan (plan.md) for Epic 8 – Accounting & Finance.

This document will become the implementation blueprint for developers. It must align with the Engineering Constitution, Approved Epic 8 spec.md, and Approved Epics 0–7.

The plan must describe HOW the Accounting domain will be implemented — components, interactions, dependencies, scalability, and future ERP module integration.

Key requirements: PostingEngine as single GL gate; double-entry enforcement; 12 implementation phases; DDD with 9 aggregate roots; AR/AP subsidiary ledger design; bank reconciliation; multi-currency with gain/loss; tax engine with jurisdiction adapters; financial statements (Balance Sheet, P&L, Cash Flow); performance targets (trial balance < 10s at 500K entries); AI readiness hooks; multi-tenant isolation; immutable audit trail.

Architecture: Modular Monolith, Clean Architecture, DDD, Repository Pattern, Service Layer, Docker First.

Do NOT generate Code, SQL, Database Schema, Folder Structure, APIs, or Pseudo Code.

## Response snapshot

Generated the OFFICIAL enterprise-grade Implementation Plan for Epic 8 — Accounting & Finance.

**Artifacts Created:**
- `specs/008-accounting-finance/plan.md` — 12-phase implementation plan
- `specs/008-accounting-finance/research.md` — 15 Phase 0 architecture decisions resolved
- `specs/008-accounting-finance/data-model.md` — 9 aggregates, state machines, entity relationships, 47 DB tables, migration strategy
- `specs/008-accounting-finance/quickstart.md` — developer quickstart guide
- `specs/008-accounting-finance/contracts/events.md` — 17 outbound + 8 inbound domain events with full payload schemas
- `CLAUDE.md` — updated with Epic 8 technology stack (APScheduler added)

**Key Architecture Decisions (research.md):**
1. PostingEngine as single GL gate — all 9 posting paths through one domain service
2. Append-only GL — structural immutability, no soft-delete on journal lines
3. Dual-layer balance validation — application (PostingEngine) + DB constraint/trigger
4. AR/AP allocation table pattern — separate allocation table, no running balance column
5. Statement-first bank reconciliation — statement lines are the reference
6. Tax engine with pluggable jurisdiction adapters — country-neutral by design
7. Transaction-time FX rate locking — IFRS-compliant; realized gain/loss at settlement
8. Period lock via InProcessEventBus — Sales/Purchase/Inventory notified synchronously
9. Real-time financial statement aggregation — no pre-computed statements
10. Synchronous audit trail — within same DB transaction as the financial action
11. Recurring journals via APScheduler — in-process, no Redis/Celery
12. COA hierarchy — company-scoped account codes; self-referencing parent FK
13. Cost center — optional per account (requires_cost_center flag); stored on GL line
14. Frontend — RSC for read-heavy reports; React Query + Client Components for interactive workflows
15. Advisory lock for gap-free journal numbering — same pattern as Epic 7 invoice sequencing

**12 Implementation Phases:**
- Phase 1: Foundation (currencies, config, sequences, feature flags)
- Phase 2: Chart of Accounts (hierarchy, templates, system accounts)
- Phase 3: Fiscal Calendar (fiscal years, periods, locks, opening balances, year-end close)
- Phase 4: General Ledger & PostingEngine (the critical phase — all posting paths built here)
- Phase 5: Accounts Receivable (customer ledger, aging, credit management, write-offs)
- Phase 6: Accounts Payable (supplier ledger, aging, reconciliation)
- Phase 7: Banking (multi-bank, reconciliation, cheques)
- Phase 8: Cash Management (cash accounts, petty cash)
- Phase 9: Payments (allocation engine, partial/advance/FX/WHT payments)
- Phase 10: Tax Engine & Cost Centers
- Phase 11: Financial Reporting (all statements, KPI dashboard)
- Phase 12: Integration, Contracts, Performance & Epic Closure

**Constitution Check: ALL 18 PRINCIPLES PASS**

## Outcome

- ✅ Impact: Complete 12-phase implementation plan created. 9 DDD aggregates defined. 15 architecture decisions resolved. 47 conceptual DB tables mapped (migrations 034–047). 17 outbound + 8 inbound domain events contracted. PostingEngine design documented as the single GL gate. Full integration strategy with Epics 2–7 and future Epics 9–12.
- 🧪 Tests: N/A — planning stage; test strategy documented in plan.md
- 📁 Files: plan.md, research.md, data-model.md, quickstart.md, contracts/events.md, CLAUDE.md
- 🔁 Next prompts: `/sp.tasks` to generate the task list for Epic 8 implementation
- 🧠 Reflection: Comprehensive 12-phase plan generated with clear PostingEngine-first strategy. The most critical architectural insight: every GL posting path (manual, Sales event, Purchase event, Inventory event, bank, cash, payment, reversal, recurring) flows through PostingEngine — this single invariant guarantees ledger integrity at the architectural level. Recurring journals via APScheduler is a simpler choice than Celery/Redis that matches the monolith architecture.

## Evaluation notes (flywheel)

- Failure modes observed: None — clear spec with well-defined accounting domain; all decisions resolved without ambiguity
- Graders run and results (PASS/FAIL): Constitution Check — ALL 18 PRINCIPLES PASS
- Prompt variant (if applicable): sp.plan v1
- Next experiment (smallest change to try): Consider adding a Phase 0.5 for PostingEngine spike/prototype before committing to full Phase 4 scope
