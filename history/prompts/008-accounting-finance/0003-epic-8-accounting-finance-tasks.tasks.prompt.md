---
id: "0003"
title: "Epic 8 Accounting Finance Tasks"
stage: tasks
date: 2026-08-05
surface: agent
model: claude-sonnet-4-6
feature: 008-accounting-finance
branch: 008-accounting-finance
user: architext
command: /sp.tasks
labels: ["accounting","finance","tasks","general-ledger","posting-engine","ar","ap","banking","payments","tax","multi-currency","cost-centers","epic-8","implementation-roadmap"]
links:
  spec: specs/008-accounting-finance/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/008-accounting-finance/tasks.md
tests:
  - "N/A — task generation stage; no tests generated"
---

## Prompt

# =============================================================================
# DevSphere ERP
# Epic 8 – Accounting & Finance
# Official Enterprise Implementation Tasks (tasks.md)
# =============================================================================

## ROLE

Act as a Principal ERP Architect, Enterprise Solution Architect,
Chief Financial Systems Architect, ERP Domain Expert,
Staff Software Engineer, DDD Expert,
Enterprise SaaS Architect, Engineering Manager,
Technical Lead and Enterprise Technical Writer.

Generate the OFFICIAL implementation roadmap (tasks.md)
for Epic 8 – Accounting & Finance.

This document becomes the official implementation guide
used by Claude Code.

It must align with:

✓ Engineering Constitution

✓ Approved Epic 8 spec.md

✓ Approved Epic 8 plan.md

✓ Approved Epics 0–7

Generate ONLY implementation tasks.

Never generate:

- Code
- SQL
- APIs
- Folder Structure
- Class Names
- Function Names
- Pseudo Code

This document is implementation planning only.

[...full prompt as submitted via /sp.tasks — 19 phases, 321 tasks covering all accounting domains from Chart of Accounts through AI Readiness and Testing Validation]

## Response snapshot

Generated the OFFICIAL enterprise-grade tasks.md for Epic 8 — Accounting & Finance.

**Artifacts Created:**
- `specs/008-accounting-finance/tasks.md` — 321-task implementation roadmap

**Task Summary:**
- **Total Tasks**: 321 (T001–T321)
- **Total Phases**: 19 (Phase 0–Phase 18)
- **User Stories**: 16 (US1–US16)

**Task Count by Phase:**
- Phase 0 — Architecture Preparation: 15 tasks (T001–T015)
- Phase 1 — Chart of Accounts [US1]: 34 tasks (T016–T049)
- Phase 2 — General Ledger [US2]: 18 tasks (T050–T067)
- Phase 3 — Posting Engine [US3]: 21 tasks (T068–T088)
- Phase 4 — Journal Entries [US4]: 26 tasks (T089–T114)
- Phase 5 — Fiscal Management [US5]: 17 tasks (T115–T131)
- Phase 6 — Accounts Receivable [US6]: 24 tasks (T132–T155)
- Phase 7 — Accounts Payable [US7]: 19 tasks (T156–T174)
- Phase 8 — Bank Management [US8]: 17 tasks (T175–T191)
- Phase 9 — Cash Management [US9]: 12 tasks (T192–T203)
- Phase 10 — Payment Management [US10]: 20 tasks (T204–T223)
- Phase 11 — Tax Engine [US11]: 23 tasks (T224–T246)
- Phase 12 — Multi-Currency [US12]: 8 tasks (T247–T254)
- Phase 13 — Cost Accounting [US13]: 17 tasks (T255–T271)
- Phase 14 — Financial Statements [US14]: 14 tasks (T272–T285)
- Phase 15 — Financial Controls [US15]: 8 tasks (T286–T293)
- Phase 16 — Financial Intelligence [US16]: 9 tasks (T294–T302)
- Phase 17 — Integration Readiness: 7 tasks (T303–T309)
- Phase 18 — Testing, Validation & Epic Closure: 12 tasks (T310–T321)

**Parallelizable Tasks**: 187 tasks marked [P] (independent file-level parallelism)

**Critical Path**: Phase 0 → Phase 1 (COA) → Phase 2 (GL) → Phase 3 (PostingEngine) → Phase 4 (Journals) → Phase 5 (Fiscal) → Phase 6–13 (concurrent AR/AP/Banking/Cash/Payments/Tax/FX/Cost) → Phase 14 (Statements) → Phase 15–18 (Controls/Intelligence/Integration/Testing)

**PostingEngine Phase** (Phase 3, T068–T088): Most critical phase — 21 tasks documenting all 9 posting paths, 7 validation steps, dual-layer balance enforcement, period lock checks, audit trail synchronization, and integration event handler registration.

**Key Architecture Invariants in Tasks:**
- T068: PostingEngine domain service as single GL gate — no direct DB writes to journal_lines
- T074: Dual-layer balance validation — app-layer + DB constraint
- T075: Append-only GL — no UPDATE/DELETE ever on accounting_journal_lines
- T080: All integration event handlers (sales.invoice.posted, purchase.bill.posted, inventory.adjustment.posted) call PostingEngine exclusively

**Constitution Check: ALL 18 PRINCIPLES COVERED across all 321 tasks**

## Outcome

- ✅ Impact: 321 implementation tasks created across 19 phases. 16 user stories mapped. 187 parallelizable tasks identified. Critical path from Architecture Preparation through PostingEngine to Financial Statements documented. Full migration sequence 034–047 covered. All accounting domains (COA, GL, PostingEngine, Journals, Fiscal, AR, AP, Banking, Cash, Payments, Tax, Multi-Currency, Cost Centers, Financial Statements, Controls, Intelligence, Integration) included with exact file paths referencing backend/modules/accounting/, frontend/src/app/(protected)/(accounting)/, backend/tests/, and backend/migrations/versions/.
- 🧪 Tests: N/A — task generation stage; test tasks included within Phase 18 (T310–T321) and per-phase test tasks throughout
- 📁 Files: specs/008-accounting-finance/tasks.md
- 🔁 Next prompts: `/sp.implement` to begin executing tasks from tasks.md; start with Phase 0 Architecture Preparation tasks T001–T015
- 🧠 Reflection: The 321-task roadmap maintains strict alignment with PostingEngine-first strategy established in plan.md. The most critical insight preserved: Phase 3 (PostingEngine) must complete before any posting-related work in Phases 4–13. The parallelizable [P] markers allow efficient execution — up to 187 tasks can run concurrently within their phase boundaries. Phase 4 (PostingEngine) with 26 tasks is the most complex phase, correctly reflecting the architectural centrality of the GL gate. The task structure follows exactly the same format as Epic 7 sales tasks.md, enabling consistent AI-assisted implementation.

## Evaluation notes (flywheel)

- Failure modes observed: None — clear plan.md and spec.md provided full context; all 321 tasks generated without ambiguity
- Graders run and results (PASS/FAIL): Constitution Check — ALL 18 PRINCIPLES COVERED; Format Check — all tasks follow `- [ ] T### [P?] [US?] Description in file/path` pattern
- Prompt variant (if applicable): sp.tasks v1
- Next experiment (smallest change to try): Consider splitting Phase 3 (PostingEngine) into two sub-phases: 3a (core engine + validation) and 3b (integration event handlers) for safer incremental delivery
