# Epic 11 — Reports & Analytics: Official Business Specification

**Feature Branch**: `011-reports-analytics`
**Epic Sequence**: Built directly on completed **Epic 8 — Accounting & Finance**, **Epic 9 — CRM**, **Epic 9A — Platform Administration**, and **Epic 10 — Installments**. Sequence: Epic 0 ✅ → 1 ✅ → 2 ✅ → 3 ✅ → 4 ✅ → 5 ✅ → 6 ✅ → 7 ✅ → 8 ✅ → 9 ✅ → 9A ✅ → 10 ✅ → **Epic 11 ← Current** → Epic 12 (Deployment/Production Readiness) → AI Layer (future, out of scope here).
**Created**: 2026-09-11
**Status**: Draft — ready for review (specification-only; no `/sp.plan` or `/sp.tasks` performed)
**Input**: User description — "Epic 11 — Reports & Analytics: perform deep repository discovery and produce the final implementation-ready specification for a centralized, tenant-aware, branch-aware, permission-aware, entitlement-aware Reporting & Analytics Read Layer for DevSphere ERP — covering a curated report/metric catalog, source-of-truth matrix, executive dashboard, Sales/Purchase/Inventory/Accounting/CRM/Installment analytics, filters, period/comparison/money/branch/status semantics, drill-down, pagination/sorting, saved views, exports and export security, performance guardrails, freshness/caching strategy, RBAC/entitlement/tenant-isolation/privacy/audit, API and frontend requirements, real-Postgres and financial-invariant test strategy, type-safety/CI requirements, and AI-readiness — without implementing Epic 11, without an arbitrary query engine, and without duplicating any module's existing transactional or financial source of truth."

---

## Table of Contents

1. [Feature Overview](#1-feature-overview)
2. [Goals](#2-goals)
3. [Non-Goals](#3-non-goals)
4. [Actors / Personas](#4-actors--personas)
5. [Assumptions](#5-assumptions)
6. [Dependencies — Reuse vs. New Work](#6-dependencies--reuse-vs-new-work)
7. [Source-of-Truth Matrix](#7-source-of-truth-matrix)
8. [Reporting Architecture](#8-reporting-architecture)
9. [Report Catalog](#9-report-catalog)
10. [KPI / Metric Catalog](#10-kpi--metric-catalog)
11. [User Stories with Priority](#11-user-stories-with-priority)
12. [Functional Requirements — Platform & Registry](#12-functional-requirements--platform--registry)
13. [Executive Dashboard](#13-executive-dashboard)
14. [Sales Analytics](#14-sales-analytics)
15. [Purchase Analytics](#15-purchase-analytics)
16. [Inventory Analytics](#16-inventory-analytics)
17. [Accounting / Financial Reporting](#17-accounting--financial-reporting)
18. [CRM Analytics](#18-crm-analytics)
19. [Installment Analytics](#19-installment-analytics)
20. [Cross-Module Analytics](#20-cross-module-analytics)
21. [Query / Filter Contract](#21-query--filter-contract)
22. [Date/Time & Period Semantics](#22-datetime--period-semantics)
23. [Comparison Semantics](#23-comparison-semantics)
24. [Money & Currency Semantics](#24-money--currency-semantics)
25. [Branch Semantics](#25-branch-semantics)
26. [Status / Reversal / Historical-Truth Semantics](#26-status--reversal--historical-truth-semantics)
27. [Drill-Down](#27-drill-down)
28. [Pagination & Sorting](#28-pagination--sorting)
29. [Saved Report Views](#29-saved-report-views)
30. [Exports & Export Security](#30-exports--export-security)
31. [Performance & Query Guardrails](#31-performance--query-guardrails)
32. [Freshness & Caching Strategy](#32-freshness--caching-strategy)
33. [RBAC — Permission Matrix](#33-rbac--permission-matrix)
34. [Entitlements — Entitlement Matrix](#34-entitlements--entitlement-matrix)
35. [Multi-Tenancy & Tenant Isolation](#35-multi-tenancy--tenant-isolation)
36. [Security Requirements — Security Matrix](#36-security-requirements--security-matrix)
37. [Privacy & Sensitive Data](#37-privacy--sensitive-data)
38. [Platform Admin & Support-Access Boundary](#38-platform-admin--support-access-boundary)
39. [Audit & Observability](#39-audit--observability)
40. [API & Response Envelope Requirements](#40-api--response-envelope-requirements)
41. [Frontend & UX Requirements](#41-frontend--ux-requirements)
42. [Accessibility & Responsiveness](#42-accessibility--responsiveness)
43. [Concurrency / Failure / Recovery Behavior](#43-concurrency--failure--recovery-behavior)
44. [Non-Functional Requirements](#44-non-functional-requirements)
45. [Edge Cases](#45-edge-cases)
46. [Acceptance Scenarios](#46-acceptance-scenarios)
47. [Success Criteria](#47-success-criteria)
48. [Test Strategy](#48-test-strategy)
49. [Type Safety / CI Requirements](#49-type-safety--ci-requirements)
50. [AI-Readiness](#50-ai-readiness)
51. [Out of Scope / Deferred](#51-out-of-scope--deferred)
52. [Risks](#52-risks)
53. [Open Questions / Clarifications](#53-open-questions--clarifications)
54. [Constitution Compliance / Traceability](#54-constitution-compliance--traceability)

---

## 1. Feature Overview

Epic 11 introduces the **Reporting & Analytics Read Layer** — a centralized, curated surface through which authorized tenant users understand business performance, inspect operational activity, analyze financial results, compare periods, filter and segment data, drill down into supporting records, export authorized report data, use an executive dashboard, and (optionally) save private reporting configurations, with consistent KPI definitions across every module.

Repository discovery (§6) found something the governing prompt anticipated but did not assume: **every completed module already has its own production-grade, tested, exported report/KPI layer.** Accounting alone already implements Trial Balance, General Ledger, Profit & Loss, Balance Sheet, Cash Flow, AR/AP aging + statements, bank/cash books, tax reports, cost-center/project P&L, and a 15-KPI CFO dashboard, all with PDF/Excel export (`modules/accounting/services/{financial_statements,report_service,ar_service,ap_service,kpi_service,report_export}.py`). Sales exposes 25 report types + 12 KPIs (`modules/sales/services/{report_service,kpi_service}.py`). Purchase exposes 14 reports + 11 KPIs (`modules/purchase/services/{report_service,kpi_service}.py`). Inventory exposes 14 reports + a 10-KPI dashboard, including dead-stock, fast/slow-moving, and stock-aging computations (`modules/inventory/services/{report_service,kpi_service}.py`). CRM exposes a dashboard plus pipeline/lead/activity reports (`modules/crm/services/reporting_service.py`). Installments exposes 8 report types plus a dashboard, explicitly built "so a future Epic 11 reporting/analytics platform can consume it without requiring Installments' own internal schema knowledge" (`specs/010-installments/spec.md` §23, FR-INST-362).

**Epic 11 is therefore not a green-field report-building exercise.** Its genuine, non-duplicative scope is: (a) a curated cross-module **report/metric registry** giving every existing and new report a stable key, permission, entitlement, and freshness classification; (b) a **executive dashboard** composing KPIs already computed by each module's own KPI service, under one authoritative definition per metric; (c) a small number of genuinely new **cross-module reports** that cannot be produced by any single existing module service; (d) a consistent, secure **query/filter/pagination/export/drill-down contract** wrapping the existing per-module report endpoints, which today are inconsistent in shape (Sales: one generic `/reports/{report_type}`; Purchase: one endpoint per report; Accounting: one endpoint per statement; Installments: one generic `/reports/{reportType}`); (e) **saved private report views**, which do not exist anywhere in the repository today; and (f) forward-compatible, typed, permission-aware contracts a future AI layer can safely reuse.

Frontend discovery (§6.4) found the reporting UI is currently siloed per module with no charting library, no shared `DataTable`, no shared money/date formatting utilities, and no cross-module dashboard — confirming the frontend consolidation work is genuinely new, even though the backend computation logic mostly is not.

## 2. Goals

- G1: Establish one **report/metric registry** so every report and every important KPI has exactly one authoritative definition, consumed identically by the executive dashboard, domain report pages, exports, and (later) AI tools — "One Metric → One Authoritative Definition → Many Consumers."
- G2: Wrap the already-completed per-module report/KPI services (Sales, Purchase, Inventory, Accounting, CRM, Installments) behind one consistent, secure, typed query/response contract, rather than re-deriving any of their business logic.
- G3: Deliver a curated executive dashboard blending Sales, Purchase, Inventory, Accounting (financial authority), CRM, and Installments KPIs, gracefully degrading per widget when a module is disabled, unentitled, unpermitted, or has no data.
- G4: Enforce tenant isolation, RBAC, and module entitlement identically for every report, dashboard widget, export, drill-down, and saved view — no report, chart, count, or export may ever expose another tenant's data, and no disabled module's data may leak through a report.
- G5: Provide controlled, auditable exports (CSV/XLSX; PDF only where an existing precedent — Accounting's financial statements — already justifies it) that preserve the exact tenant/branch/filter/permission scope of the report that produced them.
- G6: Provide private, user-owned saved report views (filters, grouping, sorting, columns, date preset) — new Epic 11-owned state, with report execution itself remaining strictly read-only against every business domain.
- G7: Make Accounting the unambiguous financial authority for every financial metric (AR, AP, revenue recognition, cash, GL-derived figures), and make each operational module authoritative for its own operational activity, explicitly distinguishing operational metrics (e.g., "Sales Orders Created") from financial metrics (e.g., "Recognized Revenue") wherever the repository shows they are not the same number.
- G8: Produce stable, typed, permission-aware report/metric contracts structurally ready for a future AI layer to consume safely — without implementing any AI capability now.

## 3. Non-Goals

- NG1: Epic 11 does not implement an arbitrary query engine, user-defined SQL, unrestricted query builder, arbitrary column access, or raw database exploration API. Every report is a curated, registered capability.
- NG2: Epic 11 does not become a second source of financial truth. It never writes to Sales, Purchase, Inventory, Accounting, CRM, or Installments business tables; report execution is read-only in every business domain (Epic 11-owned state — saved views, export metadata — is the only thing it may write).
- NG3: Epic 11 does not rebuild Trial Balance, GL, P&L, Balance Sheet, Cash Flow, AR/AP aging, or any of the 90+ report/KPI computations that already exist across Accounting, Sales, Purchase, Inventory, CRM, and Installments (§6). It consumes them.
- NG4: Epic 11 does not implement a data warehouse, OLAP engine, ClickHouse, Elasticsearch analytics, materialized-view infrastructure, or event-stream analytics platform.
- NG5: Epic 11 does not implement scheduled/emailed reports, report subscriptions, shared/collaborative saved views, an arbitrary custom report builder, or a pivot builder.
- NG6: Epic 11 does not implement any AI capability — no LLM integration, no NL-to-SQL, no embeddings/vector database, no AI agent, no AI credit billing. §50 establishes readiness only.
- NG7: Epic 11 does not implement asynchronous/background export job infrastructure. No such infrastructure exists anywhere in the repository today (§6.5); Epic 11 defines a synchronous export contract with an explicit, extensible seam for a future async path.
- NG8: Epic 11 does not grant Platform Administration any new tenant-business-data access. Platform Admin's existing aggregate-only, business-record-excluded boundary (Constitution §50; `specs/009a-platform-admin/spec.md` BR-9A-021, FR-9A-121) is preserved unchanged (§38).
- NG9: Epic 11 does not implement cross-tenant/platform-wide SaaS analytics. It is tenant ERP reporting only (§51).
- NG10: Epic 11 does not implement or require a first-class `Branch` entity, per-user branch access-control list, or branch-level authorization boundary — none exists anywhere in the repository today (§25), and inventing one is out of scope for this epic.

## 4. Actors / Personas

Consistent with the existing company-scoped RBAC model (Constitution §16; `modules/users_roles`), Epic 11 introduces no new actor *types*, only new *permissions* (§33) assignable to existing and custom company roles.

| Actor | Description |
|---|---|
| **Company Owner / Admin** | Full tenant authority; can view/export every enabled, permitted report family and manage their own saved views. |
| **Executive / Business Owner** | Primary consumer of the executive dashboard and financial reports; typically holds broad `reports.*.view` permissions but not necessarily operational write permissions in every module. |
| **Sales / CRM / Purchase / Inventory / Installments Operational User** | Views reports scoped to their own module(s) per assigned `reports.<domain>.view` permission; drill-down still requires the underlying module's own record-view permission (§27). |
| **Accountant / Finance User** | Views financial reports (`reports.accounting.view`), for which Accounting itself remains the sole source of truth; may hold export rights for statutory/financial reports. |
| **Auditor / Read-Only User** | Views reports and, where granted, drill-down and audit history; never exports or manages saved views unless separately permitted. |
| **Platform Administrator** | Governs the `reports` module entitlement for a tenant (Epic 9A model); gains **no** tenant business-data report access through that governance (§38). |
| **Future AI Agent (out of scope, forward-referenced)** | Not implemented in Epic 11; §50 defines the contract shape a future AI gateway would consume, inheriting the same tenant/branch/RBAC/entitlement context as a human user. |

## 5. Assumptions

- A1: "Epic 11" is the correct, current numbering (Constitution's own example table, and `specs/010-installments/spec.md`'s epic-sequence note, both place Reports & Analytics at Epic 11, following the resolved Epic 10 = Installments numbering).
- A2: Every domain report Epic 11 catalogs (§9) computes its figures by calling the already-completed per-module report/KPI services identified in §6, not by querying their underlying tables directly — this is the central architectural decision of this Epic and is treated as non-negotiable for `/sp.plan`.
- A3: **Branch is NOT currently an authorization boundary anywhere in DevSphere ERP.** No first-class `Branch` entity, branch table, or user-branch access-control concept exists anywhere in the repository (§25). Where a `branch_id` column exists, it is nullable, unconstrained, and explicitly documented in source as "reserved for future branch-linkage." Epic 11 therefore treats branch filtering as an optional **data filter** on the handful of entities that already carry the column (Installment contracts, Purchase POs/PRs/Suppliers, Inventory warehouses) — never as an authorization boundary — and defers true branch-level RBAC to a future epic when a Branch entity/ACL exists (§25, matches Constitution §10 "readiness, not full implementation"). This is a load-bearing fact for this specification, re-confirmed during the 2026-09-11 correction pass.
- A4: Money precision for any figure that touches Accounting or Installments follows their shared `NUMERIC(20,6)`/`Decimal` convention; Sales/Purchase figures use their own `NUMERIC(15,2)` convention at the source. Where Epic 11 combines figures from both families (e.g., a dashboard summing Sales' operational revenue estimate alongside Accounting's recognized revenue), the higher-precision `NUMERIC(20,6)` representation is used for any arithmetic, with rounding applied only at final display per the tenant's currency decimal places (mirrors `specs/010-installments/spec.md` Assumption A4's precedent of resolving in Accounting's favor).
- A5: Full multi-currency infrastructure (`ExchangeRate`, per-entry `exchange_rate`, `base_currency_code`) is confirmed to exist only in Accounting (`modules/accounting/models/foundation.py`). Whether Sales/Purchase/Inventory/CRM carry a genuine multi-currency transaction model was not exhaustively confirmed during discovery beyond Installments' single immutable `currency_code` per contract; `/sp.plan` MUST verify this per module before implementing cross-module currency aggregation. Until verified, Epic 11 reports display amounts in the currency captured on the source record and only translate to the company's base currency (using Accounting's `CurrencyService`) for financial reports that are already expressed in base currency today.
- A6 (**re-verified and corrected, 2026-09-11 correction pass**): Reports & Analytics is entitled as its own whole module (`grain=module` Capability, following the CRM/Installments precedent — `specs/010-installments/spec.md` §22), registered with the existing Platform Admin Capability/Plan catalogue, resolved through the existing `PlatformEntitlementService`/`require_capability_entitled()` mechanism (`modules/platform_admin/{services/entitlement_service.py,dependencies.py}`). Domain-specific report families additionally require that domain's own module entitlement (§34) — e.g., CRM reports require both `reports` and `crm` to be entitled. **Definitive re-verification finding (supersedes the original discovery pass's unverified "always-on core module" hedge):** all six source modules — Sales, Purchase, Inventory, Accounting, CRM, Installments — are genuinely registered `grain=module` Capabilities in the platform Capability catalogue (`CapabilitySeedService.MODULE_CAPABILITY_CATALOGUE`, `modules/platform_admin/services/capability_seed_service.py:25-32`), and every one of them has a real, structural entitlement-enforcement point: Sales/Purchase/Inventory/Accounting/CRM at router-mount time (`require_capability_entitled(...)`, `api/v1/router.py:122-175`), and Installments at service-method time via `InstallmentAccessPolicy.authorize()` (a deliberate, deeper-granularity design per ADR-INST-06, not an absence of gating). **None of the six is structurally ungated or exempt from entitlement.** They differ only in *default state* for a tenant with no active Subscription (the normal state for a brand-new company today, since `CompanyService.create_company()` never auto-assigns a Subscription): Sales/Purchase/Inventory/Accounting resolve to entitled by default because they have no dedicated tenant-level master toggle and instead use a stateless `DefaultAlwaysEnabledModuleProvider` (`modules/platform_admin/services/module_enablement.py:79-96`) for the Tenant Toggle input, while CRM and Installments each have an explicit master toggle that defaults to `False` until a tenant deliberately enables it (`modules/crm/services/feature_flag_service.py:64-72`; Installments' analogous flag service). This resolves Open Question OQ-2 from the original discovery pass — see §34 for the corrected Entitlement Matrix and FR-RPT-254/255 for the resulting requirements.
- A7: The Report Registry (§8.2) is implemented as a static, typed, in-code catalog (module-local, versioned with the code) rather than a database-backed, user-editable metadata table — because the catalog is curated and fixed by the platform team, not end-user-defined, and a static registry avoids drift between code and data (mirrors the constitution's simplicity/DRY priorities, §2, §7). `/sp.plan` may revisit this if a concrete need for runtime-editable report metadata emerges.
- A8: No specific numeric performance/scale targets exist elsewhere in the repository for a module of this kind (matching the precedent already set by `specs/009a-platform-admin/spec.md` and `specs/010-installments/spec.md` Assumption A8); Non-Functional Requirements (§44) remain qualitative and testable rather than fabricated SLAs, except where a guardrail number is explicitly marked as a **Recommended Decision** in §31/§30 with its own rationale.
- A9: Every report/dashboard figure is computed at request time from authoritative source data (transactional/live freshness), mirroring the explicit precedent that "no materialized/cached KPI table exists" for Installments, CRM, Sales, Purchase, or Inventory reporting today (all confirmed per-request computation). Caching is explicitly deferred (§32) rather than introduced speculatively.
- A10: The existing `StandardResponse[T]`/`PaginatedResponse[T]`/`ErrorResponse`/`PaginationParams` envelope (`core/schemas/{response,pagination}.py`) is reused verbatim for all Epic 11 endpoints; Epic 11 introduces no competing envelope shape.
- A11 (**re-verified and corrected, 2026-09-11 correction pass**): Inventory valuation authority is **genuinely unresolved/incomplete in the repository today — not a clean case of either module owning it** (supersedes the original discovery pass's flat "Inventory is authoritative, not Accounting" conclusion, which overstated the evidence). ADR-0004 (`history/adr/0004-gl-account-resolution-for-sales-purchase-inventory-integration-events.md`) has **Status: Proposed** (never Accepted) and explicitly declines to resolve the question, stating inventory-event GL-value sufficiency "is not yet confirmed and is called out as a residual open item for Phase 4 implementation, not resolved by this ADR." Accounting's own Chart-of-Accounts templates already seed real Inventory ASSET accounts (`modules/accounting/services/coa_templates.py:149,158-162,186,206,221`, e.g. `"1300" Merchandise Inventory`) — so Accounting's data model was designed to eventually hold this authority — but zero code path ever posts to them (no COGS entry on any sale; `handle_inventory_adjustment_posted` is an unsubscribed stub whose own module docstring says "no safe default account mapping exists yet," `modules/accounting/handlers/integration_handlers.py:17,197-206`), so those accounts sit permanently unpopulated for inventory activity. Meanwhile Inventory's own live `StockPosition.unit_cost` WAC figure (`_compute_wac()`, `modules/inventory/services/stock_service.py:70-81`) is documented only as an internal operational costing field ("Current weighted-average or FIFO unit cost," `modules/inventory/models/stock.py:121-126`) — never as "the tenant's authoritative balance-sheet inventory value" — and Inventory's own Epic 5 specification frames it as something that "feeds into" and must be "auditable for" Accounting's eventual balance sheet (`specs/005-inventory-management/spec.md:858,1981`), i.e. an operational input to a not-yet-built integration, not a declared final figure. The dedicated regression test making this explicit is literally named `TestInventoryAdjustmentGLGap` and documents itself as "a deliberate tripwire, not an oversight" (`tests/integration/api/v1/accounting/test_e2e_inventory_gl.py`). Epic 11 MUST NOT paper over this gap by unilaterally declaring either module "authoritative" — see the corrected §7 row, §9/§10 catalog entries, and §16 requirements, all of which now present Inventory's WAC figure explicitly as an **operational stock valuation**, distinct from any (currently nonexistent) **accounting inventory balance**, with the reconciliation gap stated as a documented prerequisite rather than fabricated behavior (governing correction-pass §5/§6).

## 6. Dependencies — Reuse vs. New Work

### 6.1 Existing Dependencies (Reused, Not Redefined)

| Dependency | Source Epic | What Epic 11 Reuses |
|---|---|---|
| `company_id` tenant isolation, `get_current_company_member` dependency | Epic 1/3/4 | Every report query is scoped through the existing tenant-context dependency; no new tenant-resolution mechanism. |
| Permission model: `Permission`/`RolePermission`, dot-notation `<module>.<resource>.<action>` codes, per-module inline `user_has_<module>_permission()` check functions | Epic 4 | New `reports.*` permission codes only (§33); reuses the exact enforcement pattern already used by every other module. |
| `PlatformEntitlementService.resolve_effective_entitlement()`, `require_capability_entitled()` router-mount gate, `ModuleEnablementProvider` | Epic 9A | The two-tier Plan-ceiling + tenant-toggle + override entitlement model Epic 11 plugs `reports` into (§34), following the CRM/Installments precedent exactly. |
| `AccountsReceivableService`, `AccountsPayableService`, `FinancialStatementService`, `ReportService` (accounting), `FinancialKPIService`, `PostingEngine`, `Currency`/`ExchangeRate`/`CurrencyService` | Epic 8 | The complete, already-tested financial-statement/subsidiary-ledger/KPI computation layer Epic 11 wraps for every financial figure (§17). |
| `modules/sales/services/{report_service,kpi_service,report_export_service}.py` | Epic 7 | The complete Sales report/KPI computation layer (§14). |
| `modules/purchase/services/{report_service,kpi_service,report_export_service}.py` | Epic 6 | The complete Purchase report/KPI computation layer (§15). |
| `modules/inventory/services/{report_service,kpi_service,export_service}.py` | Epic 5 | The complete Inventory report/KPI computation layer, including dead-stock/velocity/aging (§16). |
| `modules/crm/services/reporting_service.py` | Epic 9 | The complete CRM pipeline/lead/activity reporting layer (§18). |
| `modules/installments/services/reporting_service.py` | Epic 10 | The complete Installments contract/collection/aging reporting layer, explicitly built for this Epic to consume (§19). |
| `StandardResponse[T]`, `PaginatedResponse[T]`, `ErrorResponse`, `PaginationParams` (`core/schemas/{response,pagination}.py`) | Platform convention | The response/pagination envelope for every Epic 11 endpoint (§40). |
| `openpyxl`/`reportlab`-based export pattern: service returns `(bytes, filename, content_type)`, router returns a `Response` with `Content-Disposition: attachment` | Accounting/Sales/Purchase/Inventory/Platform Admin | The export mechanism Epic 11 reuses, rather than introducing a new file-generation stack (§30). |
| `core/events/outbox.py` transactional outbox | Platform convention | Reused only if Epic 11 needs to publish its own domain events (e.g., `ReportExported`) for audit/observability — no new event-bus mechanism introduced. |
| `core/utils/datetime.py` (`utcnow()`, `ensure_utc()`), `Company.default_timezone` (IANA string) | Epic 1/3 | Period-boundary computation (§22) uses the existing per-company timezone setting; no new timezone infrastructure. |
| Real-Postgres test fixture chain (`tests/integration/migrations/conftest.py` `pg_test_db`/`alembic_upgrade`, per-directory `pg_engine`/`db_session` re-exports) | Pre-Epic-11 stabilization | The exact fixture pattern Epic 11's Postgres-dependent report tests reuse (§48). |
| CI gates: `ruff`, `ruff format --check`, blocking `mypy .` (covering `tests/`), `pytest --cov-fail-under=80` against a real `postgres:16-alpine` service | Pre-Epic-11 stabilization | Unchanged; Epic 11 code and tests are subject to the same gates (§49). |

### 6.2 New Requirements Introduced by Epic 11

- A Report Registry / Report Definition catalog (§8.2, §9) — no report metadata registry exists anywhere in the repository today; each module's reports are only individually enumerated inside that module's own schema/service code.
- A Metric/KPI semantic catalog (§10) with one authoritative definition per cross-module metric — no such catalog exists today; each module defines its own KPI names independently (confirmed risk: Sales' "Gross Margin" and Accounting's "Gross Profit Margin" are two different computations today, §10).
- A unified, consistent query/filter/pagination/drill-down contract wrapping the structurally inconsistent existing per-module report endpoints (§21).
- A new `SavedReportView` entity (§29) — no saved-view/saved-query concept exists anywhere in the repository today.
- A new Executive Dashboard endpoint composing KPIs across modules (§13) — no cross-module dashboard exists; `dashboard/page.tsx` today only shows the authenticated user's own profile.
- New permission codes under the `reports.*` namespace (§33).
- Registration of `reports` as a new `grain=module` Capability with the Platform Admin Capability/Plan catalogue (§34).
- A frontend `(reports)` route group, a shared `DataTable` component (pagination/sorting/column formatting), a shared money/date formatting utility, a charting library dependency, and entitlement/permission-aware nav wiring — none of which exist today (§41).
- Domain events for report-affecting audit purposes (e.g., `ReportExported`) if `/sp.plan` determines the existing per-module audit logs are insufficient for export auditability (§39).

## 7. Source-of-Truth Matrix

| Reporting Area | Authoritative Domain | Evidence |
|---|---|---|
| Sales order / quotation / delivery activity | **Sales** | `modules/sales/models/{order,quotation,delivery}.py`; no other module owns this data. |
| Sales invoice commercial facts (amounts, lines, status) | **Sales** | `modules/sales/models/invoice.py`. |
| Recognized revenue / Accounts Receivable balance | **Accounting** | `SalesInvoice` has no `paid_amount`/`amount_due` field; AR is created only via `handle_sales_invoice_posted` → `AccountsReceivableService.record_sales_invoice()` (`modules/accounting/handlers/integration_handlers.py:71-117`). |
| Procurement activity (POs, requests, amendments) | **Purchase** | `modules/purchase/models/{purchase_order,purchase_request}.py`. |
| Goods receipt / vendor return activity | **Purchase** | `modules/purchase/models/{goods_receipt,vendor_return}.py`. |
| Accounts Payable balance / supplier bills | **Accounting** | No Supplier Invoice/Bill/AP entity exists in Purchase at all; bills are entered directly via `POST /accounting/ap/bills` (`AccountsPayableService.record_supplier_bill()`); `Cost.invoice_id` is a reserved, currently-unpopulated FK. |
| Stock on hand / stock movement | **Inventory** | `modules/inventory/models/stock.py` (`StockPosition`, immutable `StockMovement` ledger). |
| **Inventory valuation** | **Unresolved / incomplete — neither module is cleanly authoritative (Assumption A11).** Inventory owns a live **operational stock valuation** (WAC); Accounting owns the eventual **accounting inventory balance** concept (seeded GL accounts) but no integration populates it. | ADR-0004 (Status: **Proposed**, never Accepted) explicitly leaves "Inventory GL-value sufficiency" unresolved; `handle_inventory_adjustment_posted` is an unsubscribed stub (`modules/accounting/handlers/integration_handlers.py:17,197-206`); Accounting's COA templates seed real Inventory ASSET accounts that are never posted to (`modules/accounting/services/coa_templates.py:149,158-162,186,206,221`); Inventory computes WAC operationally (`_compute_wac()`, `modules/inventory/services/stock_service.py:70-81`) without claiming financial authority; the gap is explicitly documented as a live tripwire in `tests/integration/api/v1/accounting/test_e2e_inventory_gl.py` (`TestInventoryAdjustmentGLGap`). Epic 11 reports this as an **operational stock valuation, not a financial-statement figure** (§9, §10, §16). |
| Chart of accounts, journal entries, posting status, fiscal periods | **Accounting** | `modules/accounting/models/{coa,gl,fiscal}.py`; `PostingEngine` is "the single domain service authorised to write to the General Ledger." |
| Financial statements (Trial Balance, GL, P&L, Balance Sheet, Cash Flow) | **Accounting** | `FinancialStatementService`, `ReportService` (accounting). |
| Bank / cash summaries | **Accounting** | `BankAccountService.get_bank_book()`, `CashAccountService.get_cash_book()`. |
| CRM pipeline (leads, opportunities, stages, win/loss) | **CRM** | `modules/crm/models/{lead,opportunity,pipeline,pipeline_stage}.py`. |
| Installment contract / schedule / operational delinquency state | **Installments** | `modules/installments/models/{contract,schedule}.py`; `DueStateCalculator` computes due-state deterministically at read time. |
| Installment financial postings (collections, allocations, AR effect) | **Accounting**, read through `AccountingIntegrationGateway` | "No Accounting balance is cached or duplicated inside Installments — every read call here is a live pass-through against Accounting's own authoritative state" (`modules/installments/services/accounting_gateway.py:16-18`). |
| Customer/Supplier master data | **Sales** (Customer) / **Purchase** (Supplier) | `modules/sales/models/customer.py`, `modules/purchase/models/supplier.py`. |
| Product/Item master data | **Inventory** | `modules/inventory/models/product.py`; Sales/Purchase lines reference it by loose UUID only (no DB-level FK). |
| Tenant lifecycle, plans, entitlements, platform-level users | **Platform Administration** | `specs/009a-platform-admin/spec.md`; never a source for tenant business-data reports (§38). |

## 8. Reporting Architecture

### 8.1 Execution Model

```
Authenticated Request
  → Tenant Context (get_current_company_member, company_id from path)
  → Entitlement Gate — "reports" module entitlement (require_capability_entitled("reports"))
  → Domain Entitlement Gate — the report's source module's own entitlement, where applicable (§34)
  → RBAC Permission Check — reports.<domain>.view / .export (inline user_has_reports_permission(), matching platform convention)
  → Report Definition Lookup (Report Registry, §8.2) — resolves the requested report_key
  → Filter Validation — only the filters/dimensions/sort fields the Report Definition declares are accepted (§21)
  → Branch Scope Application — optional data filter only where the underlying entity carries branch_id (§25)
  → Reporting Service — calls the authoritative per-module report/KPI service identified in §6/§7 (never a raw query against another module's tables)
  → Typed Result — a Pydantic response schema specific to the report
  → API Response — StandardResponse[T] or PaginatedResponse[T] (§40), or a file Response for export (§30)
```

This adapts the governing prompt's suggested flow to what the repository already enforces (tenant context, permission checks, entitlement gates) rather than introducing new layers where an equivalent already exists.

### 8.2 Report Registry / Report Definition Model

Each catalog entry in §9 is backed by a typed **Report Definition** (Assumption A7: static, in-code, versioned with the codebase) declaring:

- `key` — stable, permanent identifier (e.g. `sales.summary`, `accounting.trial_balance`, `exec.dashboard`); never renamed once shipped (§40.2).
- `name`, `description`, `domain` (module/family).
- `authoritative_source` — which module's service this definition calls (traceable to §7).
- `required_permission` — the `reports.<domain>.view` (or `.export`) permission code (§33).
- `required_entitlements` — `reports` plus, where applicable, the source domain's own entitlement (§34).
- `supported_filters`, `supported_dimensions`, `supported_measures`, `sortable_fields` — explicit allow-lists; nothing outside this list is queryable (§21, NG1).
- `exportable` (bool, formats), `drill_down_targets` (§27), `freshness` classification (§32), `branch_filterable` (bool, §25).

**FR-RPT-001**: The system MUST maintain a Report Registry containing exactly one Report Definition per catalog entry in §9, and MUST reject any request referencing an unregistered `report_key` with a documented 404-class error.
**FR-RPT-002**: The system MUST NOT expose any endpoint that accepts an arbitrary table name, arbitrary column list, or arbitrary SQL/query expression, under any permission level (NG1).
**FR-RPT-003**: Every Report Definition's `authoritative_source` MUST resolve to an existing, already-implemented per-module report/KPI service identified in §6.1/§7; a Report Definition MUST NOT re-implement logic an authoritative module already owns.
**FR-RPT-004**: The Report Registry MUST be independently unit-testable — for every registered key, the declared filters/dimensions/measures/sort fields MUST match what the wrapped service method actually accepts, preventing catalog/implementation drift.

## 9. Report Catalog

Epic 11's catalog is organized into (a) reports **wrapped** from an already-implemented per-module service (the large majority — see §6.1/§7), and (b) reports that are genuinely **new** cross-module compositions. Per-module services already expose more report *variants* than are listed individually below (e.g., Sales' 25 report types, Purchase's 14, Inventory's 14); this catalog registers each **family** as one or more Report Definitions and defers the exhaustive one-row-per-variant enumeration to `/sp.plan` and `/sp.tasks`, where each family expands into its full set of registry entries using the same required-columns shape shown here.

Legend — **Src**: W = Wrapped (existing service), N = New (Epic 11-only composition). **Branch**: Y = optional branch filter available (§25), — = not available (no `branch_id` on the source entity).

| Report | Key | Domain | Purpose | Authoritative Source | Permission | Entitlement | Branch | Filters | Measures | Drill-down | Export | Now/Deferred |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Executive Dashboard | `exec.dashboard` | Cross-module | Curated KPI overview | §10 metrics, each from its own module | `reports.executive.view` | `reports` + per-widget source entitlement | — | period, comparison | see §13 | to source report | — (dashboard only) | Now |
| Sales Summary | `sales.summary` | Sales | Orders/invoices/revenue overview | Sales `ReportService._sales_summary` | `reports.sales.view` | `reports` + `sales` | — | period, status, customer | Gross/Net Sales, order count, AOV | invoice/order list | CSV/XLSX | Now |
| Sales by Customer | `sales.by_customer` | Sales | Revenue/volume per customer | Sales `ReportService` | `reports.sales.view` | `reports` + `sales` | — | period, customer | Net Sales, count | customer → invoices | CSV/XLSX | Now |
| Sales by Product | `sales.by_product` | Sales | Revenue/volume per product | Sales `ReportService` | `reports.sales.view` | `reports` + `sales` | — | period, product | Net Sales, qty | product → invoice lines | CSV/XLSX | Now |
| Top Customers | `sales.top_customers` | Sales | Ranked customer value | Sales `ReportService` | `reports.sales.view` | `reports` + `sales` | — | period, limit | Net Sales rank | customer detail | CSV/XLSX | Now |
| Sales Trend | `sales.trend` | Sales | Period-over-period trend | Sales `ReportService` | `reports.sales.view` | `reports` + `sales` | — | period, granularity | Net Sales series | period → invoices | CSV/XLSX | Now |
| Quotation Pipeline / Conversion | `sales.quotation_pipeline` | Sales | Quote-to-order funnel | Sales `ReportService` | `reports.sales.view` | `reports` + `sales` | — | period, status | conversion rate | quotation detail | CSV/XLSX | Now |
| Sales Returns | `sales.returns` | Sales | Return/credit-note activity | Sales `ReportService` | `reports.sales.view` | `reports` + `sales` | — | period, status | return value/count | return detail | CSV/XLSX | Now |
| Sales KPI Dashboard | `sales.kpis` | Sales | 12 existing Sales KPIs | Sales `KPIService.get_dashboard()` | `reports.sales.view` | `reports` + `sales` | — | period, comparison | 12 KPIs (verbatim) | to each source report | — | Now |
| Remaining Sales report variants (17 of 25) | `sales.*` (deferred keys) | Sales | Ageing, credit, discount, audit, pricing variants | Sales `ReportService` | `reports.sales.view`(+`.export`) | `reports` + `sales` | — | per variant | per variant | per variant | CSV/XLSX | Deferred (catalogued in `/sp.tasks`) |
| Purchase Summary | `purchase.summary` | Purchase | PO/spend overview | Purchase `ReportService.purchase_order_summary` | `reports.purchase.view` | `reports` + `purchase` | — | period, status, supplier | spend, PO count | PO list | CSV/XLSX | Now |
| Purchase by Supplier | `purchase.by_supplier` | Purchase | Spend per supplier | Purchase `ReportService.purchase_by_supplier` | `reports.purchase.view` | `reports` + `purchase` | — | period, supplier | spend | supplier → POs | CSV/XLSX | Now |
| Supplier Performance | `purchase.supplier_performance` | Purchase | On-time %, rejection %, PPV | Purchase `KPIService` | `reports.purchase.view` | `reports` + `purchase` | — | period, supplier | OTD%, rejection%, PPV% | supplier detail | CSV/XLSX | Now |
| Open Purchase Commitments | `purchase.open_commitments` | Purchase | Outstanding PO value | Purchase `ReportService.open_purchase_commitments` | `reports.purchase.view` | `reports` + `purchase` | Y (PO) | period, supplier, branch | open value | PO list | CSV/XLSX | Now |
| Pending / Overdue Deliveries | `purchase.pending_deliveries` | Purchase | POs awaiting receipt | Purchase `ReportService` | `reports.purchase.view` | `reports` + `purchase` | Y (PO) | period, supplier, branch | count, value | PO detail | CSV/XLSX | Now |
| Vendor Return Report | `purchase.vendor_returns` | Purchase | RMA activity | Purchase `ReportService.vendor_return_report` | `reports.purchase.view` | `reports` + `purchase` | — | period, supplier | return value/count | RMA detail | CSV/XLSX | Now |
| Purchase KPI Dashboard | `purchase.kpis` | Purchase | 11 existing Purchase KPIs | Purchase `KPIService.get_all_kpis()` | `reports.purchase.view` | `reports` + `purchase` | — | period | 11 KPIs (verbatim) | to each source report | — | Now |
| Remaining Purchase report variants (7 of 14) | `purchase.*` (deferred keys) | Purchase | PPV detail, category, trend, rejection, audit-trail variants | Purchase `ReportService` | `reports.purchase.view`(+`.export`) | `reports` + `purchase` | Y where source supports it | per variant | per variant | per variant | CSV/XLSX | Deferred |
| Inventory Summary | `inventory.summary` | Inventory | Stock overview | Inventory `ReportService` | `reports.inventory.view` | `reports` + `inventory` | Y (warehouse) | period, warehouse, category | qty, value | product detail | CSV/XLSX | Now |
| Operational Stock Valuation (WAC) **(renamed, 2026-09-11 — was "Inventory Valuation")** | `inventory.valuation` | Inventory | On-hand stock costed at Weighted-Average-Cost for **operational** purposes; explicitly **not** a reconciled accounting inventory balance (§7, Assumption A11 — authority is unresolved/incomplete) | Inventory `ReportService.inventory_valuation` (WAC, §7) | `reports.inventory.view` | `reports` + `inventory` | Y (warehouse) | as-of date, warehouse | operational valuation (WAC) | stock position detail | CSV/XLSX | Now — with a mandatory "operational, unreconciled with Accounting GL" disclaimer in the response (FR-RPT-071) |
| Stock Position | `inventory.stock_position` | Inventory | On-hand by location | Inventory `ReportService` | `reports.inventory.view` | `reports` + `inventory` | Y (warehouse) | warehouse, product | qty on hand/reserved | movement history | CSV/XLSX | Now |
| Dead Stock | `inventory.dead_stock` | Inventory | Zero-movement products | Inventory `ReportService.dead_stock` | `reports.inventory.view` | `reports` + `inventory` | Y (warehouse) | threshold days | dead value | product detail | CSV/XLSX | Now |
| Movement Velocity (fast/slow-moving) | `inventory.movement_velocity` | Inventory | Fast/slow movers | Inventory `ReportService.movement_velocity` | `reports.inventory.view` | `reports` + `inventory` | Y (warehouse) | period, top N | movement count rank | product detail | CSV/XLSX | Now |
| Stock Aging | `inventory.stock_aging` | Inventory | Age-bucketed on-hand stock | Inventory `ReportService.stock_aging` | `reports.inventory.view` | `reports` + `inventory` | Y (warehouse) | as-of date | qty/value per bucket | product detail | CSV/XLSX | Now |
| Low-Stock / Reorder Alerts | `inventory.low_stock` | Inventory | Alerts below reorder point | Inventory `LowStockAlert`/`ReorderRule` | `reports.inventory.view` | `reports` + `inventory` | Y (warehouse) | warehouse | alert count/value | product detail | CSV/XLSX | Now |
| Inventory KPI Dashboard | `inventory.kpis` | Inventory | 10 existing Inventory KPIs | Inventory `KPIService` | `reports.inventory.view` | `reports` + `inventory` | Y (warehouse) | period | 10 KPIs (verbatim) | to each source report | — | Now |
| Remaining Inventory report variants (6 of 14) | `inventory.*` (deferred keys) | Inventory | Category/brand, warehouse utilisation, operational/trend variants | Inventory `ReportService` | `reports.inventory.view`(+`.export`) | `reports` + `inventory` | Y where source supports it | per variant | per variant | per variant | CSV/XLSX | Deferred |
| Trial Balance | `accounting.trial_balance` | Accounting | Debit=Credit control | `FinancialStatementService.get_trial_balance` | `reports.accounting.view` | `reports` + `accounting` | — | period, comparative | account balances | account → GL | PDF/XLSX | Now |
| General Ledger | `accounting.gl` | Accounting | Account/journal detail | `ReportService.get_gl_report` (cursor-paginated) | `reports.accounting.view` | `reports` + `accounting` | — | period, account, source | debit/credit lines | journal entry detail | CSV/XLSX | Now |
| Profit & Loss | `accounting.profit_loss` | Accounting | Income statement | `FinancialStatementService.get_pl` | `reports.accounting.view` | `reports` + `accounting` | — | period, comparative, cost center | revenue/expense/net income | account → GL | PDF/XLSX | Now |
| Balance Sheet | `accounting.balance_sheet` | Accounting | Financial position | `FinancialStatementService.get_balance_sheet` | `reports.accounting.view` | `reports` + `accounting` | — | as-of date, comparative | assets/liabilities/equity | account → GL | PDF/XLSX | Now |
| Cash Flow Statement | `accounting.cash_flow` | Accounting | Indirect-method cash flow | `FinancialStatementService.get_cash_flow` | `reports.accounting.view` | `reports` + `accounting` | — | period | operating/investing/financing | account → GL | PDF/XLSX | Now |
| AR Aging & Customer Statement | `accounting.ar_aging` | Accounting | Receivable exposure | `AccountsReceivableService.get_aging_report/get_customer_statement` | `reports.accounting.view` | `reports` + `accounting` | — | as-of date, customer | aging buckets, balance | customer → invoices | PDF/XLSX | Now |
| AP Aging & Supplier Statement | `accounting.ap_aging` | Accounting | Payable exposure | `AccountsPayableService.get_aging_report/get_supplier_statement` | `reports.accounting.view` | `reports` + `accounting` | — | as-of date, supplier | aging buckets, balance | supplier → bills | PDF/XLSX | Now |
| Bank Book / Cash Book | `accounting.bank_cash_book` | Accounting | Bank/cash transaction detail | `BankAccountService.get_bank_book/CashAccountService.get_cash_book` | `reports.accounting.view` | `reports` + `accounting` | — | period, account | running balance | transaction detail | CSV/XLSX | Now |
| Financial KPI Dashboard | `accounting.kpis` | Accounting | 15 existing CFO KPIs | `FinancialKPIService` | `reports.accounting.view` | `reports` + `accounting` | — | period, comparison | 15 KPIs (verbatim) | to each source report | — | Now |
| Tax Summary / Detail | `accounting.tax` | Accounting | Tax liability reporting | Accounting `ReportService` tax reports | `reports.accounting.view` | `reports` + `accounting` | — | period, tax type | tax collected/paid | journal detail | PDF/XLSX | Deferred |
| Cost-Center / Project P&L | `accounting.cost_center_pl` | Accounting | Departmental P&L | Accounting `ReportService` | `reports.accounting.view` | `reports` + `accounting` | — | period, cost center/project | net income | account → GL | PDF/XLSX | Deferred |
| CRM Dashboard | `crm.dashboard` | CRM | Current-period pipeline snapshot | `CrmReportingService.get_dashboard` | `reports.crm.view` | `reports` + `crm` | — | period | pipeline value, win rate | to detail reports | — | Now |
| Pipeline Report | `crm.pipeline` | CRM | Value by stage/owner/source | `CrmReportingService` pipeline report | `reports.crm.view` | `reports` + `crm` | — | period, stage, owner | value, win rate, cycle time | opportunity detail | CSV/XLSX | Now |
| Leads Report | `crm.leads` | CRM | Lead volume & conversion | `CrmReportingService` leads report | `reports.crm.view` | `reports` + `crm` | — | period, source, status | count, conversion rate | lead detail | CSV/XLSX | Now |
| Activities Report | `crm.activities` | CRM | Completed/overdue activity | `CrmReportingService` activities report | `reports.crm.view` | `reports` + `crm` | — | period, owner, type | count | activity detail | CSV/XLSX | Now |
| Installment Contract Register | `installments.register` | Installments | Full contract listing | `InstallmentReportingService` (contract-register) | `reports.installments.view` | `reports` + `installments` | Y (contract) | period, status, customer | count, outstanding | contract detail | CSV/XLSX | Now |
| Installment Collection Report | `installments.collections` | Installments | Payments collected | `InstallmentReportingService` (collection) | `reports.installments.view` | `reports` + `installments` | Y (contract) | period | collected amount | payment/allocation | CSV/XLSX | Now |
| Due / Overdue Report | `installments.due_overdue` | Installments | Upcoming/overdue installments | `InstallmentReportingService` (due, overdue) | `reports.installments.view` | `reports` + `installments` | Y (contract) | as-of date | due/overdue amount | schedule line | CSV/XLSX | Now |
| Installment Aging | `installments.aging` | Installments | Delinquency buckets | `InstallmentReportingService` (aging) via `InstallmentAgingCalculator` | `reports.installments.view` | `reports` + `installments` | Y (contract) | as-of date | aging buckets | contract detail | CSV/XLSX | Now |
| Settlement / Default / Write-off Report | `installments.settlement_writeoff` | Installments | Early payoff, default, write-off activity | `InstallmentReportingService` (settlement, default-writeoff) | `reports.installments.view` | `reports` + `installments` | Y (contract) | period, status | settled/written-off value | contract detail | CSV/XLSX | Now |
| Plan/Template Performance | `installments.plan_performance` | Installments | Adoption by plan template | `InstallmentReportingService` (plan-performance) | `reports.installments.view` | `reports` + `installments` | — | period, template | contract count/value | template detail | CSV/XLSX | Now |
| Installment Dashboard | `installments.dashboard` | Installments | Existing 13-metric dashboard | `InstallmentReportingService` dashboard | `reports.installments.view` | `reports` + `installments` | — | as-of date | 13 metrics (verbatim) | to each source report | — | Now |
| Customer 360 Financial View **(new)** | `crossmodule.customer_360` | Cross-module | One customer's Sales activity + AR balance + CRM/Installment exposure in one authorized view | Sales, Accounting AR, CRM, Installments (each read independently, never re-derived) | `reports.customer_360.view` | `reports` required globally to open the report at all; each constituent section (Sales, Accounting, CRM, Installments) is independently entitlement/permission-gated and omitted if its own gate fails — **section-level compound authorization, not all-or-nothing domain entitlement** (§20.2, corrected 2026-09-11) | — | customer, period | per-domain measures, side by side | to each domain's own record | CSV/XLSX | Now |
| Branch Performance Summary **(new, best-effort)** | `crossmodule.branch_performance` | Cross-module | Purchase/Inventory/Installments activity by the reserved `branch_id` column, where populated | Purchase, Inventory, Installments (branch-tagged entities only) | `reports.branch_performance.view` | `reports` + relevant domain(s) | Y (best-effort) | period, branch | per-domain measures | to domain report | CSV/XLSX | Deferred — requires `/sp.plan` to confirm real branch data exists in a tenant before shipping |

**FR-RPT-010**: Every catalog entry MUST be independently permission- and entitlement-gated exactly as declared in its Report Definition; no report may be reachable by satisfying only a subset of its declared gates.
**FR-RPT-011**: A "Now" report MUST be backed by a working Report Definition and passing tests before Epic 11 implementation is considered complete; a "Deferred" entry MUST NOT be exposed through any endpoint until it is promoted to "Now" in a future catalog revision.
**FR-RPT-012**: The `crossmodule.branch_performance` report MUST NOT be shipped as "Now" unless `/sp.plan`/`/sp.tasks` confirms, against real tenant data, that the underlying `branch_id` columns are actually populated for at least one representative tenant — shipping a report keyed entirely on an unpopulated reserved column would silently mislead users (§25).

## 10. KPI / Metric Catalog

Each metric has exactly one authoritative definition, consumed identically by the executive dashboard (§13), the relevant domain report, any export, and any future AI tool (§50). Where two modules compute similarly-named but different figures (e.g., Sales' operational margin vs. Accounting's recognized margin), they are given **distinct** names below to prevent the "same name, two meanings" drift the governing prompt explicitly warns against.

| Metric | Semantic ID | Definition | Authoritative Domain | Inclusion / Exclusion | Date Basis | Aggregation | Money/Currency | Comparison |
|---|---|---|---|---|---|---|---|---|
| Gross Sales | `metric.sales.gross` | Sum of invoiced amounts before credit-note offset | Sales | `SalesInvoice.status IN (ISSUED, PAID, CREDIT_NOTE_ISSUED)`; excludes `DRAFT`, `CANCELLED` | `invoice_date` | SUM(`total_amount`) | `NUMERIC(15,2)`, invoice's own currency | vs. prior period, absolute + % |
| Net Sales | `metric.sales.net` | Gross Sales minus recorded credit-note offsets | Sales | Same invoice set as Gross Sales | `invoice_date` | SUM(`total_amount` − `credit_note_amount`) | `NUMERIC(15,2)` | vs. prior period, absolute + % |
| Sales Order Count | `metric.sales.order_count` | Count of non-void orders created | Sales | Excludes `DRAFT`, `REJECTED`, `CANCELLED` | `order_date` | COUNT | N/A | vs. prior period |
| Average Order Value | `metric.sales.aov` | Net Sales ÷ invoice count in the same period | Sales | Derived from Net Sales | `invoice_date` | derived | `NUMERIC(15,2)` | vs. prior period |
| Sales Line-Item Margin (operational) | `metric.sales.line_margin` | Sum of (`unit_price` − `cost_price`) × qty across order lines | Sales | Non-cancelled order lines | `order_date` | SUM | `NUMERIC(15,2)` | vs. prior period — **explicitly not the same figure as Recognized Gross Profit Margin below** |
| Recognized Gross Profit Margin (financial) | `metric.accounting.gross_profit_margin` | Existing Accounting KPI: (Revenue − COGS) / Revenue from posted GL | Accounting | Posted journal entries only | `posting_date` | per `FinancialKPIService` | `NUMERIC(20,6)`, base currency | vs. prior period — the authoritative margin figure for financial reporting |
| Purchase Spend | `metric.purchase.spend` | Sum of PO totals | Purchase | `PurchaseOrder.status IN (APPROVED, PARTIALLY_RECEIVED, FULLY_RECEIVED, CLOSED)`; excludes `DRAFT`, `REJECTED`, `CANCELLED` | `created_at` (no distinct `po_date` field exists — documented repository gap) | SUM(`total`) | `NUMERIC(15,2)` (Purchase precision to be confirmed in `/sp.plan`) | vs. prior period |
| Accounts Receivable Balance | `metric.ar.balance` | Total outstanding customer receivables | **Accounting** (never Sales) | Per `AccountsReceivableService` aging logic | `due_date` for aging; as-of for balance | per `AccountsReceivableService` | `NUMERIC(20,6)`, base currency | vs. prior as-of date |
| Accounts Payable Balance | `metric.ap.balance` | Total outstanding supplier payables | **Accounting** (never Purchase) | Per `AccountsPayableService` aging logic | `due_date` for aging; as-of for balance | per `AccountsPayableService` | `NUMERIC(20,6)`, base currency | vs. prior as-of date |
| Overdue Receivables | `metric.ar.overdue` | AR balance outside the "Current" aging bucket | Accounting | Aging buckets `1-30`…`120+`, excludes `Current` | `due_date` | SUM | `NUMERIC(20,6)` | vs. prior as-of date |
| Operational Inventory Value (WAC) **(renamed, 2026-09-11 — was "Inventory Value")** | `metric.inventory.value_operational` | On-hand stock valued at Weighted Average Cost — an **operational** costing figure, not a reconciled financial-statement balance | **Inventory** — the only figure that currently exists; there is no separate "accounting inventory balance" to compare it against (§7, Assumption A11: authority is unresolved/incomplete, not a clean Inventory-vs-Accounting split) | `StockPosition.qty_on_hand > 0` | as-of date | SUM(`qty_on_hand × unit_cost`) | per-position `currency_code` | vs. prior as-of date |
| Cash Position | `metric.cash.position` | Existing Accounting KPI: total bank + cash balances | Accounting | Active bank/cash accounts | as-of date | per `FinancialKPIService` | `NUMERIC(20,6)`, base currency | vs. prior as-of date |
| CRM Pipeline Value | `metric.crm.pipeline_value` | Sum of open opportunity value | CRM | `Opportunity.status = OPEN` | as-of date (opportunity `created_at`/`expected_close_date` for period filters) | SUM(`value`) | `NUMERIC(15,2)`, opportunity `currency_code` | vs. prior as-of date |
| CRM Win Rate | `metric.crm.win_rate` | WON ÷ (WON + LOST) closed in period | CRM | `Opportunity.status IN (WON, LOST)` | `won_at`/`lost_at` | derived % | N/A | vs. prior period |
| Outstanding Installment Principal | `metric.installments.outstanding` | Remaining scheduled principal across serviceable contracts | Installments, cross-checked against Accounting via `AccountingIntegrationGateway` | `InstallmentContract.status IN (ACTIVE, DEFAULTED)` | as-of date | per `InstallmentReportingService` | `NUMERIC(20,6)` | vs. prior as-of date |
| Overdue Installments | `metric.installments.overdue` | Installment lines in `OVERDUE` due-state | Installments | Per `DueStateCalculator`/`InstallmentAgingCalculator` (same bucket convention as Accounting AR) | as-of date | per `InstallmentReportingService` | `NUMERIC(20,6)` | vs. prior as-of date |

**FR-RPT-020**: The system MUST NOT expose two differently-computed metrics under the same displayed name anywhere in the executive dashboard, a domain report, or an export; where two modules independently compute a similarly-named figure (e.g., "margin"), the system MUST use the distinguishing names in this catalog.
**FR-RPT-021**: Every metric in this catalog MUST declare its authoritative domain, and any consumer (dashboard widget, report column, export field, future AI tool) requesting that metric MUST resolve it through that domain's service — never through a locally recomputed formula.
**FR-RPT-022**: Financial metrics (Recognized Gross Profit Margin, AR/AP Balance, Cash Position) MUST always be sourced from Accounting; operational metrics (Sales Order Count, Purchase Spend, CRM Pipeline Value) MUST always be sourced from their owning operational module; no metric may silently substitute one for the other.

## 11. User Stories with Priority

### US-1 (P1) — Executive views the dashboard

An authorized executive opens the Reports & Analytics dashboard and sees a curated set of KPI widgets (Net Sales, Purchase Spend, AR/AP, Cash Position, Operational Inventory Value, CRM pipeline, Installment exposure), each showing the current period and its comparison to the prior period, with any disabled/unentitled/unpermitted module's widget simply absent rather than erroring.

**Independent Test**: Can be fully tested by seeding representative data in two enabled modules and one disabled module, loading the dashboard, and verifying the enabled modules' widgets show correct figures while the disabled module's widget does not render and does not appear in the response payload.

### US-2 (P1) — Finance user runs a financial statement

An accountant selects Trial Balance, Profit & Loss, or Balance Sheet for a chosen period, sees the figures returned, and confirms they reconcile exactly with what Accounting's own existing report endpoints return for the same inputs.

**Independent Test**: Can be fully tested by calling both Accounting's existing endpoint and Epic 11's wrapped endpoint with identical parameters and asserting byte-for-byte-equivalent financial totals.

### US-3 (P1) — Operational user drills from a report into a source record

A sales user views the Sales by Customer report, selects a customer row, and drills down into that customer's underlying invoice list, and from there into a single invoice's full detail — never seeing a record they could not already access directly.

**Independent Test**: Can be fully tested by drilling from report → filtered list → detail as a user holding both report and invoice-view permissions, then repeating as a user holding only the report permission and confirming the drill-down step is denied.

### US-4 (P2) — User exports a report

An authorized user exports the Sales Summary report as CSV for the exact filter scope they were viewing, and the exported file contains only the rows that filter scope would have returned online, with no cross-tenant or cross-branch leakage.

**Independent Test**: Can be fully tested by comparing an export's row set against the paginated online result set for the same filters (unioned across all pages).

### US-5 (P2) — User saves a private report view

A user configures filters/grouping/sorting/columns on a report, saves it as a private named view, and later reopens it to get the exact same configuration — no other user in the same tenant can see or use that saved view.

**Independent Test**: Can be fully tested by saving a view as User A, confirming it reappears identically on next login, and confirming User B (same tenant) cannot list or load it.

### US-6 (P2) — Installment officer reviews delinquency without duplicating Accounting

A user reviews the Installment Aging report and Overdue Installments metric, and independently confirms via the Accounts Receivable report that the same underlying obligations are reflected in Accounting — the two reports never contradict each other because both ultimately read from (or reconcile against) the same Accounting-owned financial truth.

**Independent Test**: Can be fully tested by creating an overdue installment obligation, then confirming both the Installment Aging report and Accounting's AR aging report reflect a consistent outstanding amount for that obligation.

### US-7 (P3) — Platform Admin enables Reports for a tenant without gaining data access

A Platform Administrator enables the `reports` module entitlement for a tenant via the existing Epic 9A entitlement model, and confirms that doing so grants them no ability to view that tenant's actual report data.

**Independent Test**: Can be fully tested by enabling entitlement as Platform Admin, then confirming a subsequent attempt by that same Platform Admin session to call any `reports.*` tenant endpoint is denied.

### US-8 (P3) — Auditor traces a dashboard figure back to source records

An auditor viewing an executive dashboard KPI drills through to the underlying report, then to the filtered record list, then to one source record, confirming the figure is fully explainable rather than a black box.

**Independent Test**: Can be fully tested by picking one dashboard KPI, following its drill-down chain to a specific source transaction, and confirming that transaction's amount is included in the KPI's computed total.

## 12. Functional Requirements — Platform & Registry

- **FR-RPT-030**: The system MUST expose a Report Registry (§8.2) as the single mechanism by which any report becomes reachable; no endpoint may bypass it.
- **FR-RPT-031**: The system MUST resolve, for every report request, the full gate chain in §8.1 in order — tenant context, `reports` entitlement, domain entitlement, RBAC permission, filter validation — and MUST short-circuit and deny at the first failing gate without executing the underlying report query.
- **FR-RPT-032**: The system MUST provide a discovery endpoint listing the Report Definitions the requesting user is currently authorized to see (permission- and entitlement-filtered), so the frontend can render navigation without probing endpoints (contrasted with the platform-admin frontend's current probe-and-hide-on-403 pattern, which Epic 11 explicitly improves on).
- **FR-RPT-033**: The system MUST version report contracts additively — an existing `report_key`'s response shape MUST NOT have fields removed or repurposed without a new `report_key`; new optional fields MAY be added.

## 13. Executive Dashboard

The dashboard is a single, curated composition of the metrics in §10 — not an open-ended widget builder.

- **FR-RPT-040**: The Executive Dashboard MUST present, at minimum: Net Sales (+trend), Gross Sales, Purchase Spend, Accounts Receivable balance + Overdue Receivables, Accounts Payable balance, Cash Position, Operational Inventory Value (WAC) — clearly labeled as operational, not a reconciled accounting balance (§7, Assumption A11) — CRM Pipeline Value + Win Rate, Outstanding Installment Principal + Overdue Installments, and Recognized Gross Profit Margin.
- **FR-RPT-041**: Each dashboard widget MUST independently evaluate tenant, `reports` entitlement, its source domain's entitlement, RBAC permission, and the selected date filter before rendering; a widget whose gate fails MUST simply be omitted from the response, never rendered with an error state that reveals the underlying reason (which could itself leak entitlement/permission information — §37). **Exception (corrected, 2026-09-11):** the Outstanding Installment Principal / Overdue Installments widget follows §34's generic-exception rule exactly like the underlying `installments.*` reports do — if Installments is disabled but serviceable obligations exist (FR-RPT-104 Case B), the widget renders with its read-only servicing-continuity figures instead of being omitted; it is omitted only under Case A (disabled, no existing obligations) or if the RBAC permission gate independently fails. No other widget has this exception.
- **FR-RPT-042**: The dashboard MUST support the standard period selector (§22) and comparison (§23) uniformly across all widgets it renders.
- **FR-RPT-043**: The dashboard response MUST include, per widget, a reference sufficient to drill down into that widget's underlying report (§27) — the dashboard itself never returns row-level source data.
- **FR-RPT-044**: The dashboard MUST behave correctly for a company with zero data in every module (all widgets render a defined zero/empty state, never an error) and for a company with only one module enabled (only that module's widgets render).

## 14. Sales Analytics

- **FR-RPT-050**: The system MUST wrap Sales' existing `ReportService`/`KPIService` report and KPI computations (§9 Sales rows) behind Report Definitions using this Epic's query/response/export/permission contract, without altering Sales' own existing `/sales/reports/*` endpoints.
- **FR-RPT-051**: Sales reports MUST use `invoice_date` for revenue-shaped reports and `order_date` for order-pipeline-shaped reports (§22), never `created_at`, since both authoritative business dates already exist on the source models.
- **FR-RPT-052**: Sales reports MUST respect the confirmed absence of a `branch_id` on any Sales model (§25) — no Sales report may expose a branch filter.
- **FR-RPT-053**: Any Sales report referencing product identity MUST resolve display names through Inventory's `Product` (loose UUID reference, §7) and MUST NOT assume a DB-enforced relationship exists.

## 15. Purchase Analytics

- **FR-RPT-060**: The system MUST wrap Purchase's existing `ReportService`/`KPIService` report and KPI computations (§9 Purchase rows) behind Report Definitions using this Epic's contract, without altering Purchase's own existing `/purchase/reports/*` endpoints.
- **FR-RPT-061**: Purchase order reports MUST use `created_at` as the order-date basis and document this as a repository gap (no distinct `po_date`/`order_date` field exists on `PurchaseOrder`) rather than fabricating a field; goods-receipt reports MUST use `GoodsReceipt.received_at`.
- **FR-RPT-062**: Purchase reports MAY expose an optional branch filter only for the three entities that already carry a (reserved, nullable) `branch_id` column — `PurchaseOrder`, `PurchaseRequest`, `Supplier` — per §25, and MUST clearly label it as a data filter, not an authorization boundary.
- **FR-RPT-063**: No Purchase report may present payable/AP balances as authoritative; any payable-linked figure MUST be sourced from Accounting (§7) and MUST be visually/structurally distinguished from Purchase's own operational spend figures.

## 16. Inventory Analytics

- **FR-RPT-070**: The system MUST wrap Inventory's existing `ReportService`/`KPIService` computations (§9 Inventory rows), including dead-stock, movement-velocity, and stock-aging, behind Report Definitions using this Epic's contract, without altering Inventory's own existing `/inventory/reports/*` endpoints.
- **FR-RPT-071** (**corrected, 2026-09-11**): Inventory valuation reports MUST use Inventory's own Weighted-Average-Cost computation (`StockPosition.unit_cost`) as the sole available **operational** stock-costing figure, and MUST NOT attempt to derive an alternative valuation from Accounting, since no GL-level inventory balance is currently populated there (§7, Assumption A11). Crucially, the system MUST NOT label this figure "authoritative," "financial," or otherwise imply it is a reconciled accounting balance — inventory valuation authority is genuinely unresolved/incomplete in the repository today (ADR-0004, Status: Proposed, never Accepted), and Epic 11 MUST NOT resolve that gap unilaterally by declaring Inventory's operational figure to be the tenant's official balance-sheet inventory value. Every response for `inventory.valuation` and `metric.inventory.value_operational` MUST carry an explicit `valuation_basis: "operational_wac"` (or equivalent) field and a documented disclaimer that this figure is not reconciled with Accounting's general ledger.
- **FR-RPT-072**: Inventory reports MAY expose an optional branch filter only insofar as `Warehouse.branch_id` (reserved, nullable) is populated for a given tenant (§25); absent that, reports scope by warehouse only.
- **FR-RPT-073**: Historical inventory reports (e.g., valuation-as-of-date, movement history) MUST use `StockMovement`'s own point-in-time `unit_cost`/`total_cost` (immutable, insert-only ledger) rather than the Product's current `cost_price`, preserving historical truth (§26).
- **FR-RPT-074** (**new, 2026-09-11 correction pass**): If Accounting later resolves ADR-0004 and begins posting a real, GL-backed inventory balance, that figure — once it exists — becomes a *separate*, additional catalog entry with its own authoritative-domain declaration (Accounting); it MUST NOT silently replace or be merged into the existing operational `inventory.valuation` report/metric, to avoid retroactively changing the meaning of a report key already in use (§40.2, FR-RPT-312).

## 17. Accounting / Financial Reporting

- **FR-RPT-080**: The system MUST wrap Accounting's existing `FinancialStatementService`, `ReportService`, `AccountsReceivableService`, `AccountsPayableService`, and `FinancialKPIService` computations (§9 Accounting rows) behind Report Definitions using this Epic's contract, without altering Accounting's own existing `/accounting/reports/*` endpoints.
- **FR-RPT-081**: Every financial report MUST reconcile exactly with Accounting's own existing endpoint output for identical parameters (§48.3 financial invariant tests) — Epic 11 introduces no new financial computation, only a consistent access/permission/export layer.
- **FR-RPT-082**: Financial reports MUST use `posting_date` (not `created_at`, not any operational-module date) as their period-filter date basis, since `JournalEntry.posting_date` is the authoritative financial date.
- **FR-RPT-083**: AR/AP aging reports MUST reuse Accounting's exact aging bucket convention (`Current`, `1-30`, `31-60`, `61-90`, `91-120`, `120+`) rather than the coarser 4-bucket scheme some product framing might informally suggest — matching the precedent already set for Installments (`specs/010-installments/spec.md` Assumption A7).
- **FR-RPT-084**: No Accounting report may expose a branch filter; no `branch_id` was found on any Accounting model during discovery.

## 18. CRM Analytics

- **FR-RPT-090**: The system MUST wrap CRM's existing `CrmReportingService` dashboard/pipeline/leads/activities computations (§9 CRM rows) behind Report Definitions using this Epic's contract, without altering CRM's own existing `/crm/reports/*`/`/crm/dashboard` endpoints.
- **FR-RPT-091**: CRM reports MUST use the actual repository-confirmed status values (`Lead.status`: `NEW, CONTACTED, QUALIFIED, UNQUALIFIED, CONVERTED, LOST`; `Opportunity.status`: `OPEN, WON, LOST`) — no invented status names.
- **FR-RPT-092**: Win/loss and conversion-rate metrics MUST use `Opportunity.status`/`won_at`/`lost_at` as defined by CRM (§10); Epic 11 MUST NOT introduce a competing attribution or conversion definition.
- **FR-RPT-093**: No CRM report may expose a branch filter; no `branch_id` was found on any CRM model during discovery.
- **FR-RPT-094**: If a tenant's CRM entitlement is disabled, every `crm.*` report key and the CRM dashboard widget MUST become unreachable/absent (§34), matching CRM's own `require_crm_enabled` module-wide gate precedent.

## 19. Installment Analytics

- **FR-RPT-100**: The system MUST wrap Installments' existing `InstallmentReportingService` (contract-register, collection, due, overdue, aging, settlement, default-writeoff, plan-performance, dashboard) behind Report Definitions using this Epic's contract, without altering Installments' own existing `/installments/reports/*`/`/installments/dashboard` endpoints — fulfilling FR-INST-362's forward promise.
- **FR-RPT-101**: Installment reports MUST use the real repository-confirmed contract status values (`DRAFT, PENDING_APPROVAL, APPROVED, ACTIVE, DEFAULTED, COMPLETED, CANCELLED, WRITTEN_OFF`; no `REJECTED` state exists) and the real `DueStateCalculator` precedence (`VOIDED > WAIVED > PAID > PARTIALLY_PAID > OVERDUE > DUE > UPCOMING`).
- **FR-RPT-102**: Installment financial figures (collections, allocations) MUST always be sourced through `AccountingIntegrationGateway`'s existing read-through pattern, never cached or independently recomputed inside the reporting layer, preserving the "no shadow financial truth" invariant already established for Installments (BR-INST-004/007).
- **FR-RPT-103**: Installment reports MAY expose an optional branch filter using `InstallmentContract.branch_id` (reserved, nullable) per §25, clearly labeled as a data filter, not an authorization boundary — matching Installments' own documented treatment of the column ("reserved column, not yet an authorization boundary").
- **FR-RPT-104** (**corrected, 2026-09-11 micro-correction pass — now the single authoritative statement of this rule; §34's generic disabled-domain rule explicitly defers to it**): Installments' disabled-entitlement reporting behavior has exactly two cases, and the system MUST resolve which case applies on every request rather than applying a single blanket rule:
  - **Case A — disabled with no existing serviceable contracts/obligations**: Installment reporting is unavailable under the normal disabled-domain rule (FR-RPT-252) — the documented "module not entitled" error, identical to CRM's behavior.
  - **Case B — disabled but serviceable contracts/obligations already exist**: Installment reports MUST remain available in **read-only** form (mirroring FR-INST-354's servicing-continuity policy) rather than disappearing entirely, since existing obligations must remain explainable, inspectable, and reconcilable even while origination is blocked. This read-only scope covers: the contract register, schedules, due/overdue status, collections, and settlement/default/write-off history for contracts that already existed — it explicitly does NOT reopen new contract origination, configuration, plan/template creation, or any other disabled write capability (matching FR-INST-353/357's origination-vs-servicing boundary exactly; Epic 11 introduces no new entitlement mechanism to achieve this — it reuses Installments' own existing policy).
  This is a documented, narrow exception to the generic disabled-domain rule (FR-RPT-252), not a competing rule — see §34's generic-exception statement.

## 20. Cross-Module Analytics

### 20.1 Customer 360 — Explicit Nature and Source Mapping (corrected, 2026-09-11)

Customer 360 (`crossmodule.customer_360`) is explicitly a **composite read model / analytical projection** — a read-time aggregation that presents multiple modules' independently-authoritative facts about one customer side by side. It is explicitly **NOT**: a new customer system of record; a new financial source of truth; a replacement for CRM, Sales, Accounting, or Installments; or any kind of persisted, materialized "customer" entity of its own. Nothing about a customer is ever written, cached, or re-derived by Customer 360 — it only composes reads.

| Section | Authoritative Source | Notes |
|---|---|---|
| Identity / customer master fields (name, code, contact summary) | **Sales** (`Customer` model) | Sales owns Customer master data (§7). |
| CRM activity (leads, opportunities, pipeline value tied to this customer) | **CRM** | Omitted entirely if CRM is not entitled (§20.2). |
| Orders / invoices / commercial activity | **Sales** | Per §14, using Sales' own status-inclusion rules. |
| Accounting balance / receivables | **Accounting** — via `AccountsReceivableService` | Never recomputed from Sales invoice totals (§7). |
| Installment operational exposure | **Installments** — via `InstallmentReportingService`, financial figures cross-checked through `AccountingIntegrationGateway` | Omitted entirely if Installments is not entitled (§20.2). |

- **FR-RPT-110**: The system MUST provide the Customer 360 Financial View (`crossmodule.customer_360`, §9) composing Sales' own customer activity, Accounting's authoritative AR balance for that customer, and (where entitled) Installments' exposure for that customer — each figure read independently from its own authoritative source per the table above, never blended into a single re-derived number, and never persisted as a new customer record of its own.

### 20.2 Customer 360 — Compound Authorization

- **FR-RPT-111**: Any cross-module report MUST independently apply every relevant per-domain gate (entitlement, permission) for each domain it touches — a user missing the Accounting permission MUST see the Sales portion of Customer 360 without the AR portion, not be denied the whole report or shown a fabricated AR figure. A user gains access to no domain's data through Customer 360 that they could not already reach directly through that domain's own report/detail view.
- **FR-RPT-114** (**new, 2026-09-11 correction pass**): Each constituent section of Customer 360 MUST resolve to exactly one of three states, and the response MUST distinguish them explicitly rather than collapsing them into a single "empty" representation:
  1. **Present** — the section's data is returned normally.
  2. **Omitted (not entitled / not permitted)** — the requesting user's session lacks the domain entitlement or the domain's own `reports.<domain>.view` permission for that section; the section is entirely absent from the response (never included with fabricated or zeroed values), consistent with FR-RPT-041's per-widget gating philosophy.
  3. **Unavailable (not configured / no data)** — the user is authorized for the domain, but the domain itself has no data or is not yet configured for this tenant (e.g., Accounting has no chart of accounts configured yet, or the customer has zero Sales transactions) — the section is present but explicitly marked `unavailable`/`not_configured`, never silently rendered as a numeric zero that could be mistaken for "confirmed zero balance."
- **FR-RPT-115** (**new, 2026-09-11 correction pass**): Specifically for module-disabled scenarios: if CRM is disabled for the tenant, the CRM section of Customer 360 is **omitted** (state 2 above); if Installments is disabled, the Installments section is **omitted** (subject to FR-RPT-104's Case B servicing-continuity exception if serviceable obligations already exist, in which case that section is **present** instead — §19); if Accounting has no receivable transactions for this customer yet, the Accounts Receivable section is **present** with an explicit zero (state 1, a real confirmed zero, since Accounting is always the queried source of truth and "no transactions" is a valid, queryable answer); if Sales has zero transactions for this customer, the Sales section is likewise **present** with an explicit zero. The distinction between "confirmed zero" (FR-RPT-115) and "not available for this reason" (FR-RPT-114.3) MUST never be conflated in the response schema.
- **FR-RPT-116** (**new, 2026-09-11 micro-correction pass**): If, after section-level authorization (FR-RPT-111/114/115), **none** of the four constituent business sections is available to the requesting user (every section omitted), the system MUST NOT return an empty cross-module "shell" response containing only the customer's identity — doing so would itself leak the existence of a customer the user cannot otherwise access, an IDOR-adjacent information disclosure. Instead: (a) if the requesting user is independently authorized to view the customer master record itself (Sales' own customer-view permission), the response MAY return the identity/master-data section alone, clearly indicating zero business sections are available and why (each per its FR-RPT-114 state); (b) if the requesting user is not authorized to view the customer master record at all, the entire Customer 360 request MUST be denied using the platform's existing IDOR-safe "not found" response (§36, FR-RPT-271) — indistinguishable from the customer not existing — never a distinguishable "found but empty" response.
- **FR-RPT-112**: The Branch Performance Summary (`crossmodule.branch_performance`, §9) remains Deferred until `/sp.plan` confirms real, populated `branch_id` data exists for at least one representative tenant (FR-RPT-012); it MUST NOT ship reporting purely synthetic/empty branch groupings.
- **FR-RPT-113**: Cross-module reports MUST NOT introduce a new blended metric that isn't already defined in §10 — if a cross-module view needs a new combined figure, that figure MUST first be added to the KPI/Metric Catalog with its own authoritative definition before being surfaced.

## 21. Query / Filter Contract

- **FR-RPT-120**: Every report request MUST be validated against its Report Definition's declared `supported_filters`/`supported_dimensions`/`supported_measures`/`sortable_fields`; any filter, dimension, measure, or sort field not declared MUST be rejected with a documented 4xx error, never silently ignored.
- **FR-RPT-121**: Representative filter parameters across the catalog include: date range, branch (where declared, §25), status, customer, supplier, item/product, warehouse, salesperson/owner, account, installment status, grouping, sorting, and page/page-size — no report is required to support every parameter; only its declared subset.
- **FR-RPT-122**: An unauthorized branch filter value (a branch the user cannot access, once branch-level authorization exists in a future epic), an unsupported grouping, an invalid date range, an impossible status value, a disabled-module filter target, or an inaccessible account/customer reference MUST each produce a documented, predictable error using the platform's existing `ErrorResponse` envelope (§40) — never a silent empty result that could be mistaken for "no data."
- **FR-RPT-123**: Sorting MUST only be permitted on a report's declared `sortable_fields`; arbitrary client-supplied column names MUST be rejected.

## 22. Date/Time & Period Semantics

- **FR-RPT-130**: The system MUST support the standard period presets: Today, Yesterday, This Week, Last Week, This Month, Last Month, This Quarter, Last Quarter, This Year, Last Year, and Custom Range.
- **FR-RPT-131**: Period boundaries MUST be computed using the requesting company's `Company.default_timezone` (IANA identifier, default `UTC`) — never the server's local timezone — converted to a UTC range for querying, consistent with the platform's existing `DateTime(timezone=True)`/`ensure_utc()` convention.
- **FR-RPT-132**: Period boundaries MUST be half-open intervals `[start, end)` in the company's local time, consistently applied across every report, to avoid off-by-one-day double-counting or gaps at period boundaries.
- **FR-RPT-133**: Every Report Definition MUST declare which business date field drives its period filter (§14–§19 per-domain requirements document the actual field per report family); no report may default to `created_at` where a more meaningful business date already exists on the source model (governing prompt requirement, and explicitly resolved per-domain in §14–§19).
- **FR-RPT-134**: A custom date range crossing a fiscal-year or calendar-year boundary MUST be computed the same way as any other range — no special-casing that would silently truncate or split the result at the year boundary.

## 23. Comparison Semantics

- **FR-RPT-140**: Where a report/widget supports comparison, the system MUST support: previous period, previous month, previous quarter, previous year, and same-period-last-year, and MUST return both absolute change and percentage change.
- **FR-RPT-141**: Percentage-change computation MUST define explicit zero-denominator behavior: when the prior period's value is zero and the current period's value is non-zero, the system MUST return a documented "not comparable" indicator rather than an infinite or undefined percentage; when both are zero, percentage change MUST be reported as `0%`, not "not comparable."
- **FR-RPT-142**: A comparison against an **incomplete current period** (e.g., "This Month" requested on the 5th day of the month) MUST be clearly labeled as partial/incomplete in the response, since comparing a 5-day partial month against a full prior month would otherwise silently mislead.
- **FR-RPT-143**: The system MUST NOT silently compare incomparable period lengths (e.g., a 7-day custom range against a 31-day "previous month") without labeling the comparison as such.

## 24. Money & Currency Semantics

- **FR-RPT-150**: All monetary computation MUST use `Decimal` arithmetic exclusively; floating-point types MUST NEVER be used for any monetary aggregation, comparison, or export value (Constitution §17).
- **FR-RPT-151**: Aggregations combining Sales/Purchase (`NUMERIC(15,2)`) figures with Accounting/Installments (`NUMERIC(20,6)`) figures MUST perform arithmetic at `NUMERIC(20,6)` precision and round only at final display, per the tenant's currency decimal places (Assumption A4).
- **FR-RPT-152**: Every monetary figure in a response or export MUST carry its currency code alongside the amount; the system MUST NEVER sum amounts across different currency codes without an explicit, Accounting-sourced exchange-rate conversion (Constitution §36).
- **FR-RPT-153**: Financial reports already expressed in the company's base currency (P&L, Balance Sheet) MUST continue to use Accounting's own `CurrencyService` translation convention (`CLOSING` rate for Balance Sheet, `AVERAGE` rate for P&L) unchanged.
- **FR-RPT-154**: Rounding MUST use an explicit, documented policy (`ROUND_HALF_UP` at the currency's configured decimal places for display), consistent with the platform's existing Decimal-quantization convention (matches Installments' `Decimal("0.000001")`/`ROUND_HALF_UP` precedent for internal precision).

## 25. Branch Semantics

> **Branch is NOT currently an authorization boundary in DevSphere ERP.** This is a load-bearing architectural fact, re-verified during the 2026-09-11 correction pass, and every requirement in this section follows from it.

Repository discovery is unambiguous and is treated as authoritative for this Epic (Assumption A3):

- No `Branch` model, `branches` table, or any "user's permitted branches" concept exists anywhere in the repository.
- `branch_id` exists only as a **nullable, unconstrained** column on: `InstallmentContract`, `InstallmentConfiguration`, `PurchaseOrder`, `PurchaseRequest`, `Supplier`, and `Warehouse` — each explicitly documented in source as "reserved for future branch-linkage."
- Sales, Accounting, and CRM models carry **no** `branch_id` at all.

**FR-RPT-160**: Where a report's underlying entity carries a `branch_id` column, the system MAY expose an optional branch filter as a plain data filter (WHERE-clause equality/IN), applied identically to how any other filter is validated (§21).
**FR-RPT-161**: The system MUST NOT present a branch filter as, or rely on it for, any authorization decision — because no per-user branch access-control concept exists, restricting a report to "branches the user may access" is not implementable today and MUST NOT be silently assumed or half-implemented.
**FR-RPT-162**: Reports whose underlying entities carry no `branch_id` (all of Sales, Accounting, CRM) MUST NOT expose a branch filter parameter at all — offering a no-op or silently-ignored branch filter would misrepresent capability.
**FR-RPT-163**: When multi-branch authorization becomes a first-class platform capability in a future epic, Epic 11's branch filter fields are designed to be upgraded to an authorization boundary (permitted-branches intersection) without a breaking contract change — but that upgrade is explicitly out of scope here (NG10).
**FR-RPT-164**: Company-wide (no branch filter applied) MUST always remain the default view for every report, regardless of whether a branch filter is available.

## 26. Status / Reversal / Historical-Truth Semantics

- **FR-RPT-170**: Every report MUST use the real, repository-confirmed status enum values for its domain (quoted per-domain in §14–§19) — no invented status names, and no silent inclusion of `DRAFT`/`CANCELLED`/`REJECTED` records in any revenue-, spend-, or balance-shaped metric unless explicitly declared as an "all statuses" variant.
- **FR-RPT-171**: A cancelled, returned, reversed, or written-off business event MUST remain visible in historical/audit-shaped reports (contract register, journal report, audit trail) — Epic 11 MUST NOT filter reversed activity out of history, only out of forward-looking revenue/balance totals per the domain's own defined inclusion rules (§10).
- **FR-RPT-172**: Journal reversals MUST be represented using Accounting's existing mechanism (`JournalEntry.reversal_of_journal_id`/`is_reversal`, a new counter-entry, never an in-place mutation) — any GL-shaped report MUST show both the original and the reversing entry distinctly, never collapse them into a net figure that hides the reversal occurred.
- **FR-RPT-173**: Sales credit notes (`SalesInvoice.status = CREDIT_NOTE_ISSUED`, `credit_note_amount`) and Purchase vendor returns MUST be reflected in Net Sales / Net Purchase figures per their domain's defined inclusion rule (§10), never silently deleted from the source report.

## 27. Drill-Down

- **FR-RPT-180**: Every "Now" report/widget in §9 that has a declared `drill_down_targets` MUST support navigating from an aggregate figure to its contributing filtered record list, and from there to a single record's detail — Executive Dashboard → domain report → filtered list → record detail, or Financial report/aging → customer/supplier balance → open transactions → transaction detail.
- **FR-RPT-181**: Drill-down MUST re-evaluate authorization at every step — a user permitted to view an aggregate report is NOT automatically permitted to view the underlying record; the underlying module's own record-view permission (e.g., `sales.invoices.read`) MUST be separately checked before returning any record-level detail (US-3).
- **FR-RPT-182**: A drill-down request MUST preserve the exact filter/tenant/branch scope of the report it originated from — it MUST NOT become a means to browse records outside that scope.
- **FR-RPT-183**: A drill-down target that resolves to a deleted/soft-deleted/inactive customer, supplier, product, or contract MUST still be viewable (historical truth) but MUST be clearly labeled as inactive/deleted in the response.

## 28. Pagination & Sorting

- **FR-RPT-190**: Every report capable of returning many rows MUST use the platform's existing `PaginationParams`/`PaginatedData[T]`/`PaginatedResponse[T]` convention (`page ≥ 1`, `page_size` 1–100, default 20) — Epic 11 introduces no competing pagination shape.
- **FR-RPT-191**: List-shaped report results MUST use stable, deterministic ordering (a documented default sort, with ties broken by a stable secondary key such as `id`) so that paginating through results never skips or duplicates a row.
- **FR-RPT-192**: Aggregate/dashboard-shaped endpoints (KPI dashboards, the Executive Dashboard) are explicitly exempt from pagination — they return a bounded, fixed-shape summary object, not a row list.
- **FR-RPT-193**: `total`/`pages` counts MUST reflect the exact same filter scope as the returned page of rows.

## 29. Saved Report Views

New Epic 11-owned state (§6.2); no equivalent exists anywhere in the repository.

- **FR-RPT-200**: The system MUST allow an authorized, `reports.saved_view.manage`-permitted user to save a named, private view referencing: `report_key`, filters, grouping, sorting, visible columns, and an optional date preset.
- **FR-RPT-201**: A saved view MUST NEVER store arbitrary SQL, a raw query expression, or any field not already declared in that report's Report Definition (§8.2) — saving a view is equivalent to saving a validated filter/display configuration, not a query.
- **FR-RPT-202**: Saved views are **private/user-owned** for Epic 11 (per the governing prompt's own recommended boundary) — no sharing, no team/company-wide visibility, and no separate "view others' saved views" permission is introduced in this Epic (NG5).
- **FR-RPT-203**: Loading a saved view MUST re-validate it against the current Report Definition and the loading user's current permissions/entitlements at load time — a saved view MUST NEVER become a bypass of a permission or entitlement the user has since lost (e.g., after a role change or module disablement).
- **FR-RPT-204**: A saved view referencing a report_key that has been retired MUST fail gracefully with a documented error, never silently execute a different report.
- **FR-RPT-205**: Saved views MUST be tenant-scoped and MUST NEVER be listable, loadable, or discoverable by a user of a different tenant, or by another user of the same tenant who is not its owner (US-5).

## 30. Exports & Export Security

- **FR-RPT-210**: The system MUST support CSV and XLSX export for every tabular "Now" report, reusing the existing platform export pattern (service returns `(bytes, filename, content_type)`; router returns a `Response` with `Content-Disposition: attachment`).
- **FR-RPT-211**: PDF export MUST be limited to the reports where an existing repository precedent already justifies it — Accounting's financial statements (Trial Balance, P&L, Balance Sheet, Cash Flow, AR/AP statements) — reusing Accounting's own existing `reportlab`-based `export_to_pdf()`; PDF MUST NOT be forced onto every chart/dashboard widget.
- **FR-RPT-212**: Export MUST require the report's own `.export` permission (`reports.<domain>.export`), distinct from its `.view` permission — a user who can view a report is not automatically assumed to have bulk-export rights (matches the existing `sales.reports.export`/`inventory.reports.export` precedent).
- **FR-RPT-213**: Exports MUST preserve the exact tenant, branch, and filter scope of the report request that produced them — an export can never contain rows outside what the equivalent paginated online view would return for the same filters (US-4).
- **FR-RPT-214** (**corrected, 2026-09-11**): Synchronous export MUST NEVER be allowed to produce unbounded memory, CPU, or database load — this is the binding invariant, not any specific number. Concretely: a request whose filtered result set exceeds the export's configured maximum row count MUST return a documented "narrow your filters" error rather than silently truncating the file or hanging the request. The maximum row count itself MUST be a **centrally defined, configurable parameter** (not hardcoded per endpoint), MAY differ by format where justified (CSV streams row-by-row with a smaller memory footprint per row than XLSX, which must hold more structure in memory before writing — `/sp.plan` MAY therefore set a higher CSV limit than XLSX), and MUST be finalized during implementation planning using measured memory/runtime behavior against representative payload widths, not fixed by this specification. **Non-binding planning candidate**: 50,000 rows as a starting point for `/sp.plan` to validate or revise — this number carries no independent authority and is not itself a requirement.
- **FR-RPT-215**: Exported files MUST use a safe, predictable filename derived from the report key and filter/date scope, with no user-supplied string interpolated unescaped into the filename or `Content-Disposition` header.
- **FR-RPT-216**: CSV exports MUST neutralize formula-injection payloads (values beginning with `=`, `+`, `-`, `@`) per standard CSV-injection mitigation (prefixing with a neutralizing character or quoting), since exported spreadsheets are opened in end-user spreadsheet applications.
- **FR-RPT-217**: Every export MUST produce an audit record identifying the actor, tenant, report key, filter scope, format, and row count (§39) — exports are treated as a data-exfiltration boundary, not merely a reporting convenience (governing prompt §40).
- **FR-RPT-218**: Sensitive fields excluded from a report's normal response (§37) MUST remain excluded from that report's export in every format — export MUST NEVER be a channel for exposing a field the online view withholds.
- **FR-RPT-219**: An export whose filtered result set is empty MUST still produce a valid, well-formed file (correct headers, zero data rows) rather than an error or a malformed/empty file.

## 31. Performance & Query Guardrails

- **FR-RPT-220**: Every report query MUST avoid N+1 query patterns (Constitution §25); list-shaped reports MUST use eager loading or batch queries when resolving related display data (e.g., product names for line-item rows).
- **FR-RPT-221**: Reports that aggregate/count/sum MUST NOT load full ORM entity graphs merely to compute a scalar; they MUST use the underlying module's existing aggregation-capable service methods (already true for every wrapped service in §6.1) rather than re-fetching rows into Python to sum them.
- **FR-RPT-222**: Where a wrapped service does not already impose one, a report with an unbounded date range parameter MUST enforce a maximum synchronous query range; `/sp.plan` MUST determine the exact bound per report family from the wrapped service's own existing constraints (several already paginate/cursor internally, e.g. the GL report) rather than inventing a new one where none is needed.
- **FR-RPT-223**: A report supporting a `group by` dimension MUST document a maximum practical grouping cardinality (e.g., "by customer" is bounded by the tenant's actual customer count) and MUST NOT silently return an unbounded number of groups without pagination.
- **FR-RPT-224**: `/sp.plan` MUST review and document candidate database indexes for any new cross-module query path Epic 11 introduces (e.g., the Customer 360 view's per-domain customer lookups); Epic 11 specification itself introduces no migrations (constraint, not requirement).

## 32. Freshness & Caching Strategy

- **FR-RPT-230**: Every report and dashboard widget in §9/§13 is classified **transactional/live** — computed at request time directly from its authoritative source's existing service call, with no materialized or precomputed intermediate (Assumption A9, matching the confirmed "no cached KPI table" precedent across every module examined).
- **FR-RPT-231**: Caching is explicitly **deferred** for Epic 11's initial scope (NG4-adjacent) — no result caching, query caching, or dashboard caching is implemented now.
- **FR-RPT-232**: Should caching be introduced in a future revision, a cache key MUST be composed of, at minimum: tenant (`company_id`), branch scope (where applicable, §25), `report_key`, the full validated filter set, the requesting user's effective permission/entitlement state, and a freshness window — and MUST NEVER be composed in a way that could return one tenant's cached result to another tenant's request. This constraint is recorded now so a future caching layer cannot be added carelessly, even though no caching ships in this Epic.

## 33. RBAC — Permission Matrix

Following the existing dot-notation convention (`<module>.<resource>.<action>`) and the existing pattern of inline `user_has_<module>_permission()` checks at the start of each endpoint body (matching `modules/{accounting,installments,sales}/services/permission_check.py`):

| Permission | Capability |
|---|---|
| `reports.executive.view` | View the Executive Dashboard |
| `reports.sales.view` / `reports.sales.export` | View / export Sales analytics |
| `reports.purchase.view` / `reports.purchase.export` | View / export Purchase analytics |
| `reports.inventory.view` / `reports.inventory.export` | View / export Inventory analytics |
| `reports.accounting.view` / `reports.accounting.export` | View / export financial reports |
| `reports.crm.view` / `reports.crm.export` | View / export CRM analytics |
| `reports.installments.view` / `reports.installments.export` | View / export Installment analytics |
| `reports.customer_360.view` | View the cross-module Customer 360 Financial View |
| `reports.branch_performance.view` | View the (deferred) Branch Performance Summary |
| `reports.saved_view.manage` | Create/edit/delete one's own private saved report views |

- **FR-RPT-240**: Each permission above MUST be checked independently; holding one `reports.*` permission MUST NEVER implicitly grant another (least-privilege, matching every other module's established convention).
- **FR-RPT-241**: `.export` permissions MUST always be distinct from `.view` permissions (§30, FR-RPT-212) — no permission implicitly grants both.
- **FR-RPT-242**: Sensitive financial report permissions (`reports.accounting.*`) MUST NOT be implicitly granted merely because a user holds an operational module's own report permission (e.g., holding `reports.sales.view` never implies `reports.accounting.view`) — directly satisfying the governing prompt's requirement that "sensitive financial information should not automatically become visible merely because a user can access an operational module."

### Representative Role Mapping (illustrative — actual roles remain tenant-configurable per existing RBAC convention)

| Actor / Role Category | View | Drill-Down | Export | Save View |
|---|---|---|---|---|
| Company Owner / Admin | All domains | All (subject to underlying record permission) | All | Yes |
| Executive / Business Owner | Executive + Accounting + assigned operational domains | Yes | Per assigned `.export` | Yes |
| Sales User | `reports.sales.*` only | Sales records only | If granted `.export` | Yes |
| Accountant / Finance User | `reports.accounting.*` (+ others if separately granted) | Accounting records only | If granted `.export` | Yes |
| Auditor / Read-Only | View + drill-down only, as separately granted | Yes, if underlying record-view granted | No (unless explicitly granted) | No (unless explicitly granted) |
| Platform Administrator | None (tenant business data) | None | None | None |

**FR-RPT-243**: Role-to-permission assignment MUST remain tenant-configurable through the existing RBAC role/permission management surface — Epic 11 MUST NOT hardcode which role gets which `reports.*` permission; the table above is illustrative default guidance only, not an enforced mapping.

## 34. Entitlements — Entitlement Matrix

**Definitively resolved, 2026-09-11 correction pass (supersedes the original discovery pass's hedged "core module — verify in `/sp.plan`" language and closes former Open Question OQ-2 — see Assumption A6).** Every one of the six source modules is a genuinely registered `grain=module` Capability in the platform Capability catalogue (`CapabilitySeedService.MODULE_CAPABILITY_CATALOGUE`, `modules/platform_admin/services/capability_seed_service.py:25-32`) with a real, structural entitlement-enforcement point — five at router-mount time (`require_capability_entitled(...)`), Installments at service-method time via `InstallmentAccessPolicy.authorize()`. **None is structurally ungated.** They differ only in *default resolved state* for a tenant with no active Subscription (the normal state for a brand-new company today, since company creation never auto-assigns one): Sales/Purchase/Inventory/Accounting default to **entitled** (no dedicated tenant-level master toggle exists for them; they use a stateless `DefaultAlwaysEnabledModuleProvider`), while CRM/Installments default to **disabled** (each has an explicit master toggle that starts `False` until a tenant deliberately enables it).

> **Generic disabled-domain rule and its one documented exception (2026-09-11 micro-correction pass):** A disabled-domain report family is normally fully unreachable (FR-RPT-252). **Installments is currently the sole, explicitly documented exception**, under the established Epic 10 servicing-continuity invariant (FR-INST-354): when Installments is disabled *and* serviceable contracts/obligations already exist, Installment reporting remains available in a narrowly-scoped, read-only form (FR-RPT-104, Case B) — it does not become "still fully available," only servicing-continuity-scoped. When Installments is disabled with no existing obligations, the normal rule applies without exception (FR-RPT-104, Case A). No other domain in this table — including CRM — has such an exception; CRM disabled always means CRM reporting is fully unreachable, with no carve-out.

| Report Family | Requires `reports` Entitled | Requires Domain Entitlement | Domain Capability Key | Domain Default State (no Subscription) | Behavior When Domain Disabled |
|---|---|---|---|---|---|
| Executive Dashboard | Yes | N/A (per-widget, see below) | N/A | N/A | Widgets for disabled domains are simply omitted (FR-RPT-041) |
| Sales Analytics | Yes | `sales` — genuinely gated, not structurally exempt | `sales` | Entitled by default (no master toggle; `DefaultAlwaysEnabledModuleProvider`) | Unreachable if disabled via override/future Plan restriction |
| Purchase Analytics | Yes | `purchase` — genuinely gated, not structurally exempt | `purchase` | Entitled by default (same mechanism) | Unreachable if disabled |
| Inventory Analytics | Yes | `inventory` — genuinely gated, not structurally exempt | `inventory` | Entitled by default (same mechanism) | Unreachable if disabled |
| Accounting / Financial Reporting | Yes | `accounting` — genuinely gated, not structurally exempt | `accounting` | Entitled by default (same mechanism) | Unreachable if disabled |
| CRM Analytics | Yes | `crm` — genuinely gated, explicit master toggle | `crm` | **Disabled by default** until tenant explicitly enables it | Unreachable if disabled — matches CRM's own `require_crm_enabled` precedent |
| Installment Analytics | Yes | `installments` — genuinely gated (service-method depth, not router depth), explicit master toggle | `installments` | **Disabled by default** until tenant explicitly enables it | **Case A** (no existing obligations): unreachable, same as any other disabled domain. **Case B** (serviceable obligations exist): remains read-only per FR-RPT-104/FR-INST-354 — the one documented exception to the generic rule in this table. |
| Customer 360 Financial View | Yes | **Section-level compound authorization, not all-or-nothing (corrected, 2026-09-11 — §20.2)**: `reports` + `reports.customer_360.view` required to open the report at all; each of the four constituent sections (Sales, Accounting, CRM, Installments) then independently evaluates its own domain entitlement | `sales`, `accounting`, `crm`, `installments` (evaluated independently per section, not as a combined AND-gate on the whole report) | Sales/Accounting default entitled; CRM/Installments default disabled | Any section whose domain entitlement is not active is **omitted** from the response (§20.2, FR-RPT-114/115); the remaining authorized sections are still returned. The report is denied only if the base gate (`reports` + `reports.customer_360.view`) itself fails, or per FR-RPT-116 if the user cannot access the customer master record at all. |
| Branch Performance Summary (deferred) | Yes | `purchase`/`inventory`/`installments` per populated data | `purchase`, `inventory`, `installments` | Per above | Deferred entirely until FR-RPT-012 is satisfied |

- **FR-RPT-250**: `reports` MUST be registered as its own `grain=module` Capability with the existing Platform Admin Capability/Plan catalogue (Assumption A6), resolved through the existing `PlatformEntitlementService.resolve_effective_entitlement()`.
- **FR-RPT-251**: Every domain-specific report family MUST additionally require its source domain's own entitlement to be active — enabling `reports` alone MUST NEVER expose a disabled domain's data (directly satisfies the governing prompt's CRM/Installments examples). This applies uniformly to all six domains — Sales/Purchase/Inventory/Accounting are not exempt from this check merely because they resolve to entitled by default today (FR-RPT-254).
- **FR-RPT-252** (**corrected, 2026-09-11 micro-correction pass**): When a domain's entitlement is disabled, its report keys, dashboard widgets, and any drill-down targets into it MUST become unreachable, returning the platform's existing documented "module not entitled" error — never a silently empty or zeroed report that could be mistaken for "no data" (Constitution §11). **This is the generic rule; it applies to CRM without exception.** It applies to every other domain the same way **except where the underlying domain already defines an established, documented post-disable servicing-continuity invariant** — currently, Installments is the sole such exception (FR-INST-354, FR-RPT-104): a disabled domain's reports become unreachable under this rule *unless* that domain's own specification defines a narrower, explicitly-scoped servicing-continuity carve-out, in which case the narrower rule governs instead of this one, and only for the exact scope that carve-out defines (never a blanket "disabled modules still work" precedent). No other domain in this specification currently has such a carve-out.
- **FR-RPT-253**: Disabling `reports` itself MUST NOT retroactively delete saved views (§29); they simply become unreachable until re-entitled, consistent with the platform's "disabling never destroys existing state" precedent (BR-INST-014 analog).
- **FR-RPT-254** (**new, 2026-09-11 correction pass**): The `reports.<domain>.view`/`.export` gate chain (§8.1) MUST evaluate every domain's entitlement identically through `PlatformEntitlementService.resolve_effective_entitlement()`, regardless of that domain's current default-resolved state — Epic 11 MUST NOT hardcode Sales/Purchase/Inventory/Accounting as unconditionally entitled, since a future Plan restriction, tenant-toggle addition, or `EntitlementOverride` could disable any of them, and the reporting layer must correctly honor that the moment it takes effect, with no separate code path required.
- **FR-RPT-255** (**new, 2026-09-11 correction pass**): `/sp.plan` MUST decide the `reports` Capability's own default-resolved state (entitled-by-default like Sales/Purchase/Inventory/Accounting, or disabled-by-default like CRM/Installments) as an explicit product decision — this specification recommends disabled-by-default, treating Reports & Analytics as an opt-in add-on capability consistent with the CRM/Installments precedent, rather than assuming it inherits the "no master toggle" default-on behavior of the four core operational-recording modules. This recommendation does not block spec approval (§53).

## 35. Multi-Tenancy & Tenant Isolation

- **FR-RPT-260**: Every report query, aggregate, count, chart, drill-down, export, saved view, and (future) cache key MUST be scoped to the authenticated tenant's `company_id`, enforced at API, service, and repository layers via the existing `get_current_company_member` dependency (Constitution §9) — no new tenant-resolution mechanism.
- **FR-RPT-261**: Tenant-aware search/report/export MUST NEVER return, count, or otherwise reveal another tenant's data, including through indirect signals (sequential ID probing, error-message differences between "not found" and "not authorized"), mirroring BR-INST-001/BR-INST-015's precedent.
- **FR-RPT-262**: A cross-module report (§20) MUST apply tenant scoping independently to each domain it touches — it MUST NOT rely on one domain's tenant check to implicitly secure another domain's data.
- **FR-RPT-263**: `company_id`/branch/ownership fields supplied by the client MUST NEVER be trusted over the authenticated session's tenant context (mass-assignment protection), matching every other module's established pattern.

## 36. Security Requirements — Security Matrix

| Capability | Tenant | Branch | Permission | Entitlement | Underlying Record Access | Export |
|---|---|---|---|---|---|---|
| View a report | Enforced (§35) | Data-filter only, no ACL (§25) | `reports.<domain>.view` | `reports` + domain (§34) | N/A (aggregate) | N/A |
| Drill down | Enforced | Inherited from parent report scope | `reports.<domain>.view` | `reports` + domain | Underlying module's own record-view permission re-checked (§27) | N/A |
| Export a report | Enforced | Inherited from report filter scope | `reports.<domain>.export` (distinct from `.view`) | `reports` + domain | Same field-level restrictions as the online view (§30) | Row-limit + audit (§30) |
| Save a view | Enforced (owner-only) | N/A | `reports.saved_view.manage` | `reports` | N/A | N/A |
| Load a saved view | Enforced (owner-only) | Re-validated at load | Re-checked at load (§29) | Re-checked at load | Re-checked at load | N/A |

- **FR-RPT-270**: Every Epic 11 endpoint MUST require authentication and MUST enforce tenant-scoped, permission-based authorization before any service call, before returning any data (Constitution §15/§16).
- **FR-RPT-271**: Direct-object-reference drill-down endpoints (report → specific record) MUST verify tenant ownership before returning any data, returning an identical "not found" response for both "does not exist" and "exists but belongs to another tenant" (IDOR prevention).
- **FR-RPT-272**: Internal error details (stack traces, SQL, internal identifiers) MUST NEVER be exposed to clients in production, consistent with Constitution §21.
- **FR-RPT-273**: The Platform Admin / support-access boundary (§38) MUST be enforced identically for Epic 11 as for every other tenant business-record domain — no shortcut route exists.

## 37. Privacy & Sensitive Data

- **FR-RPT-280**: Reports MUST expose only the fields required for their declared analytical purpose; a Report Definition's response schema MUST be an explicit allow-list of fields, never a raw pass-through of a source model's full column set.
- **FR-RPT-281**: Reports MUST NEVER expose passwords/secrets, authentication metadata, internal security tokens, or platform-support internals — none of the wrapped per-module services expose these today, and Epic 11's own schemas MUST preserve that boundary explicitly rather than accidentally widening it through a generic pass-through.
- **FR-RPT-282**: Personally identifiable customer/supplier contact fields exposed in a report MUST be limited to what the report's stated business purpose requires (e.g., a sales-by-customer summary needs a customer name, not a full contact/address block) — full PII detail remains available only through the underlying module's own detail view, reached via drill-down (§27) with its own permission check.

## 38. Platform Admin & Support-Access Boundary

Constitution §50 and `specs/009a-platform-admin/spec.md` establish Platform Administration as a control-plane actor distinct from Company/Tenant Admin, with authority over tenant lifecycle/entitlements/plans, never over tenant business records. Discovery confirms this is enforced in code today (`modules/platform_admin/router.py:1212-1217`: "This module imports no business-record repository from any of Inventory/Purchase/Sales/Accounting/CRM"), and BR-9A-021/FR-9A-121 explicitly reserve tenant business reporting for "a future dedicated reporting module/Epic" — this Epic.

- **FR-RPT-290**: Platform Administration governing the `reports` module entitlement for a tenant (enabling/disabling it, per §34) MUST NOT grant the acting Platform Administrator any read or write access to that tenant's report data, saved views, or export history (BR-9A-021 analog).
- **FR-RPT-291**: Where an active, time-bounded Epic 9A `SupportAccessGrant` exists for a tenant, that grant's existing inspection-only, business-record-excluded scope applies unchanged to Epic 11 — report data, saved views, and exports remain outside support-access scope unless a future, separate specification amendment explicitly changes that boundary (mirrors FR-INST-311's precedent exactly).
- **FR-RPT-292**: Epic 11 MUST NOT introduce any new cross-tenant aggregation surface reachable by Platform Administration — cross-tenant/platform-wide analytics is explicitly out of scope (§51, NG9).

## 39. Audit & Observability

- **FR-RPT-300**: The following MUST produce an audit record: every report export (§30, FR-RPT-217), saved-view creation/edit/deletion, and any Platform Admin action affecting the `reports` entitlement (reusing the existing entitlement-change audit path already established in Epic 9A) — matching the governing prompt's guidance to audit exports and sensitive/high-value actions without flooding the audit log with every ordinary dashboard refresh.
- **FR-RPT-301**: Ordinary report/dashboard *views* (as opposed to exports) are NOT required to produce a persistent audit-log record — only lightweight operational observability (below) — consistent with the governing prompt's explicit instruction not to over-audit routine reads.
- **FR-RPT-302**: Each audit record MUST identify: tenant, actor, action, target report key/saved-view ID, timestamp, and (for exports) the filter scope and row count — consistent with the existing per-module audit-log shape (Constitution §35).
- **FR-RPT-303**: The system MUST log, for observability (not necessarily the audit log), at minimum: report key, execution duration, success/failure, and result row/size where applicable, for every report and export request — without logging the actual sensitive report contents (Constitution §22, governing prompt §62).
- **FR-RPT-304**: A slow-running report request SHOULD be identifiable in logs (duration threshold left to `/sp.plan`, since no numeric SLA is fabricated here per Assumption A8) to support future performance triage.

## 40. API & Response Envelope Requirements

- **FR-RPT-310**: Every Epic 11 endpoint MUST follow the existing `/api/v1/companies/{company_id}/reports/...` routing convention, MUST use `StandardResponse[T]` for single-object results and `PaginatedResponse[T]` for list results, and MUST use `ErrorResponse` for all error cases — reusing `core/schemas/{response,pagination}.py` verbatim (Assumption A10).
- **FR-RPT-311**: Every report response MUST carry, at minimum: the resolved `report_key`, the filters actually applied, the period resolved (including timezone-derived boundaries), the measures/dimensions returned, pagination metadata (where applicable), comparison data (where requested), a freshness classification (§32), and drill-down references (where applicable) — matching the governing prompt's required envelope shape, expressed through the existing `StandardResponse`/`PaginatedResponse` wrapper rather than a new incompatible shape.
- **FR-RPT-312**: Report contract identity MUST be the stable `report_key`, never a UI label — renaming a report's display name in the frontend MUST NOT require a contract version bump (§8.2, FR-RPT-033).

## 41. Frontend & UX Requirements

Discovery found no existing cross-module reporting UI, no charting library, no shared `DataTable`, and no shared money/date formatting utility (§6.2) — this section is genuinely new frontend work, not a wrapper.

- **FR-RPT-320**: The frontend MUST introduce a `(reports)` route group under `app/(protected)/` providing: Overview/Executive, Sales, Purchase, Inventory, Finance, CRM, and Installments sections — with each section's visibility driven by the discovery endpoint (FR-RPT-032), never hardcoded, so a disabled/unentitled/unpermitted section is simply absent from navigation (never an empty page).
- **FR-RPT-321**: The frontend MUST introduce one reusable `DataTable` component supporting pagination, sortable-column indication (server-driven per §28), column-level money/date formatting, and export triggering — replacing the current per-page hand-rolled tables and the one-off `ReportViewer.tsx` (which lacks pagination).
- **FR-RPT-322**: The frontend MUST introduce a shared, currency-aware money-formatting utility and a shared date-formatting utility, used by every Epic 11 report/dashboard component — no report page may render a raw unformatted numeric string for a monetary value (the current state of several existing report pages, per discovery).
- **FR-RPT-323**: Charts MUST be used only where they communicate a meaningful pattern (trend lines, period comparisons) and MUST be driven by the same backend metric definitions as the equivalent tabular report — no separate frontend-computed KPI value that could drift from the backend's definition (governing prompt §58, directly enforced by FR-RPT-020/021).
- **FR-RPT-324**: The dashboard and every report page MUST implement defined loading, empty, error, permission-denied, and module-disabled states (Constitution §23), consistent with §13's per-widget graceful-degradation requirement.
- **FR-RPT-325**: `/sp.plan` MUST select and introduce exactly one charting library dependency (none exists today), with its justification documented per Constitution §26 Dependency Management.

## 42. Accessibility & Responsiveness

- **FR-RPT-330**: Reporting UI MUST meet the platform's existing WCAG 2.1 AA baseline (Constitution §23) — keyboard-navigable tables and filters, semantic labels for charts (or an accessible tabular alternative/summary alongside every chart), and readable, responsive table layouts on all supported screen sizes.
- **FR-RPT-331**: Every chart MUST have an accessible non-visual alternative (a data table or textual summary) so a screen-reader user can obtain the same information a sighted user gets from the chart.

## 43. Concurrency / Failure / Recovery Behavior

- **FR-RPT-340**: Because report execution is strictly read-only against every business domain (NG2), Epic 11 introduces no new concurrency-control requirement for business data; saved-view creation/edit (Epic 11-owned state) MUST use the platform's existing optimistic-concurrency or last-write-wins convention, documented in `/sp.plan`.
- **FR-RPT-341**: If a wrapped per-module service call fails (timeout, unavailable dependency, unconfigured account) mid-report, the system MUST return a documented, clear failure for that report/widget rather than a partial or silently-zeroed result that could be mistaken for a real "zero" figure (governing prompt §61).
- **FR-RPT-342**: A dashboard widget whose underlying service call fails MUST fail independently — one widget's failure MUST NOT prevent the remaining widgets from rendering (matches FR-RPT-041's per-widget gating philosophy).
- **FR-RPT-343**: A suspended tenant (Epic 9A tenant lifecycle) MUST be denied all Epic 11 activity consistent with however suspension is already enforced platform-wide — Epic 11 introduces no separate suspension-enforcement mechanism.

## 44. Non-Functional Requirements

No specific numeric performance/scale targets exist elsewhere in the repository for a module of this kind (Assumption A8); the following remain qualitative and testable, except where §30/§31 explicitly mark a **Recommended Decision** with its own rationale:

- **Correctness**: Every wrapped report's totals MUST be reconcilable, field-for-field, against its authoritative source service's own existing output for identical inputs (§17 FR-RPT-081, §48.3).
- **Security**: Every requirement in §36 is independently verifiable via security testing (IDOR, tenant-isolation, permission/entitlement-boundary tests).
- **Tenant Isolation**: Every report, dashboard widget, drill-down, export, and saved view is independently testable for cross-tenant leakage (§35).
- **Consistency**: One metric never produces two different values across the dashboard, a domain report, and an export for the same filters (§10, FR-RPT-020/021).
- **Auditability**: Every action enumerated in §39 is independently testable for producing exactly one, correctly attributed audit record.
- **Performance**: List/report/export endpoints remain responsive under pagination as data volume grows, consistent with the platform's existing N+1-query prohibition (Constitution §25); no specific latency figure is fabricated here beyond the explicit export row-count guardrail (§30).
- **Scalability**: The Report Registry MUST NOT assume a fixed maximum number of registered reports, saved views, or export requests per tenant.
- **Maintainability**: Epic 11 follows the existing modular monolith module structure (Constitution §12) — API/schemas/models/services/repositories/validators/permissions/tests/docs — enabling independent review and testing.
- **Observability**: Every report/export operation is logged consistent with Constitution §22 (§39).
- **Type Safety**: See §49.

## 45. Edge Cases

- What happens for a new company with zero transactions in every module? Every report/widget MUST render a defined empty state (zero counts, empty tables) — never an error (§13 FR-RPT-044).
- What happens when a user has no authorized branches? Because no branch-ACL concept exists (§25), this scenario does not yet apply; branch filters, where offered, remain unrestricted data filters until a future epic introduces branch-level authorization.
- What happens when a user has exactly one branch's worth of data available via a `branch_id` filter? The branch filter behaves as an ordinary equality filter; no special-case handling is required.
- What happens when CRM is disabled mid-session while a user has a CRM report open? The next request for a `crm.*` report key MUST return the documented "module not entitled" error (§34, FR-RPT-252); the frontend MUST handle this as a module-disabled state (§41). CRM has no servicing-continuity exception — this is the unconditional generic rule.
- What happens when Installments is disabled mid-session while a user has an `installments.*` report open? (**Corrected, 2026-09-11 — this is NOT the same answer as CRM's.**) The next request is resolved per FR-RPT-104's two cases: if no serviceable contracts/obligations exist for the tenant (Case A), the request returns the same "module not entitled" error as CRM; if serviceable obligations already exist (Case B), the request instead succeeds in read-only form, per the documented Epic 10 servicing-continuity exception (§34's generic-exception statement, FR-INST-354) — never treated identically to CRM's unconditional denial.
- What happens to a saved view referencing a report the user's role no longer permits? Loading it MUST fail with a documented permission error, never silently execute with reduced scope (§29, FR-RPT-203).
- What happens to a saved view whose report_key is later retired from the catalog? Loading it MUST fail gracefully (§29, FR-RPT-204).
- What happens when a deleted/inactive customer or supplier appears in historical report data? It remains visible (historical truth) but is labeled inactive/deleted (§27, FR-RPT-183).
- What happens for a cancelled transaction, reversed journal, or partially paid installment inside a report? It is preserved per the domain's own defined status-inclusion rule (§26) — never silently dropped from history.
- What happens when a custom date range crosses a year boundary? It is computed identically to any other range — no truncation at the boundary (§22, FR-RPT-134).
- What happens at a company's local-timezone day boundary for a "Today"/"This Month" preset? The boundary is computed from `Company.default_timezone`, not server/UTC time (§22, FR-RPT-131).
- What happens when a comparison period's denominator is zero? A documented "not comparable" indicator is returned, not an infinite/undefined percentage (§23, FR-RPT-141).
- What happens for a very large filtered dataset requested as a synchronous export? The system rejects the request with a documented "narrow your filters" error once the row-count guardrail is exceeded (§30, FR-RPT-214).
- What happens for an export whose filters match zero rows? A valid, well-formed, empty-body file is returned, not an error (§30, FR-RPT-219).
- What happens when a report's prerequisite configuration is missing (e.g., Accounting not yet configured with a chart of accounts for a brand-new tenant)? The report MUST represent this as an explicit "not yet configured/unavailable" state, never a misleading zero total (governing prompt §61).
- What happens when two modules define similarly-named metrics that are not actually the same figure (Sales' line-item margin vs. Accounting's recognized margin)? They are exposed under distinct catalog names and never merged (§10, FR-RPT-020).

## 46. Acceptance Scenarios

- **Scenario A — Wrapped financial statement reconciles exactly**: Given posted journal entries in Accounting, when a user requests the Epic 11 Trial Balance report and separately calls Accounting's own existing Trial Balance endpoint for identical parameters, then both return identical, debit-equals-credit totals (FR-RPT-081).
- **Scenario B — Executive dashboard graceful degradation**: Given a tenant with CRM disabled, when an authorized user loads the Executive Dashboard, then every widget except the CRM Pipeline widget renders correctly, and the CRM widget is simply absent from the response (FR-RPT-041, FR-RPT-044).
- **Scenario C — Drill-down re-checks permission**: Given a user holding `reports.sales.view` but not `sales.invoices.read`, when they attempt to drill down from the Sales Summary report into an invoice's detail, then the drill-down is denied even though the report itself was viewable (FR-RPT-181).
- **Scenario D — Export scope matches online view**: Given a filtered Sales by Customer report returning 3 pages online, when the same filters are exported as CSV, then the exported file's row set is the exact union of all 3 online pages, no more, no fewer (FR-RPT-213).
- **Scenario E — Saved view re-validated at load**: Given a user saves a view referencing `reports.accounting.view`, and their role is later changed to remove that permission, when they attempt to load the saved view, then the load is denied with a documented permission error (FR-RPT-203).
- **Scenario F — Tenant isolation on a cross-module report**: Given Tenant A's Customer 360 view, when Tenant B's authenticated user attempts to load it by any identifier or search, then the response is indistinguishable from "not found" (FR-RPT-261, FR-RPT-271).
- **Scenario G — Branch filter is a data filter, not a security boundary**: Given a Purchase Order tagged with a `branch_id`, when a user without any special branch grant (because none exists) filters the Open Purchase Commitments report by that branch, then the filter applies as an ordinary data filter and returns the matching rows — this scenario itself documents that no authorization narrowing occurs (FR-RPT-160/161).
- **Scenario H — Disabled Installments entitlement, existing contracts remain reportable (Case B)**: Given a tenant whose Installments entitlement is later disabled while serviceable contracts already exist, when an authorized user requests the Installment Aging report, then the report still returns correctly, read-only, consistent with FR-INST-354 (FR-RPT-104 Case B) — this is the one documented exception to the generic disabled-domain rule.
- **Scenario I — Zero-denominator comparison**: Given a metric whose prior-period value is zero and current-period value is non-zero, when a period-over-period comparison is requested, then the response marks the comparison "not comparable" rather than returning an undefined/infinite percentage (FR-RPT-141).
- **Scenario J — Export row-count guardrail**: Given a filter scope matching more than 50,000 rows, when a synchronous export is requested, then the system rejects the request with a documented "narrow your filters" error rather than generating an oversized file (FR-RPT-214).
- **Scenario K — Platform Admin cannot read tenant report data**: Given a Platform Administrator who just enabled the `reports` entitlement for a tenant, when that same Platform Administrator attempts to call any `reports.*` tenant endpoint for that tenant, then the request is denied (FR-RPT-290).
- **Scenario L — CSV export neutralizes formula injection**: Given a customer name value beginning with `=SUM(...)`, when that value is included in a CSV export, then the exported cell is neutralized (not interpreted as a spreadsheet formula when opened) (FR-RPT-216).
- **Scenario M — Disabled Installments entitlement, no existing obligations (Case A, new, 2026-09-11 micro-correction pass)**: Given a tenant whose Installments entitlement is disabled and who has never had any installment contracts, when an authorized user requests any `installments.*` report, then the request is denied with the same documented "module not entitled" error CRM would return in the equivalent scenario (FR-RPT-104 Case A, FR-RPT-252) — confirming Case A and Case B (Scenario H) are not treated identically, and that the servicing-continuity exception never applies where there is nothing to service.
- **Scenario N — Customer 360 section-level partial availability (new, 2026-09-11 micro-correction pass)**: Given a tenant with CRM disabled and Installments entitled, when an authorized user (holding `reports.customer_360.view`, `reports.sales.view`, and `reports.accounting.view`, but not `reports.crm.view`) requests Customer 360 for a customer with Sales and Accounting activity, then the response includes the Sales, Accounting, and Installments sections normally, the CRM section is omitted (FR-RPT-114 state 2), and the response is never denied outright merely because one section's gate failed (FR-RPT-111).
- **Scenario O — Customer 360 minimum useful response (new, 2026-09-11 micro-correction pass)**: Given a user who cannot access any of the four constituent business sections for a given customer but is separately authorized to view that customer's master record, when they request Customer 360, then the response returns the identity/master-data section only, with every business section explicitly marked omitted/unavailable per FR-RPT-114 — never a distinguishable "empty shell" for a user who is not authorized to view the customer master record at all, who instead receives the platform's standard IDOR-safe "not found" response (FR-RPT-116).

## 47. Success Criteria

- **SC-001**: Every "Now" financial report in the catalog reconciles exactly with Accounting's own existing endpoint output across representative test fixtures — zero discrepancies.
- **SC-002**: Zero cross-tenant data exposure across all tenant-isolation test scenarios (§36, §46 Scenario F).
- **SC-003**: 100% of registered "Now" reports are reachable only through the full gate chain (tenant → `reports` entitlement → domain entitlement → permission → filter validation) — verified by a security test attempting to skip each gate independently.
- **SC-004**: Zero instances, across the executive dashboard, any domain report, and any export, of the same displayed metric name resolving to two different computed values for identical inputs.
- **SC-005**: 100% of the export/saved-view actions enumerated in §39 produce a correctly attributed, tenant-scoped audit record in representative test scenarios.
- **SC-006**: Disabling a domain's entitlement (CRM, Installments) makes 100% of that domain's report keys and dashboard widgets unreachable within the same request cycle — no stale/cached access persists (subject to §32's "no caching in Epic 11" scope).
- **SC-007**: A representative saved-view round trip (save → reload) reproduces the identical filter/grouping/sorting/column configuration in 100% of test cases, and is never visible to a second user of the same tenant.
- **SC-008**: `mypy .` remains at zero errors across the entire repository (production and tests) after Epic 11 implementation, with no broad suppressions introduced.

## 48. Test Strategy

### 48.1 Security Testing

Required, per governing prompt §63: tenant isolation, cross-tenant ID tampering, branch-filter-is-not-authorization boundary tests (confirming no false sense of branch security is created), RBAC (including `.view`-vs-`.export` separation), entitlement denial (both `reports` and per-domain), disabled-module behavior, export authorization, saved-view ownership, drill-down re-authorization, Platform Admin/support-access boundary, and (once introduced) cache isolation.

### 48.2 Report Correctness Testing

Every "Now" report requires deterministic correctness tests using fixtures with known expected totals, covering: included/excluded records per status rule (§26), date boundaries (§22), branch-filter behavior where applicable (§25), cancellations/returns/reversals (§26), partial payments, Decimal precision (§24), and empty states.

### 48.3 Financial Invariant Testing

Required, per governing prompt §65 — since Epic 11 wraps rather than recomputes: Trial Balance debits = credits (reused from Accounting's own existing invariant test, re-asserted through Epic 11's wrapper endpoint); Balance Sheet equation holds; every wrapped financial report's totals equal Accounting's own existing endpoint output for identical inputs (FR-RPT-081); AR/AP totals reconcile with `AccountsReceivableService`/`AccountsPayableService`; Installment aging reconciles with Accounting's AR for the same obligations (US-6).

### 48.4 Real PostgreSQL Testing

Reporting SQL paths that involve aggregation, joins, date grouping, Decimal/Numeric precision, pagination, or PostgreSQL-specific expressions MUST be validated against real PostgreSQL using the existing `pg_test_db`/`alembic_upgrade`/`pg_engine` fixture chain (`tests/integration/migrations/conftest.py`), following the established per-directory re-export convention — not the default in-memory SQLite suite.

### 48.5 Performance Testing

Consistent with the lesson explicitly carried forward from the Pre-Epic-11 stabilization effort: no fragile universal wall-clock assertions. Prefer query-count expectations (asserting no N+1 pattern per FR-RPT-220/221), bounded-query-plan checks for high-value reports (GL, Trial Balance), dataset-size scenarios, and isolated slow/performance tests where genuinely necessary — never a shared-CI-runner-sensitive timing assertion.

## 49. Type Safety / CI Requirements

- **FR-RPT-350**: Epic 11's production code and its tests MUST maintain the repository-wide `mypy . = 0` invariant established by the Pre-Epic-11 stabilization effort — no `Any` used as an escape hatch, no broad per-file or per-line MyPy suppressions, and no weakening of `mypy.ini`/CI configuration.
- **FR-RPT-351**: All Report Definitions, filter schemas, metric definitions, and wrapped-service call signatures MUST be fully typed Pydantic/Python constructs — consistent with every other module's existing convention.
- **FR-RPT-352**: Epic 11 code MUST pass `ruff check` and `ruff format --check` unchanged from the existing CI configuration (`.github/workflows/backend.yml`), and MUST participate in the existing `pytest --cov-fail-under=80` gate against a real `postgres:16-alpine` CI service.
- **FR-RPT-353**: No new CI job, coverage threshold reduction, or gate bypass may be introduced for Epic 11 — it is subject to the identical `lint → {test, security, migrations} → docker-build` pipeline as every other module.

## 50. AI-Readiness

Epic 11 deliberately produces stable, typed, permission-aware contracts a future AI layer (post-Epic-12) can consume safely, without implementing any AI capability now.

- **FR-RPT-360**: Every Report Definition's `key`, `required_permission`, `required_entitlements`, declared filters, and declared measures (§8.2) MUST be structured so a future AI gateway can invoke the same report a human user would, inheriting — never bypassing — that same tenant context, RBAC permission, and entitlement state (governing prompt §69/§70).
- **FR-RPT-361**: The KPI/Metric Catalog (§10) is the exact semantic surface a future AI layer would answer questions like "What were our sales this month?" or "How much do customers owe us?" against — by calling the same registered report/metric, never by generating ad hoc SQL.
- **FR-RPT-362**: Epic 11 MUST NOT implement, and this specification explicitly records as out of scope: any LLM API integration, AI agent, AI employee, embeddings, vector database, RAG, natural-language-to-SQL translation, AI chat interface, AI credit billing, or token accounting (NG6).
- **FR-RPT-363**: No hidden "AI bypass" path may exist in Epic 11's design — every future AI consumer of a report/metric MUST pass through the exact same gate chain (§8.1) as a human request; this specification introduces no privileged internal API that skips tenant/RBAC/entitlement enforcement.

## 51. Out of Scope / Deferred

The following remain explicitly future-ready rather than implemented in Epic 11:

- Arbitrary custom report builder, arbitrary SQL, or unrestricted query builder (NG1).
- Data warehouse, OLAP engine, ClickHouse, Elasticsearch analytics, materialized-view infrastructure, or event-stream analytics (NG4).
- Scheduled/emailed reports and report subscriptions (NG5).
- Shared/collaborative saved views (private-only for Epic 11, NG5, §29).
- Asynchronous/background export job infrastructure (NG7) — Epic 11 defines a synchronous contract with a documented, extensible seam only.
- Any AI capability whatsoever (NG6, §50).
- Cross-tenant / platform-wide SaaS analytics (NG9, §38).
- A first-class `Branch` entity or branch-level authorization boundary (NG10, §25) — branch filters in this Epic remain plain data filters only.
- The `crossmodule.branch_performance` report, pending confirmation of populated branch data (§9, FR-RPT-012).
- Predictive analytics, anomaly detection, or forecasting models.
- Result caching (§32) — deferred, with the cache-key shape pre-specified for future use.
- Tax Summary/Detail and Cost-Center/Project P&L wrapping (listed "Deferred" in §9 pending `/sp.tasks` prioritization, though their source services already exist in Accounting).
- The remaining Sales/Purchase/Inventory report variants beyond the "Now" rows in §9 — these are wrapped using the identical mechanism, just sequenced later in `/sp.tasks`.
- **Resolving ADR-0004** (inventory-to-GL valuation integration) — that gap belongs to Accounting/Inventory's own domain architecture (a future Phase 4 item per ADR-0004 itself), not to Epic 11. Epic 11 reports Inventory's existing operational WAC figure honestly labeled as such (§7, §9, §10, §16, Assumption A11) and explicitly does not invent a new valuation algorithm or a synthetic reconciliation to fill that gap.

## 52. Risks

| Risk | Mitigation |
|---|---|
| Epic 11 accidentally re-derives a financial figure instead of calling Accounting's existing service, creating a second, drifting source of truth. | FR-RPT-003/081 make "wrap, never re-derive" an architectural constraint, verified by FR-RPT-004's registry/implementation consistency test and §48.3's financial invariant tests. |
| A branch filter is misread by implementers or users as a security boundary when none exists, creating a false sense of data isolation. | §25 states the finding explicitly and FR-RPT-161/162 forbid presenting it as authorization; Scenario G is a dedicated test making this non-guarantee explicit. |
| The same metric name (e.g., "margin") is computed two different ways in two places, confusing users and eroding trust. | §10's catalog assigns distinct names to distinct computations; FR-RPT-020/021/SC-004 make this independently testable. |
| Export becomes a data-exfiltration path bypassing the RBAC granularity applied to the online view. | §30's dedicated `.export` permission, row-count guardrail, audit requirement, and field-parity requirement (FR-RPT-218) mitigate this directly. |
| Sales/Accounting decimal-precision mismatch (`NUMERIC(15,2)` vs `NUMERIC(20,6)`) causes silent rounding drift in cross-module aggregations. | Assumption A4/FR-RPT-151 resolve this explicitly in Accounting's favor for arithmetic, matching the Installments precedent. |
| A Platform Admin action (entitlement change) is misconstrued as a route to tenant business data. | §38's explicit boundary requirements and Scenario K's dedicated test make this non-access verifiable. |
| The large "Deferred" tail of existing per-module report variants (§9) never gets promoted, leaving Epic 11's catalog perpetually incomplete relative to what each module already offers. | §9 explicitly scopes "Now" vs "Deferred" per family and defers exhaustive enumeration to `/sp.tasks`, which is the correct venue for sequencing, not a specification gap. |
| A user (or a future AI consumer) mistakes Inventory's operational WAC figure for a reconciled, GL-backed accounting inventory balance, since ADR-0004's gap is easy to overlook. | §7/§9/§10/§16 rename and re-label every inventory-valuation surface as explicitly "operational," require a `valuation_basis` disclaimer field (FR-RPT-071), and Assumption A11 documents the underlying ADR-0004 gap in full so `/sp.plan` cannot silently paper over it. |
| Implementers assume Sales/Purchase/Inventory/Accounting are structurally exempt from entitlement checks (because they're "core"), and hardcode them as always-entitled — breaking the moment a future Plan/override restricts one of them. | FR-RPT-254 explicitly requires the identical `resolve_effective_entitlement()` gate for all six domains regardless of current default state; §34's corrected matrix documents the real mechanism (default-state vs. structural exemption) so this distinction cannot be missed in `/sp.plan`. |

## 53. Open Questions / Clarifications

**Status after the 2026-09-11 correction pass: no blocking open decisions for `/sp.plan`.**

- **OQ-1 — Exact synchronous export row-count guardrail (FR-RPT-214).** No existing repository precedent sets a numeric export limit anywhere. *(Recommended decision, not blocking.)* The binding requirement is now the invariant itself ("never unbounded memory/CPU/DB load," configurable, may differ by format); 50,000 rows remains only a **non-binding planning candidate** for `/sp.plan` to validate or revise via representative payload-size testing — this is a pure implementation-planning parameter, not a product-architecture question, and does not block spec approval.
- ~~OQ-2 — Whether Sales and Purchase can be fully disabled per tenant.~~ **RESOLVED during this correction pass** (see Assumption A6, §34). Definitive repository evidence confirms all six source modules (Sales, Purchase, Inventory, Accounting, CRM, Installments) are genuinely registered, individually-gated `grain=module` Capabilities — none is structurally exempt from entitlement. They differ only in default-resolved state for a tenant with no active Subscription (Sales/Purchase/Inventory/Accounting default entitled; CRM/Installments default disabled). This is no longer an open question.
- ~~OQ-3 — Whether `crossmodule.branch_performance` should ship at all in Epic 11's first release.~~ **RESOLVED — DEFERRED (locked, 2026-09-11 micro-correction pass).** This is no longer framed as an open product decision: no Branch domain/ACL exists and real, populated `branch_id` data is not established for any known tenant today (§25, Assumption A3), so `crossmodule.branch_performance` is definitively Deferred, not merely "recommended" Deferred. **Promotion prerequisite** (the only condition under which this changes): `/sp.plan` confirms, against real tenant data, that the underlying `branch_id` columns are actually populated for at least one representative tenant (FR-RPT-012) — until that prerequisite is met, this report MUST NOT be promoted to "Now," and no further discussion of shipping it in Epic 11 is needed.
- **OQ-4 — Default-resolved state of the new `reports` Capability itself (FR-RPT-255).** *(Recommended decision, not blocking — deliberately NOT locked.)* Unlike OQ-2 (entitlement gating, resolved from hard evidence about the existing six modules) and OQ-3 (branch data, resolved from hard evidence about what doesn't exist), repository evidence cannot fully determine `reports`' own default state, because `reports` does not exist in the repository yet — there is no seeded Capability row, master toggle, or Plan assignment to inspect. The CRM/Installments precedent (optional add-on capabilities default to disabled) is a reasonable product analogy, not a proven fact about `reports` specifically; the four core modules' precedent (default-entitled) is an equally real alternative analogy. **Recommendation: disabled-by-default**, on the grounds that Reports & Analytics is an opt-in add-on rather than an operational-recording domain — but this specification deliberately leaves it as a `/sp.plan`-level product decision rather than locking it, and requires (FR-RPT-255) that whichever default is chosen be explicitly implemented and documented, never silently inherited from whichever default mechanism happens to get implemented first.

**Status after this micro-correction pass: no blocking open decisions for `/sp.plan`.** OQ-1 and OQ-4 remain recommended, non-blocking planning decisions with stated rationale; OQ-2 and OQ-3 are both fully resolved (OQ-2 from repository evidence, OQ-3 by explicit lock in this pass).

## 54. Constitution Compliance / Traceability

| Constitution Section | How Epic 11 Complies |
|---|---|
| §9 Multi-Tenant Principles | Every report/dashboard/export/saved-view query is `company_id`-scoped at every layer (§35). |
| §10 Multi-Branch Readiness | Branch filtering is offered only where a reserved `branch_id` column already exists, explicitly as a data filter, never an authorization boundary until a future epic delivers a real Branch entity (§25). |
| §11 Feature Toggles | `reports` and each domain's own entitlement are enforced via the existing Epic 9A toggle/entitlement mechanism (§34). |
| §12 Module Design | Epic 11 follows the standard module vertical-slice structure (api/schemas/models/services/repositories/validators/permissions/tests/docs) — deferred to `/sp.plan`. |
| §13 Repository Rules / §14 Service Layer Rules | Epic 11's own repositories (for `SavedReportView` and any export metadata) follow the same layering; report computation itself calls existing services, never raw SQL against another module's tables (§8.1, NG2). |
| §16 Authentication & Authorization | Every endpoint is authenticated and RBAC-gated before any service call (§33, §36). |
| §17 Database Principles (Money Handling Standard) | All monetary values use `Decimal`/`NUMERIC`, never floats; currency stored alongside amounts (§24). |
| §19 Security Principles | OWASP-aligned requirements throughout §36 (IDOR prevention, least privilege, no internal error leakage). |
| §21 Error Handling | Consistent `ErrorResponse` envelope for every documented failure mode (§21 filter contract, §40). |
| §25 Performance Principles | N+1 avoidance and aggregation-not-full-load requirements (§31). |
| §35 Audit Trail | Export and saved-view actions produce audit records following the existing who/what/when schema; append-only (§39). |
| §36 Internationalization Readiness | No cross-currency summation without conversion; monetary values carry currency codes; period boundaries use company timezone, not server timezone (§22, §24). |
| §37 SaaS Readiness | `reports` plugs into the existing Plan/Capability/Subscription model rather than defining a parallel one (§34). |
| §46 Business Configuration Philosophy | Period presets, comparison behavior, and export limits remain implementation-configurable rather than hardcoded business assumptions where the repository already supports that pattern. |
| §48 Shared Kernel Principles | No competing `Money`/date value object is introduced; existing per-module `Decimal`/`DateTime(timezone=True)` conventions are reused as-is (§24, §22). |
| §49 Event-Driven Communication Principles | Any new domain events Epic 11 publishes (e.g., `ReportExported`) follow the past-tense naming and outbox-pattern convention (§6.2, §39). |
| §50 Platform Administration & SaaS Control Plane Principles | Platform Admin governs the `reports` entitlement only, never tenant report data; the existing Epic 9A support-access boundary is preserved unchanged (§38). |

---
