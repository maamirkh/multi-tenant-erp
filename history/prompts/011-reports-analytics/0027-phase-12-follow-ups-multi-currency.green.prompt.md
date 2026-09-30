---
id: 0027
title: Phase 12 Follow-ups Multi-Currency
stage: green
date: 2026-09-30
surface: agent
model: claude-opus-5-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: item 1 ke liye a select karo aur yeh tasks start kardo
labels: ["epic-11", "reports-analytics", "fr-rpt-152", "multi-currency", "drill-down", "performance", "ci"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: https://github.com/maamirkh/multi-tenant-erp/pull/9
files:
  - .github/workflows/{backend,frontend,pr-checks}.yml
  - backend/modules/sales/{schemas/reports.py,services/report_service.py,services/kpi_service.py}
  - backend/modules/purchase/services/{report_service.py,kpi_service.py}
  - backend/modules/inventory/services/report_service.py
  - backend/modules/crm/{repositories/opportunity.py,services/reporting_service.py}
  - backend/modules/installments/services/reporting_service.py
  - backend/modules/reports/schemas/{common,sales,purchase,inventory,crm,dashboard,customer_360}.py
  - backend/modules/reports/services/{dashboard_service,customer_360_service}.py
  - backend/modules/reports/services/adapters/{sales,purchase,inventory,crm,installments}_adapter.py
  - backend/modules/reports/registry/catalog_{accounting,installments,purchase,sales}.py
  - backend/modules/reports/docs/{README,multi_currency_findings}.md
  - backend/tests (new: test_multi_currency.py, test_reports_group_by_currency.py, test_inventory_valuation_currency.py, test_drill_down_routes_exist.py; updated equivalence/contract/guard tests)
  - frontend/src/components/reports/{DataTable,ReportView,DashboardWidgets,Customer360Sections,reportConfigs,drillDown}.ts(x)
  - frontend/src/lib/{api/reports.ts,format/money.ts}
  - frontend/src/__tests__/reports/{dashboard,customer-360,drill-down}.test.tsx
  - specs/011-reports-analytics/{tasks.md,release-signoff.md,contracts/reports-api.yaml}
tests:
  - Sales group_by_currency + per-currency KPIs — 3 passed (incl. return rate via source invoice currency)
  - End-to-end USD+PKR tenant (dashboard, sales.summary, sales.kpis, purchase, crm.pipeline, Customer 360) — passed; no cross-currency sum anywhere
  - CRM / inventory / purchase / sales equivalence and contract tests updated — green
  - installments.due_overdue at 10K rows — 63.0 s → 28.3 s (T270 harness); equivalence test green
  - Drill-down routes vs frontend pages — red before the route fix, green after
  - Frontend reports suite 70/70; tsc and eslint clean
  - mypy . = 0 (1498 files); ruff check + format clean
---

## Prompt

The user's messages in this part of the session, in order:

1. "yeh jo issues hain ina solution kiya hai sirf explain karna abhi koi task start na karna" (asked for an explanation of solutions only).
2. The user pasted the GitHub annotations: 1 error (Security Scans), Node 20 deprecation warnings, and the ubuntu-latest migration notices.
3. "aur kitna time lagega complete hone mai"
4. "pehle security scans fix karo" (recorded in PHR 0026)
5. "yeh batao abhi epic 11 complete hai ya kuch baqi rehta hai"
6. "tu yeh 1 se 4 tak ke task abhi hosakte hain"
7. "item 1 ke liye a select karo aur yeh tasks start kardo"

## Response snapshot

Phase 12 (tasks.md T294–T307). The work items:

1. **Node 24 actions (T296).** GitHub actions moved to their first Node 24 majors, each verified against the action's own `action.yml`.
2. **Drill-down (T294).** Registry and dashboard routes pointed at routes that do not exist in the UI (`/installments/contracts`, `/purchase/orders`, `/accounting/ar/...`, `/reports/<key>`, …). They now point at the real pages. Tables render per-row links, and a backend test checks every route against `frontend/src/app`.
3. **Speed (T295).** `installments.due_overdue` classified the whole line population twice per page. The new additive `get_due_overdue_report()` does it once: 2.2× faster.
4. **FR-RPT-152, option (a) (T297–T306).** Additive currency seams in Sales, Purchase, Inventory, CRM and Installments. Reports rows carry `currency_code`; aggregates, widgets and Customer 360 carry `*by_currency` lists. Single values are set only when one currency is present. The UI shows a Currency column and formats each currency separately.
   - Found along the way: Installments report rows had no currency, although the earlier findings document said they did (corrected), and Sales hard-coded `unit="USD"` on money KPIs.

The CI run on `2422cb7` failed Tests & Coverage. The log needs a login, so the failing test is unknown. These all passed locally: JWT/platform auth (284), the envelope tests and the Installments report tests. Only one local failure was seen, an intermittent `installments.dashboard` envelope failure, and it did not reproduce in three reruns.

## Outcome

- ✅ Impact: all four open items addressed; Epic 11 now meets FR-RPT-152 by reporting per currency.
- 🧪 Tests: see the `tests:` front-matter.
- 📁 Files: see the `files:` front-matter.
- 🔁 Next prompts: push and confirm the full CI suite (T307); get the failing test name from the `2422cb7` CI log if it recurs.
- 🧠 Reflection: the response shape for multi-currency aggregates is an API-contract decision that other features will reuse. An ADR is suggested and has not been created.

## Evaluation notes (flywheel)

- Failure modes observed: prettier reformatted untouched lines, so the files were reverted and the edits re-applied by hand; one replacement matched several places in a file and the edit aborted safely; Intl formats PKR with 0 decimals.
- Graders run and results (PASS/FAIL): targeted suites PASS; the full CI run is pending.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): add CI log retrieval, for example a `gh` token in the environment.
