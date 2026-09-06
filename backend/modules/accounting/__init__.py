"""Accounting & Finance module — Epic 8.

The Accounting domain is DevSphere ERP's financial system of record — the
double-entry general ledger that every business transaction from Sales
(Epic 7), Purchase (Epic 6), and Inventory (Epic 5) ultimately posts to.

Sub-domains (delivered across Phases 1-12):
  - Foundation: module scaffolding, currencies, exchange rates, journal
    number sequencing, feature flags (Phase 1 — this phase)
  - Chart of Accounts: hierarchical account structure, COA templates (Phase 2)
  - Fiscal Calendar: fiscal years, period locking, opening balances (Phase 3)
  - General Ledger: PostingEngine, journal entries, GL reporting (Phase 4)
  - Journal Entries: manual/recurring/reversal workflows (Phase 5)
  - Accounts Receivable / Accounts Payable (Phases 5-6)
  - Banking & Cash Management (Phases 7-8)
  - Payments & Allocation (Phase 9)
  - Tax Engine & Cost Centers (Phase 10)
  - Financial Reporting & KPI Dashboard (Phase 11)
  - Integration Contracts & Epic Closure (Phase 12)

The non-negotiable architectural constraint: ALL general ledger postings
flow through a single ``PostingEngine`` domain service (introduced in
Phase 4). No code path bypasses it.

Spec ref: specs/008-accounting-finance/spec.md (v1.0)
Plan ref: specs/008-accounting-finance/plan.md
"""
