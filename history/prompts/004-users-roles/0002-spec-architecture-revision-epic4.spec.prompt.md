---
id: "0002"
title: Spec architecture revision Epic 4
stage: spec
date: 2026-07-16
surface: agent
model: claude-sonnet-4-6
feature: 004-users-roles
branch: 004-users-roles
user: shehla83
command: /sp.analyze
labels: ["spec-revision","architecture","platform-identity","role-hierarchy","tenant-isolation","lifecycle","audit"]
links:
  spec: specs/004-users-roles/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/004-users-roles/spec.md
tests:
  - "All 10 architectural improvements applied successfully"
---

## Prompt

/sp.analyze Epic 4 – spec.md Architecture Revision — Apply 10 architectural improvements to the existing spec.md: (1) Platform Identity Layer, (2) Company User Hierarchy with expanded roles, (3) Multi-Company Membership rules, (4) Stronger Company Isolation, (5) Role Hierarchy visualization, (6) Future Authorization Foundation, (7) Expanded User Lifecycle with locked state, (8) Audit Improvements, (9) Future Enterprise Compatibility, (10) Refined Out of Scope.

## Response snapshot

Applied all 10 architectural improvements to specs/004-users-roles/spec.md via 21 targeted edits:

1. **Platform Identity Layer**: Added two-tier identity architecture description in Section 1.1, new Section 1.4 with Platform/Company layer diagram and key architectural principles
2. **Company User Hierarchy**: Expanded FR-040 from 5 to 8 system roles (Owner, Admin, Manager, Accountant, Salesperson, Cashier, Store Keeper, Viewer) with responsibilities column. Replaced generic Staff role with specific operational roles.
3. **Multi-Company Membership**: Added FR-065–FR-067 explicitly defining independent memberships, single active context, and per-company permission evaluation
4. **Company Isolation**: Added FR-068–FR-069 and BR-054–BR-057 mandating company-scoped operations, prohibiting cross-company access, requiring future modules to inherit isolation
5. **Role Hierarchy**: Added Section 1.5 with conceptual hierarchy diagram from Platform Super Admin through Viewer, with hierarchy rules
6. **Future Authorization Foundation**: Added Section 6.4 with 9-row table covering RBAC, ABAC, Feature/Module/Record/Field permissions, Approval Workflows, Delegation, Temporary Permissions
7. **User Lifecycle**: Added `locked` state to FR-007, BR-020 state machine (4 new transitions), BR-025 defining locked semantics, lifecycle diagram
8. **Audit Improvements**: Added 5 new audit events: INVITATION_ACCEPTED, COMPANY_CONTEXT_SWITCHED, ROLE_PERMISSIONS_UPDATED, MEMBER_LOCKED, MEMBER_UNLOCKED
9. **Enterprise Compatibility**: Expanded Section 13.2 from 7 to 15 future modules including Reports, Installments, AI, Notifications, Billing, API Keys, Mobile, Integrations, SSO
10. **Out of Scope**: Added architectural foundation callout, updated assumptions A6/A8/A9, added 11 future enhancements, updated glossary with 8 new terms

## Outcome

- Impact: Enterprise-grade architectural revision bringing spec to production-grade SaaS ERP standard
- Tests: All 21 edits applied cleanly, no contradictions introduced
- Files: specs/004-users-roles/spec.md updated (~1050 lines, up from 903)
- Next prompts: /sp.clarify or /sp.plan
- Reflection: Incremental editing approach preserved all existing content while integrating new architecture naturally. The two-tier identity architecture and expanded role hierarchy bring the spec closer to SAP/Dynamics 365/Odoo enterprise standards.

## Evaluation notes (flywheel)

- Failure modes observed: None — all edits applied cleanly with no conflicts
- Graders run and results (PASS/FAIL): Manual review PASS — no contradictions, terminology consistent
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): none
