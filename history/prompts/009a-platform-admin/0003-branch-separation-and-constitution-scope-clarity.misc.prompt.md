---
id: 0003
title: Branch separation and constitution scope clarity
stage: misc
date: 2026-08-19
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: none
labels: ["platform-admin", "branching", "constitution", "governance"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - .specify/memory/constitution.md
 - specs/009a-platform-admin/spec.md
 - history/prompts/009a-platform-admin/0003-branch-separation-and-constitution-scope-clarity.misc.prompt.md
tests:
 - none (spec/governance-document-only change)
---

## Prompt

constitution.md mai bhi epic 9a ko bilkul seprate hi hona chaye jese baqi hain yeh epic crm se bilkul seperate hi hoga aur yeh bhi clear kardon ke yeh platform administration ke liye hai jo tenant companies aur users aur poore app ko controll karega

(Preceded by: "epic 9a ki branch bhi alag hi rakhna agar abhi bhi yeh epic 9 crm ki branch mai hai tu wahan se hatado" — the user asked for Epic 9A's branch to stay fully separate from 009-crm, and when asked whether constitution.md's §50 addition should also be removed from 009-crm, clarified that yes, it should be completely separate like every other epic branch, AND that §50 itself should explicitly state Platform Administration's scope covers tenant companies, users, and the whole application.)

## Response snapshot

Two-part fix:

1. **Branch separation** — On `009-crm`, removed `specs/009a-platform-admin/` (spec.md + checklists/requirements.md), `history/prompts/009a-platform-admin/` (both prior PHRs), and reverted `.specify/memory/constitution.md`'s §50 addition back to the v1.1.0 state (checked out main's copy of the file, verified via diff that only the §50-related content was removed and nothing else was touched). Committed as `37e5ba3` on `009-crm`. This restores the one-epic-per-branch pattern already used by Epics 1–8 — `009-crm` no longer carries any Epic 9A artifact.

2. **Constitution scope clarity** — Switched to `009a-platform-admin` (which already had §50 from its own commit history) and strengthened §50's intro paragraph: it previously said Platform Administration is "the central SaaS control plane — a distinct actor from Company/Tenant Administration" without enumerating what that control plane actually spans. Rewrote it to explicitly name three domains: (1) tenant companies — lifecycle, entitlements, plans, quotas; (2) users — both Platform Administrator accounts (independent of any tenant) and aggregate/oversight-only visibility into tenant user populations; (3) the whole application — platform-wide configuration, operational health, security/audit oversight. This didn't introduce a new rule (the scope was already implied by the existing bullet list — tenant lifecycle, RBAC, cross-tenant audit, AI/billing readiness), so it's a PATCH-level clarification (1.2.0 → 1.2.1) per the constitution's own MAJOR/MINOR/PATCH versioning rule (§ "PATCH: Clarifications, wording improvements, typo fixes"), not a MINOR/new-principle bump. Updated the Sync Impact Report header and the version/date footer accordingly. Also bumped `specs/009a-platform-admin/spec.md`'s "Constitution Version" metadata field from v1.2.0 to v1.2.1 to stay consistent.

## Outcome

- ✅ Impact: `009-crm` is now clean of all Epic 9A content (matches every other epic branch's one-epic-per-branch convention); `009a-platform-admin` is the sole source of truth for Epic 9A's spec and constitution amendment, and that amendment now unambiguously states Platform Administration's three-domain scope (tenant companies, users, whole app) instead of leaving it to be inferred from a bullet list.
- 🧪 Tests: N/A — governance/spec documents only, no code affected.
- 📁 Files: `.specify/memory/constitution.md` (§50 intro + sync report + version footer), `specs/009a-platform-admin/spec.md` (Constitution Version field) — both on `009a-platform-admin` branch only; `009-crm` had 5 files deleted (spec + 2 PHRs + checklist) and constitution.md reverted.
- 🔁 Next prompts: none requested; ready for `/sp.plan` on the `009a-platform-admin` branch whenever the user wants to proceed.
- 🧠 Reflection: The user's correction here was about architectural hygiene, not content — a spec/constitution artifact belonging to one epic had leaked onto another epic's branch via an earlier cherry-pick, and the fix had to go both ways (remove from the wrong branch, strengthen on the right one) rather than just deleting.

## Evaluation notes (flywheel)

- Failure modes observed: none — verified the constitution.md revert on 009-crm with an explicit diff review before committing, to confirm no unrelated content was accidentally reverted (main and 009-crm's constitution.md had diverged only by the §50 addition, nothing else).
- Graders run and results (PASS/FAIL): N/A (governance document, no automated grader)
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
