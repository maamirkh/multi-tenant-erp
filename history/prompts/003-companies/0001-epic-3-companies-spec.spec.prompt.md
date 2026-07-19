---
id: "0001"
title: "epic-3-companies-spec"
stage: spec
date: 2026-07-15
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: shehla83
command: /sp.specify
labels: ["spec", "companies", "multi-tenant", "epic-3", "foundation"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/003-companies/spec.md
  - specs/003-companies/checklists/requirements.md
tests:
  - "All 12 AC groups (AC-001 through AC-012) defined in spec"
---

## Prompt

# DevSphere ERP
# Spec-Driven Development (SpecKit Plus)

## TASK

Create the complete `spec.md` for:

Epic 3 – Companies

This is NOT an implementation task.

Do NOT generate code.

Your responsibility is to produce a production-grade engineering specification.

The generated specification will become the Single Source of Truth (SSOT) for the Companies module.

[Full prompt included: Epic 3 Companies module specification request covering multi-tenant architecture, functional requirements, business rules, user stories, database design, API design, permissions, validation, error handling, audit logging, domain events, reporting, out-of-scope, acceptance criteria, and future enhancements for DevSphere ERP.]

## Response snapshot

Created branch `003-companies` and wrote a complete enterprise-grade `spec.md` at `specs/003-companies/spec.md`. The specification covers:

- Terminology & definitions (Tenant, Company, Owner, Slug, company_id)
- Multi-tenant isolation strategy (Shared DB + company_id row isolation; RLS future hook)
- 6 prioritized user stories with acceptance scenarios and edge cases
- 42 functional requirements (FR-001–FR-042) across lifecycle, profile, regional settings, branding, settings
- Status transition table with allowed transitions and authorized actors
- 9 NFR categories (performance, scalability, security, availability, maintainability, auditability, data integrity, disaster recovery)
- 29 business rules (BR-001–BR-029) covering naming, slugs, ownership, deletion, status, currency
- Permission matrix for 7 roles across all company actions
- Validation rules for all 14 field categories with error codes
- Conceptual DB design: `companies`, `company_addresses`, `company_audit_logs` entities with all attributes, relationships, indexes, and unique constraints
- Full REST API design: 14 endpoints with request/response models and error codes
- 22 error codes with HTTP status mapping and consistent error envelope
- 16 audit event types with before/after state capture and immutability rules
- 11 domain events with full payload definitions and Transactional Outbox Pattern
- 6 future reporting requirements
- Explicit out-of-scope table (15 excluded areas)
- 8 assumptions documented
- 12 measurable acceptance criteria groups (AC-001–AC-012)
- 14 future enhancements with design notes
- 8 success criteria (SC-001–SC-008)

## Outcome

- Impact: Complete SSOT specification for the Companies module — the foundational multi-tenant boundary for all future ERP modules
- Tests: Acceptance criteria AC-001 through AC-012 defined; quality checklist all items pass
- Files: specs/003-companies/spec.md, specs/003-companies/checklists/requirements.md
- Next prompts: /sp.clarify (if needed), /sp.plan, /sp.tasks
- Reflection: Comprehensive enterprise-grade spec aligned with SAP/NetSuite/Odoo patterns; extensible for future SaaS, white-label, and subdomain routing

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): Spec quality checklist — all 17 items PASS
- Prompt variant (if applicable): sp.specify v1
- Next experiment: Run /sp.clarify to validate assumptions A-01 through A-08 with stakeholder
