---
id: 0001
title: Epic 11 Reports Analytics specification
stage: spec
date: 2026-09-11
surface: agent
model: claude-sonnet-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: /sp.specify
labels: ["epic-11", "reports-analytics", "specification", "discovery"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/011-reports-analytics/spec.md
 - specs/011-reports-analytics/checklists/requirements.md
tests:
 - none (specification-only phase; no code changes made)
---

## Prompt

/sp.specify

DevSphere ERP SaaS
Epic 11 — Reports & Analytics
Full & Final Specification (spec.md) Prompt

You are working on the existing DevSphere ERP SaaS repository.

Your task is to perform deep repository discovery and produce the final implementation-ready specification for Epic 11 — Reports & Analytics.

This is a SPECIFICATION-ONLY phase.

Do NOT implement Epic 11.

1. CURRENT PROJECT STATE

DevSphere ERP is an established multi-tenant modular-monolith ERP.

Completed and verified:

Epic 0 — Constitution / Architecture Foundation
Epic 1 — Foundation
Epic 2 — Authentication
Epic 3 — Companies / Multi-Tenancy
Epic 4 — Users & Roles / RBAC
Epic 5 — Inventory
Epic 6 — Purchase / Procurement
Epic 7 — Sales / Order-to-Cash
Epic 8 — Accounting / Finance
Epic 9 — CRM
Epic 9A — Platform Administration / Super Admin
Epic 10 — Installments

Epic 11 is:

Reports & Analytics

Epic 12 will later cover:

Deployment / Production Readiness

After Epic 12, a separate AI Layer will be integrated.

Epic 11 must therefore establish a trustworthy reporting foundation that both human users and future AI capabilities can safely consume.

2. PRE-EPIC-11 STABILIZATION BASELINE

A dedicated MyPy/type-safety stabilization effort has been completed before starting Epic 11.

Current verified baseline:

production MyPy: 0 errors
test MyPy: 0 errors
repository-wide mypy .: 0 errors
Ruff: clean
formatting: clean
repository-wide MyPy is a blocking CI gate
real PostgreSQL integration environment has been restored
remediation branch has been pushed and preserved
no known remaining first-party MyPy debt

Do NOT treat historical MyPy error counts as accepted technical debt.

Epic 11 must preserve this clean baseline.

Any Epic 11 implementation planned from this specification must maintain:

mypy . = 0

and must not weaken typing configuration or introduce broad suppressions.

3. FIRST RULE — DISCOVER BEFORE SPECIFYING

Before writing the final specification, deeply inspect the repository.

Do not assume architecture, field names, statuses, tables, service contracts, permission names, feature flags, route conventions, response envelopes, branch semantics, accounting semantics, or frontend conventions.

The repository is authoritative.

Inspect at minimum:

constitution / architecture documents
previous Epic specifications
previous plans/tasks where useful
backend module structure
shared/core abstractions
SQLAlchemy models
repositories
services
API routers
Pydantic schemas
permissions / RBAC
module entitlements
company/tenant context
branch context
audit/event infrastructure
pagination/filter conventions
export-related infrastructure
frontend architecture
existing dashboards
reusable UI components
existing charts/tables
date/time utilities
money/Decimal conventions
timezone conventions
PostgreSQL indexes
existing query patterns
test conventions
CI/type-check requirements.

Inspect the completed modules specifically for reporting-relevant contracts:

Sales
Purchase
Inventory
Accounting
CRM
Installments
Companies
Users/RBAC
Platform Administration where relevant.

Document reused capabilities versus genuinely new Epic 11 capabilities.

Do not duplicate functionality already implemented elsewhere.

4. CONSTITUTION IS AUTHORITATIVE

The existing project constitution and architectural rules remain binding.

If this prompt conflicts with an established repository invariant, follow the repository invariant and document the conflict in the specification.

Do not silently invent a competing architecture.

5. EPIC 11 PRODUCT PURPOSE

Epic 11 must provide a centralized:

Reporting & Analytics Read Layer

for DevSphere ERP.

This is not merely a collection of frontend report pages.

It must define a trusted read architecture through which authorized tenant users can:

understand business performance;
inspect operational activity;
analyze financial results;
compare periods;
filter and segment data;
drill down into supporting records;
export authorized report data;
use executive dashboards;
save useful reporting configurations where justified;
obtain consistent KPIs across modules.

The reporting layer must become the authoritative analytical surface for DevSphere ERP.

6. CORE DESIGN PRINCIPLE

Operational modules remain authoritative for operational transactions.

Accounting remains authoritative for financial truth.

Epic 11 must:

READ, AGGREGATE, INTERPRET, PRESENT, AND EXPORT

trusted information.

It must NOT create an alternative transactional source of truth.

Reports must not mutate Sales, Purchase, Inventory, Accounting, CRM, or Installment business state.

7. REPORTING SEMANTIC LAYER — REQUIRED RECOMMENDATION

Design Epic 11 around a centralized semantic/reporting layer rather than allowing every page or API endpoint to independently invent KPI calculations.

The specification should define, where compatible with the repository:

report definitions;
metric definitions;
dimensions;
filters;
grouping;
sorting;
period semantics;
comparison semantics;
authorization requirements;
source modules;
source-of-truth ownership;
drill-down contracts;
export capability;
freshness characteristics.

The same business metric must not acquire different meanings across different dashboards.

For example, if the system defines:

Net Sales
Gross Sales
Accounts Receivable
Inventory Value
Outstanding Installments

their calculation and source-of-truth semantics should be centralized and documented.

8. REPORT / METRIC REGISTRY

Evaluate and specify an internal report/metric registry or equivalent metadata mechanism.

The specification should determine whether each report should declare metadata such as:

stable report key;
human-readable name;
module/domain;
description;
required permission;
required entitlement;
allowed dimensions;
supported filters;
supported grouping;
supported sorting;
available measures;
comparison support;
drill-down support;
export support;
data freshness classification.

This does NOT mean implementing a generic arbitrary query engine.

The goal is a curated, controlled report catalog.

9. ABSOLUTELY NO ARBITRARY QUERY ENGINE

Epic 11 must NOT expose:

arbitrary SQL;
arbitrary table selection;
user-defined SQL;
unrestricted query builders over database tables;
arbitrary column access;
unrestricted cross-module joins;
raw database exploration APIs.

Reports must be curated application capabilities.

This is important for:

tenant isolation;
RBAC;
privacy;
accounting integrity;
predictable performance;
future AI safety.

10. MULTI-TENANCY — NON-NEGOTIABLE

Every report, dashboard, KPI, export, comparison, aggregation, drill-down, saved view, cache key, and asynchronous reporting artifact must be tenant-safe.

No cross-company leakage is acceptable.

The specification must explicitly define tenant isolation for:

report queries;
totals;
aggregates;
counts;
charts;
drill-downs;
exports;
cached results;
saved views;
async jobs if introduced;
generated files.

Never rely on frontend filtering for tenant security.

11. BRANCH-AWARE REPORTING

Inspect existing branch semantics and define how reports behave for:

a single branch;
multiple permitted branches;
company-wide views;
users with restricted branch access.

A user must never obtain data from a branch they cannot access merely by modifying:

query parameters;
report IDs;
saved filters;
export requests;
drill-down URLs.

The specification must distinguish:

tenant scope

from:

branch scope

where the existing architecture requires it.

12. RBAC

Every report capability must be permission-aware.

Do not create a single overly broad reports.view permission if existing project patterns support meaningful granular permissions.

Discover current permission conventions first.

Specify permissions for areas such as:

executive analytics;
sales reports;
purchase reports;
inventory reports;
accounting/financial reports;
CRM reports;
installment reports;
exports;
saved/shared reporting configurations if applicable.

Sensitive financial information should not automatically become visible merely because a user can access an operational module.

13. MODULE ENTITLEMENTS

Reporting must respect the existing module entitlement system.

Examples:

If CRM is disabled for a company, CRM analytics must not expose CRM data.

If Installments is disabled, installment reports must not become an alternative access path.

If a module requires a subscription entitlement, reporting cannot bypass it.

Specify the interaction:

Authentication → Tenant Context → Branch Scope → RBAC → Entitlement → Report Execution

using the repository's actual established order/contracts.

14. SOURCE-OF-TRUTH MATRIX — REQUIRED

The final spec.md must contain an explicit source-of-truth matrix.

At minimum cover:

Reporting Area    Authoritative Domain
Sales activity    Sales
Procurement    Purchase
Stock movement    Inventory
Inventory valuation    inspect repository authority
Financial statements    Accounting
Receivables/payables    Accounting where authoritative
CRM pipeline    CRM
Installment contract state    Installments
Installment financial postings    Accounting where applicable

Do not blindly use this table.

Inspect actual implementation and correct it according to repository truth.

For every major KPI, identify the authoritative owner.

15. ACCOUNTING IS FINANCIAL AUTHORITY

Financial reporting must not reconstruct accounting truth from Sales/Purchase/Installments when Accounting already owns the authoritative financial representation.

For financial reports, inspect existing:

chart of accounts;
journal entries;
journal lines;
posting status;
fiscal periods;
trial balance;
general ledger;
receivables/payables;
existing financial services;
currency/money handling.

Financial statements must reconcile with Accounting.

16. FINANCIAL REPORTS

Specify appropriate reporting contracts for the repository's implemented Accounting capabilities.

Evaluate at minimum:

Trial Balance
General Ledger
Profit & Loss / Income Statement
Balance Sheet
Accounts Receivable
Accounts Payable
Cash / Bank summaries where supported
journal activity
account activity
customer balances where authoritative
supplier balances where authoritative.

Do not invent financial capabilities not supported by the completed Accounting epic.

Where a report is not possible from current source contracts, document the prerequisite rather than fabricating behavior.

17. SALES ANALYTICS

Specify useful Sales reports based on actual Sales implementation.

Evaluate:

sales summary;
gross/net sales;
order/invoice counts;
sales by customer;
sales by product/item;
sales by branch;
sales by period;
sales by status;
returns/refunds/credit effects where implemented;
receivable-linked views;
top customers;
top-selling products;
average order/invoice value;
trend comparison.

Ensure financial metrics do not conflict with Accounting.

18. PURCHASE / PROCUREMENT ANALYTICS

Evaluate:

purchase summary;
purchase orders;
purchases by supplier;
purchases by item;
purchases by branch;
procurement trends;
outstanding procurement;
supplier spend;
purchase returns where supported;
payable-linked analytics where authoritative.

Respect actual Purchase lifecycle/status semantics.

19. INVENTORY ANALYTICS

Evaluate:

stock on hand;
inventory valuation;
stock movement;
low-stock items;
out-of-stock items;
inventory by warehouse/location/branch where supported;
fast-moving items;
slow-moving items;
dead/non-moving stock where enough historical data exists;
receipts/issues/transfers;
inventory adjustments;
stock aging only if the underlying data supports a defensible definition.

Do not derive valuation using a new formula if Inventory or Accounting already owns the valuation method.

20. CRM ANALYTICS

Evaluate based on existing CRM implementation:

lead counts;
opportunities;
pipeline value;
stage distribution;
conversion;
win/loss;
activity;
salesperson/owner performance;
customer acquisition trends.

Do not fabricate attribution or conversion definitions.

Define them explicitly from existing CRM lifecycle semantics.

21. INSTALLMENT ANALYTICS

Epic 10 is complete and verified.

Epic 11 must integrate Installments into reporting without duplicating its domain engine.

Evaluate:

active contracts;
portfolio value;
outstanding principal;
amount due;
amount collected;
upcoming installments;
overdue installments;
delinquency buckets;
collections;
settlements;
cancellations;
defaults;
write-offs;
product/customer/branch breakdowns where supported.

Where financial amounts are posted to Accounting, clearly distinguish:

operational installment state

from:

accounting financial truth.

22. EXECUTIVE DASHBOARD

Define a useful executive dashboard.

It should not become an uncontrolled mega-query.

Specify a carefully curated set of KPIs, potentially including:

sales;
purchases;
gross/net performance where defensible;
receivables;
payables;
cash/bank position where supported;
inventory value;
overdue receivables/installments;
CRM pipeline;
key trends.

Dashboard widgets must individually respect:

tenant;
branch;
RBAC;
entitlements;
date filters;
source-of-truth rules.

The dashboard must gracefully handle disabled modules.

23. KPI DEFINITIONS

Every important KPI must have an explicit semantic definition.

For each KPI specify where appropriate:

name;
business meaning;
authoritative source;
calculation;
included statuses;
excluded statuses;
date field used;
tenant scope;
branch scope;
currency assumptions;
rounding;
null behavior;
comparison semantics.

Avoid ambiguous names such as "Revenue" unless the exact accounting/business meaning is defined.

24. PERIOD SEMANTICS

Define standard reporting periods.

Evaluate:

Today
Yesterday
This Week
Last Week
This Month
Last Month
This Quarter
Last Quarter
This Year
Last Year
Custom Range.

Use company/tenant timezone semantics already established by the repository.

Define whether date boundaries are:

inclusive;
exclusive;
half-open intervals.

Prefer a consistent convention.

25. COMPARISON SEMANTICS

Where supported, reports should allow meaningful comparisons such as:

previous period;
previous month;
previous quarter;
previous year;
same period last year.

Specify:

absolute change;
percentage change;
zero-denominator behavior;
incomplete-current-period behavior.

Do not compare incomparable periods silently.

26. DATE FIELD SEMANTICS

Different domains have multiple dates:

created date;
order date;
invoice date;
posting date;
due date;
payment date;
settlement date;
journal date.

Every report must define which date drives its period filter.

Do not default all reports to created_at.

27. TIMEZONE

Reporting boundaries must use established company/tenant timezone rules.

Specify handling of:

UTC persistence;
local reporting dates;
DST where applicable;
start/end boundaries;
export timestamps.

Do not let server timezone accidentally redefine business days.

28. MONEY AND DECIMAL

All monetary analytics must preserve existing Decimal semantics.

Specify:

Decimal calculations;
rounding policy;
display precision;
aggregation precision;
currency presentation.

Do NOT convert financial calculations to binary floating point.

29. MULTI-CURRENCY

Inspect whether DevSphere currently supports:

one currency per company;
transaction currencies;
exchange rates;
reporting/base currency.

Do not invent multi-currency reporting.

If current architecture is effectively single-company-currency, state that clearly.

If multi-currency infrastructure exists, define reporting rules using actual contracts.

Never sum unrelated currencies without valid conversion semantics.

30. STATUS SEMANTICS

Reports must explicitly define which lifecycle states count.

Examples may include:

draft;
approved;
posted;
cancelled;
voided;
returned;
settled;
written-off.

Discover actual enums.

Do not invent status names.

A draft invoice must not accidentally count as recognized revenue if Accounting semantics say otherwise.

31. CANCELLATIONS / RETURNS / REVERSALS

Specify how reports handle:

cancellations;
returns;
refunds;
credit notes;
journal reversals;
installment cancellations;
settlements;
write-offs.

Preserve historical truth.

Do not simply delete reversed business activity from analytics.

32. AGING

Where aging reports are supported, define canonical buckets.

Possible examples:

Current
1–30
31–60
61–90
90+

But inspect existing domain rules first.

Specify:

reference date;
due date semantics;
partial payment behavior;
settled items;
write-offs;
timezone/date handling.

33. DRILL-DOWN

Important aggregates should support controlled drill-down where appropriate.

Example:

Executive Dashboard
→ Sales KPI
→ Sales Report
→ filtered invoice list
→ authorized invoice detail

or:

Accounts Receivable
→ Customer balance
→ open invoices
→ invoice detail.

Drill-down must preserve authorization.

A report must never become a bypass to inaccessible underlying records.

34. REPORT QUERY CONTRACT

Define a consistent query/filter contract for reports.

Evaluate common parameters such as:

date range;
branch;
status;
customer;
supplier;
item/product;
warehouse;
salesperson/owner;
account;
installment status;
grouping;
sorting;
page/page size.

Not every report must support every filter.

The report definition should explicitly declare supported filters.

35. FILTER VALIDATION

Invalid filter combinations must fail predictably.

Examples:

unauthorized branch;
unsupported grouping;
invalid date range;
impossible status;
disabled module;
inaccessible account/customer;
excessive range if limits exist.

Use existing API error-envelope conventions.

36. PAGINATION

Detailed/tabular reports capable of returning many rows must be paginated.

Do not return unbounded datasets synchronously.

Specify:

pagination model;
stable ordering;
page-size limits;
total-count semantics where useful.

Aggregation endpoints may use different contracts where justified.

37. SORTING

Sorting must be controlled.

Do not allow arbitrary database column names supplied by clients.

Expose only report-defined sortable fields.

38. SAVED REPORT VIEWS

Evaluate a tenant-scoped saved-view capability.

A saved view may persist:

report key;
filters;
grouping;
sorting;
visible columns;
date preset;
optional display preferences.

Do NOT store arbitrary SQL/query expressions.

Specify ownership and visibility.

Recommended initial model:

private/user-owned saved views first;
shared views only if existing RBAC/audit architecture makes the permission model clear.

Do not overbuild collaboration features in Epic 11.

39. EXPORTS

Specify authorized report exports.

Evaluate:

CSV;
XLSX;
PDF only where justified by repository capability/product need.

Recommendation:

Prioritize structured data exports such as CSV/XLSX for analytical tables.

Do not force every chart/dashboard into PDF generation.

Exports must preserve:

tenant scope;
branch scope;
filters;
report definition;
permissions;
entitlements.

40. EXPORT SECURITY

Exporting is a data-exfiltration boundary.

Specify:

export permission checks;
row limits;
file naming;
temporary storage behavior;
expiry if stored;
audit logging;
safe content disposition;
CSV injection/formula-injection protection;
sensitive-field restrictions.

A user who can view one report must not automatically be assumed to have unlimited bulk-export rights if repository security patterns justify a separate permission.

41. SYNCHRONOUS VS ASYNCHRONOUS EXPORT

Small exports may be synchronous.

Large exports may require asynchronous generation.

The specification must determine what Epic 11 actually needs now.

If asynchronous infrastructure does not yet exist, define an extensible contract without prematurely building a distributed job system unless justified.

Epic 12 is still upcoming.

42. REPORT FRESHNESS

Reports must communicate their freshness semantics.

Classify reports where appropriate as:

transactional/live;
near-real-time;
cached;
precomputed.

Initially prefer correctness and simplicity over premature aggregation infrastructure.

Do not introduce a data warehouse merely because this is an analytics epic.

43. PERFORMANCE STRATEGY

Epic 11 must be production-conscious.

Specification must address:

bounded date ranges where needed;
pagination;
selective projections;
aggregation queries;
indexes;
avoiding N+1;
avoiding loading ORM graphs solely to count/sum;
query plans for high-value reports;
cache suitability;
future materialization.

Do not optimize blindly.

Use PostgreSQL capabilities appropriately.

44. QUERY BUDGET / GUARDRAILS — RECOMMENDED

For expensive reports, define guardrails such as:

maximum synchronous date range;
maximum page size;
export thresholds;
maximum grouping cardinality;
timeout expectations.

Do not permit one report request to accidentally scan the entire tenant history without control.

Exact limits should be decided from repository/product context, not invented arbitrarily in this prompt.

45. INDEX REVIEW

Epic 11 specification should identify likely query/index needs.

But do not create migrations during specification.

Document candidate indexes only where existing schema inspection demonstrates a likely requirement.

Implementation planning can decide exact migrations later.

46. CACHING

Do not make caching mandatory everywhere.

Specify which results could safely be cached and what cache identity would require:

tenant;
branch scope;
report;
filters;
permissions/visibility where relevant;
entitlement state;
freshness window.

Never use a cache key that could return one tenant's data to another.

If caching is unnecessary initially, explicitly defer it.

47. SNAPSHOT / MATERIALIZED ANALYTICS

Do NOT introduce:

warehouse;
OLAP service;
Elasticsearch analytics;
ClickHouse;
materialized-view infrastructure;
event-stream analytics

unless repository evidence proves it is necessary now.

Preferred Epic 11 architecture:

PostgreSQL + curated reporting services/read queries

with clear future extension points.

48. DATA FRESHNESS VS HISTORICAL TRUTH

Historical reports must use historical transaction/accounting facts rather than current mutable master-data values where that would distort history.

Inspect existing snapshot/history behavior for:

prices;
names/descriptions;
tax values;
statuses;
exchange rates if present.

Document expected semantics.

49. RECONCILIATION

Critical financial/operational analytics should have reconciliation expectations.

Examples:

P&L values reconcile with Accounting.
Trial Balance remains balanced.
AR totals reconcile with authoritative receivable balances.
Inventory valuation reconciles with Inventory's authoritative valuation logic.
Installment financial totals reconcile appropriately with Accounting postings.

Define testable invariants.

50. REPORT AUDITABILITY

Reports themselves are reads, but sensitive actions around them may require audit events.

Evaluate audit requirements for:

exports;
shared saved views;
high-sensitivity financial reports;
generated files.

Do not flood the audit log with every dashboard refresh unless existing architecture requires it.

51. PRIVACY / SENSITIVE DATA

Reports should expose only fields required for the analytical purpose.

Do not automatically expose:

passwords/secrets;
authentication metadata;
internal security tokens;
unnecessary PII;
platform-support internals.

Respect existing privacy/security boundaries.

52. PLATFORM ADMIN BOUNDARY

Platform Administration must not gain unrestricted tenant business reporting merely because Epic 11 exists.

Inspect existing Platform Admin and Support Access rules.

Preserve the established distinction between:

platform operational administration;
authorized support access;
tenant business data.

Reports must not create a shortcut around support-access controls.

53. API DESIGN

Use existing API conventions.

Specify appropriate route families without implementing them.

Prefer stable report identities.

Avoid hundreds of inconsistent one-off endpoints if a curated reporting contract can remain clear and type-safe.

At the same time:

Do NOT build a generic arbitrary query DSL.

Find the appropriate middle ground based on repository architecture.

54. RESPONSE ENVELOPES

Reuse established response-envelope conventions.

Define report responses with clear structures for:

metadata;
filters applied;
period;
measures;
dimensions;
rows/series;
pagination;
comparison;
freshness;
drill-down references where useful.

Do not invent incompatible envelope patterns without justification.

55. FRONTEND INFORMATION ARCHITECTURE

Specify the user-facing reporting experience.

Evaluate navigation such as:

Reports

Overview / Executive
Sales
Purchases
Inventory
Finance
CRM
Installments

Exact navigation must reflect enabled modules and permissions.

Do not expose empty sections for disabled modules.

56. DASHBOARD UX

Dashboard UX should include:

clear KPI cards;
period selector;
branch selector where authorized;
comparisons;
trends;
loading states;
empty states;
error states;
permission-denied behavior;
module-disabled behavior.

Avoid decorative charts without decision-making value.

57. TABLE UX

Analytical tables should specify:

filters;
sorting;
pagination;
totals/subtotals where appropriate;
column formatting;
money formatting;
date formatting;
export;
drill-down.

Do not require client-side loading of entire datasets.

58. CHARTS

Use charts only where they communicate meaningful patterns.

Evaluate:

line charts for trends;
bar charts for comparisons;
stacked charts for composition where justified;
donut/pie only when genuinely useful.

Charts must be driven by the same trusted metric definitions as tabular reports.

No separate frontend KPI calculations that can drift from backend semantics.

59. ACCESSIBILITY / RESPONSIVENESS

Reporting UI must follow existing frontend quality expectations.

Specify:

keyboard accessibility;
semantic labels;
readable tables;
responsive layouts;
accessible chart alternatives or summaries;
loading/error feedback.

60. EMPTY / PARTIAL DATA

Reports must behave correctly for:

new companies;
no transactions;
one branch;
disabled modules;
partially configured Accounting;
no CRM data;
no installment contracts.

Zero data is not necessarily an error.

61. REPORT AVAILABILITY / READINESS

A report may require prerequisites.

For example, a financial statement may depend on Accounting configuration.

Specify how unavailable/not-configured reports are represented.

Do not silently return misleading zero values when prerequisites are absent.

62. OBSERVABILITY

Specify lightweight observability for reporting:

report key;
execution duration;
success/failure;
row/result size where appropriate;
slow-query identification;
export execution.

Never log sensitive report contents unnecessarily.

63. SECURITY TESTING

Specification must require tests for:

tenant isolation;
cross-tenant ID tampering;
branch restrictions;
RBAC;
entitlement denial;
disabled modules;
export authorization;
saved-view ownership;
drill-down authorization;
support/platform boundaries;
cache isolation if caching exists.

These are first-class Epic 11 requirements.

64. REPORT CORRECTNESS TESTING

Every critical report needs deterministic correctness tests.

Use fixtures with known expected totals.

Test:

included records;
excluded records;
statuses;
date boundaries;
branch boundaries;
cancellations;
returns;
partial payments;
comparisons;
Decimal precision;
empty states.

65. FINANCIAL INVARIANT TESTS

Require strong invariant tests for financial reporting.

Examples where applicable:

Trial Balance debits = credits.
Balance Sheet equation holds according to existing Accounting semantics.
financial report totals reconcile with ledger data.
AR/AP totals reconcile with authoritative source.
reversal handling is correct.

Use actual Accounting domain rules.

66. REAL POSTGRESQL TESTS

Reporting SQL must be validated against real PostgreSQL.

Do not rely exclusively on mocks or SQLite-like substitutes.

This is particularly important for:

aggregates;
joins;
date grouping;
Decimal/Numeric;
PostgreSQL-specific expressions;
pagination;
indexes/query behavior;
tenant isolation.

Use the now-established real PostgreSQL test environment.

67. PERFORMANCE TESTING

Define targeted performance expectations for representative report workloads.

Do not introduce fragile universal wall-clock assertions that fail merely because a shared CI runner is under load.

Prefer robust performance evidence such as:

query-count expectations;
bounded query plans;
dataset-size scenarios;
gross regression thresholds where stable;
isolated slow/performance tests if necessary.

This explicitly incorporates the lesson from the Pre-Epic-11 regression effort.

68. TYPE SAFETY

Epic 11 must preserve the newly established repository invariant:

mypy . = 0

Requirements:

fully typed first-party code;
typed report contracts;
typed filters;
typed metric definitions;
typed repositories/services;
no Any as an escape hatch;
no broad MyPy suppressions;
no weakening CI.

Tests are part of the typing gate.

69. FUTURE AI READINESS — IMPORTANT

After Epic 12, DevSphere ERP will receive a dedicated AI Layer.

Epic 11 should deliberately create safe, reusable analytical contracts that future AI employees/agents can consume.

Potential future questions include:

"What were our sales this month?"
"Which products are slow moving?"
"How much do customers owe us?"
"Which installment contracts are overdue?"
"Why did revenue change compared with last month?"
"Show our highest-value customers."

The future AI layer should preferably consume:

trusted reporting services / report definitions

rather than unrestricted raw SQL.

Therefore Epic 11 should expose stable, typed, permission-aware analytical contracts.

70. AI MUST INHERIT SECURITY

Future AI consumption must be capable of inheriting:

tenant context;
branch scope;
RBAC;
entitlements;
metric semantics;
report filters.

Do not design a hidden "AI bypass" into Epic 11.

71. NO AI IMPLEMENTATION IN EPIC 11

Epic 11 must NOT implement:

OpenClaw;
LLM APIs;
AI agents;
AI employees;
embeddings;
vector databases;
RAG;
natural-language-to-SQL;
AI chat;
AI credit billing;
token accounting.

Only make the reporting layer structurally ready for later controlled AI consumption.

72. NO NATURAL-LANGUAGE-TO-SQL

Explicitly record as out of scope:

NL-to-SQL is NOT part of Epic 11.

Future AI should initially interact with curated reporting capabilities rather than arbitrary SQL generation.

73. API/REPORT VERSION STABILITY

Because Epic 11 may later serve:

frontend dashboards;
exports;
AI tools;
external integrations;

define stable report keys and contracts.

Do not couple report identity solely to UI labels.

Where appropriate, design report contracts so future additive evolution does not unnecessarily break consumers.

Do not over-engineer versioning prematurely.

74. RECOMMENDED REPORT EXECUTION MODEL

Evaluate a conceptual flow similar to:

Authenticated Request
→ Tenant Context
→ Branch Scope
→ RBAC
→ Entitlement
→ Report Definition
→ Filter Validation
→ Reporting Service / Read Repository
→ Authoritative Domain Data
→ Typed Result
→ API Response / Export

Adapt this to actual repository architecture.

Do not introduce layers merely because they appear in this prompt.

75. RECOMMENDED REPORT DEFINITION MODEL

Consider whether a typed report definition should declare concepts such as:

key
domain
permission
entitlement
supported filters
supported dimensions
supported measures
sortable fields
exportability
drill-down capability
freshness

The goal is consistency and future extensibility.

It must not become a dynamic SQL DSL.

76. MVP VS FUTURE CAPABILITY

The specification must clearly distinguish:

Epic 11 Required

What must be implemented now.

Deferred / Future

Examples that may be deferred:

data warehouse;
OLAP engine;
ClickHouse;
distributed analytics;
predictive forecasting;
scheduled email reports;
report subscriptions;
advanced custom report builder;
arbitrary pivot builder;
AI-generated reports;
NL-to-SQL;
anomaly detection;
forecasting models;
cross-tenant platform analytics.

Do not let future ideas inflate Epic 11 unnecessarily.

77. CROSS-TENANT PLATFORM ANALYTICS

Tenant business reporting and SaaS platform analytics are different concerns.

Do NOT automatically add platform-wide aggregation across customers.

If future platform analytics are useful for DevSphere SaaS administration, record them separately as future scope with strict privacy boundaries.

Epic 11 is primarily tenant ERP reporting.

78. ACCEPTANCE CRITERIA STYLE

Requirements must be objectively testable.

Avoid vague statements like:

"Reports should be fast."

Prefer measurable/observable requirements such as:

result pagination is bounded;
unsupported filters are rejected;
unauthorized branch requests are denied;
totals reconcile to authoritative source;
no cross-tenant records appear;
export contains the same authorized filter scope;
mypy . remains zero.

Do not invent unrealistic millisecond SLAs without evidence.

79. REQUIRED SPECIFICATION STRUCTURE

Create or update:

specs/011-reports-analytics/spec.md

Use repository conventions if they differ, but the final specification must cover at least:

Epic title/status
Executive summary
Problem statement
Goals
Non-goals
Architectural context
Existing capabilities discovered
Reuse vs new work
Actors/personas
User stories
Functional requirements
Reporting architecture
Report/metric semantic model
Report catalog
Source-of-truth matrix
Executive dashboard
Sales analytics
Purchase analytics
Inventory analytics
Accounting/financial reporting
CRM analytics
Installment analytics
Cross-module analytics
Filters
Date/time semantics
comparison semantics
money/currency semantics
branch semantics
status/reversal semantics
drill-down
pagination/sorting
saved views
exports
performance/query guardrails
freshness/caching strategy
RBAC
entitlements
tenant isolation
privacy/security
audit/observability
API requirements
frontend requirements
accessibility/responsiveness
test strategy
real-Postgres validation
financial reconciliation/invariants
type-safety/CI requirements
AI-readiness
edge cases
assumptions/dependencies
risks
deferred/future scope
acceptance criteria
traceability/readiness matrix.

Merge sections where repository conventions make that clearer, but do not omit the substance.

80. REPORT CATALOG — REQUIRED DELIVERABLE

The final specification must contain a concrete report catalog.

For every proposed report record at least:

report name;
stable key;
domain/module;
business purpose;
authoritative source;
required permission;
entitlement dependency;
branch behavior;
main filters;
main measures;
drill-down;
export support;
whether required now or deferred.

This catalog will later drive planning and tasks.

Do not leave the catalog as "TBD".

81. KPI / METRIC CATALOG — REQUIRED DELIVERABLE

Create a metric catalog for important KPIs.

For each key metric include:

metric name;
stable semantic identifier where useful;
definition;
authoritative domain;
inclusion/exclusion semantics;
date basis;
aggregation;
money/currency semantics;
comparison behavior.

Focus on important reusable metrics rather than cataloguing every database field.

82. PERMISSION MATRIX — REQUIRED DELIVERABLE

Provide a proposed permission/report matrix grounded in existing RBAC conventions.

Show which actor/permission category can:

view report;
drill down;
export;
save view;
share view if sharing is included.

Do not assign permissions to roles merely by assumption if roles are configurable.

Prefer capability/permission mapping.

83. ENTITLEMENT MATRIX — REQUIRED DELIVERABLE

Document which report families depend on which existing modules/features.

Reports must default-deny where required by existing entitlement architecture.

84. SECURITY MATRIX — REQUIRED DELIVERABLE

For major report capabilities, identify expected enforcement for:

tenant;
branch;
permission;
entitlement;
underlying record access;
export.

This must be testable later.

85. TRACEABILITY

Assign stable requirement identifiers using repository conventions.

If no convention exists, use clear identifiers such as:

FR-11-001
SEC-11-001
PERF-11-001
DATA-11-001
AI-11-001

Avoid duplicate or unstable IDs.

Later plan/tasks must be traceable back to these requirements.

86. EDGE CASES — REQUIRED

Explicitly specify behavior for cases including:

company with no data;
user with no authorized branches;
user with one authorized branch;
module disabled;
entitlement removed;
unauthorized saved view;
deleted/inactive customer or supplier;
cancelled transactions;
reversed journals;
partial payments;
partially paid installments;
written-off installments;
date range crossing year boundaries;
timezone boundary;
zero comparison denominator;
very large dataset;
empty export;
report prerequisite not configured.

Add repository-specific cases discovered during inspection.

87. SPECIFICATION QUESTIONS

If repository discovery reveals genuine unresolved product decisions, do not silently choose high-impact behavior.

Classify them as:

resolved from repository;
recommended decision;
requires owner confirmation.

However, use professional judgment to resolve low-risk implementation details where the architecture already implies the answer.

The final spec should minimize unnecessary open questions.

88. MY RECOMMENDED PRODUCT BOUNDARY FOR EPIC 11

Unless repository discovery strongly contradicts it, prefer this boundary:

Build now

centralized reporting read architecture;
curated report catalog;
authoritative KPI definitions;
executive dashboard;
core Sales reports;
core Purchase reports;
core Inventory reports;
core Accounting reports;
core CRM reports;
core Installment reports;
secure filtering;
branch/company scoping;
comparison periods;
drill-down;
pagination;
structured exports;
saved private report views if architecture supports them cleanly;
audit for sensitive exports;
performance guardrails;
real-Postgres correctness tests;
stable contracts suitable for future AI consumption.

Do not build now

arbitrary custom report builder;
arbitrary SQL;
BI warehouse;
OLAP infrastructure;
ClickHouse;
scheduled report emails;
complex shared-report collaboration;
predictive analytics;
anomaly detection;
AI-generated reports;
AI agents;
OpenClaw;
NL-to-SQL;
embeddings/vector DB;
AI usage billing.

This keeps Epic 11 powerful without turning it into an entire BI platform.

89. IMPORTANT ARCHITECTURAL RECOMMENDATION — ONE METRIC, ONE MEANING

Treat this as a core Epic 11 principle:

One Metric → One Authoritative Definition → Many Consumers

For example:

The executive dashboard, Sales report, export, and future AI query should not separately calculate "Net Sales".

They should consume the same authoritative semantic definition or service contract.

This is essential to prevent reporting drift.

90. IMPORTANT ARCHITECTURAL RECOMMENDATION — REPORTING IS READ-ONLY

Epic 11 reporting execution should remain read-only with respect to business domains.

Saved views/export-job metadata may legitimately mutate Epic 11-owned state if specified.

But report execution itself must not mutate operational business records.

Do not introduce hidden write-side effects merely to generate analytics.

91. IMPORTANT ARCHITECTURAL RECOMMENDATION — FINANCIAL VS OPERATIONAL KPIs

The specification must distinguish:

Operational metric

Example:
Sales orders created.

from:

Financial metric

Example:
recognized revenue.

They are not automatically equivalent.

Similarly distinguish:

invoice amount vs recognized revenue;
installment scheduled amount vs receivable/accounting balance;
purchase order amount vs recognized payable;
stock movement vs accounting inventory balance.

This distinction is essential for ERP-grade reporting.

92. IMPORTANT ARCHITECTURAL RECOMMENDATION — EXPLAINABILITY

For important KPIs, users should be able to understand where the number came from.

Where practical, define:

KPI
→ report
→ filtered rows
→ source transaction

This will improve:

trust;
reconciliation;
support;
auditing;
future AI explanations.

Do not make dashboards black boxes.

93. IMPORTANT ARCHITECTURAL RECOMMENDATION — FUTURE AI TOOL SURFACE

Without implementing AI, structure report contracts so a later AI gateway can expose curated tools conceptually like:

get_sales_summary
get_inventory_status
get_receivables_summary
get_installment_delinquency
compare_reporting_periods

These are conceptual examples only.

Do not implement these AI tools now.

The point is to ensure Epic 11 does not produce UI-only logic that future AI cannot safely reuse.

94. SPEC QUALITY GATE

Before finalizing spec.md, audit it for:

contradiction with repository;
duplicate business logic;
ambiguous KPI definitions;
missing tenant scope;
missing branch scope;
missing RBAC;
missing entitlements;
incorrect Accounting authority;
unbounded query behavior;
insecure exports;
unsupported report assumptions;
missing real-Postgres tests;
vague acceptance criteria;
accidental AI implementation;
premature infrastructure.

Resolve issues before declaring the spec complete.

95. SPEC CHECKLIST

Create/update the repository's normal specification quality checklist if that workflow exists.

If the project convention uses something similar to:

specs/011-reports-analytics/checklists/requirements.md

create/update it accordingly.

Validate the final specification against that checklist.

Do not invent a parallel workflow if the repository already defines one.

96. NO IMPLEMENTATION

During this task, do NOT:

create migrations;
create SQLAlchemy models;
create repositories;
create services;
create routes;
create frontend pages;
create charts;
create report queries;
modify production domain code;
implement exports;
implement saved views;
add dependencies;
write Epic 11 implementation tests;
create plan.md;
create tasks.md.

This task ends with the specification.

97. FINAL RESPONSE FORMAT

After completing repository discovery and the final specification, return a concise but evidence-based report containing:

A. Discovery Summary

What existing capabilities were found and will be reused.

B. Specification Files

Files created/modified.

C. Report Catalog Summary

Number of required report families/reports proposed.

D. Key Architectural Decisions

Especially:

reporting read layer;
semantic metrics;
source-of-truth;
Accounting authority;
tenant/branch/RBAC/entitlement enforcement;
export security;
AI readiness.

E. Reuse vs New Work

Clearly distinguish existing contracts from Epic 11 additions.

F. Security Summary

Tenant, branch, RBAC, entitlement, export and platform/support boundaries.

G. Performance Strategy

High-level query/guardrail decisions.

H. AI-Readiness Boundary

What was made future-ready and what AI work remains explicitly out of scope.

I. Open Decisions

List only genuine owner decisions still unresolved.

If none:

None.

J. Specification Validation

Checklist/quality-gate result.

K. Git Status

Report branch and working-tree state.

Do not commit or push unless the existing repository workflow explicitly requires specification-stage commits and that is already established.

L. Verdict

Return exactly one:

EPIC 11 SPECIFICATION READY FOR REVIEW

or

EPIC 11 SPECIFICATION BLOCKED

If blocked, explain the blocker.

98. STOP CONDITION

After spec.md and its specification checklist are complete:

STOP.

Do NOT proceed automatically to:

plan.md;
tasks.md;
implementation;
Epic 12;
AI Layer.

Wait for explicit review/approval of the Epic 11 specification.

FINAL INSTRUCTION

Treat Epic 11 as the foundation of DevSphere ERP's trusted analytical intelligence.

Do not build a collection of disconnected report screens.

Build the specification for a:

secure, tenant-aware, branch-aware, permission-aware, entitlement-aware, financially authoritative, explainable, typed and reusable Reporting & Analytics Read Layer

where:

one metric has one meaning,

financial truth comes from the authoritative financial domain,

every number can be traced to trusted business data,

and future AI can safely consume the same curated analytical contracts without bypassing ERP security or generating arbitrary SQL.

Perform repository discovery first.

Then produce the final spec.md.

Then validate it.

Then STOP.

## Response snapshot

Performed deep repository discovery via 6 parallel research agents covering: (1) core/shared infra — RBAC dot-notation permission convention with inline `user_has_<module>_permission()` checks, two-tier Plan/toggle/override entitlement model (`PlatformEntitlementService`), `get_current_company_member` tenant-context dependency, confirmed absence of any `Branch` entity (only reserved nullable `branch_id` columns on a few models), `StandardResponse`/`PaginatedResponse`/`ErrorResponse` envelope, existing export infra (openpyxl/reportlab), per-module audit logs (no unified table), `Decimal`/`NUMERIC` conventions (Accounting/Installments `NUMERIC(20,6)` vs Sales `NUMERIC(15,2)`), UTC storage + per-company `default_timezone`, real-Postgres test fixture chain, and the blocking `mypy .` CI gate; (2) Sales + Purchase — confirmed real status enums, confirmed Sales has no branch_id/AR balance field, confirmed Purchase has no Bill/AP entity at all (manual Accounting entry only), and confirmed both already have full report/KPI service layers (25 Sales report types + 12 KPIs; 14 Purchase reports + 11 KPIs); (3) Inventory — confirmed WAC valuation owned by Inventory itself (Accounting's inventory-GL handler is a documented ADR-0004 stub), confirmed dead-stock/velocity/aging reports already exist, confirmed immutable point-in-time `StockMovement.unit_cost`; (4) Accounting — confirmed it already implements Trial Balance, GL, P&L, Balance Sheet, Cash Flow, AR/AP aging+statements, bank/cash books, tax reports, cost-center/project P&L, and a 15-KPI dashboard, all exportable; confirmed `PostingEngine` as sole GL writer and the aging-bucket convention; (5) CRM + Installments — confirmed real status enums, confirmed both already have their own read-only reporting services (`CrmReportingService`, `InstallmentReportingService`, the latter explicitly built for Epic 11 to consume per FR-INST-362), confirmed Installments' `AccountingIntegrationGateway` read-through (never-cache) pattern; (6) Platform Admin + frontend — confirmed Platform Admin has zero tenant-business-data reporting capability by design (BR-9A-021), confirmed no charting library, no shared `DataTable`, no shared money/date formatting utilities, and no entitlement-driven nav exist in the frontend today.

Read the project constitution (50 sections) and the most recent precedent spec (`specs/010-installments/spec.md`, 35 sections, `FR-INST-XXX`/`BR-INST-XXX` module-prefixed requirement IDs, User Stories/Acceptance Scenarios/Constitution-Traceability structure) to determine the actual repository specification convention, and followed that convention (rather than the generic `spec-template.md` or the prompt's own `FR-11-XXX` fallback) since a real convention already exists.

Wrote `specs/011-reports-analytics/spec.md` (54 sections, 821 lines, 143 unique `FR-RPT-XXX` requirements, zero `[NEEDS CLARIFICATION]` markers) establishing: Epic 11 as a thin, curated cross-module read/registry/dashboard/export/saved-view layer wrapping ~90 already-implemented per-module reports/KPIs rather than rebuilding them; a corrected Source-of-Truth Matrix (notably: Inventory owns valuation, not Accounting; Accounting owns AR/AP balances, not Sales/Purchase); a Report Catalog (~45 rows, Now vs Deferred, no TBDs); a KPI/Metric Catalog (16 metrics, each with one authoritative definition, resolving a discovered Sales-vs-Accounting "margin" naming conflict into two distinctly-named metrics); Permission/Entitlement/Security matrices; an explicit, load-bearing finding that no `Branch` entity or branch-ACL exists anywhere, so all branch filtering is specified as a plain data filter, never an authorization boundary; money/currency, period/timezone, comparison, and status/reversal semantics grounded in actual discovered enums and column types; saved private report views (genuinely new); synchronous CSV/XLSX/PDF export with a recommended 50,000-row guardrail; RBAC/entitlement/tenant-isolation/Platform-Admin-boundary requirements; a real-Postgres + financial-invariant test strategy; AI-readiness contracts with explicit NG/out-of-scope statements against implementing any AI now; and a Constitution Compliance/Traceability table. Also wrote `specs/011-reports-analytics/checklists/requirements.md` validating the spec against content-quality, requirement-completeness, feature-readiness, and Epic-11-specific deliverable-coverage criteria — all items pass. Created feature branch `011-reports-analytics` via `.specify/scripts/bash/create-new-feature.sh`. No code, migrations, models, services, routes, frontend pages, `plan.md`, or `tasks.md` were created, per the specification-only constraint. Verdict: EPIC 11 SPECIFICATION READY FOR REVIEW.

## Outcome

- ✅ Impact: Produced the complete, implementation-ready Epic 11 specification and its quality checklist; established feature branch `011-reports-analytics`; no production code touched.
- 🧪 Tests: None run/added (specification-only phase; §48 of spec.md defines the future test strategy).
- 📁 Files: `specs/011-reports-analytics/spec.md` (new, 821 lines), `specs/011-reports-analytics/checklists/requirements.md` (new).
- 🔁 Next prompts: Await explicit user review/approval before `/sp.plan`; open decisions in spec.md §53 (export row-count guardrail, Sales/Purchase/Inventory "always-on" entitlement labeling, branch-performance-report activation timing) may be revisited during planning.
- 🧠 Reflection: The single highest-leverage discovery was that every completed module already owns a full report/KPI service layer — this reframed Epic 11 from "build reports" to "wrap, register, and secure existing reports," which is now encoded as a hard architectural constraint (FR-RPT-003/081) rather than left implicit.

## Evaluation notes (flywheel)

- Failure modes observed: None blocking; the checklist required no revision iterations.
- Graders run and results (PASS/FAIL): Self-validated against `specs/011-reports-analytics/checklists/requirements.md` — all items PASS.
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
