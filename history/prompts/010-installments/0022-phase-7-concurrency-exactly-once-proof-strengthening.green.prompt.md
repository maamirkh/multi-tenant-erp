---
id: 0022
title: Phase 7 concurrency exactly-once proof strengthening
stage: green
date: 2026-08-27
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: none
labels: [installments, epic-10, phase-7, collections, concurrency, accounting-integration, postgresql, verification]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/tests/integration/api/v1/installments/test_concurrent_collections.py
tests:
 - backend/tests/integration/api/v1/installments/test_concurrent_collections.py::TestConcurrentFullAmountCollections::test_exactly_one_of_two_concurrent_full_collections_succeeds
 - Phase-7 closure tests (4 files, 11 tests) — full run
 - full suite: backend/tests/integration/api/v1/installments/ + backend/tests/unit/modules/installments/ (157 passed)
 - full suite: backend/tests/unit/modules/accounting + integration/api/v1/accounting + integration/repositories/accounting + security/accounting (583 passed)
---

## Prompt

# Phase 7 — Final Concurrency Evidence Fix Only

Make ONE narrow test-only correction in:

`test_concurrent_collections.py`

Do NOT modify production code.
Do NOT start Phase 8.
Do NOT change architecture, migrations, or planning artifacts.

## Required fix

After the real-Postgres concurrent collection race, strengthen the Accounting assertions so they explicitly prove company-wide exactly-once effects.

Keep the existing assertions, but additionally query unconditionally by authoritative `company_id` and assert:

- exactly 1 `InstallmentAllocationReference`
- exactly 1 `Payment`
- exactly 1 `ARTransaction`
- exactly 1 `JournalEntry`

Do NOT rely only on:
- winning payment ID,
- winning journal ID,
- source_document_id,
- PK uniqueness,
- rollback inference from other tests.

The concurrency test itself must directly prove that no second ARTransaction or JournalEntry exists for the company.

Use fixture/test isolation carefully so unrelated rows cannot create false positives. If the test database contains baseline rows, scope by the smallest authoritative Phase-7 source/type/company criteria that still rules out duplicate financial effects without filtering down to the winning row itself.

## Verification

Run:

1. the strengthened concurrency test against real PostgreSQL;
2. all 4 Phase-7 closure test files;
3. full Installments regression;
4. full Accounting regression.

Report exact passed/failed/skipped counts.

If the stronger assertions expose a real duplicate financial-effect bug, STOP and report it before changing production code.

If all pass, commit the test-only fix and conclude exactly:

`PHASE 7 FULLY VERIFIED — COLLECTIONS FINANCIAL/IDEMPOTENCY BOUNDARY CLOSED — SAFE TO START PHASE 8`

Do not touch the existing untracked baseline files.

## Response snapshot

Closed the one gap identified in the prior verification pass (PHR 0021): `test_concurrent_collections.py`'s JournalEntry/ARTransaction assertions filtered by the winning payment's own id (`JournalEntry.id == winning_payment_journal_entry_id`, `ARTransaction.source_document_id == winning_payment_id`) — trivially true for any existing row via PK uniqueness, not an actual duplicate-detection proof.

Investigated the fixture (`conftest.py::build_active_contract_with_schedule`) to identify what baseline rows exist per company: `AccountsReceivableService.record_sales_invoice()` commits one pre-existing `ARTransaction` (`transaction_type="INVOICE"`, `source_document_type="SalesInvoice"`) and its own `JournalEntry` (`posting_source="SALES"`) as part of every test's fixture setup — confirmed via `ar_service.py`/`payment_service.py`/`allocation_engine.py` grep that a collection's own Payment-side rows are always tagged `posting_source="PAYMENT"` (JournalEntry) and `transaction_type="PAYMENT"` + `source_document_type="Payment"` (ARTransaction), giving an authoritative, non-ID way to exclude the invoice's baseline rows.

Added, after the existing assertions (kept intact, nothing removed):
- `select(InstallmentAllocationReference).where(company_id==...)` → `len == 1`
- `select(JournalEntry).where(company_id==..., posting_source=="PAYMENT")` → `len == 1`
- `select(ARTransaction).where(company_id==..., transaction_type=="PAYMENT", source_document_type=="Payment")` → `len == 1`

None of the three new queries filter by the winning row's own id — a genuinely broken lock leaving a second row behind would be caught.

Verified in sequence: the strengthened test alone (real Postgres) → 1 passed; all 4 Phase-7 closure files together → 11 passed; full Installments suite (integration+unit) → 157 passed; full Accounting suite (unit+integration+repository+security) → 583 passed. Zero failures, zero skips at every stage — no duplicate financial-effect bug was exposed. `pre-commit`'s `black` hook reformatted one long assert line's wrapping (whitespace-only) on first commit attempt; re-staged, re-ran the test to confirm the reformat changed nothing behaviorally, then committed clean.

Committed `462e14f` (test-only, 1 file, 57 insertions). Left the pre-existing untracked baseline files (spec-stage PHRs 0001–0008/0014, `specs/010-installments/*.md`, `checklists/`, `contracts/`) untouched throughout, per instruction. No production code, migrations, or planning artifacts touched.

## Outcome

- ✅ Impact: Phase 7's real-Postgres concurrency test now proves company-wide, ID-independent exactly-once Accounting effects for all four rows a collection touches (allocation reference, Payment, JournalEntry, ARTransaction) — the last gap from the prior verification pass is closed with equal rigor to the Payment check already in the same test and to `test_idempotency_replay_conflict.py`'s `_counts()` pattern.
- 🧪 Tests: strengthened test 1/1 passed; Phase-7 closure tests 11/11 passed; full Installments suite 157/157 passed; full Accounting suite 583/583 passed. 0 failed, 0 skipped across all four runs.
- 📁 Files: `backend/tests/integration/api/v1/installments/test_concurrent_collections.py` only (test-only, as scoped).
- 🔁 Next prompts: Phase 8 (Delinquency, T138–T153) is now clear to start per the user's own gating criteria.
- 🧠 Reflection: The fixture's own baseline invoice rows (committed in every test via `record_sales_invoice()`) were the actual reason the original assertions couldn't safely go fully unconditional without more care — the fix wasn't "remove the ID filter," it was "replace the ID filter with the correct type/source discriminator" (`posting_source`/`transaction_type`+`source_document_type`), which required reading `ar_service.py`/`payment_service.py`/`allocation_engine.py` to find the actual literal values Accounting's own code writes, not guessing them.

## Evaluation notes (flywheel)

- Failure modes observed: none — no test failures, no flaky reruns, no production-code bug surfaced by the stronger assertions.
- Graders run and results (PASS/FAIL): 4 real-Postgres pytest runs — PASS (1/1, 11/11, 157/157, 583/583).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
