# Multi-currency verification (Epic 11, Phase 10 — T273, Assumption A5)

Verified 2026-09-29 against the code on branch `011-reports-analytics`.
The question A5 left open: do Sales / Purchase / Inventory / CRM carry a
genuine multi-currency model, and does Reports honour FR-RPT-152
("every monetary figure carries its currency code; never sum across
currency codes without an Accounting-sourced exchange-rate conversion")?

## Per-module currency model

| Module | Where currency lives | Conversion to base currency | Source aggregations group by currency? |
|---|---|---|---|
| Accounting | `base_currency_code` on `AccountingConfiguration`; per-entry `exchange_rate`, `amount_foreign`/`amount_base` | Yes — `CurrencyService` (CLOSING for BS, AVERAGE for P&L) | Reports read base-currency figures (`amount_base`) — **compliant** |
| Installments | One immutable `currency_code` per contract | No | Per-contract rows carry `currency_code` — compliant per row |
| Sales | `currency_code` per invoice / order / quotation / customer | **No** (no exchange-rate field used) | **No** — `ReportService` sums `total_amount` across invoices regardless of currency |
| Purchase | `currency_code` per PO / cost entry; `purchase_orders.exchange_rate` exists but is nullable and documented "reserved" (unused) | **No** | Per-PO/per-line rows carry `currency_code`; **`purchase_by_supplier` and KPIs sum across currencies** |
| Inventory | Nullable `currency_code` per stock position / movement / transfer | **No** | **Valuation `grand_total_value` sums positions across currencies** |
| CRM | `currency_code` per opportunity | **No** | **Pipeline value sums opportunities across currencies** |

## Epic 11 response shapes vs. FR-RPT-152

Reports never recomputes a domain metric (one metric → one authoritative
definition), so each of these passes the source module's own
cross-currency sum through unchanged:

| Report / figure | Carries currency code? | Sums across currencies? |
|---|---|---|
| `sales.summary`, `sales.trend`, `sales.by_customer`, `sales.top_customers`, `sales.by_product`, `sales.kpis` | No | Yes (source `ReportService`/`KPIService`) |
| `sales.quotation_pipeline` (per-quotation rows) | No | No (per row) |
| `purchase.summary`, `open_commitments`, `pending_deliveries` | **Yes** (`currency_code` per row) | No |
| `purchase.by_supplier`, `purchase.kpis` | No | Yes |
| `inventory.valuation` | One nullable top-level `currency_code` | Yes (positions of different currencies) |
| `crm.pipeline`, `crm.dashboard` | No | Yes |
| Dashboard: net sales, gross sales, purchase spend, inventory value, CRM pipeline | No | Yes (inherits the above) |
| Dashboard: AR, AP, cash position, gross profit margin | No code in payload | No — Accounting base currency |
| Customer 360: sales revenue, CRM open value | No | Yes (inherits the above) |
| Customer 360: AR balance | No code in payload | No — Accounting base currency |
| Accounting statements / aging / GL / bank-cash | Base currency | No — compliant |
| Installments list reports | Yes (per-contract `currency_code` in row) | No |

## Conclusion

- **Single-currency tenants** (every record in the tenant's base currency —
  the only case the domain modules' own report screens handle today):
  every figure is correct; the omission of a currency code is cosmetic.
- **Multi-currency tenants**: FR-RPT-152 is **not met** for the Sales,
  Purchase-aggregate, Inventory-valuation and CRM figures above and for
  the dashboard/Customer 360 figures derived from them — they would sum
  different currencies as if they were one. This is inherited from each
  domain's existing (pre-Epic-11) aggregation, which Reports passes
  through by design; plan.md §20's statement that "response schemas group
  amounts by currency rather than pre-summing them" does not match the
  implemented schemas.
- Fixing it needs either currency-grouped aggregations in the four source
  modules (their own report services) or conversion via Accounting's
  `CurrencyService` — a cross-module change outside Phase 10's scope and
  a decision for the product owner (tracked as an open finding in the
  Phase 10 report / tasks.md T273).
