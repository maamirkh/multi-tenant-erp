---
id: 0005
title: Three targeted wording corrections to spec.md
stage: spec
date: 2026-08-19
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: none
labels: ["platform-admin", "spec", "wording-correction"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/009a-platform-admin/spec.md
 - history/prompts/009a-platform-admin/0005-three-targeted-wording-corrections.spec.prompt.md
tests:
 - none (specification-only wording correction; no Plan/Tasks/implementation/code touched)
---

## Prompt

Review and update the current Epic 9A `spec.md` ONLY for three consistency corrections: (1) remove stale "future CRM" wording in §26 Integration Boundaries now that Epic 9 is complete; (2) Risk #6 in §28 must no longer frame audit fail-closed (BR-9A-024/FR-9A-204) as pending Product Owner confirmation during Plan review — it's already a final, approved requirement; (3) clarify §18.1's "tenant-specific business context" wording, which could be misread as implying business-record access, to "tenant-specific administrative context," consistent with §18.3/§18.4/BR-9A-021/OQ-2's inspection-only-no-business-records decision. Explicit constraints: no rewrite, no new requirements, no numbering changes, no changes to already-resolved decisions, smallest possible textual diff, constitution.md/plan.md/tasks.md/code untouched.

## Response snapshot

Located each exact string via grep (single occurrence each, lines 947, 979, 717 pre-edit) and applied one minimal Edit per correction:

1. §26 Integration Boundaries table row: "Inventory, Purchase, Sales, Accounting, future CRM" → "Inventory, Purchase, Sales, Accounting, CRM". No other wording in that row touched.
2. §28 Risk #6: replaced "must be explicitly confirmed with the product owner during Plan review since it changes operational behavior" with "is NOT an open product decision requiring reconfirmation during `/sp.plan` (see §29)... Plan/implementation MUST account for its transactional and operational consequences" — same sentence structure and surrounding context preserved, only the pending-decision framing removed. BR-9A-024 and FR-9A-204 themselves were not touched (verified byte-identical before/after).
3. §18.1 Principle: "inspect tenant-specific business context" → "inspect tenant-specific administrative context (configuration, entitlements, users, lifecycle/audit information — see §18.3)", adding a forward reference to the section that already enumerates the exact allowed scope, without changing anything else in the paragraph.

Ran the 7-item targeted validation the user specified: confirmed zero remaining "future CRM" occurrences; confirmed zero remaining "confirmed with the product owner during Plan review" occurrences; confirmed BR-9A-024 and FR-9A-204 text identical to pre-edit; confirmed §18.1/§18.3/§18.4/BR-9A-021/OQ-2 all semantically consistent (Platform Admin: configuration/entitlements/users/audit only, never business records); confirmed no FR/BR/SC/OQ numbering changed (counts stable — no additions or removals this turn); confirmed no new requirement or decision introduced; confirmed `git status` shows only `spec.md` modified.

## Outcome

- ✅ Impact: Three residual wording inconsistencies eliminated with the smallest possible diffs — no structural or requirement-level change, purely removing stale/ambiguous phrasing left over from before Epic 9's completion and before the audit-fail-closed and support-access-scope decisions were finalized.
- 🧪 Tests: N/A — wording-only specification change.
- 📁 Files: `specs/009a-platform-admin/spec.md` (3 single-line edits) only.
- 🔁 Next prompts: Product Owner approval → commit → `/sp.plan` (not started, per explicit instruction).
- 🧠 Reflection: This was a precision task, not a completeness task — the value was in touching exactly the flagged text and nothing adjacent, verified via targeted grep both before locating the strings and after editing, rather than re-reading and re-judging the whole document as in the prior correction pass.

## Evaluation notes (flywheel)

- Failure modes observed: none.
- Graders run and results (PASS/FAIL): 7/7 targeted validation items PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
