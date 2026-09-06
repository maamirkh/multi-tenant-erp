---
id: "002"
title: Epic 5 spec v1.1 enrichment updates
stage: spec
date: 2026-07-20
surface: agent
model: claude-sonnet-4-6
feature: 005-inventory-management
branch: 005-inventory-management
user: shehla83
command: /sp.specify (update — do not rewrite)
labels: ["inventory","branch-readiness","multi-currency","procurement-metadata","cross-epic","epic-5","spec","v1.1"]
links:
  spec: specs/005-inventory-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/005-inventory-management/spec.md
tests:
  - none (spec stage)
---

## Prompt

Update existing spec.md for Epic 5 — do NOT rewrite. Add missing enterprise concepts:

1. Branch Readiness (highest priority): Company → Branch (Future) → Warehouse hierarchy
2. Multi-Currency Readiness: Base Currency, Transaction Currency, Reporting Currency, Exchange Rate integration (Future)
3. Procurement Metadata Readiness on Product Master: Preferred Supplier, Supplier Code, Lead Time, Purchase UOM, Sales UOM, Reorder Quantity, Reorder Point, EOQ, Tax Category, Storage Conditions, Shelf Life, Hazard Classification, Country of Origin
4. Cross-Epic Compatibility: Explicit contracts for Epic 6 (Purchase), Epic 7 (Sales), Epic 8 (Accounting), Epic 9 (CRM)
5. Business Rules: Warehouse ownership hierarchy, Product lifecycle governance, Valuation ownership, Procurement metadata ownership, Branch-aware ownership
6. Future Roadmap: ERP domain evolution map (Company → Branch → Warehouse → Inventory → Purchase → Sales → Accounting → CRM → AI)

## Response snapshot

Updated `specs/005-inventory-management/spec.md` from v1.0.0 to **v1.1.0** with targeted, non-destructive edits only. No existing content removed or rewritten.

**Changes made**:

1. **§14.16 Procurement Metadata Readiness (Future)** — Added after §14.15 Tags. Documents 13 procurement metadata fields (Preferred Supplier, Supplier Product Code, Lead Time, Purchase UOM, Sales UOM, Reorder Quantity, Reorder Point, EOQ, Tax Category, Storage Conditions, Shelf Life, Hazard Classification, Country of Origin) with ownership assignments to future Epics. Established governance principle: Product Master owns all procurement metadata.

2. **§15.18 Multi-Currency Readiness (Future)** — Added after §15.17 Inventory Snapshot. Documents 5 currency concepts (Base Currency, Transaction Currency, Inventory Valuation Currency, Reporting Currency, Exchange Rate Integration) with Epic 5 status and future behaviour. Establishes that all monetary amounts must be stored with currency code from day 1.

3. **§16.10 Branch Hierarchy Readiness (Future)** — Added after §16.9 Warehouse Status. Documents current architecture (Company → Warehouse) and future architecture (Company → Branch → Warehouse). Defines 5 compatibility principles and explicitly lists non-goals for Epic 5. Compatibility guarantee: no schema change to stock ledger or product master when Branch is introduced.

4. **§23 Business Rules** — Added BR-024 through BR-029: warehouse ownership hierarchy, Product Master governance, currency code requirement, product lifecycle ownership, procurement metadata governance, monetary amount currency code requirement.

5. **§44.2 Downstream Dependencies** — Enriched with explicit "Stability Requirement" column for each downstream module. Added §44.3 Cross-Epic Architectural Compatibility Commitment with 3 formal guarantees: Product Master Stability, Stock Ledger Immutability, Future Module Readiness Without Redesign.

6. **§58 Future Roadmap Phase 7** — Added ERP Domain Evolution Map showing the 7-layer evolution from Platform → Product Foundation → Commercial Transactions → Financial Intelligence → Post-Sale Services → Intelligence → Organisational Expansion. Strategic principle: Product Master and Stock Ledger are permanent foundations, never to be redesigned.

7. **Out of Scope (§6)** — Added 3 explicit entries for Branch Management, Procurement Metadata, and Multi-Currency with cross-references to readiness sections.

8. **Terminology (§7)** — Added 13 new terms: Branch, Base Currency, Transaction Currency, Reporting Currency, Preferred Supplier, Lead Time, EOQ, Purchase UOM, Sales UOM, Storage Conditions, Hazard Classification.

9. **Feature Matrix (§27.3 Future)** — Added Branch Management and Procurement Metadata Readiness entries with cross-references.

## Outcome

- Impact: spec.md v1.1.0 — all 6 required enterprise updates applied without removing any existing content
- Tests: none (spec stage)
- Files: specs/005-inventory-management/spec.md (updated in-place)
- Next prompts: /sp.plan to generate plan.md from this enriched specification
- Reflection: All edits were targeted surgical insertions — zero existing content was modified or removed. Cross-references between new sections established (§14.16 ↔ §44.3, §15.18 ↔ §44.3, §16.10 ↔ §44.3, §27.3 ↔ all readiness sections).

## Evaluation notes (flywheel)

- Failure modes observed: none — all Edit operations were clean exact-string replacements
- Graders run and results (PASS/FAIL): grep verification confirms all 6 new section anchors present at correct line numbers
- Prompt variant (if applicable): update-not-rewrite variant of sp.specify
- Next experiment: Run /sp.clarify to validate no ambiguity remains before /sp.plan
