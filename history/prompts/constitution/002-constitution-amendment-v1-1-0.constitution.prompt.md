---
id: "002"
title: Constitution Amendment v1.1.0 Eight Principles Added
stage: constitution
date: 2026-07-10
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: unknown
command: /sp.constitution
labels: ["constitution","amendment","business-config","plugin-architecture","shared-kernel","event-driven","money-handling","soft-delete"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - .specify/memory/constitution.md
tests:
  - none
---

## Prompt

Review the existing CONSTITUTION.md.

Do NOT rewrite the document.

Do NOT remove any existing content.

Do NOT change the document structure.

Only improve it by adding the following missing enterprise engineering principles in the most appropriate sections.

### Add Business Configuration Philosophy

The ERP must support configurable business behavior instead of hardcoded business rules.

Examples include: Invoice Prefix, Invoice Number Format, Voucher Number Format, Currency, Fiscal Year,
Decimal Precision, Tax Configuration, Warranty Settings, Barcode Configuration, Receipt Layout,
Payment Methods, Return Policy, Delivery Policy.

Configuration should always be preferred over hardcoding.

---

### Add Plugin Architecture Principles

External integrations must be implemented using plugin/adaptor architecture.
Examples: WhatsApp, Email, SMS, Payment Gateways, Barcode Devices, Printers, AI Providers, Cloud Storage.
The ERP Core must never directly depend on third-party vendors.

---

### Add Shared Kernel Principles

The platform should contain a Shared Kernel for reusable business concepts.
Examples: Money, Currency, Units, Taxes, Countries, Cities, Common Enums, Date Helpers,
Validation Helpers, Utility Classes.
Business modules should reuse the Shared Kernel instead of duplicating logic.

---

### Add Event-Driven Communication Principles

Whenever practical, modules should communicate using Domain Events instead of direct dependencies.
Example flow: Sale Completed → Inventory Updated → Accounting Entry Created → Notification Sent → Audit Logged.
Avoid unnecessary coupling between modules.

---

### Add Money Handling Standard

Never use floating-point data types for financial calculations.
Always use Decimal or an equivalent precise numeric type.

---

### Add Time Handling Standard

Store all timestamps in UTC. Convert to local time only at presentation.

---

### Add Soft Delete Policy

Business data should use Soft Delete by default.
Hard Delete should only be allowed for system-level administrative operations.

---

### Improve AI Development Rules

- Claude Code must never assume business rules.
- Claude Code should ask for clarification whenever requirements are ambiguous.
- Claude Code must not introduce new dependencies without justification.
- Claude Code must update documentation whenever implementation changes.

Keep the existing writing style. Generate the updated CONSTITUTION.md.

## Response snapshot

Amended `.specify/memory/constitution.md` from v1.0.0 to v1.1.0 using targeted edits (no existing content removed or restructured).

Changes made:
1. Updated HTML Sync Impact Report to reflect v1.1.0 amendment.
2. Added §46–49 to Table of Contents.
3. Augmented §17 Database Principles with two new sub-sections:
   - Money Handling Standard (Decimal-only rule, currency alongside amounts, explicit rounding)
   - Soft Delete Policy (business data = soft delete by default; hard delete = admin-only with audit)
4. Augmented §38 AI Development Rules:
   - Strengthened "never assume business rules" to be explicit about asking for clarification
   - Added "ask for clarification whenever requirements are ambiguous"
   - Strengthened "NEVER introduce new dependencies without documented justification in the same PR"
   - Strengthened "Update documentation in the same PR"
   - Added MUST NOT rule about assuming business configuration defaults
5. Added four new sections:
   - §46: Business Configuration Philosophy (13 configurable examples, rules on config-over-hardcoding)
   - §47: Plugin Architecture Principles (ASCII diagram, 5 integration categories, 7 rules)
   - §48: Shared Kernel Principles (6 categories, dependency direction rule, Money type mandate)
   - §49: Event-Driven Communication Principles (past-tense naming, idempotency, outbox pattern, when-to-use table)
6. Updated version footer to 1.1.0.

## Outcome

- ✅ Impact: Constitution v1.1.0 ratified. Platform now has explicit governance for business configurability, plugin integrations, shared kernel reuse, and event-driven module communication.
- 🧪 Tests: N/A — governance document
- 📁 Files: .specify/memory/constitution.md (amended in-place, all existing content preserved)
- 🔁 Next prompts: Run /sp.adr to document plugin architecture and event-driven decisions; begin first feature spec with /sp.specify
- 🧠 Reflection: All 8 user requirements addressed. Money Handling and Soft Delete folded into §17 for cohesion. Time Handling (UTC) was already present in §36 and implicitly covered by the new §17 additions; no duplication added. New §46–49 placed after §45 Governance to preserve existing section numbering.

## Evaluation notes (flywheel)

- Failure modes observed: First Edit attempt failed due to minor content mismatch in the HTML comment block — resolved by targeting a shorter unique string.
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): sp.constitution v1 (amendment mode)
- Next experiment: Validate that §47 Plugin Architecture aligns with §33 File Storage Principles (both reference storage abstraction)
