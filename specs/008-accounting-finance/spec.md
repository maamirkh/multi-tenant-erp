# Epic 8 — Accounting & Finance: Official Business Specification

**Document Type**: Official Enterprise Business Specification (SSOT)
**Epic Number**: 008
**Feature Branch**: `008-accounting-finance`
**Version**: 1.0
**Status**: Draft — Pending Approval
**Created**: 2026-08-05
**Compatible With**: Epic 0 (Constitution), Epic 1 (Foundation), Epic 2 (Authentication), Epic 3 (Companies), Epic 4 (Users & Roles), Epic 5 (Inventory Management), Epic 6 (Purchase Management), Epic 7 (Sales Management)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Epic Overview](#2-epic-overview)
3. [Business Vision](#3-business-vision)
4. [Business Goals](#4-business-goals)
5. [Business Scope](#5-business-scope)
6. [Out of Scope](#6-out-of-scope)
7. [Accounting Philosophy](#7-accounting-philosophy)
8. [Domain Boundaries](#8-domain-boundaries)
9. [Bounded Context](#9-bounded-context)
10. [Stakeholders](#10-stakeholders)
11. [User Personas](#11-user-personas)
12. [Business Capabilities](#12-business-capabilities)
13. [Chart of Accounts](#13-chart-of-accounts)
14. [General Ledger](#14-general-ledger)
15. [Journal Entries](#15-journal-entries)
16. [Fiscal Calendar](#16-fiscal-calendar)
17. [Financial Statements](#17-financial-statements)
18. [Accounts Receivable](#18-accounts-receivable)
19. [Accounts Payable](#19-accounts-payable)
20. [Banking](#20-banking)
21. [Cash Management](#21-cash-management)
22. [Payments](#22-payments)
23. [Tax Management](#23-tax-management)
24. [Multi-Currency](#24-multi-currency)
25. [Cost Accounting](#25-cost-accounting)
26. [Financial Controls](#26-financial-controls)
27. [Business Workflows](#27-business-workflows)
28. [Functional Requirements](#28-functional-requirements)
29. [Non-Functional Requirements](#29-non-functional-requirements)
30. [Business Rules](#30-business-rules)
31. [Business Invariants](#31-business-invariants)
32. [Validation Rules](#32-validation-rules)
33. [Permission Matrix](#33-permission-matrix)
34. [Feature Matrix](#34-feature-matrix)
35. [Financial Governance](#35-financial-governance)
36. [Conceptual Domain Model](#36-conceptual-domain-model)
37. [Aggregate Roots](#37-aggregate-roots)
38. [Domain Events](#38-domain-events)
39. [Reporting Requirements](#39-reporting-requirements)
40. [KPI Requirements](#40-kpi-requirements)
41. [Search Requirements](#41-search-requirements)
42. [Import and Export](#42-import-and-export)
43. [Notifications](#43-notifications)
44. [Audit Requirements](#44-audit-requirements)
45. [Security Requirements](#45-security-requirements)
46. [Compliance Requirements](#46-compliance-requirements)
47. [Data Retention](#47-data-retention)
48. [Disaster Recovery](#48-disaster-recovery)
49. [Performance Targets](#49-performance-targets)
50. [Scalability Targets](#50-scalability-targets)
51. [Cross-Module Dependencies](#51-cross-module-dependencies)
52. [Cross-Module Contracts](#52-cross-module-contracts)
53. [Integration Readiness](#53-integration-readiness)
54. [AI Readiness](#54-ai-readiness)
55. [Analytics Readiness](#55-analytics-readiness)
56. [Multi-Tenant SaaS](#56-multi-tenant-saas)
57. [Extensibility Strategy](#57-extensibility-strategy)
58. [Versioning Strategy](#58-versioning-strategy)
59. [Risks](#59-risks)
60. [Assumptions](#60-assumptions)
61. [Constraints](#61-constraints)
62. [Success Metrics](#62-success-metrics)
63. [Glossary](#63-glossary)
64. [Acceptance Criteria](#64-acceptance-criteria)
65. [Epic Completion Criteria](#65-epic-completion-criteria)
66. [Future Roadmap](#66-future-roadmap)

---

## 1. Executive Summary

Epic 8 delivers the Accounting & Finance domain of DevSphere ERP — the financial backbone of the entire platform. It transforms raw business transactions from Sales (Epic 7), Purchase (Epic 6), and Inventory (Epic 5) into a complete, auditable, double-entry general ledger that produces internationally-recognized financial statements.

The Accounting domain provides the authoritative financial record for every company managed within DevSphere ERP. It enforces double-entry accounting principles, maintains immutable audit trails, supports multi-currency operations, manages tax obligations across jurisdictions, and delivers the financial intelligence required by business owners, accountants, auditors, and executives.

Designed to match the financial depth of SAP Business One, Microsoft Dynamics 365 Business Central, and Oracle NetSuite, this specification defines an industry-neutral financial engine capable of serving retail, wholesale, construction, travel, medical, manufacturing, and service businesses equally.

The Accounting module is the final arbiter of all financial truth within DevSphere ERP.

---

## 2. Epic Overview

| Attribute | Value |
|-----------|-------|
| Epic Number | 008 |
| Epic Name | Accounting & Finance |
| Domain | Finance |
| Priority | P1 — Core ERP |
| Depends On | Epics 0, 1, 2, 3, 4, 5, 6, 7 |
| Enables | Epics 9, 10, 11, 12 |
| Accounting Standard | Double-Entry (GAAP/IFRS compatible) |
| Multi-Tenant | Yes — strict financial isolation |
| Multi-Currency | Yes |
| Multi-Branch | Readiness only (full implementation in future) |
| AI Ready | Yes — conceptual hooks defined |

---

## 3. Business Vision

Accounting & Finance in DevSphere ERP must become the financial nervous system of every business that adopts the platform. The vision is to:

- Provide every business with a complete, professional-grade accounting system that requires no external accounting software.
- Eliminate the gap between operational transactions and financial records by automatically reflecting every business event in the general ledger.
- Give business owners real-time financial clarity — balance sheet, profit & loss, and cash position — at any moment.
- Enforce financial integrity through double-entry accounting, period controls, approval workflows, and immutable audit trails.
- Support businesses across any industry, country, or tax jurisdiction by providing flexible, configurable financial infrastructure.
- Prepare the platform for AI-powered financial intelligence — anomaly detection, forecasting, and smart reconciliation.

The ultimate measure of success: every CFO, accountant, auditor, and business owner on the DevSphere platform should have complete confidence in the financial data they see.

---

## 4. Business Goals

### Primary Goals

- **BG-001**: Deliver a complete double-entry general ledger that serves as the financial SSOT for every company.
- **BG-002**: Automate financial entries from Sales, Purchase, and Inventory with zero manual effort.
- **BG-003**: Produce accurate, real-time financial statements (Balance Sheet, P&L, Cash Flow).
- **BG-004**: Provide complete Accounts Receivable and Accounts Payable management.
- **BG-005**: Support banking, cash management, and payment processing workflows.
- **BG-006**: Enable multi-currency operations with automated exchange gain/loss accounting.
- **BG-007**: Deliver tax management supporting VAT, GST, Sales Tax, and Withholding Tax.
- **BG-008**: Enforce period locking, approval workflows, and financial controls.
- **BG-009**: Maintain an immutable, complete audit trail for all financial events.
- **BG-010**: Prepare financial data structures for AI-powered insights and forecasting.

### Secondary Goals

- **BG-011**: Provide cost center and department accounting for internal financial reporting.
- **BG-012**: Enable bank reconciliation to maintain cash accuracy.
- **BG-013**: Support credit management, collections, and bad debt readiness.
- **BG-014**: Deliver financial KPIs for executive dashboards.
- **BG-015**: Prepare extension points for budgeting, fixed assets, payroll, and treasury.

---

## 5. Business Scope

### In Scope

**General Ledger & Chart of Accounts**
- Chart of Accounts with hierarchical account groups and types
- Double-entry general ledger with balanced journal entries
- Recurring journal entries
- Fiscal year and period management
- Opening balance setup
- Period-end and year-end closing process
- Trial balance generation

**Financial Statements**
- Balance Sheet
- Profit & Loss (Income Statement)
- Cash Flow Statement (indirect method)

**Accounts Receivable (AR)**
- Customer ledger
- Invoice tracking and aging
- Customer statements
- Credit limit and credit hold management
- Collections workflow
- Receivable adjustments and write-offs readiness

**Accounts Payable (AP)**
- Supplier ledger
- Bill tracking and aging
- Supplier statements
- Vendor credits and adjustments
- Supplier reconciliation

**Banking**
- Bank account management
- Bank transfers
- Bank deposits
- Cheque management and printing readiness
- Bank reconciliation
- Electronic payment readiness

**Cash Management**
- Cash account management
- Cash receipts and payments
- Petty cash management
- Cash reconciliation

**Payments**
- Customer payment processing
- Supplier payment processing
- Partial payments, advance payments, overpayments
- Refunds, credit notes, debit notes
- Payment allocation and matching

**Tax Management**
- Sales Tax, VAT, GST, Withholding Tax
- Tax groups, tax codes, tax calendars
- Tax reports and filings readiness
- Country-specific tax extensibility

**Multi-Currency**
- Base and foreign currency support
- Exchange rate management
- Exchange gain/loss accounting
- Currency revaluation

**Cost Accounting**
- Cost centers
- Departments
- Projects
- Profit centers

**Financial Controls**
- Approval workflows for journals and payments
- Period locking
- Journal locking and reversal rules
- Posting rules
- Segregation of duties

**Reporting**
- General Ledger report
- Trial Balance
- Balance Sheet
- Profit & Loss
- Cash Flow statement
- Customer Ledger report
- Supplier Ledger report
- Journal report
- Bank Book
- Cash Book
- Tax reports
- Financial KPI dashboard

---

## 6. Out of Scope

The following are explicitly excluded from Epic 8 and planned for future epics:

- **Budgeting & Forecasting** — Epic 11 (Reports & Intelligence)
- **Fixed Assets & Depreciation** — Future dedicated epic
- **Payroll Processing** — Future dedicated epic
- **Loan Management & Treasury** — Future dedicated epic
- **CRM Integration** — Epic 9
- **Installment Billing** — Epic 10
- **Advanced Business Intelligence** — Epic 11
- **Deployment Infrastructure** — Epic 12
- **Multi-Branch Full Implementation** — Branch readiness only in this epic
- **E-invoicing / Government submission portals** — Future integration epic
- **Consolidated Group Accounts** — Future epic
- **External Audit Integration** — Future epic

---

## 7. Accounting Philosophy

### Core Principles

**Double-Entry Accounting**
Every financial transaction must produce at least two journal entries — a debit and a credit — that are always equal and opposite. This principle is inviolable and cannot be bypassed by any business process.

**Accrual Basis First**
DevSphere Accounting defaults to the accrual basis of accounting, where revenue is recognized when earned and expenses when incurred, regardless of cash movement. Cash-basis reporting is a secondary view derived from accrual records.

**Industry Neutrality**
The Chart of Accounts is configurable per company. No industry-specific accounts are hardcoded. The system provides templates for common industries (retail, manufacturing, services, construction, medical) while allowing full customization.

**Financial Isolation**
Each company's financial records are completely isolated from all other companies within the platform. An accountant for Company A cannot see, access, or influence the financial data of Company B.

**Immutability**
Posted financial entries cannot be edited or deleted. Corrections are always made through reversal entries and new postings. This preserves a complete, truthful financial history at all times.

**Auditability**
Every financial action — creation, approval, posting, reversal, payment — is stamped with the user, timestamp, and reason. This audit trail is immutable and always available for review.

**Real-Time Accuracy**
Financial statements reflect the current state of all posted transactions at any moment. There is no batch processing delay between a transaction being posted and it appearing in financial reports.

---

## 8. Domain Boundaries

The Accounting domain owns the following data and processes:

**Accounting Owns:**
- Chart of Accounts and account master data
- General Ledger and all journal entries
- Fiscal years, periods, and accounting calendar
- Financial statements and their calculation rules
- Customer ledger balances and AR aging
- Supplier ledger balances and AP aging
- Bank account register and reconciliation records
- Cash account register
- Payment records and allocation
- Tax codes, rates, and tax journal entries
- Exchange rates and currency gain/loss records
- Cost center and department allocations
- Period locks and journal locks

**Accounting Receives From (but does not own):**
- Sales invoices and credit notes → from Epic 7 Sales
- Purchase bills and vendor credits → from Epic 6 Purchase
- Inventory adjustments → from Epic 5 Inventory
- Customer master data → from Epic 7 Sales (shared reference)
- Supplier master data → from Epic 6 Purchase (shared reference)
- User identity and roles → from Epic 4 Users & Roles
- Company configuration → from Epic 3 Companies

**Accounting Does NOT Own:**
- Sales order or delivery processing
- Purchase order or receipt processing
- Inventory stock records
- Customer contact management
- Supplier relationship management
- HR or employee records

---

## 9. Bounded Context

The Accounting bounded context is the **Financial Record** — the authoritative source of all financial truth for a company.

**Context Map:**

```
[Sales Context] ----publishes---> [Accounting Context]
  invoice.posted                    creates GL entry
  payment.received                  allocates AR

[Purchase Context] --publishes---> [Accounting Context]
  bill.posted                       creates GL entry
  payment.made                      allocates AP

[Inventory Context] -publishes---> [Accounting Context]
  adjustment.posted                 creates GL entry
  cost.updated                      revalues inventory GL

[Accounting Context] -publishes-> [Reports Context (Ep11)]
  period.closed                     triggers reporting
  statement.generated               consumed by dashboards

[Accounting Context] -publishes-> [CRM Context (Ep9)]
  customer.creditlimit.breached     triggers collection
  customer.onhold                   blocks new orders
```

The Accounting context is the downstream consumer of all operational contexts and the upstream publisher to reporting and intelligence contexts.

---

## 10. Stakeholders

| Stakeholder | Role | Interest |
|-------------|------|----------|
| Business Owner / Director | Decision Maker | Financial health, P&L, cash position |
| Chief Financial Officer (CFO) | Financial Governance | Compliance, controls, reporting accuracy |
| Controller / Head of Accounts | Operational Ownership | GL accuracy, period close, reconciliation |
| Accountant / Bookkeeper | Daily Operations | Data entry, journal postings, reconciliation |
| Accounts Receivable Clerk | AR Operations | Invoice collection, customer aging |
| Accounts Payable Clerk | AP Operations | Bill processing, supplier payments |
| Cashier | Cash Management | Receipts, payments, petty cash |
| External Auditor | Compliance Review | Audit trail, trial balance, financial statements |
| Tax Consultant | Tax Compliance | Tax reports, VAT/GST accuracy |
| IT Administrator | System Health | Tenant isolation, data integrity |
| SaaS Tenant (DevSphere Customer) | Platform Subscriber | Feature availability, data privacy |

---

## 11. User Personas

### Persona 1: The Accountant (Maria)

Maria is a certified accountant managing the books for a mid-sized retail company. She needs to:
- Post journal entries for month-end adjustments
- Reconcile bank accounts weekly
- Generate and review the trial balance
- Close accounting periods on schedule
- Produce financial statements for management

Maria values accuracy, auditability, and a clean audit trail above all else.

### Persona 2: The AR Clerk (James)

James manages customer payments and collections. He needs to:
- Review outstanding invoices and customer aging
- Apply customer payments to open invoices
- Issue credit notes and adjust receivables
- Monitor customers on credit hold
- Send payment reminders and statements

James values speed of payment processing and clear visibility of who owes what.

### Persona 3: The AP Clerk (Aisha)

Aisha manages supplier bills and payments. She needs to:
- Review incoming bills and match to purchase orders
- Schedule supplier payments
- Apply vendor credits against outstanding bills
- Reconcile supplier statements
- Generate payment batches for approval

Aisha values accuracy in payables and clean supplier account balances.

### Persona 4: The CFO (David)

David is responsible for financial governance and reporting. He needs to:
- Review financial statements at any time
- Approve large journal entries and payment batches
- Monitor financial KPIs and cash flow
- Ensure period controls and approval workflows are enforced
- Review audit trails for compliance

David values real-time visibility, strong controls, and compliance assurance.

### Persona 5: The Business Owner (Sarah)

Sarah owns and runs a growing services company. She needs to:
- See her cash position daily
- Understand monthly profit and loss
- Know who owes her money and who she owes
- Ensure taxes are tracked and filed on time

Sarah values simplicity, clarity, and confidence in her numbers.

### Persona 6: The Tax Consultant (Raj)

Raj handles tax compliance for multiple clients on the platform. He needs to:
- Review tax transactions for a period
- Generate VAT/GST returns
- Verify withholding tax balances
- Export tax data for government submission

Raj values accuracy, completeness, and exportability of tax data.

---

## 12. Business Capabilities

### Capability Map

| Capability | Description | Priority |
|------------|-------------|----------|
| Chart of Accounts Management | Define and maintain the full account hierarchy | P1 |
| General Ledger | Record, post, and query all financial transactions | P1 |
| Journal Entry Management | Create, approve, post, and reverse journal entries | P1 |
| Fiscal Calendar Management | Define fiscal years and periods; control opens/closes | P1 |
| Financial Statement Generation | Produce Balance Sheet, P&L, Cash Flow on demand | P1 |
| Accounts Receivable Management | Track customer balances, invoices, payments, aging | P1 |
| Accounts Payable Management | Track supplier balances, bills, payments, aging | P1 |
| Bank Account Management | Manage bank accounts, reconcile statements | P1 |
| Cash Management | Track cash receipts, payments, petty cash | P1 |
| Payment Processing | Process and allocate all inbound and outbound payments | P1 |
| Tax Management | Configure and compute tax on transactions | P1 |
| Multi-Currency Operations | Operate in multiple currencies with gain/loss accounting | P2 |
| Cost Center Accounting | Allocate transactions to cost centers and departments | P2 |
| Financial Controls | Enforce approvals, locks, reversal rules | P1 |
| Audit Trail Management | Record and surface complete financial event history | P1 |
| Financial Reporting | Generate all standard financial and management reports | P1 |
| AR Collections Management | Manage credit limits, holds, and collection workflows | P2 |
| Bank Reconciliation | Match bank statements to GL entries | P1 |
| Recurring Journal Entries | Automate periodic accruals and amortizations | P2 |
| Period-End Close | Execute structured period close procedures | P1 |

---

## 13. Chart of Accounts

### 13.1 Purpose

The Chart of Accounts (COA) is the foundational taxonomy of every account used to record financial transactions. It defines the structure, classification, and hierarchy of all accounts in the general ledger.

### 13.2 Account Types

The system recognizes five fundamental account types aligned with the accounting equation (Assets = Liabilities + Equity + Revenue − Expenses):

| Account Type | Normal Balance | Represents |
|-------------|----------------|------------|
| Asset | Debit | Resources owned by the business |
| Liability | Credit | Obligations owed by the business |
| Equity | Credit | Owner's residual interest in the business |
| Revenue | Credit | Income earned by the business |
| Expense | Debit | Costs incurred in operating the business |

### 13.3 Account Groups

Account Groups provide a sub-classification within account types for financial statement presentation:

**Asset Groups:** Current Assets, Fixed Assets, Intangible Assets, Other Assets
**Liability Groups:** Current Liabilities, Long-Term Liabilities, Other Liabilities
**Equity Groups:** Share Capital, Retained Earnings, Other Equity
**Revenue Groups:** Operating Revenue, Other Income, Exceptional Items
**Expense Groups:** Cost of Goods Sold, Operating Expenses, Financial Expenses, Exceptional Expenses

### 13.4 Account Hierarchy

Accounts are organized in a hierarchical structure:
- **Root Level**: Account Type (Asset, Liability, Equity, Revenue, Expense)
- **Group Level**: Account Group (Current Assets, Fixed Assets, etc.)
- **Sub-Group Level**: Optional additional grouping
- **Leaf Level**: Individual account (only leaf accounts accept transaction postings)

### 13.5 Account Codes

Each account is assigned a unique numeric code. Companies may define their own coding scheme. The system enforces code uniqueness within a company. Standard code ranges are:

| Range | Type |
|-------|------|
| 1000–1999 | Assets |
| 2000–2999 | Liabilities |
| 3000–3999 | Equity |
| 4000–4999 | Revenue |
| 5000–5999 | Cost of Goods Sold |
| 6000–8999 | Operating Expenses |
| 9000–9999 | Other / System Reserved |

### 13.6 Account Properties

Each account carries:
- **Account Code**: Unique identifier within the company
- **Account Name**: Descriptive name
- **Account Type**: Asset / Liability / Equity / Revenue / Expense
- **Account Group**: Sub-classification for reporting
- **Currency**: Base currency (or foreign currency for foreign-denominated accounts)
- **Tax Category**: Whether this account is subject to tax
- **Cost Center Tracking**: Whether cost center assignment is required on posting
- **Bank Account Link**: For bank and cash accounts
- **Active Status**: Active or inactive (inactive accounts reject new postings)
- **Notes**: Internal description

### 13.7 System Accounts

Certain accounts are designated as system accounts and are configured during company setup. These include:
- Accounts Receivable control account
- Accounts Payable control account
- Bank and cash accounts
- Tax liability accounts (VAT/GST collected and paid)
- Retained earnings account
- Exchange gain/loss account
- Inventory control account (linked from Epic 5)

### 13.8 COA Templates

The system provides industry-specific COA templates during company setup:
- Retail
- Manufacturing
- Services / Professional Services
- Construction
- Medical / Healthcare
- Wholesale / Distribution
- Hospitality / Travel
- Generic (blank template)

Companies may modify any template after creation.

---

## 14. General Ledger

### 14.1 Purpose

The General Ledger (GL) is the master financial record of the company. Every monetary transaction that affects the company's financial position is recorded in the GL through journal entries. The GL is the source of truth for all financial statements and reports.

### 14.2 GL Structure

The GL is organized by:
- Company (strict isolation)
- Fiscal Year
- Accounting Period
- Account
- Journal Entry

Every GL entry records: account, date, debit or credit amount, currency, exchange rate, reference, description, source document, cost center, user, and timestamp.

### 14.3 Posting Sources

GL entries originate from the following sources:

| Source | Origin | Example |
|--------|---------|---------|
| Manual Journal | Accountant entry | Month-end accrual |
| Sales Invoice | Epic 7 Sales | Revenue and AR posting |
| Sales Credit Note | Epic 7 Sales | Revenue reversal |
| Customer Payment | AR module | Cash receipt and AR clearance |
| Purchase Bill | Epic 6 Purchase | Expense and AP posting |
| Vendor Credit | AP module | AP reversal |
| Supplier Payment | AP module | Cash payment and AP clearance |
| Inventory Adjustment | Epic 5 Inventory | Stock value change |
| Bank Transfer | Banking module | Cash movement between banks |
| Recurring Journal | Automated | Periodic accruals |
| Opening Balance | Setup | Initial account balances |
| Exchange Revaluation | Multi-currency | Currency gain/loss |
| Tax Journal | Tax module | Tax liability entries |

### 14.4 GL Query Capabilities

Users must be able to query the GL by:
- Date range
- Account or account range
- Cost center
- Department
- Project
- Reference number
- Source document type
- Posting user
- Journal batch

### 14.5 Drilldown

Every GL entry must be drillable to its source document. Clicking a GL entry from a sales invoice must navigate to the original invoice. This traceability is mandatory.

---

## 15. Journal Entries

### 15.1 Journal Entry Types

| Type | Description |
|------|-------------|
| Standard | Regular manual journal entry |
| Adjusting | Period-end adjustment entry |
| Reversing | Automatic reversal of a prior entry |
| Recurring | Template-based periodic entry |
| Opening Balance | Initial balance setup entry |
| Closing | Year-end retained earnings entry |
| Automated | System-generated from source documents |

### 15.2 Journal Entry Lifecycle

```
Draft --> Submitted --> Approved --> Posted --> [Reversed (optional)]
         (optional      (optional    (final,
          approval       by role)     immutable)
          step)
```

- **Draft**: Being prepared; can be edited or deleted.
- **Submitted**: Awaiting approval; can be recalled by creator.
- **Approved**: Cleared by authorised approver; ready for posting.
- **Posted**: Finalized; immutable; reflected in GL.
- **Reversed**: A new reversal entry has been created; original entry remains.

### 15.3 Entry Validation Rules

A journal entry cannot be posted unless:
- Total debits equal total credits (the entry is balanced)
- Each line references a valid, active account
- The posting date falls within an open fiscal period
- All required cost center assignments are provided
- The entry has been approved (if approval is required by the configured workflow)
- The currency and exchange rate are valid

### 15.4 Recurring Journal Entries

Recurring journal entries allow accountants to define a template that generates entries automatically on a schedule:
- Frequency: Daily, Weekly, Monthly, Quarterly, Annually
- Duration: Defined start and end dates, or indefinite
- Amount: Fixed amount or percentage-based
- Auto-post or submit-for-approval options
- Audit trail of every generated instance

Use cases: rent amortization, depreciation placeholders, insurance prepayments, subscriptions.

### 15.5 Journal Reversal

Any posted journal entry can be reversed. Reversal creates a new journal entry with all debits and credits swapped. The original entry is marked as reversed. The reversal entry references the original. Both entries remain permanently visible in the GL.

### 15.6 Batch Journals

Multiple journal entries can be grouped in a batch for joint approval and posting. Batches are approved and posted atomically — either all entries post or none do.

---

## 16. Fiscal Calendar

### 16.1 Fiscal Year

A fiscal year defines the company's accounting year. It may follow the calendar year or a custom 12-month period. The system supports:
- Multiple active fiscal years (for multi-year comparison)
- Fiscal year status: Open, Locked, Closed
- Year-end closing process
- Opening balance propagation to the next fiscal year

### 16.2 Accounting Periods

Each fiscal year is divided into accounting periods (typically 12 monthly periods). Periods can be:
- **Open**: Transactions may be posted
- **Locked**: No new postings; only authorized unlocks permitted
- **Closed**: Permanently closed; no postings under any circumstances

Period management is a privileged operation requiring Controller-level access.

### 16.3 Opening Balances

When a company begins using DevSphere Accounting mid-year or migrates from another system:
- Opening balance journals capture the starting balances for all accounts
- AR and AP opening balances link to individual customer and supplier ledgers
- Opening balances must be approved before the live period begins
- The system validates that total opening debits equal total opening credits

### 16.4 Period-End Close Procedure

The period close is a structured workflow:
1. Generate trial balance for the period
2. Review and post all outstanding journals and accruals
3. Reconcile bank accounts
4. Reconcile AR and AP control accounts
5. Review inter-company entries (if applicable)
6. Approve all outstanding transactions
7. Lock the period
8. Generate and archive period financial statements

### 16.5 Year-End Close

At fiscal year end:
1. Complete all period-end steps for the final period
2. Post year-end adjusting entries
3. Calculate profit/loss for the year
4. Post closing entry: transfer net income/loss to retained earnings
5. Lock the fiscal year
6. Initialize the new fiscal year with opening balances

---

## 17. Financial Statements

### 17.1 Balance Sheet

The Balance Sheet presents the financial position of the company at a point in time:

**Assets Section**
- Current Assets: Cash, bank, accounts receivable, inventory, prepaid expenses
- Fixed Assets: Property, plant and equipment
- Intangible Assets
- Other Assets

**Liabilities Section**
- Current Liabilities: Accounts payable, accrued expenses, short-term loans, tax payable
- Long-Term Liabilities

**Equity Section**
- Share capital, retained earnings, current period net income/loss

**Key Requirement**: Total Assets must always equal Total Liabilities plus Total Equity. Any imbalance indicates a data integrity error that must be immediately surfaced.

The Balance Sheet is generated for any date, any period, and any comparative period.

### 17.2 Profit & Loss (Income Statement)

The P&L presents the financial performance over a period:

**Revenue Section**
- Operating Revenue by category
- Other Income

**Cost of Goods Sold Section**
- Direct costs, materials, labour (industry dependent)

**Gross Profit**

**Operating Expenses Section**
- By account or account group
- Organized by expense category

**Operating Profit (EBIT)**

**Financial Income/Expense Section**
- Interest income, bank charges, exchange gain/loss

**Net Profit Before Tax**

**Tax Expense**

**Net Profit After Tax**

The P&L is generated for any period, year-to-date, prior period comparison, prior year comparison, and budget comparison (when budgets are available in future).

### 17.3 Cash Flow Statement

The Cash Flow Statement presents how cash moved during a period, using the indirect method:

**Operating Activities**
- Net profit adjusted for non-cash items (depreciation placeholders, etc.)
- Changes in working capital (AR, AP, inventory, prepayments)

**Investing Activities**
- Cash spent on or received from fixed assets (readiness)

**Financing Activities**
- Cash from loans, repayments, equity injections (readiness)

**Net Change in Cash**

**Opening Cash Balance**

**Closing Cash Balance**

### 17.4 Trial Balance

The Trial Balance is the foundational verification report that lists every account with its total debit and credit balances for a period. It must always balance (total debits = total credits). The Trial Balance is available:
- At any date
- By period
- As a comparative (current vs prior)
- In summary or detail

---

## 18. Accounts Receivable

### 18.1 Customer Ledger

The Customer Ledger is the subsidiary ledger that records all financial transactions with each customer. It must reconcile to the AR control account in the general ledger at all times.

Each customer ledger contains:
- All invoices issued
- All credit notes issued
- All payments received
- All adjustments made
- Running balance at any point in time

### 18.2 Invoice Tracking

AR tracks every sales invoice from Epic 7:
- Invoice date and due date
- Invoice amount and outstanding balance
- Currency and exchange rate
- Payment terms
- Status: Open, Partially Paid, Paid, Overdue, Disputed, Written Off

### 18.3 Customer Aging

Customer aging classifies outstanding receivables by overdue period:

| Bucket | Description |
|--------|-------------|
| Not Yet Due | Within payment terms |
| 1–30 Days Overdue | |
| 31–60 Days Overdue | |
| 61–90 Days Overdue | |
| 91–120 Days Overdue | |
| 120+ Days Overdue | High collection risk |

Aging is available per customer and as an aggregate AR aging summary. Aging is calculated from the invoice due date, not the invoice date.

### 18.4 Credit Limits

Each customer may have a credit limit defined. The system:
- Tracks current outstanding AR balance against the credit limit
- Warns when the limit is approached (configurable threshold, e.g., 80%)
- Blocks new invoices when the limit is exceeded (if enforcement is enabled)
- Escalates to Credit Hold status when the limit is significantly exceeded or an invoice is critically overdue

### 18.5 Credit Hold

A customer on Credit Hold:
- Cannot have new sales orders or invoices created without override approval
- Is flagged across all operational modules (Sales module is notified)
- Requires an authorized user to release the hold
- Has all hold/release actions recorded in the audit trail

### 18.6 Customer Statements

Customer statements are periodic summaries sent to customers showing:
- Opening balance
- All transactions (invoices, credits, payments) in the period
- Closing balance and amount due

Statements are generated per customer, per period, and are ready for email delivery.

### 18.7 Collections

The collections workflow supports:
- Identifying overdue customers by aging bucket
- Generating and tracking collection reminders (1st, 2nd, final notice)
- Recording collection actions and notes
- Escalating to credit hold or write-off

### 18.8 Receivable Adjustments

Authorized users may post adjustments to the customer ledger for:
- Disputed amounts
- Discounts granted post-invoice
- Rounding adjustments
- Write-off preparation (full write-off is part of the bad debt process)

### 18.9 Bad Debt Write-Off Readiness

The system is designed to support bad debt write-offs. A write-off:
- Removes the receivable from the customer ledger
- Posts to a Bad Debt Expense account in the GL
- Requires approval from an authorized financial controller
- Is fully reversible if the debt is subsequently recovered
- Creates a complete audit trail

---

## 19. Accounts Payable

### 19.1 Supplier Ledger

The Supplier Ledger records all financial transactions with each supplier. It reconciles to the AP control account in the GL at all times.

Each supplier ledger contains:
- All bills received
- All vendor credit notes
- All payments made
- All adjustments posted
- Running balance at any point

### 19.2 Bill Tracking

AP tracks every purchase bill from Epic 6:
- Bill date and due date
- Bill amount and outstanding balance
- Currency and exchange rate
- Payment terms
- Status: Open, Partially Paid, Paid, Overdue, On Hold, Disputed

### 19.3 Payables Aging

Payables aging classifies outstanding AP by payment due date:

| Bucket | Description |
|--------|-------------|
| Not Yet Due | Within payment terms |
| 1–30 Days Overdue | |
| 31–60 Days Overdue | |
| 61–90 Days Overdue | |
| 91–120 Days Overdue | |
| 120+ Days Overdue | Relationship risk |

Aging is available per supplier and as an aggregate AP aging summary.

### 19.4 Vendor Credits

Vendor credits (credit notes from suppliers) reduce the outstanding payable to that supplier. They are:
- Created from supplier credit notes received
- Applied against outstanding bills (partial or full)
- Tracked until fully allocated
- Visible in the supplier ledger and AP aging

### 19.5 Payment Adjustments

Authorized users may post adjustments to supplier ledgers for:
- Early payment discounts taken
- Disputed deductions
- Rounding adjustments
- Write-back of unclaimed credits

### 19.6 Supplier Reconciliation

Supplier reconciliation matches the supplier's statement of account (received from the supplier) against the AP ledger:
- Side-by-side comparison
- Identification of unmatched items
- Resolution workflow (disputes, timing differences)
- Reconciliation report for audit purposes

### 19.7 Supplier Statements

Supplier statements are generated for internal use, showing:
- Opening AP balance
- Bills, credits, and payments in the period
- Closing balance and amount owed to supplier

---

## 20. Banking

### 20.1 Bank Account Management

Each company may maintain multiple bank accounts. Each bank account is linked to a GL account (bank account type). Bank account records include:
- Bank name and branch
- Account number and IBAN/SWIFT (where applicable)
- Account currency
- Opening balance
- Current GL balance vs bank statement balance (reconciliation gap)
- Active status

### 20.2 Bank Transfers

Bank transfers move funds between two bank accounts owned by the same company. A bank transfer:
- Creates a payment from the source bank account
- Creates a receipt in the destination bank account
- May record bank charges associated with the transfer
- Is reflected in the GL as a cash movement between bank accounts

### 20.3 Bank Deposits

Bank deposits record the physical deposit of cash or cheques into a bank account:
- Batch multiple receipts into a single deposit
- Match to the bank statement deposit line
- Track deposit slip reference

### 20.4 Cheque Management

The system manages outgoing cheques issued to suppliers or others:
- Cheque number tracking
- Cheque status: Issued, Presented, Cleared, Cancelled, Stale
- Reconciliation of presented cheques against the GL
- Cheque printing readiness (print template, cheque format, MICR support readiness)
- Stale cheque management and re-issue

### 20.5 Bank Reconciliation

Bank reconciliation matches the company's GL bank balance to the bank statement:

**Process:**
1. Import or enter bank statement transactions
2. Auto-match GL entries to bank statement lines (by amount, date, reference)
3. Review unmatched items (on both sides)
4. Post bank charges, interest, and fees from the statement
5. Resolve timing differences
6. Finalize reconciliation — statement balance must equal GL balance
7. Lock the reconciled period
8. Generate reconciliation report

Bank reconciliation is a mandatory control and should be performed at minimum monthly.

### 20.6 Electronic Payment Readiness

The system is architecturally prepared to support electronic payment file generation:
- ACH / EFT payment batches
- SWIFT international payments
- Country-specific payment file formats
- Integration with payment gateway providers

Full electronic payment integration is a future feature; the data model and workflow support is in place.

---

## 21. Cash Management

### 21.1 Cash Accounts

Cash accounts represent physical cash held by the company. They are linked to GL accounts of type Cash. The system supports multiple cash accounts per company (e.g., main till, branch till, petty cash box).

### 21.2 Cash Receipts

Cash receipts record cash received from any source:
- Customer payments received in cash
- Other cash income
- Petty cash top-ups from the bank
- Each receipt references the payer, amount, purpose, and GL accounts

### 21.3 Cash Payments

Cash payments record cash paid out:
- Supplier payments made in cash
- Petty cash disbursements
- Other cash expenses
- Each payment references the payee, amount, purpose, and GL accounts

### 21.4 Petty Cash Management

Petty cash is a small fund of physical cash used for minor business expenses:
- Opening balance setup
- Petty cash vouchers for each disbursement
- Expense categorization per voucher
- Petty cash reconciliation (count vs GL balance)
- Petty cash replenishment journal (reimbursing from bank to restore float)

### 21.5 Cash Reconciliation

Cash reconciliation matches the physical cash count to the GL cash balance:
- Record physical cash count
- Identify discrepancies (overages or shortages)
- Post cash short/over journal entry
- Approve and lock the reconciled cash period

---

## 22. Payments

### 22.1 Customer Payment Processing

Customer payments are received against outstanding invoices:
- Select customer and open invoices
- Enter payment amount, date, method (cash, cheque, bank transfer, card)
- Allocate payment to specific invoices (partial or full)
- Record any early payment discounts taken
- Post: debit bank/cash account, credit AR control account
- Generate payment receipt

### 22.2 Supplier Payment Processing

Supplier payments are made against outstanding bills:
- Select supplier and open bills
- Enter payment amount, date, method (bank transfer, cheque, cash)
- Allocate payment to specific bills (partial or full)
- Record any early payment discounts
- Post: credit bank/cash account, debit AP control account
- Generate remittance advice

### 22.3 Partial Payments

A payment may be less than the total outstanding balance. The system:
- Allocates the partial payment to specified invoices/bills
- Leaves the remaining balance on the open invoices/bills
- Updates the aging report accordingly

### 22.4 Advance Payments

An advance payment is received from a customer or made to a supplier before an invoice is issued:
- Recorded against a designated advance/deposit account
- Applied to invoices when they are subsequently raised
- Tracked as an open advance until fully allocated

### 22.5 Overpayments

When a customer pays more than the outstanding amount:
- The overpayment is captured as a credit on the customer account
- It can be applied to future invoices
- Or refunded to the customer
- It is visible in customer aging as a credit balance

### 22.6 Refunds

Refunds represent money returned to customers or received back from suppliers:
- Customer refund: debit customer AP/credit account, credit bank
- Supplier refund: credit vendor account, debit bank
- Fully traced to original payment and invoice

### 22.7 Credit Notes

Credit notes reduce the amount owed by a customer or owed to a supplier:
- **Customer Credit Note**: Reduces the customer's outstanding balance; may be allocated to open invoices or carried as a credit
- **Supplier Credit Note**: Reduces the amount owed to the supplier; allocated against open bills

### 22.8 Debit Notes

Debit notes increase the amount owed:
- **Customer Debit Note**: Increases the customer's outstanding balance (e.g., for undercharged amounts)
- **Supplier Debit Note**: Increases the amount owed to the supplier

### 22.9 Payment Allocation

The allocation engine matches payments and credits to invoices/bills:
- Auto-allocation: oldest-first or exact-match rules
- Manual allocation: user-directed matching
- Partial allocation: apply payment to selected lines
- Re-allocation: reverse and redo an incorrect allocation
- Allocation audit trail: every allocation action is recorded

---

## 23. Tax Management

### 23.1 Tax Philosophy

Tax management in DevSphere Accounting is jurisdiction-neutral and configurable. The system does not hardcode tax rules for any country. Instead, it provides a flexible tax framework into which any tax regime can be configured.

### 23.2 Tax Types Supported

| Tax Type | Description |
|----------|-------------|
| Sales Tax | Applied at point of sale; varies by jurisdiction and product type |
| VAT (Value Added Tax) | Multi-stage consumption tax; input VAT recoverable |
| GST (Goods and Services Tax) | Similar to VAT; used in many Commonwealth countries |
| Withholding Tax (WHT) | Deducted at source on payments to suppliers or contractors |
| Compound Tax | Tax calculated on a base that includes another tax |
| Exempt | Transaction is exempt from tax |
| Zero-Rated | Subject to tax at 0%; still reportable |
| Out of Scope | Not subject to tax and not reportable |

### 23.3 Tax Codes

Tax codes are the atomic unit of tax configuration. Each code specifies:
- Tax type
- Rate (percentage)
- Tax account (GL account where tax is posted)
- Effective date range
- Country/jurisdiction
- Applicability (sales, purchases, or both)
- Rounding rule

### 23.4 Tax Groups

Tax groups allow multiple tax codes to be bundled and applied together (e.g., Federal GST + Provincial Tax). A tax group applied to a transaction applies all component taxes simultaneously.

### 23.5 Tax on Transactions

When a tax code or group is applied to a sales invoice or purchase bill:
- The system calculates the tax amount per line
- Tax amounts are posted to the configured tax GL account
- The customer/supplier sees the net amount, tax amount, and gross total
- Tax values are locked once the document is posted

### 23.6 Input Tax (Recoverable)

For VAT/GST regimes, tax paid on purchases (input tax) is recoverable:
- Input tax is posted to a recoverable tax asset account
- Output tax (on sales) is posted to a tax liability account
- Net VAT/GST payable = Output Tax − Input Tax
- The system supports standard-rated, reduced-rate, and zero-rated inputs

### 23.7 Withholding Tax

For jurisdictions requiring WHT on supplier payments:
- WHT percentage is configured per tax code
- WHT is deducted from the gross payment
- The deducted amount is posted to a WHT payable liability account
- WHT certificates are generated for suppliers
- WHT periodic returns are prepared for the tax authority

### 23.8 Tax Reports

The system produces:
- Tax Return Summary (Output Tax, Input Tax, Net Payable)
- Detailed Tax Transaction Report (every taxable transaction)
- VAT/GST Return (formatted for common jurisdictions)
- Withholding Tax Report
- Exception Report (unclassified or unusual tax transactions)

### 23.9 Country-Specific Extensibility

The tax framework is designed for extensibility:
- New tax types can be added via configuration
- Jurisdiction-specific calculation rules can be implemented without changing core business logic
- Integration points for future e-invoicing and government API submissions are conceptually defined

---

## 24. Multi-Currency

### 24.1 Base Currency

Each company defines a base (functional) currency during setup. All financial statements and the general ledger are maintained in the base currency. Foreign currency transactions are translated to the base currency at the time of posting.

### 24.2 Currency Setup

The system supports any ISO 4217 currency. Each currency is defined with:
- ISO code (USD, EUR, GBP, AED, PKR, etc.)
- Display name and symbol
- Decimal places
- Active status

### 24.3 Exchange Rates

Exchange rates define the conversion rate between a foreign currency and the base currency:
- **Spot Rate**: Rate on a specific date
- **Average Rate**: Monthly average (used for P&L translation in some jurisdictions)
- **Closing Rate**: Period-end rate (used for Balance Sheet translation)
- **Historical Rate**: Rate at original transaction date

Exchange rates are maintained per currency pair per date. The system may allow manual rate entry or integration with rate providers in future.

### 24.4 Foreign Currency Transactions

When a transaction is recorded in a foreign currency:
- The transaction is stored in both the foreign currency amount and the base currency equivalent
- The base currency equivalent is calculated using the exchange rate on the transaction date
- The foreign currency balance is maintained for AR and AP customer/supplier accounts

### 24.5 Exchange Gain / Loss

Exchange differences arise when:
- A foreign currency invoice is raised at one rate and paid at a different rate
- AR/AP foreign currency balances are revalued at period end

These differences are automatically calculated and posted to an Exchange Gain/Loss account in the GL. The system supports:
- **Realized Gain/Loss**: On actual settlement of a foreign currency invoice
- **Unrealized Gain/Loss**: On period-end revaluation of open foreign currency balances

### 24.6 Currency Revaluation

Period-end revaluation re-states all open foreign currency AR, AP, and bank balances at the current exchange rate:
- The difference from the rate used at booking is posted as unrealized gain or loss
- Revaluation is reversible — the revaluation entry can be reversed at the start of the next period
- A revaluation report documents all accounts revalued and the resulting entries

### 24.7 Multi-Currency Reporting

Financial statements can be generated in:
- Base currency (primary)
- Any configured foreign currency (translated using the applicable rate)
- Dual currency view (transaction currency and base currency side by side)

---

## 25. Cost Accounting

### 25.1 Cost Centers

A cost center is an organizational unit that incurs costs. Assigning transactions to cost centers enables internal financial reporting by segment:
- Each cost center has a code, name, and responsible manager
- GL accounts may be configured to require cost center assignment on posting
- Cost center reports show revenue and/or expenses by organizational unit

### 25.2 Departments

Departments group cost centers for higher-level reporting. A company may have Finance, Operations, Sales, HR, and IT departments, each containing relevant cost centers.

### 25.3 Projects

Projects enable tracking of revenue and costs against a defined initiative:
- Revenue, costs, and profitability per project
- Project budget vs actual (when budgets are available in future)
- Multi-year project tracking
- Project-level P&L

### 25.4 Profit Centers

Profit centers are revenue-generating units used for internal P&L reporting. Unlike cost centers that only track costs, profit centers track both revenue and expenses, enabling a P&L at the segment level.

### 25.5 Branch Accounting Readiness

The data model and cost accounting framework are designed to support branch-level financial reporting in a future phase. Each branch will function as a profit/cost center combination, with:
- Branch-specific P&L
- Branch cash and bank management
- Branch inter-company transfers
- Consolidated company view

---

## 26. Financial Controls

### 26.1 Approval Workflows

The system supports configurable approval workflows for:
- Journal entries above a defined monetary threshold
- Payment batches above a defined threshold
- Period closing authorization
- Write-offs and adjustments above a threshold
- Credit limit overrides

Approval workflows define:
- Who can approve (role-based)
- Sequential or parallel approval
- Escalation rules (if not approved within a time limit)
- Delegation of authority (DFA)

### 26.2 Period Locking

Accounting periods can be locked to prevent further postings. Locks are:
- Applied per company, per fiscal period
- Enforced across all posting sources (manual journals, system-generated entries)
- Unlockable only by authorized roles (Controller, CFO, System Admin)
- Audited: every lock and unlock is recorded

### 26.3 Journal Locking

Individual journal entries are locked when posted. A posted journal:
- Cannot be edited
- Cannot be deleted
- Can only be modified through a formal reversal + re-post process
- Every reversal is linked to the original entry

### 26.4 Posting Rules

Configurable rules determine what can and cannot be posted:
- Only balanced entries may be posted
- Posting to inactive accounts is blocked
- Posting to locked periods is blocked
- Posting to closed fiscal years is blocked
- Entries in foreign currencies require a valid exchange rate

### 26.5 Reversal Rules

- Any posted journal entry can be reversed (no exceptions)
- Reversals post the inverse entry on a specified date
- The reversal date must fall within an open period
- Reversal audit trail is mandatory

### 26.6 Segregation of Duties

The system enforces separation of duties through role-based access:
- A user who creates a journal cannot be the sole approver
- A user who processes a payment cannot approve it above their authority level
- A user who manages supplier master data cannot independently post supplier payments
- All SoD violations are flagged and reported

### 26.7 Financial Audit Trail

Every financial action generates an immutable audit record:
- What: the action performed
- Who: the user who performed it
- When: date and time (UTC)
- Where: the source module
- Before/After: state of the record before and after the change
- Why: the reason or reference provided

Audit records cannot be deleted or altered. They are retained per the configured data retention policy.

---

## 27. Business Workflows

### 27.1 Sales-to-Cash Workflow

```
Sales Invoice (Epic 7)
        |
        v
GL Posting: DR Accounts Receivable / CR Revenue + Tax
        |
        v
AR Aging Tracking
        |
        v
Customer Payment Received
        |
        v
GL Posting: DR Bank/Cash / CR Accounts Receivable
        |
        v
Invoice Marked as Paid / Partially Paid
        |
        v
Bank Reconciliation: Bank statement matched to GL
```

### 27.2 Purchase-to-Pay Workflow

```
Purchase Bill (Epic 6)
        |
        v
GL Posting: DR Expense/Inventory / CR Accounts Payable + Tax
        |
        v
AP Aging Tracking
        |
        v
Supplier Payment Made
        |
        v
GL Posting: DR Accounts Payable / CR Bank/Cash
        |
        v
Bill Marked as Paid / Partially Paid
        |
        v
Bank Reconciliation: Payment matched to bank statement
```

### 27.3 Month-End Close Workflow

```
1. Review and post all outstanding journals
2. Post recurring journal entries
3. Process bank reconciliations
4. Run AR and AP aging; confirm control account reconciliation
5. Run foreign currency revaluation
6. Review trial balance; investigate anomalies
7. Generate draft financial statements
8. Obtain Controller/CFO approval
9. Lock the period
10. Archive financial statements
```

### 27.4 Tax Filing Workflow

```
1. Run tax transaction report for the period
2. Review output and input tax balances
3. Post any tax adjustments required
4. Generate tax return
5. Review and approve tax liability amount
6. Make tax payment to authority
7. Post tax payment: DR Tax Liability / CR Bank
8. Mark period tax return as filed
```

---

## 28. Functional Requirements

### General Ledger

- **FR-001**: The system MUST enforce double-entry accounting on every financial transaction without exception.
- **FR-002**: The system MUST prevent posting of unbalanced journal entries.
- **FR-003**: The system MUST provide a full GL query with filtering by account, date, period, cost center, and source.
- **FR-004**: Every GL entry MUST link to its originating source document with drilldown capability.
- **FR-005**: The system MUST support manual journal entries, automated system journals, and recurring journals.

### Chart of Accounts

- **FR-006**: The system MUST support hierarchical account structure (type → group → sub-group → account).
- **FR-007**: The system MUST prevent duplicate account codes within a company.
- **FR-008**: The system MUST prevent posting to parent/group accounts — only leaf accounts accept entries.
- **FR-009**: The system MUST support industry-specific COA templates during company setup.
- **FR-010**: The system MUST allow accounts to be deactivated; inactive accounts must reject new postings.

### Fiscal Calendar

- **FR-011**: The system MUST support multiple fiscal year configurations per company.
- **FR-012**: The system MUST enforce period locks — no postings permitted in locked or closed periods.
- **FR-013**: The system MUST execute a formal year-end close process that transfers net income to retained earnings.
- **FR-014**: The system MUST support opening balance entry for new company setup or system migration.

### Accounts Receivable

- **FR-015**: The system MUST maintain a per-customer subsidiary ledger that reconciles to the AR control account.
- **FR-016**: The system MUST provide customer aging by configurable buckets (current, 30, 60, 90, 90+ days).
- **FR-017**: The system MUST enforce credit limits and credit hold rules per customer.
- **FR-018**: The system MUST generate customer statements for any period.
- **FR-019**: The system MUST support AR write-off with approval workflow.

### Accounts Payable

- **FR-020**: The system MUST maintain a per-supplier subsidiary ledger reconciling to the AP control account.
- **FR-021**: The system MUST provide payables aging by configurable buckets.
- **FR-022**: The system MUST support supplier statement reconciliation.
- **FR-023**: The system MUST generate remittance advice for supplier payments.

### Banking

- **FR-024**: The system MUST support multiple bank accounts per company.
- **FR-025**: The system MUST provide a formal bank reconciliation workflow that locks when completed.
- **FR-026**: The system MUST track cheque status (issued, presented, cleared, cancelled, stale).

### Cash Management

- **FR-027**: The system MUST support multiple cash accounts including petty cash.
- **FR-028**: The system MUST support petty cash vouchers, reconciliation, and replenishment.

### Payments

- **FR-029**: The system MUST support partial payments, advance payments, and overpayments.
- **FR-030**: The system MUST provide payment allocation to specific invoices/bills.
- **FR-031**: The system MUST support credit notes, debit notes, refunds, and adjustments.
- **FR-032**: The system MUST apply payment discounts (early payment) with automatic GL posting.

### Tax

- **FR-033**: The system MUST support configurable tax codes for any jurisdiction.
- **FR-034**: The system MUST calculate and post tax entries automatically on taxable transactions.
- **FR-035**: The system MUST generate tax returns and detailed tax transaction reports.
- **FR-036**: The system MUST support tax-exempt, zero-rated, and out-of-scope classifications.

### Multi-Currency

- **FR-037**: The system MUST record all foreign currency transactions in both foreign and base currency.
- **FR-038**: The system MUST calculate and post realized exchange gain/loss at settlement.
- **FR-039**: The system MUST support period-end currency revaluation with automated GL posting.

### Cost Accounting

- **FR-040**: The system MUST support cost center assignment on all GL entries (mandatory or optional per account).
- **FR-041**: The system MUST produce cost center P&L and expense reports.
- **FR-042**: The system MUST support project-level revenue and cost tracking.

### Financial Controls

- **FR-043**: The system MUST enforce configurable approval workflows for journals and payments.
- **FR-044**: The system MUST prevent posting to locked or closed periods from any module.
- **FR-045**: The system MUST prevent deletion or modification of posted journal entries.
- **FR-046**: The system MUST enforce segregation of duties per the configured permission matrix.

### Reporting

- **FR-047**: The system MUST generate Balance Sheet, P&L, and Cash Flow statements on demand.
- **FR-048**: The system MUST generate a trial balance for any period.
- **FR-049**: The system MUST provide comparative financial statements (period vs prior period, year vs prior year).
- **FR-050**: The system MUST produce GL reports, journal reports, bank book, cash book, and tax reports.

---

## 29. Non-Functional Requirements

### Performance

- **NFR-001**: Trial balance generation for a full fiscal year MUST complete in under 10 seconds for companies with up to 500,000 GL entries.
- **NFR-002**: Financial statement generation MUST complete in under 15 seconds.
- **NFR-003**: Payment processing for a single transaction MUST complete in under 2 seconds.
- **NFR-004**: GL queries must return results in under 5 seconds for date ranges within a single fiscal year.

### Scalability

- **NFR-005**: The GL must support up to 5,000,000 journal entry lines per company without degradation.
- **NFR-006**: The system must support 500 concurrent financial users per tenant.
- **NFR-007**: Batch payment processing must handle up to 1,000 payments per batch.

### Reliability

- **NFR-008**: Financial posting operations must be transactional — either fully committed or fully rolled back. No partial postings are acceptable.
- **NFR-009**: The Accounting module must maintain 99.9% uptime (excluding planned maintenance).
- **NFR-010**: Financial data must be backed up with a Recovery Point Objective (RPO) of ≤ 1 hour.

### Maintainability

- **NFR-011**: All financial business rules must be configurable per company without code changes.
- **NFR-012**: Tax codes and rates must be updateable by authorized users without system downtime.

### Observability

- **NFR-013**: All financial posting events must be logged with sufficient detail for forensic audit.
- **NFR-014**: System must expose financial health metrics: total GL entries, period close status, open reconciliations.

### Compliance Readiness

- **NFR-015**: The Accounting module must be capable of producing audit-ready reports for any fiscal period.
- **NFR-016**: Data retention must support regulatory requirements of at minimum 7 years for financial records.

---

## 30. Business Rules

### Double-Entry Rules

- **BR-001**: Every financial transaction must produce at least one debit entry and at least one credit entry.
- **BR-002**: The sum of all debits in a journal must equal the sum of all credits. No exceptions.
- **BR-003**: Debits increase Assets and Expenses; Credits increase Liabilities, Equity, and Revenue.

### Posting Rules

- **BR-004**: A journal entry may only be posted to an open fiscal period.
- **BR-005**: A journal entry may only reference active accounts.
- **BR-006**: A journal entry may only be posted after all required approvals are granted.
- **BR-007**: Automated entries from source modules (Sales, Purchase, Inventory) are posted immediately upon source document posting and require no additional approval.
- **BR-008**: Manual journal entries above a configured threshold require approval before posting.

### Reversal Rules

- **BR-009**: Any posted journal entry may be reversed.
- **BR-010**: A reversal must be posted to an open period (not necessarily the same period as the original).
- **BR-011**: A reversal creates a new journal entry; it does not modify or delete the original.
- **BR-012**: A reversal entry is itself reversible (creating a double-reversal, which restores the original effect).

### Fiscal Rules

- **BR-013**: No posting is permitted to a locked or closed period.
- **BR-014**: Period locking requires Controller or higher authority.
- **BR-015**: Year-end close must post a balancing entry transferring net income/loss to retained earnings before the fiscal year is closed.
- **BR-016**: A fiscal period can be reopened only by a Controller or CFO, and only with an audit trail entry documenting the reason.

### Currency Rules

- **BR-017**: Every foreign currency transaction must record both the foreign currency amount and the base currency equivalent.
- **BR-018**: The exchange rate used for a transaction is locked at posting and cannot be retrospectively changed.
- **BR-019**: Exchange gain/loss entries are system-generated and cannot be manually overridden; they can only be reversed if the underlying transaction is reversed.

### Payment Rules

- **BR-020**: A payment cannot exceed the outstanding balance of the invoice/bill it is applied to, unless the overpayment is explicitly confirmed and recorded as a credit.
- **BR-021**: A payment posted to a locked period is rejected.
- **BR-022**: Advance payments must be recorded to a designated advance account and not directly to revenue or expense.
- **BR-023**: Payment allocation must leave no payment unallocated beyond 90 days without a review flag.

### Tax Rules

- **BR-024**: Tax is calculated based on the tax code assigned to the transaction line.
- **BR-025**: A tax-exempt transaction must explicitly reference its exemption reason.
- **BR-026**: Tax values on a posted document cannot be modified; corrections require a credit note and re-invoice.
- **BR-027**: Withholding tax deducted must be remitted to the tax authority by the due date defined in the tax calendar.

### AR / AP Rules

- **BR-028**: A customer in Credit Hold status cannot have new invoices created without an override approved by an authorized role.
- **BR-029**: The AR control account balance must equal the sum of all customer ledger balances at all times.
- **BR-030**: The AP control account balance must equal the sum of all supplier ledger balances at all times.
- **BR-031**: A write-off requires approval; once approved, the GL entry is posted and the invoice marked as written off.

### Closing Rules

- **BR-032**: A period can be closed only after bank reconciliation is completed for that period.
- **BR-033**: A period can be closed only after AR and AP control account reconciliation confirms no discrepancy.

---

## 31. Business Invariants

Invariants are conditions that must always be true, regardless of the operation:

- **INV-001**: Total GL debits always equal total GL credits (for any subset: company, period, fiscal year).
- **INV-002**: The Balance Sheet equation always holds: Assets = Liabilities + Equity.
- **INV-003**: AR control account = Sum of all customer ledger balances.
- **INV-004**: AP control account = Sum of all supplier ledger balances.
- **INV-005**: Bank/Cash GL balance = Sum of all reconciled bank/cash transactions.
- **INV-006**: No posted journal entry may have a null or invalid account reference.
- **INV-007**: Every posted journal entry has a complete audit trail record.
- **INV-008**: A closed fiscal year produces no new GL entries.
- **INV-009**: Tax liability = Sum of all unremitted tax transactions by tax code.
- **INV-010**: An exchange gain/loss entry exists for every settled foreign currency transaction where the settlement rate differs from the booking rate.

---

## 32. Validation Rules

### Journal Entry Validation

- Entry date is within an open fiscal period
- All account codes exist and are active
- Sum of debits equals sum of credits
- All required fields (date, description, reference) are populated
- Cost center provided for accounts requiring it
- Currency is active; exchange rate provided for foreign currencies
- Approval obtained if amount exceeds threshold

### Payment Validation

- Payment amount is positive
- Payment date is within an open period
- Bank/cash account has sufficient balance (soft warning, not hard block by default)
- Customer/supplier exists and is active
- At least one invoice is selected for allocation (unless recording an advance)
- Payment method is specified

### Tax Validation

- Tax code is active and applicable to the transaction type (sales or purchase)
- Tax calculation is consistent with the configured rate
- Tax account is a valid GL account

### Bank Reconciliation Validation

- Statement balance is entered
- All differences are explained (matched or posted)
- Cleared balance equals statement balance before reconciliation can be finalized

---

## 33. Permission Matrix

| Action | Accountant | AR Clerk | AP Clerk | Cashier | Controller | CFO | System Admin |
|--------|------------|----------|----------|---------|------------|-----|--------------|
| View GL | Yes | Limited | Limited | Limited | Yes | Yes | Yes |
| Create Journal Entry | Yes | No | No | No | Yes | Yes | No |
| Approve Journal Entry | No | No | No | No | Yes | Yes | No |
| Post Journal Entry | Yes | No | No | No | Yes | Yes | No |
| Reverse Journal Entry | No | No | No | No | Yes | Yes | No |
| Lock/Unlock Period | No | No | No | No | Yes | Yes | No |
| Close Fiscal Year | No | No | No | No | No | Yes | Yes |
| Create Customer Payment | No | Yes | No | Yes | Yes | Yes | No |
| Approve Customer Payment | No | No | No | No | Yes | Yes | No |
| Create Supplier Payment | No | No | Yes | Yes | Yes | Yes | No |
| Approve Supplier Payment | No | No | No | No | Yes | Yes | No |
| Manage Chart of Accounts | Yes | No | No | No | Yes | Yes | No |
| Manage Tax Codes | No | No | No | No | Yes | Yes | No |
| Manage Exchange Rates | Yes | No | No | No | Yes | Yes | No |
| Perform Bank Reconciliation | Yes | No | No | No | Yes | Yes | No |
| View Financial Statements | Yes | Yes | Yes | No | Yes | Yes | Yes |
| Write-Off AR | No | No | No | No | Yes | Yes | No |
| Override Credit Limit | No | No | No | No | Yes | Yes | No |
| Manage Approval Workflows | No | No | No | No | No | Yes | Yes |

*Permissions are additive and configurable per company. This matrix represents the default configuration.*

---

## 34. Feature Matrix

| Feature | Starter Plan | Professional Plan | Enterprise Plan |
|---------|-------------|-------------------|-----------------|
| Chart of Accounts | Basic (template only) | Full customization | Full + multi-template |
| General Ledger | Yes | Yes | Yes |
| Journal Entries | Manual only | Manual + recurring | Full + batch |
| Fiscal Calendar | 1 year | Multiple years | Multiple + custom periods |
| Financial Statements | Basic (B/S, P&L) | Full statements | Full + comparative |
| Accounts Receivable | Basic | Full AR | Full AR + Collections |
| Accounts Payable | Basic | Full AP | Full AP + Reconciliation |
| Banking | 1 bank account | Multiple accounts | Full + electronic readiness |
| Cash Management | Basic | Full | Full + multi-till |
| Payments | Basic | Full | Full + batch |
| Tax Management | Single tax code | Multiple codes | Full + WHT |
| Multi-Currency | No | Yes (limited) | Full + revaluation |
| Cost Centers | No | Yes | Yes + projects |
| Approval Workflows | None | Basic | Full configurable |
| Reporting | Basic | Standard | Full + custom |
| AI Readiness | No | No | Yes (hooks enabled) |

---

## 35. Financial Governance

### 35.1 Controller Responsibilities

The Controller is the primary financial governance role:
- Owns the Chart of Accounts
- Approves all journal entries above their delegation threshold
- Owns the month-end close calendar and process
- Reviews and approves financial statements before publication
- Manages period locks
- Resolves reconciliation discrepancies

### 35.2 CFO Responsibilities

The CFO has ultimate financial authority:
- Approves year-end close
- Reviews and signs off on annual financial statements
- Sets approval thresholds and delegation matrix
- Receives escalated alerts for anomalies
- Oversees audit readiness

### 35.3 Delegation of Financial Authority

The system enforces a Delegation of Financial Authority (DFA) matrix:
- Each monetary threshold has a defined approver role
- Approvals above a user's DFA are escalated to the next level
- The DFA matrix is configurable per company
- All delegations are time-bound and audited

### 35.4 Four-Eyes Principle

For transactions above a configurable threshold, the four-eyes principle applies:
- Two authorized users must approve
- The preparer cannot be one of the two approvers
- Electronic approval signature is recorded

---

## 36. Conceptual Domain Model

### Core Aggregates

```
Company
├── ChartOfAccounts
│   ├── AccountGroup[]
│   └── Account[]
│       ├── AccountType
│       └── AccountGroup
├── FiscalCalendar
│   ├── FiscalYear[]
│   └── FiscalPeriod[]
├── GeneralLedger
│   └── JournalEntry[]
│       └── JournalLine[] (debit/credit)
├── AccountsReceivable
│   └── CustomerLedger[]
│       ├── Invoice[]
│       ├── CreditNote[]
│       └── Payment[]
├── AccountsPayable
│   └── SupplierLedger[]
│       ├── Bill[]
│       ├── VendorCredit[]
│       └── Payment[]
├── BankManagement
│   └── BankAccount[]
│       └── BankTransaction[]
├── CashManagement
│   └── CashAccount[]
│       └── CashTransaction[]
├── PaymentGateway
│   └── PaymentAllocation[]
├── TaxManagement
│   ├── TaxCode[]
│   └── TaxGroup[]
├── CurrencyManagement
│   ├── Currency[]
│   └── ExchangeRate[]
└── CostAccounting
    ├── CostCenter[]
    ├── Department[]
    └── Project[]
```

---

## 37. Aggregate Roots

| Aggregate Root | Owns | Key Invariant |
|---------------|------|---------------|
| JournalEntry | JournalLines, ApprovalRecord | Debits = Credits; all lines reference active accounts |
| FiscalYear | FiscalPeriods, OpeningBalances | Periods are non-overlapping; cover the full year |
| CustomerLedger | Invoices, CreditNotes, Payments, Adjustments | Balance = Sum of all unallocated transactions |
| SupplierLedger | Bills, VendorCredits, Payments, Adjustments | Balance = Sum of all unallocated transactions |
| BankAccount | BankTransactions, Reconciliations | GL balance reconciles to bank statement balance |
| CashAccount | CashTransactions, Reconciliations | GL balance matches physical cash count |
| Payment | AllocationLines | Sum of allocations ≤ Payment Amount |
| TaxCode | TaxRateHistory | Effective dates do not overlap |
| ExchangeRate | RateHistory | One rate per currency pair per date |

---

## 38. Domain Events

Domain events published by the Accounting module that other modules may consume:

| Event | Trigger | Consumers |
|-------|---------|-----------|
| `accounting.journal.posted` | Journal entry posted | Reports, Audit |
| `accounting.period.locked` | Period locked | All posting modules (Sales, Purchase, Inventory) |
| `accounting.period.closed` | Period fully closed | Reports, Notifications |
| `accounting.fiscalyear.closed` | Fiscal year closed | Reports, AI Readiness |
| `accounting.payment.received` | Customer payment posted | Sales (Epic 7), Notifications |
| `accounting.payment.made` | Supplier payment posted | Purchase (Epic 6), Notifications |
| `accounting.customer.credithold` | Customer placed on hold | Sales (Epic 7) — blocks new orders |
| `accounting.customer.creditlimit.warning` | 80% of limit used | Sales (Epic 7), CRM (Epic 9) |
| `accounting.ar.invoice.overdue` | Invoice past due date | AR Clerk notification, Collections |
| `accounting.ap.bill.due` | Bill approaching due date | AP Clerk notification |
| `accounting.bank.reconciled` | Bank reconciliation completed | Reports |
| `accounting.taxreturn.due` | Tax period due date approaching | Tax Consultant notification |
| `accounting.anomaly.detected` | AI anomaly detection trigger | AI module (future) |

Domain events consumed by the Accounting module:

| Event | From | Accounting Action |
|-------|------|-------------------|
| `sales.invoice.posted` | Epic 7 | Create GL entry: DR AR / CR Revenue |
| `sales.creditnote.posted` | Epic 7 | Create GL entry: DR Revenue / CR AR |
| `sales.payment.received` | Epic 7 | Post to AR; create GL entry |
| `purchase.bill.posted` | Epic 6 | Create GL entry: DR Expense / CR AP |
| `purchase.creditnote.posted` | Epic 6 | Create GL entry: DR AP / CR Expense |
| `purchase.payment.made` | Epic 6 | Post to AP; create GL entry |
| `inventory.adjustment.posted` | Epic 5 | Create GL entry: DR/CR Inventory |
| `inventory.cost.updated` | Epic 5 | Revalue inventory GL account |

---

## 39. Reporting Requirements

### 39.1 Standard Financial Reports

| Report | Description | Filters |
|--------|-------------|---------|
| General Ledger Report | All GL entries with account, date, reference, amounts | Account, date range, cost center, source |
| Trial Balance | Account balances with debit/credit totals | Period, comparison period |
| Balance Sheet | Assets, liabilities, equity at a date | Date, comparison date |
| Profit & Loss | Revenue and expenses for a period | Period, comparison period, cost center |
| Cash Flow Statement | Operating, investing, financing cash flows | Period |

### 39.2 Subsidiary Ledger Reports

| Report | Description |
|--------|-------------|
| Customer Ledger | All transactions per customer for a period |
| Customer Aging Report | Aged AR balances by customer and bucket |
| Customer Statement | Statement of account for individual customer |
| Supplier Ledger | All transactions per supplier for a period |
| Supplier Aging Report | Aged AP balances by supplier and bucket |
| Supplier Statement | Statement of account for individual supplier |

### 39.3 Cash & Banking Reports

| Report | Description |
|--------|-------------|
| Bank Book | Chronological list of bank transactions for a period |
| Cash Book | Chronological list of cash transactions for a period |
| Bank Reconciliation Report | Statement balance vs GL balance with reconciling items |
| Cheque Register | All cheques issued with current status |

### 39.4 Tax Reports

| Report | Description |
|--------|-------------|
| Tax Summary Report | Output tax, input tax, net payable by tax code |
| Detailed Tax Transaction Report | Every taxable transaction with tax breakdown |
| VAT/GST Return | Formatted return for common jurisdictions |
| Withholding Tax Report | WHT deducted and remitted by supplier/period |

### 39.5 Journal Reports

| Report | Description |
|--------|-------------|
| Journal Report | All journal entries for a period with full detail |
| Recurring Journal Report | Status and history of all recurring entry templates |
| Audit Journal | All financial events with user, action, and timestamp |

### 39.6 Management Reports

| Report | Description |
|--------|-------------|
| Cost Center P&L | Revenue and expenses by cost center |
| Department Report | Financial summary by department |
| Project P&L | Revenue and costs by project |

---

## 40. KPI Requirements

Financial KPIs available in the executive dashboard:

| KPI | Description | Frequency |
|-----|-------------|-----------|
| Cash Position | Total cash and bank balances in base currency | Real-time |
| Accounts Receivable Total | Total outstanding AR | Real-time |
| Accounts Payable Total | Total outstanding AP | Real-time |
| AR Aging — Overdue % | % of AR that is overdue | Daily |
| AP Aging — Overdue % | % of AP that is overdue | Daily |
| Revenue (MTD) | Month-to-date revenue | Real-time |
| Gross Profit Margin | Gross profit / Revenue | Monthly |
| Net Profit Margin | Net profit / Revenue | Monthly |
| Current Ratio | Current assets / Current liabilities | Daily |
| Quick Ratio | (Current assets − Inventory) / Current liabilities | Daily |
| Days Sales Outstanding (DSO) | Average days to collect from customers | Monthly |
| Days Payable Outstanding (DPO) | Average days to pay suppliers | Monthly |
| Operating Cash Flow | Net cash from operations | Monthly |
| Tax Liability Balance | Outstanding tax owed to authorities | Real-time |
| Period Close Status | Which periods are open/closed/locked | Real-time |

---

## 41. Search Requirements

Users must be able to search across:
- Journal entries: by date, reference, description, account, amount
- Customer ledger: by customer name, invoice number, payment reference
- Supplier ledger: by supplier name, bill number, payment reference
- Bank transactions: by date, reference, amount, bank account
- Tax transactions: by tax code, period, amount

All search results must be paginated and exportable.

---

## 42. Import and Export

### Import

- **Opening Balances**: Import via structured template (CSV/Excel)
- **Chart of Accounts**: Bulk COA import for new company setup
- **Journal Entries**: Bulk journal import for migration
- **Bank Statement**: Import bank statement for reconciliation (CSV, OFX, MT940 format readiness)
- **Exchange Rates**: Bulk rate import by period

### Export

- **General Ledger**: Full GL export in CSV/Excel
- **Financial Statements**: Balance Sheet, P&L, Cash Flow in PDF and Excel
- **Tax Returns**: Export in required format per jurisdiction
- **Audit File**: Standardized audit file (XBRL/SAF-T readiness)
- **Payment Files**: Export payment batch for bank upload (future)
- **Trial Balance**: CSV/Excel export

---

## 43. Notifications

The system sends automated notifications for:

| Event | Recipients | Channel |
|-------|------------|---------|
| Invoice overdue | AR Clerk, Customer (optional) | In-app, Email |
| Customer credit limit warning | AR Clerk, Sales Manager | In-app |
| Customer placed on credit hold | AR Clerk, Sales Manager, CFO | In-app, Email |
| Bill due within N days | AP Clerk | In-app |
| Recurring journal generated | Accountant | In-app |
| Journal pending approval | Approver | In-app, Email |
| Payment pending approval | Approver | In-app, Email |
| Period close reminder | Controller | In-app |
| Tax return due | Tax Consultant, CFO | In-app, Email |
| Bank reconciliation overdue | Accountant, Controller | In-app |
| Anomaly detected (future AI) | CFO, Controller | In-app, Email |

---

## 44. Audit Requirements

### 44.1 Immutable Audit Trail

Every financial event creates an audit record that cannot be altered or deleted:
- Entity type and ID
- Action performed (created, approved, posted, reversed, locked, etc.)
- Actor (user ID and name)
- Timestamp (UTC)
- Before state and after state
- Session/IP context
- Reason or notes (where applicable)

### 44.2 Audit Accessibility

- Authorized users (Controller, CFO, Auditor role) can view full audit trail
- Audit records are searchable by date, user, entity type, and action
- Audit trail is exportable for external auditor review
- Audit records are retained for the configured data retention period (minimum 7 years)

### 44.3 Non-Repudiation

Electronic approvals carry the approver's identity, timestamp, and the state of the document at the time of approval. This creates a non-repudiable record of all financial authorizations.

---

## 45. Security Requirements

### 45.1 Role-Based Access Control (RBAC)

- All accounting functions are governed by the RBAC system (Epic 4)
- Accounting roles are predefined: Accountant, AR Clerk, AP Clerk, Cashier, Controller, CFO
- Custom roles can be defined per company
- Access to financial data is strictly scoped to the user's company tenant

### 45.2 Approval Matrix

- Approval thresholds are defined per role and monetary amount
- Approvals are recorded electronically with identity and timestamp
- A user cannot approve their own entries (self-approval is blocked)

### 45.3 Financial Data Protection

- Financial data is encrypted at rest and in transit
- PII embedded in financial records (customer names, payment references) is subject to data protection policies
- Bank account numbers are masked in display; full numbers accessible only to authorized roles

### 45.4 Sensitive Data Access

- Access to full financial reports is restricted by role
- Bank account details require an additional access confirmation
- Bulk data export requires elevated permissions and is logged

### 45.5 Immutable Financial History

- No user — including System Administrators — can delete or alter a posted journal entry or payment record
- Physical delete of financial records is prohibited; all operations use soft-delete patterns for non-posted records
- Any attempt to bypass this rule is logged and escalated

---

## 46. Compliance Requirements

- **GAAP Compatibility**: All accounting logic follows Generally Accepted Accounting Principles
- **IFRS Readiness**: Reporting structures support IFRS requirements (recognition, measurement, disclosure)
- **Tax Compliance Readiness**: Tax framework supports major global tax regimes (VAT, GST, Sales Tax, WHT)
- **SOX Readiness**: Audit trail, approval workflows, period controls, and SoD enforcement are aligned with Sarbanes-Oxley requirements
- **Data Privacy**: Financial records containing PII comply with GDPR and regional equivalents
- **XBRL/SAF-T Readiness**: Conceptual export support for regulatory audit files
- **Audit Readiness**: Complete, exportable audit trail for any fiscal period, sufficient for external audit purposes

---

## 47. Data Retention

| Data Category | Minimum Retention | Reason |
|---------------|-------------------|--------|
| General Ledger entries | 7 years | Regulatory/tax compliance |
| Journal entries | 7 years | Audit requirement |
| Financial statements | 7 years | Statutory requirement |
| Bank records | 7 years | Regulatory |
| Tax records | 7 years (or local minimum if higher) | Tax authority requirement |
| Audit trail | 7 years | Compliance |
| Payment records | 7 years | Regulatory |
| Customer/Supplier ledger | 7 years | Regulatory |

Soft delete is used for all financial records. Physical deletion is prohibited within the retention period.

---

## 48. Disaster Recovery

- **Recovery Point Objective (RPO)**: ≤ 1 hour — financial data loss must not exceed 1 hour of transactions.
- **Recovery Time Objective (RTO)**: ≤ 4 hours — the Accounting module must be restored within 4 hours of a major incident.
- Transactional integrity: all financial postings are atomic; incomplete transactions are rolled back on recovery.
- Regular backup verification: restoration drills are performed quarterly.
- Point-in-time recovery capability for financial database.

---

## 49. Performance Targets

| Operation | Target | Condition |
|-----------|--------|-----------|
| Trial Balance generation | < 10 seconds | Up to 500K GL entries |
| Financial statement generation | < 15 seconds | Full fiscal year |
| Single payment processing | < 2 seconds | Standard payment |
| GL search results | < 5 seconds | Date range within one fiscal year |
| Customer aging report | < 5 seconds | Up to 10,000 customers |
| Bank reconciliation load | < 3 seconds | Up to 5,000 statement lines |
| Journal entry posting | < 1 second | Single journal with up to 50 lines |
| Period lock enforcement | Immediate | All modules simultaneously notified |

---

## 50. Scalability Targets

| Metric | Target |
|--------|--------|
| GL entries per company | Up to 5,000,000 |
| Concurrent financial users per tenant | 500 |
| Companies per tenant | Unlimited (subject to subscription) |
| Bank statement lines per reconciliation | 10,000 |
| Journal lines per batch | 10,000 |
| Currencies supported | All ISO 4217 |
| Tax codes per company | 500 |
| Cost centers per company | 5,000 |

---

## 51. Cross-Module Dependencies

| Dependency | Direction | Epic | Nature |
|------------|-----------|------|--------|
| Authentication & Sessions | Consumes | Epic 2 | All accounting actions require authenticated sessions |
| Company Configuration | Consumes | Epic 3 | Base currency, fiscal year, company details |
| Users & RBAC | Consumes | Epic 4 | All permissions and approval workflows |
| Inventory Costing | Consumes | Epic 5 | Inventory value changes generate GL entries |
| Purchase Bills & AP | Consumes | Epic 6 | Bills post to AP ledger; payments update AP |
| Sales Invoices & AR | Consumes | Epic 7 | Invoices post to AR ledger; receipts update AR |
| Reporting & BI | Publishes to | Epic 11 | Financial data feeds executive dashboards |
| CRM Alerts | Publishes to | Epic 9 | Credit hold and collection events |
| Installments | Publishes to | Epic 10 | Payment schedules consume AR/AP data |

---

## 52. Cross-Module Contracts

### Contract: Sales → Accounting (Invoice Posted)

When a sales invoice is posted in Epic 7, the following data is provided to Accounting:
- Invoice ID, date, due date, currency, exchange rate
- Customer ID and AR account
- Line items with amounts, accounts, and tax codes
- Expected GL impact: DR Accounts Receivable / CR Revenue / CR Tax Liability

### Contract: Purchase → Accounting (Bill Posted)

When a purchase bill is posted in Epic 6, the following data is provided to Accounting:
- Bill ID, date, due date, currency, exchange rate
- Supplier ID and AP account
- Line items with amounts, accounts, and tax codes
- Expected GL impact: DR Expense/Inventory / CR Accounts Payable / CR Tax Recoverable (debit)

### Contract: Inventory → Accounting (Adjustment Posted)

When an inventory adjustment is posted in Epic 5:
- Adjustment ID, date, item, quantity, unit cost
- Expected GL impact: DR/CR Inventory Control / DR/CR Inventory Adjustment Expense

### Contract: Accounting → Sales (Credit Hold)

When a customer is placed on credit hold:
- Customer ID and hold status
- Sales module must block new order creation for this customer
- Hold reason is visible in the Sales module

---

## 53. Integration Readiness

### Future Integration Points

| Integration | Purpose | Status |
|-------------|---------|--------|
| Bank API / Open Banking | Automated bank statement import | Architecture ready; implementation future |
| Payment Gateway | Electronic payment processing | Interface defined; implementation future |
| Tax Authority API | E-invoicing and return submission | Data model ready; implementation future |
| Exchange Rate Provider | Automated daily rate feeds | Integration hook defined; manual rates used now |
| Payroll System | Payroll journal import | Import template defined; integration future |
| External Reporting Tools | BI and analytics export | Data export ready; connector future |
| Document Management | Invoice/bill attachment storage | Epic 5/6/7 storage patterns apply |

---

## 54. AI Readiness

### 54.1 AI Financial Assistant

A future AI assistant embedded in the Accounting module will:
- Answer natural language questions about financial position ("What is our current cash balance?", "Which customers are most overdue?")
- Summarize period financial performance in plain language
- Guide accountants through complex processes (e.g., bank reconciliation, year-end close)

**Readiness**: The data model and audit trail produce the structured data required. No architectural change needed for AI layer addition.

### 54.2 Cash Flow Forecasting

AI-powered cash flow forecasting will:
- Analyze historical AR collection patterns to forecast when outstanding invoices will be collected
- Analyze AP aging and payment history to forecast outgoing payment timing
- Predict 30/60/90-day cash position
- Alert the CFO to potential cash shortfalls

**Readiness**: AR aging data, payment history, and supplier payment terms are captured in the data model.

### 54.3 Revenue and Expense Forecasting

- Revenue trend analysis from historical P&L data
- Expense run-rate forecasting by account/cost center
- Seasonal pattern detection
- Forecast vs actual variance analysis

**Readiness**: Multi-period P&L data in the GL provides the required historical dataset.

### 54.4 Anomaly Detection

The AI anomaly detection engine will flag:
- Unusual journal entries (unexpected accounts, amounts outside normal ranges, unusual times)
- Duplicate invoice detection (same supplier, same amount, same period)
- Round-number transactions that may indicate fraud
- Vendor/customer behavior anomalies (payments to new accounts, sudden large credits)

**Readiness**: Complete GL event stream and audit trail provide the required signal data.

### 54.5 Fraud Detection Readiness

The data model is designed to support future fraud detection:
- All financial events have user, timestamp, and context
- Segregation of duties violations are logged
- Access patterns are recorded
- Override events are auditable

A future fraud analytics layer can be added without data model changes.

### 54.6 Smart Reconciliation

AI-assisted bank reconciliation will:
- Automatically match bank statement lines to GL entries using fuzzy matching
- Learn from historical matching patterns per company
- Suggest matches for ambiguous entries
- Flag unusual unmatched items for human review

**Readiness**: Bank transaction data, GL entries, and reconciliation history are structured for ML training.

### 54.7 Budget Recommendations

When budgeting is introduced (Epic 11), AI will:
- Suggest budget allocations based on historical spend patterns
- Alert on budget variances in real-time
- Recommend reallocation of unspent budget

### 54.8 AI Financial Insights

The CFO dashboard will receive AI-generated financial insights:
- Weekly financial health summary
- Top spending anomalies
- Receivables at risk
- Payment optimization recommendations (optimize payment timing for cash flow)
- Tax exposure alerts

---

## 55. Analytics Readiness

The Accounting module exposes structured, query-optimized financial data for analytics:
- P&L by period, department, cost center, and project
- Balance Sheet trends over time
- AR and AP turnover trends
- Payment behavior analytics (DSO, DPO)
- Tax compliance analytics
- User activity and approval analytics

Data is structured to support future integration with:
- OLAP-style financial cubes
- Business intelligence tools
- Executive dashboards (Epic 11)

---

## 56. Multi-Tenant SaaS

### 56.1 Tenant Isolation

The Accounting module enforces strict financial isolation between tenants:
- Each tenant has an isolated financial data namespace
- No cross-tenant data queries are permitted
- Tenant isolation is enforced at the data layer, not only at the application layer

### 56.2 Company Financial Isolation

Within a tenant, each company's financial data is isolated:
- GL entries, COA, fiscal years, and all financial records are scoped to a single company
- A user with access to Company A cannot view Company B's financials, unless explicitly granted multi-company access by the tenant administrator

### 56.3 Branch Readiness

The data model includes branch identifiers on all financial records. In a future release, branch-level:
- Financial statements
- Bank account management
- Petty cash management
- P&L reporting

will be activated without data migration.

### 56.4 Soft Delete

All financial entities use soft delete (is_deleted flag + deleted_at timestamp). Physical deletion is prohibited for financial records within the retention period. This supports data recovery and audit trail completeness.

### 56.5 Feature Flags

Accounting features are controlled by feature flags per tenant:
- `accounting.multicurrency.enabled` — enable multi-currency operations
- `accounting.costcenters.enabled` — enable cost center accounting
- `accounting.approvalworkflow.enabled` — enable journal/payment approvals
- `accounting.taxwitholding.enabled` — enable WHT calculations
- `accounting.ai.enabled` — enable AI financial assistant (future)
- `accounting.bankreconciliation.enabled` — enable bank reconciliation module

Feature flags enable staged rollout and subscription-tier feature management.

### 56.6 Subscription Compatibility

The Accounting module's feature set maps to subscription tiers:
- **Starter**: Core GL, basic AR/AP, single bank, basic tax, basic reporting
- **Professional**: Full feature set minus AI and electronic payments
- **Enterprise**: Full feature set including AI readiness, multi-currency, cost centers, approval workflows

---

## 57. Extensibility Strategy

The Accounting domain is designed for extension through:

### 57.1 COA Extensibility

- New account groups can be defined without system changes
- Custom account types for specialized industries can be added via configuration
- COA templates are extensible for new industries

### 57.2 Tax Framework Extensibility

- New tax types can be registered via configuration
- Jurisdiction-specific calculation rules are pluggable
- Tax reporting templates are configurable per jurisdiction

### 57.3 Approval Workflow Extensibility

- Approval chains are fully configurable per transaction type and amount
- New approval step types (parallel, sequential, threshold-based) can be added
- External approval integration (email approval links) is architecturally supported

### 57.4 Reporting Extensibility

- New financial report templates can be added
- Custom report dimensions (beyond standard cost center/department) are supportable
- Report output formats (PDF, Excel, CSV, XBRL) are extensible

### 57.5 Integration Extensibility

- All accounting domain events are published to an event bus for external consumption
- Webhook support for financial events (invoice posted, payment made, period closed)
- API access for external system integration (future public API)

---

## 58. Versioning Strategy

- The Accounting module follows semantic versioning aligned with the ERP platform version
- Breaking changes to financial data structures require a migration plan and backward compatibility period
- COA and tax code configurations are versioned: historical snapshots are preserved
- API changes follow the platform API versioning policy (Epic 1)

---

## 59. Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Data migration errors during GL opening balance setup | Medium | High | Validation reports; trial balance verification before go-live |
| Exchange rate errors leading to material misstatements | Low | High | Rate validation rules; revaluation audit reports; CFO review |
| Period lock bypass — unauthorized postings in closed periods | Low | Critical | Multiple enforcement layers (application + data layer); audit alerts |
| Control account reconciliation failure (AR/AP out of sync) | Low | High | Automated reconciliation checks on every posting; daily reconciliation reports |
| Tax code misconfiguration leading to incorrect filings | Medium | High | Tax configuration review workflow; accountant sign-off before use |
| AI anomaly false positives disrupting operations | Medium | Medium | AI outputs are advisory only; human review required for all alerts |
| Performance degradation at GL entry volumes above 1M | Low | Medium | Indexed GL queries; archival strategy for historical periods |

---

## 60. Assumptions

- Companies will operate on the accrual basis of accounting by default.
- Base currency is set once at company setup and cannot be changed post go-live (requires data migration).
- The Accounting module does not process payroll; payroll journals are imported from an external system.
- Fixed asset management and depreciation are out of scope for this epic.
- The first implementation does not include consolidated financial statements across multiple companies.
- AI features are conceptually designed in this specification but implemented in a future phase.
- Exchange rates are manually entered in the initial implementation; automated feeds are a future enhancement.
- Banking integration (auto-import of bank statements) is a future feature; manual entry or CSV import is supported in this epic.
- The system operates on a single fiscal year start date per company; mid-year changes require data migration.
- Government e-invoicing submission is a future feature; export files are produced for manual submission.

---

## 61. Constraints

- The system must operate as a Modular Monolith; no separate microservice for Accounting.
- All financial operations must be transactionally consistent within the Accounting module.
- The Accounting module cannot query the Sales, Purchase, or Inventory databases directly; it only receives events and stores its own authoritative copies of financial data.
- Reporting must not degrade operational posting performance; report generation uses read-optimized views.
- Financial records must never be physically deleted within the data retention period.
- The system must support concurrent multi-user operations on the same company's GL without data corruption.

---

## 62. Success Metrics

### Financial Accuracy

- **SM-001**: Balance Sheet equation holds at all times — zero tolerance for imbalance.
- **SM-002**: AR control account reconciles to customer ledger sum — zero tolerance for discrepancy.
- **SM-003**: AP control account reconciles to supplier ledger sum — zero tolerance for discrepancy.
- **SM-004**: Zero undetected unauthorized postings to locked periods.

### Operational Efficiency

- **SM-005**: Month-end close process completed in under 2 business days.
- **SM-006**: Bank reconciliation completed in under 30 minutes for accounts with up to 500 monthly transactions.
- **SM-007**: AR aging report generated in under 5 seconds.
- **SM-008**: Financial statements generated in under 15 seconds.

### User Adoption

- **SM-009**: 90% of accountants complete core workflows (journal entry, payment, reconciliation) without support assistance after initial training.
- **SM-010**: 95% of financial KPIs accessible from the CFO dashboard without generating separate reports.

### Compliance

- **SM-011**: All financial audit trails are complete and exportable for any 7-year period.
- **SM-012**: Tax reports are accurate to 100% — zero tolerance for tax calculation errors.
- **SM-013**: Zero undetected SoD violations.

### Business Value

- **SM-014**: Companies operating on the platform require no external accounting software for core bookkeeping needs.
- **SM-015**: DSO for companies using the AR module improves by at minimum 10% within 6 months of adoption, due to better aging visibility and collections workflow.

---

## 63. Glossary

| Term | Definition |
|------|------------|
| Accounts Payable (AP) | The total amount a company owes to its suppliers |
| Accounts Receivable (AR) | The total amount owed to a company by its customers |
| Accrual Accounting | Revenue and expenses recognized when earned/incurred, not when cash moves |
| Aging | Classification of AR or AP balances by how long they have been outstanding |
| Balance Sheet | Financial statement showing assets, liabilities, and equity at a point in time |
| Base Currency | The primary operating currency in which financial statements are reported |
| Chart of Accounts (COA) | The complete list of accounts used to record financial transactions |
| Closing Entry | Year-end journal entry transferring net income/loss to retained earnings |
| Control Account | A summary GL account that reconciles to the total of a subsidiary ledger |
| Cost Center | An organizational unit used to track and allocate costs |
| Credit Note | A document reducing the amount owed by a customer or to a supplier |
| Debit Note | A document increasing the amount owed by a customer or to a supplier |
| Double-Entry Accounting | Accounting system where every transaction has equal debits and credits |
| DSO (Days Sales Outstanding) | Average days to collect payment from customers |
| Exchange Gain/Loss | Financial gain or loss due to changes in exchange rates |
| Fiscal Period | A subdivision of the fiscal year (typically monthly) for accounting purposes |
| Fiscal Year | The 12-month accounting year used by the company |
| General Ledger (GL) | The master record of all financial transactions |
| IFRS | International Financial Reporting Standards |
| Journal Entry | A record of a financial transaction in the GL with balanced debits and credits |
| P&L | Profit and Loss statement; also called Income Statement |
| Period Lock | Prevention of new postings to a specific accounting period |
| Reconciliation | The process of matching two sets of financial records to ensure they agree |
| Retained Earnings | Accumulated net income not distributed to owners |
| Revaluation | Restating foreign currency balances at current exchange rates |
| RBAC | Role-Based Access Control |
| SoD | Segregation of Duties — separation of conflicting financial responsibilities |
| Trial Balance | Report listing all GL account balances; total debits must equal total credits |
| VAT | Value Added Tax — a consumption tax charged at each stage of production/sale |
| GST | Goods and Services Tax — similar to VAT used in various countries |
| WHT | Withholding Tax — tax deducted at source on payments |
| Write-Off | Removal of an uncollectable receivable from the books |

---

## 64. Acceptance Criteria

The Accounting & Finance epic is accepted when the following capabilities are fully operational:

### General Ledger & COA

- [ ] Chart of Accounts can be created, organized hierarchically, and modified by authorized users
- [ ] Industry COA templates are available for company setup
- [ ] Manual journal entries can be created, submitted, approved, and posted
- [ ] System-generated journal entries are automatically created from Sales, Purchase, and Inventory events
- [ ] Recurring journal entries execute on schedule
- [ ] Journal reversal creates a correct inverse entry linked to the original
- [ ] GL query returns accurate results filtered by account, period, cost center, and source
- [ ] Every GL entry provides drilldown to the source document

### Fiscal Calendar

- [ ] Fiscal years and periods are configurable per company
- [ ] Period locking prevents posting from all modules
- [ ] Year-end close correctly transfers net income/loss to retained earnings
- [ ] Opening balances can be entered and validated

### Financial Statements

- [ ] Balance Sheet is accurate and the equation holds (Assets = Liabilities + Equity)
- [ ] Profit & Loss correctly summarizes revenue and expenses for any period
- [ ] Cash Flow Statement is generated using the indirect method
- [ ] Trial Balance total debits equal total credits at all times
- [ ] Comparative reporting is available (period vs prior period)

### Accounts Receivable

- [ ] Customer ledger balance reconciles to AR control account
- [ ] Customer aging correctly buckets outstanding invoices
- [ ] Customer credit limits are enforced; credit hold is applied and blocks sales
- [ ] Customer statements are generated for any period
- [ ] AR write-off requires approval and posts correct GL entry

### Accounts Payable

- [ ] Supplier ledger balance reconciles to AP control account
- [ ] Supplier aging correctly buckets outstanding bills
- [ ] Vendor credits are applied against outstanding bills
- [ ] Supplier statement reconciliation workflow is available
- [ ] Remittance advice is generated for supplier payments

### Banking & Cash

- [ ] Multiple bank accounts are supported with GL linkage
- [ ] Bank reconciliation matches GL to statement balance and locks when complete
- [ ] Cheque status lifecycle is tracked (issued → presented → cleared/cancelled)
- [ ] Petty cash vouchers, reconciliation, and replenishment are supported

### Payments

- [ ] Customer and supplier payments are processed and allocated to specific invoices/bills
- [ ] Partial payments, advance payments, and overpayments are handled correctly
- [ ] Credit notes, debit notes, and refunds are supported
- [ ] Payment allocation engine is accurate; no unallocated payment is lost

### Tax Management

- [ ] Tax codes and groups are configurable per company
- [ ] Tax is calculated and posted correctly on all taxable transactions
- [ ] Tax reports are generated with correct output and input tax balances
- [ ] Zero-rated, exempt, and out-of-scope classifications are supported

### Multi-Currency

- [ ] Foreign currency transactions record both foreign and base currency amounts
- [ ] Realized exchange gain/loss is calculated and posted at settlement
- [ ] Period-end revaluation updates open balances and posts unrealized gain/loss
- [ ] Financial statements can be generated in base currency

### Cost Accounting

- [ ] Cost center assignment is enforced on configured accounts
- [ ] Cost center P&L and expense reports are generated correctly
- [ ] Project-level revenue and cost tracking is operational

### Financial Controls

- [ ] Approval workflows are enforced for journals and payments above configured thresholds
- [ ] Period locks are enforced across all modules simultaneously
- [ ] SoD violations are blocked (creator cannot be sole approver)
- [ ] Audit trail is complete, immutable, and exportable

### Reporting

- [ ] All standard financial reports are generated accurately
- [ ] Reports are available in PDF and Excel export formats
- [ ] Financial KPIs are visible in the executive dashboard

---

## 65. Epic Completion Criteria

Epic 8 is complete when:

1. All acceptance criteria in Section 64 are verified by the QA team
2. All automated tests pass (unit, integration, and end-to-end for critical financial flows)
3. Balance Sheet equation holds under load testing with 1M+ GL entries
4. AR and AP control account reconciliation is verified automatically on every posting
5. Period lock enforcement is verified across all source modules (Sales, Purchase, Inventory)
6. Audit trail is verified to be complete and immutable for all financial events
7. All financial reports produce correct output verified against known test datasets
8. Security review confirms: RBAC enforcement, SoD controls, and data isolation between companies
9. Performance targets in Section 49 are verified under load testing
10. Migration documentation (opening balance import) is tested end-to-end
11. PHR (Prompt History Record) for this epic is created and archived
12. ADRs for significant architectural decisions are documented

---

## 66. Future Roadmap

### Epic 9 — CRM (Customer Relationship Management)

- AR data feeds CRM with customer payment behavior and credit standing
- Collections workflow integrates with CRM customer communication

### Epic 10 — Installments

- Installment billing schedules integrate with AR
- Deferred revenue recognition rules interact with the GL

### Epic 11 — Reports & Intelligence

- Financial data from Epic 8 feeds advanced BI dashboards
- AI financial forecasting and anomaly detection
- Budgeting and budget vs actual reporting

### Epic 12 — Deployment

- Financial data backup, archival, and disaster recovery procedures
- Regulatory compliance documentation for financial data

### Future Epics (Not Yet Scheduled)

- **Fixed Assets & Depreciation**: Asset register, depreciation schedules, disposal accounting
- **Payroll**: Salary processing, payroll journal automation, statutory deductions
- **Treasury Management**: Loan management, letter of credit, investment portfolio
- **Consolidated Financial Statements**: Group-level consolidation across multiple companies
- **E-Invoicing**: Government API integration for e-invoice submission and VAT reporting
- **Branch Accounting**: Full branch-level P&L, cash management, and reconciliation
- **Budgeting & Forecasting**: Budget creation, approval, and variance analysis
- **Audit Portal**: External auditor access with read-only, time-limited financial data access

---

*Document Status: Draft — Pending Controller and CFO Review*
*Next Steps: Run `/sp.clarify` for targeted clarification questions, then `/sp.plan` to generate the architectural plan.*
*SSOT Governance: This document is the single source of truth for Epic 8 — Accounting & Finance. All implementation decisions must trace to requirements defined herein.*
