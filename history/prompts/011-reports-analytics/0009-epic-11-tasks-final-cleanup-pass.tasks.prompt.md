---
id: 0009
title: Epic 11 tasks final cleanup pass
stage: tasks
date: 2026-09-12
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.tasks (final cleanup pass)
labels: ["reports-analytics", "tasks", "cleanup", "stale-references", "purchase-boundedness"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/011-reports-analytics/tasks.md
tests:
 - None executed (planning-only cleanup pass; no code/migrations created)
---

## Prompt

A 19-section governing correction brief titled "Epic 11 — Reports & Analytics: Final `tasks.md` Cleanup Pass Before T001" identified three remaining defects in the already-twice-corrected `tasks.md`, explicitly scoped as the final cleanup before implementation could begin — no redesign, no full rewrite, no global renumbering, no reopening settled architecture:

1. **Unresolved Purchase boundedness branch**: `T075`'s prior text still left an implementation-time architecture decision open for `purchase.pending_deliveries`/`purchase.vendor_returns` ("verify whether SQL-bounded; if yes add count sibling; if no keep full-fetch fallback"), while the Final Export Category Matrix simultaneously claimed "every list-shaped report except Installments `due_overdue`/`aging` is Category A" — the two statements couldn't both remain true with an open branch. Required fix: make the Epic 11 contract deterministic regardless of the repository's starting state — inspect current implementation as part of T075 itself, and if SQL-level bounded retrieval is missing, add it within that same task (preserving existing caller behavior via optional/default parameters) rather than falling back to full-fetch. End state: all six Purchase list reports (not just four) must be Category A, with zero full-fetch fallback remaining anywhere, for both online page-1 and export.

2. **Several stale task-ID references**, six specifically named (each pointing to a real task with the *wrong meaning*, not a nonexistent ID): Phase 1's "Saved View load built in Phase 3 (T085)" should say T140 (T085 is an unrelated Purchase structural test); Installments Phase 2's "execution integration is Phase 3 task T093" should say T126 (T093 is an unrelated Inventory registry task); T129's "Extended in Phase 6 (T176)" should say T212 (T176 is an unrelated Customer 360 test); T062's "Phase 6's orchestration concern (T175)" should say T190 (T175 is an unrelated Customer 360 test); T134's "their end-to-end tests are T177/T178" should say T199/T206 for `EXPORT_TOO_LARGE`/`EXPORT_AUDIT_FAILED` respectively (T177/T178 are an unrelated Gate and audit-log-model task); Execution Rule 7's source-seam task list "T060, T068, T075" should say "T047, T075, T087" (the actual final Accounting/Purchase/Inventory seam task IDs after the prior two correction passes). The brief additionally required a full semantic sweep of every `T\d{3}[A-Z]?` token beyond these six named cases — asking not just "does this ID exist" but "does it still mean what the prose claims, given everything that changed across the prior two correction passes."

3. **Stale AR/AP coverage-matrix mapping**: the Report Catalog Coverage Matrix's Accounting AR/AP row still mapped adapter work to `T052` (which, after the prior pass's Blocker-B fix, now handles only TB/PL/BS/CF/KPIs — the actual bounded AR/AP dispatch lives in `T053`) and still cited `T211` as an AR/AP test (which, after the same prior pass, now tests Installments `due_overdue`/`aging` exclusively, no longer AR/AP). Required fix: correct the adapter column to `T053`, remove `T211` from the AR/AP row's test list, and (implicitly, per the "recheck other coverage matrix rows" instruction) restore `T211` to wherever it now actually belongs.

The brief locked all previously-settled decisions as out of scope, required a final report in a specified format (Purchase final boundedness/category, each of the six stale-reference corrections individually reported, full reference audit result, AR/AP matrix confirmation, final export categories, file map, security regression confirmation, coverage, dependency audit, task count, verdict), and closed with a 17-item internal YES/NO checklist.

(The complete unabridged text was read and acted upon in full; compressed here since every item is individually traceable to a specific edit in the Response snapshot below.)

## Response snapshot

Located exact current text for every flagged item via targeted `grep` before editing (rather than a full re-read, to conserve context on a file that had already been read in full during the prior two passes) — confirmed the precise line-level content of `T075`, `T076`, `T079`, `T081`, `T082`, `T084`, `T188`, the Final Export Category Matrix, and all six named stale references before touching any of them.

**Purchase boundedness (Blocker 1)**: rewrote `T075`'s step 2 to require the deterministic end-state directly — "inspect as step one of this same task; if SQL-level `.limit()/.offset()` already exists, add a matching count sibling; if it does not, add it within this same task, then add the matching count sibling" — both branches converge on the identical required outcome, so no open architecture question survives past this task's completion regardless of what inspection finds. Propagated the fix through `T076` (regression test now explicitly names `pending_deliveries`/`vendor_returns`/`supplier_performance`), `T079` (adapter dispatch rewritten to treat all six list reports identically — the "full-fetch-then-Python-slice" branch removed from the method entirely), `T081`/`T082` (contract/equivalence tests now cover all six), `T084` (export seam — cheap-count pattern for all six, "no full-fetch-then-guard path exists anywhere in Purchase's export seam"), `T188` (Phase 6 Category A step lists all six explicitly), and the Final Export Category Matrix (removed the conditional "pending_deliveries/vendor_returns if T075's verification finds them SQL-bounded" line, replaced with an unconditional 6/6 statement).

**Six stale references**: corrected each exactly as specified — `T085→T140`, `T093→T126`, `T176→T212`, `T175→T190`, `T177/T178→T199/T206`, Execution Rule 7's `T060/T068/T075→T047/T075/T087` — each correction left an explicit inline note identifying what the old (wrong) ID actually refers to, so a future reader can see *why* it was wrong, not just that it changed.

**Full semantic sweep (not stopping at the six known cases)**: performed a broader grep-based review beyond the six named items, and found **two additional genuine defects the brief hadn't explicitly named**: (a) the Accounting AR/AP Report Catalog Matrix row, confirmed stale exactly as the brief's §9/§10 described (`T052`→`T053`, `T211` removed and relocated to the Installments servicing-continuity-eligible row where it now actually belongs); (b) the Expected File Map's summary sentence claiming "eleven additional touches," which a direct recount (4 original + 1 Purchase + 2 Inventory + 8 Accounting, after the prior pass's Blocker-B expansion added `ar.py`/`ap.py`/`ar_service.py`/`ap_service.py`) showed was actually **fifteen** — corrected with the arithmetic shown inline so the count is independently verifiable, not just asserted.

Verified the final security regression list (`T285`) entry-by-entry against current task meaning (all 20+ referenced IDs confirmed still genuinely security-relevant, still executable test tasks, zero Gate IDs) — no changes needed there beyond what the prior pass already fixed, confirming the brief's instruction not to change valid entries merely for cosmetic reasons was honored.

Performed the mandated final self-audit via a Python script matching the `T\d{3}[A-Z]?` pattern: 294 total task-checkbox lines, 294 unique IDs, zero duplicates, zero gaps in the numeric range `1`–`293` (the one suffix task `T045A` from the prior pass accounted for correctly), zero `TBD` placeholders, and confirmed the two remaining "if X then Y" phrasings in the Purchase boundedness text are describing a *mandatory, both-branches-converge* action within a single task (exactly the pattern the brief's own §4 prescribed), not a genuine open architecture branch.

## Outcome

- ✅ Impact: Purchase's export/pagination architecture is now fully deterministic (6/6 Category A, 0 full-fetch fallbacks); all six named stale references corrected; one additional stale coverage-matrix mapping and one stale file-count both caught and fixed during the broader semantic sweep the brief required.
- 🧪 Tests: None run — planning-only cleanup pass. Every corrected task still states its own required test evidence.
- 📁 Files: `specs/011-reports-analytics/tasks.md` (targeted edits only).
- 🔁 Next prompts: Human review and explicit implementation authorization; upon approval, begin at `T001`.
- 🧠 Reflection: The two self-discovered defects (the stale AR/AP catalog mapping and the "eleven vs. fifteen" file-count error) were both direct, mechanical consequences of the *prior* pass's own fixes — correcting T052/T053's split and expanding the Accounting file list were both done correctly in isolation during that pass, but their *downstream* references (a summary table row, a summary sentence's arithmetic) weren't re-derived at the same time. This is a useful pattern to watch for across any multi-pass correction: fixing a fact in place is necessary but not sufficient — every place that fact gets *counted*, *summarized*, or *cross-referenced* elsewhere in the same document needs the identical re-derivation, and those are exactly the spots a narrow, brief-driven pass can miss unless it explicitly widens its search past the named items, as this brief's §8 required.

## Evaluation notes (flywheel)

- Failure modes observed: Two additional stale-reference defects found only because the brief's §8 explicitly mandated searching past the six named cases rather than treating them as exhaustive — a good confirmation that "the user found N issues" should never be read as "there are exactly N issues," especially in a document this large (705 lines, 294 tasks) that has already been through two prior correction passes.
- Graders run and results (PASS/FAIL): Not applicable — no automated grading harness invoked; self-validated via direct Python ID-integrity verification and manual entry-by-entry re-derivation of the final security regression list and the modified-file count.
- Prompt variant (if applicable): N/A (single-pass execution of the 19-section cleanup brief).
- Next experiment (smallest change to try): Before the next correction pass (if any), consider adding a small standing checklist item to future passes: "recount every summary sentence (file-count, task-count, matrix-row totals) that depends on content just edited" — this would have caught the "eleven vs. fifteen" defect proactively rather than requiring an explicit third-pass semantic sweep to surface it.
