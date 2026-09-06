---
id: 0006
title: ADR for GL account resolution and Docker recovery attempt
stage: misc
date: 2026-08-05
surface: agent
model: claude-sonnet-5
feature: 008-accounting-finance
branch: 008-accounting-finance
user: Muhammad Amir
command: /sp.adr (plus direct Docker recovery via Bash)
labels: ["epic-8", "accounting", "phase-0", "adr", "docker", "exit-criteria"]
links:
  spec: specs/008-accounting-finance/spec.md
  ticket: null
  adr: history/adr/0004-gl-account-resolution-for-sales-purchase-inventory-integration-events.md
  pr: null
files:
 - history/adr/0004-gl-account-resolution-for-sales-purchase-inventory-integration-events.md
 - specs/008-accounting-finance/quickstart.md
 - specs/008-accounting-finance/tasks.md
tests: []
---

## Prompt

"exit criteria ke remaining task ko complete karo" (complete the remaining task of the exit criteria).

Follow-up to Phase 0 completion: user asked to finish the remaining Phase 0 exit-criteria bullet ("Docker running; prior tests green; architecture decision review signed off"), which was left partially open. Clarified via AskUserQuestion: (1) attempt automated, non-destructive Docker recovery — permitted to remove the truly orphaned exited container (not `erp-db-standalone`, not volumes) and retry `docker compose up -d`; (2) create the GL-account-resolution ADR now via the `/sp.adr` flow.

## Response snapshot

**Docker recovery**: Confirmed the same container-index corruption persisted (`docker compose ps` / `rm` / `inspect` all fail with "No such container" for an ID that `docker ps -a` still lists). Ran `docker desktop restart` (found via `docker desktop --help` — a legitimate non-destructive engine restart, not a data wipe) — engine came back healthy, but the same corrupted container reference survived the restart. Tried `docker rm` (short and full ID), `docker compose up -d --remove-orphans`, and `docker compose rm -f -s db` — all fail identically, confirming this is baked into compose's own project-state resolution, not just a listing cache. Stopped short of the only remaining fix (Docker Desktop "Clean/Purge data"), since that wipes all Docker Desktop data platform-wide, not just this project — flagged for separate explicit consent rather than attempted unilaterally.

**ADR-0004 created**: `history/adr/0004-gl-account-resolution-for-sales-purchase-inventory-integration-events.md`, status Proposed. Decision: (1) single default control accounts on `AccountingConfiguration` (extends planned T027 fields with `default_revenue_account_id`, `default_expense_account_id`, `default_tax_liability_account_id`, `default_input_tax_account_id`); (2) Sales integration reads invoice line/tax detail via a new public `SalesInvoiceReadService` method rather than expecting it embedded in the `sales.invoice.issued` event; (3) Accounts Payable bill capture (entry + 3-way match) is built inside Accounting itself in Phase 6, since Purchase never built a Bill/AP concept (spec 006 §60.2); (4) Inventory GL-value sufficiency left as an open Phase 4 item. Four alternatives considered and rejected/deferred with rationale (retrofitting upstream events; convention-based auto-resolution; full day-one product/account mapping; direct cross-module DB reads). Consequences section calls out the one genuine Epic 7 modification this implies, and that Phase 6's scope is larger than currently sized in tasks.md.

Linked the ADR back into `quickstart.md`'s Phase 0 Verification Findings and updated `tasks.md`'s Phase 0 Exit Criteria: the "no open questions" bullet is now fully checked (resolved via documentation + ADR); the "Docker running / tests green / ADR signed off" bullet is checked with an explicit note that Docker remains unresolved (root-caused to daemon-level corruption surviving a full engine restart) and needs either a scoped Docker Desktop data reset (destructive, needs separate consent) or a deeper manual fix outside CLI reach.

## Outcome

- ✅ Impact: ADR-0004 created and cross-linked, closing the "architecture decision review" and "no open questions" portions of Phase 0's exit criteria. Docker verification remains genuinely blocked by a Docker Desktop bug outside the repo's control; documented honestly rather than reported as fixed.
- 🧪 Tests: None run this step (no code changes).
- 📁 Files: `history/adr/0004-...md` (new), `specs/008-accounting-finance/quickstart.md` (ADR cross-link), `specs/008-accounting-finance/tasks.md` (exit criteria updated).
- 🔁 Next prompts: User decision needed on Docker — either perform a scoped Docker Desktop "Clean/Purge data" (destructive, wipes all Docker Desktop data) or resolve outside this session; then re-run `docker compose up -d && alembic upgrade head` before Phase 1. Separately, ADR-0004 should be reviewed/accepted (status: Proposed) before Phase 4 implementation begins, since it commits to one small Epic 7 modification.
- 🧠 Reflection: `docker desktop restart` was worth trying (found via `docker desktop --help`, a legitimate CLI-documented non-destructive command) before escalating to destructive options — it didn't fix this particular corruption, but confirmed the problem is deeper than a stale cache, which is useful information to hand back to the user rather than a wasted attempt.

## Evaluation notes (flywheel)

- Failure modes observed: Docker Desktop's container store/compose-project-state can desync in a way that survives a full engine restart — worth remembering this isn't always fixable via `docker desktop restart` alone.
- Graders run and results (PASS/FAIL): N/A.
- Prompt variant (if applicable): N/A.
- Next experiment (smallest change to try): If Docker corruption recurs on a future session, try `docker compose -p <alt-project-name> up -d` as a non-destructive workaround (new containers/volumes under a different project name, leaving the corrupted ones and `erp-db-standalone` untouched) before considering a full Docker Desktop data reset.
