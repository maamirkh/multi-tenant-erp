---
id: "0015"
title: Phase 8 Sales Intelligence Reporting
stage: green
date: 2026-08-04
surface: agent
model: claude-sonnet-4-6
feature: 007-sales-management
branch: 007-sales-management
user: shehla83
command: /sp.implement
labels: ["phase-8", "reporting", "kpis", "csv-export", "excel-export", "sales-intelligence"]
links:
  spec: specs/007-sales-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/sales/schemas/reports.py
  - backend/modules/sales/services/report_service.py
  - backend/modules/sales/services/kpi_service.py
  - backend/modules/sales/services/report_export_service.py
  - backend/modules/sales/dependencies.py
  - backend/modules/sales/router.py
  - frontend/src/app/(protected)/(sales)/reports/page.tsx
  - frontend/src/app/(protected)/(sales)/reports/[type]/page.tsx
  - frontend/src/lib/api/sales.ts
  - backend/tests/unit/modules/sales/test_kpi_service.py
  - backend/tests/integration/repositories/sales/test_reports.py
  - backend/tests/integration/api/v1/sales/test_reports_api.py
  - specs/007-sales-management/tasks.md
tests:
  - tests/unit/modules/sales/test_kpi_service.py (24 passed)
  - tests/integration/repositories/sales/test_reports.py (20 passed)
  - tests/integration/api/v1/sales/test_reports_api.py (12 passed)
---

## Prompt

/sp.implement — Phase 8: Sales Intelligence & Reporting (P2). Implement T204–T221 covering all 25 report types (ReportService), 12 KPIs (KPIService), CSV/Excel export (ReportExportService), Pydantic schemas, API endpoints (/reports/{type}, /reports/{type}/export, /kpis), frontend KPI dashboard and report library pages, API client updates, and all tests.

## Response snapshot

Implemented Phase 8 "Sales Intelligence & Reporting (P2)" end-to-end across 12 files:

**Backend:**
- `schemas/reports.py`: ReportType (25 values), KPIType (12 values), ExportFormat, ReportParams, KPIResult, KPIDashboard, ReportResponse
- `services/report_service.py`: ReportService with dispatcher and 25 private methods, all tenant-scoped; company_id normalised to UUID via `_cid()` helper for `Uuid(as_uuid=True)` compatibility with SQLite test DB
- `services/kpi_service.py`: KPIService with `get_dashboard()` computing all 12 KPIs; equal-length previous-period comparison for trend computation; KPI-02 and KPI-11 return null (COGS and outstanding_balance not stored)
- `services/report_export_service.py`: CSV via stdlib csv module; Excel via openpyxl with auto-fit columns and styled header row
- `dependencies.py`: `get_report_service`, `get_kpi_service`, `get_report_export_service` factories added
- `router.py`: 3 new endpoints — `GET /reports/{report_type}`, `GET /reports/{report_type}/export`, `GET /kpis`

**Frontend:**
- `reports/page.tsx`: KPI dashboard (12 KPI cards with trend indicators) + report library grid (25 links)
- `reports/[type]/page.tsx`: Generic report viewer with date filters, paginated table, CSV/Excel export download
- `sales.ts`: `getKPIDashboard`, `getSalesReport`, `exportSalesReport` (returns Blob for file download)

**Tests:**
- Unit: 24 tests — `_pct`, `_div`, `_trend`, `_period_label`, `_prev_period` formula helpers
- Integration: 20 tests — all 25 report types execute, tenant isolation, KPI accuracy (revenue, outstanding orders, conversion rate), export service
- API: 12 tests — KPI dashboard, selected report types, date filters, export endpoint, 401/422 errors, tenant isolation

**Key fixes during implementation:**
- `Customer.outstanding_balance` does not exist — replaced with null; `Customer.customer_code`/`legal_name` instead of `customer_number`/`name`
- `OrderLine.quantity` → `OrderLine.quantity_ordered`
- `Uuid(as_uuid=True)` on `company_id` requires UUID objects in SQLAlchemy queries — added `_cid()` normaliser in ReportService and explicit conversion in KPIService
- sed backreference `\1` corruption in report_service.py — rewrote entire file with Write tool
- Pagination test for grouped-by-date report — use different invoice dates per row

## Outcome

- ✅ Impact: Complete sales intelligence layer with 25 reports, 12 KPIs, and file export; 776 total sales tests passing (no regressions)
- 🧪 Tests: 56 Phase 8 tests passed (24 unit + 20 integration + 12 API); 776 total passing
- 📁 Files: 12 files created/modified across backend services/schemas/router and frontend pages/API client
- 🔁 Next prompts: Phase 9 (Integration, Contracts & Import/Export)
- 🧠 Reflection: Always verify model field names before writing report queries; SQLAlchemy `Uuid(as_uuid=True)` requires explicit UUID objects for comparisons in SQLite test DB; avoid sed for complex replacements in Python files — use Python script or Write tool

## Evaluation notes (flywheel)

- Failure modes observed: Wrong Customer model field names (outstanding_balance, customer_number, name); OrderLine.quantity vs quantity_ordered; Uuid(as_uuid=True) UUID type mismatch; sed backreference corruption
- Graders run and results (PASS/FAIL): All 56 Phase 8 tests PASS; 776 total sales tests PASS
- Prompt variant (if applicable): /sp.implement Phase 8 continuation from Phase 7 (context compaction boundary)
- Next experiment: Add COGS tracking to OrderLine for real gross margin computation
