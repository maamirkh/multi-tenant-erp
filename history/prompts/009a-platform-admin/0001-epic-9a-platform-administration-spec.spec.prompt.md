---
id: 0001
title: Epic 9A Platform Administration spec
stage: spec
date: 2026-08-18
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.specify
labels: ["platform-administration", "saas-control-plane", "rbac", "tenant-lifecycle", "epic-9a"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/009a-platform-admin/spec.md
 - specs/009a-platform-admin/checklists/requirements.md
tests:
 - none (specification-only stage; no code/tests produced)
---

## Prompt

# Epic 9A — Platform Administration / Super Admin
## Create Complete `spec.md`

Create the complete Specification for:

**Epic 9A — Platform Administration / Super Admin**

This is a Spec-Driven Development task.

The purpose of this step is to create the authoritative business and functional
Specification for the DevSphere ERP SaaS Platform Administration capability.

---

# 1. Mandatory First Step — Repository & Constitution Review

Before writing or modifying `spec.md`:

1. Read the current `constitution.md` completely.
2. Treat Constitution **v1.2.0** as the highest authority.
3. Pay special attention to:
   - §5 Architecture
   - §9 Multi-Tenant Principles
   - §11 Feature Toggles
   - §16 Authentication & Authorization
   - §19 Security Principles
   - §22 Logging & Observability
   - §31 Testing Standards
   - §35 Audit Trail
   - §37 SaaS Readiness
   - §38 AI Development Rules
   - §40 Change Management
   - §42 Definition of Ready
   - §43 Definition of Done
   - §44 Non-Negotiable Rules
   - §46 Business Configuration Philosophy
   - §47 Plugin Architecture Principles
   - §48 Shared Kernel Principles
   - §49 Event-Driven Communication Principles
   - §50 Platform Administration & SaaS Control Plane Principles

4. Inspect the existing repository structure and completed Epics 0–9.
5. Review existing Specifications, Plans, Tasks, models, services, permissions,
   authentication, company/tenant management, audit infrastructure, feature toggles,
   and SaaS-related foundations already implemented.
6. Reuse existing terminology, architectural concepts, entities, conventions, and
   patterns wherever applicable.
7. Do NOT contradict or duplicate capabilities already implemented by previous Epics.
8. Identify dependencies on existing modules instead of redefining their business logic.

Do NOT modify `constitution.md`.

[... full 42-section prompt covering Epic Identity, Core Product Boundary, Primary Epic
Objective, Platform Dashboard, Tenant/Company Lifecycle Management, Tenant Detail/360°
View, Platform Administrator Accounts, Platform-Level RBAC, SaaS Plan Management,
Subscription Administration, Feature Entitlements, Quotas & Usage Limits, Usage
Metering, AI Credits/Usage Readiness, Cross-Tenant Support/Administrative Access,
Audit & Security Oversight, Platform Health & Operational Monitoring, Platform
Configuration, Administrative Notifications & Alerts, Search/Filtering/Pagination/Bulk
Operations, Data Export/Administrative Reporting, Commercialization Readiness, Security
Requirements, Multi-Tenant Safety, Functional User Stories (12 minimum), Edge Cases (20
minimum), State Transitions, Business Rules (BR-9A-XXX), Functional Requirements
(FR-9A-XXX), Non-Functional Requirements, Success Criteria, Dependencies, Integration
Boundaries, Explicit Out of Scope, Specification Quality Rules, Required spec.md
Structure (30 sections), Constitution Traceability, Critical Design Principle diagram,
Do Not Over-Engineer guidance, Final Specification Review self-check (19 items), and
Final Output instructions directing that ONLY spec.md and required SpecKit metadata be
created, explicitly stopping before plan.md/tasks.md/migrations/implementation, and
requiring a concise closing summary covering: file created, capability areas included,
existing Epic dependencies discovered, unresolved clarifications, Constitution
compliance result, and confirmation that no implementation work was performed — see
full verbatim text in the user's original message for the complete 42-section prompt,
reproduced there in full without truncation.]

Full verbatim prompt text (~9,000 words) is preserved unabridged in the triggering
user message of this conversation; it is summarized here for PHR brevity per project
convention while the source-of-truth spec.md embeds every substantive requirement from
it directly.

## Response snapshot

Read the full Constitution (v1.2.0, all 50 sections, esp. §5/§9/§11/§16/§19/§22/§35/
§37/§46/§47/§49/§50). Confirmed via git that no existing branch/spec used the "9A"
identity and that the repo's numeric branch/spec-directory convention (001–009) has no
native support for an alpha-suffixed epic; asked the user how to name it and they chose
literal `009a-platform-admin`. Since the current working tree (009-crm) had substantial
uncommitted in-progress work, created an isolated git worktree at
`../erp-system-009a-platform-admin` on new branch `009a-platform-admin`, branched from
the last committed commit (b1ce764, tip of completed Epic 8) rather than disturbing the
CRM branch.

Dispatched a thorough Explore-agent research pass across the worktree to ground the
spec in actual implementation state rather than assumption, covering: the `Company`
model and `CompanyStatus` lifecycle enum (5 states: pending_setup/active/inactive/
suspended/deleted, with suspend/reactivate already documented "(SuperAdmin only)" but
never implemented — dead `CompanySuspendedEvent`/`CompanySuspensionLiftedEvent`
classes, no service method); the `users_roles` RBAC model (8 tenant roles, ~34
permission codes, zero `platform.*` codes); the `super_admin` string-check scaffolding
(3 independently-declared constants, and critically, `CurrentUser.roles` is
hardcoded to `[]` in production — the one real SuperAdmin endpoint is provably
unreachable by any authenticated user today); the auth/session model (no `company_id`
on Session, zero MFA anywhere, Better Auth mandated by the Constitution but never
actually integrated — a custom JWT stack shipped instead); three independent
append-only audit tables (auth, companies, accounting) with no cross-tenant platform
view; four separate per-module tenant feature-flag tables (inventory/sales/purchase/
accounting) with an existing, unrelated authorization gap on their update endpoints;
existing `/health`, `/health/live`, `/health/ready` endpoints; a stub (log-only)
transactional outbox relay; and confirmation that SaaS plans/subscriptions/quotas have
zero implementation beyond a single nullable `subscription_id` placeholder column and
one unused exception class. Also confirmed against `docs-project-context/EPICS.md` and
a prior hardening PHR that Epic 9 = CRM (currently gated/not started per that record)
and Epic 10 = Installments, with no prior mention of "Epic 9A" anywhere in the roadmap.

Authored a complete `specs/009a-platform-admin/spec.md` (~700 lines) following the
user's required 30-section structure verbatim (Epic Metadata → Purpose → Problem
Statement → Goals/Non-Goals → Actors & Trust Boundaries → Scope → Assumptions →
Dependencies (existing vs. new, explicitly separated) → 12 prioritized User Stories
(P1–P3, each with actor/preconditions/trigger/flows/authorization/audit/acceptance
scenarios) → 7 cross-cutting negative/boundary Acceptance Scenarios → ~130 Functional
Requirements (FR-9A-XXX) grouped by domain → 30 Business Rules (BR-9A-XXX) → Tenant
Lifecycle Requirements (reusing the real CompanyStatus model, scoping Platform Admin's
write authority strictly to Suspend/Reactivate, leaving Owner-controlled
inactive/deleted untouched) → Platform RBAC (16 permission areas, 6 candidate
least-privilege roles) → Plan & Subscription Requirements → Entitlement & Quota
Requirements (a 3-source resolution table: Plan Entitlement × Tenant Toggle ×
Administrative Override) → Support/Cross-Tenant Access Requirements (explicit,
time-bounded, reason-required, inspection-only, never silent impersonation) → Audit &
Security Requirements (fail-closed audit-write guarantee) → AI Usage/Credit Readiness
(provider-neutral) → Operational Monitoring → 23 Edge Cases (the 20 requested plus 3
discovered during research, each resolved or explicitly deferred to an Open Question)
→ State Transitions (tenant lifecycle transition table + a new minimal subscription
lifecycle) → Non-Functional Requirements → 8 Success Criteria → Integration Boundaries
→ Out of Scope → 6 Risks (explicitly flagging 3 adjacent pre-existing defects found
during research that this Epic does not fix) → 5 Open Questions (trial support,
support-access business-record visibility, session force-termination on suspension,
performance targets, Platform-Owner bootstrap — each marked rather than answered by
invention, per the prompt's own instruction) → Constitution Compliance/Traceability
table mapping every relevant section. Also created the companion
`specs/009a-platform-admin/checklists/requirements.md` quality checklist, matching the
convention already used by every prior epic in this repository, with all items passing
on first iteration.

No code, migration, plan.md, or tasks.md was created, per the prompt's explicit
instruction to stop after spec.md.

## Outcome

- ✅ Impact: A complete, Constitution-compliant, dependency-grounded Epic 9A
  specification now exists, formalizing Platform Administration as a real, reachable,
  least-privilege actor and closing the gap between the Constitution's SaaS-readiness
  aspiration and the current (largely unimplemented/unreachable) code state — ready for
  product-owner review of the 5 Open Questions and then `/sp.plan`.
- 🧪 Tests: None — specification-only stage, as explicitly required by the prompt.
- 📁 Files: `specs/009a-platform-admin/spec.md` (new),
  `specs/009a-platform-admin/checklists/requirements.md` (new), this PHR (new). All
  created in an isolated worktree/branch (`009a-platform-admin`) to avoid disturbing
  the user's in-progress, uncommitted Epic 9 (CRM) work on the main working tree.
- 🔁 Next prompts: Product-owner resolution of OQ-1 through OQ-5 (trial support scope,
  support-access business-record visibility, suspension session force-termination,
  performance targets, Platform-Owner bootstrap mechanism); then `/sp.clarify` and/or
  `/sp.plan` for Epic 9A; separately, the three adjacent defects flagged in §28 Risks
  (feature-flag endpoint authorization gap, disconnected frontend admin page, SUPER_ADMIN
  casing inconsistency) warrant their own remediation tracking outside this Epic.
- 🧠 Reflection: The single highest-leverage finding was that `CurrentUser.roles` is
  hardcoded to `[]` in production, making the existing `super_admin` mechanism
  completely theoretical — this reframed the whole epic from "add more capability to an
  existing Platform Admin" to "build the first real, reachable Platform Admin from
  scratch," which materially changed several requirements (e.g., BR-9A-002 explicitly
  forbidding authority derivation from `CurrentUser.roles`, and OQ-5 on how the very
  first Platform Owner account gets bootstrapped without circularity).

## Evaluation notes (flywheel)

- Failure modes observed: none blocking; the main process risk was the repo's numeric
  branch-naming convention not natively supporting an alpha-suffixed epic ID, resolved
  by asking the user rather than guessing, and by using an isolated `git worktree`
  rather than `git checkout -b` in place to avoid any risk to the user's substantial
  uncommitted Epic 9 (CRM) working-tree state.
- Graders run and results (PASS/FAIL): Self-review against the prompt's own §41
  19-item checklist — PASS on all items (Constitution v1.2.0 respected; Platform vs.
  Company Admin boundary explicit throughout; tenant isolation intact; RBAC boundaries
  explicit; tenant lifecycle fully specified via the real CompanyStatus model; plans
  and subscriptions conceptually separated; entitlement resolution deterministic;
  quotas covered with explicit enforcement-style declaration; cross-tenant support
  access explicitly controlled and never silent; audit requirements cover all listed
  sensitive actions; AI readiness is provider-neutral; operational monitoring
  proportionate to existing architecture; billing future-ready without implementing
  payment; existing Epic capabilities reused, not duplicated, per the Dependencies
  section split; edge cases and negative authorization scenarios covered; requirements
  testable; no DB/API/UI implementation design leaked in; no business rules invented
  where genuine ambiguity existed — routed to Open Questions instead; no existing Epic
  renumbered; no unrelated repository files modified).
- Prompt variant (if applicable): n/a — first iteration, no retry needed.
- Next experiment (smallest change to try): n/a.
