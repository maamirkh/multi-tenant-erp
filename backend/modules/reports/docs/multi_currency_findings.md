# Multi-currency in Reports (FR-RPT-152)

**Status (2026-09-30): resolved with currency-grouped aggregates.** The
user chose option (a) on 2026-09-30 (tasks.md Phase 12, T297–T307).
Reports never sums across currency codes and never converts between them.
Conversion to base currency (option b) is out of scope.

## Findings (T273, 2026-09-29)

The first check, against the Phase 10 code, found this:

| Module | Where currency lives | Conversion | Aggregates summed across currencies? |
|---|---|---|---|
| Accounting | Base currency; per-entry `exchange_rate`, `amount_foreign`/`amount_base` | Yes (`CurrencyService`) | No — Reports reads base-currency figures |
| Sales | `currency_code` per invoice / order / quotation | No | **Yes** — summary, trend, by_customer, top_customers, by_product and all KPIs |
| Purchase | `currency_code` per PO / cost entry | No | **Yes** — by_supplier; KPI 06 and 07 |
| Inventory | Nullable `currency_code` per stock position | No | **Yes** — valuation `grand_total_value` |
| CRM | `currency_code` per opportunity | No | **Yes** — every pipeline value and the dashboard |
| Installments | One `currency_code` per contract | No | **Yes, in Reports** — the report rows had no currency field, and the Dashboard and Customer 360 summed them |

The T273 note said Installments rows "carry `currency_code`". That was
wrong: the aging, due/overdue and default/write-off rows did not. This is
corrected by T303.

## Resolution

Each source module gained an **additive** seam. Its default keeps today's
output, so each module's own screens are unchanged:

| Module | Seam |
|---|---|
| Sales | `ReportParams.group_by_currency`; `KPIService.currencies_in_period()`, `get_money_kpis()` and `MONEY_KPI_IDS` |
| Purchase | `purchase_by_supplier(group_by_currency=)`, and the same on `count_purchase_by_supplier`; `open_commitments_value_by_currency()`, `total_purchase_value_by_currency()` and `MONEY_KPI_KEYS` |
| Inventory | `inventory_valuation()` returns `grand_totals_by_currency` |
| CRM | Optional `currency_code` on every opportunity aggregate; `currency_codes()`, `get_pipeline_values()` |
| Installments | Report rows carry the contract's `currency_code` |

What Reports returns now:

| Report / figure | Shape |
|---|---|
| Sales list aggregates, `purchase.by_supplier` | One row per group and currency, with `currency_code` |
| `sales.kpis` | Count, rate and time KPIs once; money KPIs in `by_currency` blocks (unit = currency) |
| `purchase.kpis` | Non-money KPIs as before; KPI 06/07 replaced by `by_currency` |
| `inventory.valuation` | `grand_totals_by_currency`; `grand_total_value` only when one currency is present |
| `crm.pipeline` | Win rate and sales cycle overall; CRM's pipeline report per currency in `by_currency` |
| `crm.dashboard` | Counts and rates as before; pipeline values in `by_currency` |
| Dashboard: net sales, gross sales, purchase spend, inventory, CRM pipeline, installment exposure | `*by_currency` lists, each with its own comparison |
| Customer 360: sales revenue, CRM open value, installments principal | `*_by_currency` lists |
| Accounting (statements, AR/AP, cash, margin) | Unchanged — base currency |

**Single-value rule.** Every legacy single-value field follows one rule:
- one currency present → that currency's figure;
- no data at all → a real zero;
- several currencies → `null`.

It is never a sum across currencies.

**UI.** Tables show a Currency column and format each row's amounts in
that row's currency. Widgets and Customer 360 figures show each currency
side by side (for example `$100.00 · PKR 5,000`).

Tests: `tests/integration/repositories/sales/test_reports_group_by_currency.py`,
`tests/unit/modules/reports/test_sales_equivalence.py`,
`tests/integration/api/v1/reports/test_multi_currency.py`, and the frontend
`dashboard.test.tsx` / `customer-360.test.tsx`.
