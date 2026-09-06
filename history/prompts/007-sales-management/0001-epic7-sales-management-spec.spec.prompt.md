---
id: "0001"
title: "Epic 7 Sales Management Spec"
stage: spec
date: 2026-07-30
surface: agent
model: claude-opus-4-6
feature: 007-sales-management
branch: 007-sales-management
user: shehla83
command: /sp.specify
labels: ["sales-management", "o2c", "epic-7", "spec"]
links:
  spec: specs/007-sales-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/007-sales-management/spec.md
  - specs/007-sales-management/checklists/requirements.md
tests:
  - none
---

## Prompt

/sp.specify Epic 7 – Sales Management: Generate the official enterprise Business Specification (spec.md) for the complete Order-to-Cash (O2C) domain. Covers Customer Master, Sales Quotations, Sales Orders, Order Fulfillment, Delivery Notes, Sales Invoicing, Sales Returns, Pricing Engine, Sales Analytics, and Customer Analytics. Must support multiple industries (Retail, Wholesale, Construction, Medical, Manufacturing, Distribution, Trading). 61 required sections including Executive Summary, Domain Philosophy, Business Capabilities, Functional/Non-Functional Requirements, Permission Matrix (11 roles), Domain Events, KPIs, Cross-Module Contracts (Epic 5 Inventory, Epic 6 Purchase), AI/Analytics Readiness, and Epic Completion Criteria. Must remain implementation-independent, fully compatible with Epics 0-6, and enterprise-grade.

## Response snapshot

Generated complete 61-section enterprise Business Specification for Epic 7 – Sales Management at `specs/007-sales-management/spec.md`. Key deliverables:

- **Branch created**: `007-sales-management` from `main`
- **Customer Master**: 13 sub-sections covering customers, categories, groups, contacts, addresses, payment terms, credit limits, territories, tax info, bank details, custom fields, documents, internal notes
- **Sales Lifecycle**: Quotation (5 states) → Sales Order (8 states) → Delivery Note (6 states) → Invoice (7 states) → Returns (6 states)
- **Pricing Engine**: 7-level price resolution hierarchy (Manual Override → Customer-Specific → Customer Group → Customer Category → Active Price List → Default Price List → Product Base Price)
- **38 Domain Events**: Covering customer, quotation, order, delivery, invoice, and return lifecycles
- **14 Feature Flags**: For ready-but-disabled capabilities (credit control, multi-currency, delivery scheduling, etc.)
- **Permission Matrix**: 11 roles with granular permissions across 8 permission areas (29.1-29.8)
- **Cross-Module Contracts**: Sales ↔ Epic 5 Inventory (stock reservation/deduction/restock), Sales → Epic 6 Purchase (reorder triggers)
- **12 KPIs** with formulas, **15+ report types**, **30 acceptance criteria**
- **Quality Checklist**: All items passed at `specs/007-sales-management/checklists/requirements.md`

## Outcome

- Impact: Complete O2C enterprise specification ready for planning
- Tests: N/A (specification document, no code)
- Files: 2 created (spec.md, requirements.md checklist)
- Next prompts: /sp.clarify or /sp.plan for Epic 7
- Reflection: Spec follows same enterprise structure as Epic 6; all 61 sections completed with no NEEDS CLARIFICATION markers

## Evaluation notes (flywheel)

- Failure modes observed: Initial Write tool failed because file wasn't read first (template-populated file); resolved by reading then writing
- Graders run and results (PASS/FAIL): Quality checklist validation PASS (all items checked)
- Prompt variant (if applicable): Standard /sp.specify with 61-section enterprise prompt
- Next experiment: Consider pre-reading template-populated files immediately after branch creation to avoid Write tool errors
