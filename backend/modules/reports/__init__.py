"""Reports & Analytics module (Epic 11).

A read-only reporting/analytics layer wrapping the already-implemented
per-module report/KPI services (Sales, Purchase, Inventory, Accounting,
CRM, Installments) behind one curated, typed, permission-and-entitlement
-aware query/response contract.

Spec ref: specs/011-reports-analytics/{spec.md, plan.md}.
"""

from __future__ import annotations
