# DATABASE_DESIGN.md

# DevSphere ERP

## Database Design Specification

Version: 1.0

Status: Approved

---

# 1. Purpose

This document defines the official database design standards for the DevSphere ERP platform.

It establishes the rules for designing tables, relationships, constraints, indexes, migrations, auditing, tenant isolation, and future database evolution.

Every existing and future database object must comply with this specification.

---

# 2. Database Engine

**Primary Database**

* PostgreSQL

**ORM**

* SQLAlchemy 2.x (Declarative Mapping)

**Migration Tool**

* Alembic

No other database engine should be considered the primary implementation unless officially approved.

---

# 3. Database Philosophy

The database is designed to be:

* Normalized
* Consistent
* Scalable
* Secure
* Multi-Tenant
* Audit Friendly
* Extensible
* Migration Safe

Business rules belong in the Service Layer, not inside the database.

---

# 4. Naming Convention

## Tables

Use plural snake_case names.

Examples:

* users
* companies
* user_credentials
* refresh_tokens
* inventory_items
* purchase_orders

---

## Columns

Use snake_case.

Examples:

* company_id
* created_at
* updated_at
* deleted_at
* first_name
* last_name

Avoid abbreviations.

Good:

customer_address

Bad:

cust_addr

---

## Primary Keys

Every table uses

```text
id UUID PRIMARY KEY
```

No integer primary keys.

---

## Foreign Keys

Always follow

```text
<referenced_table>_id
```

Examples

```text
company_id

user_id

product_id

supplier_id
```

---

## Index Names

Convention

```text
ix_<table>_<column>
```

Example

```text
ix_users_email

ix_products_sku
```

---

## Unique Constraints

Convention

```text
uq_<table>_<column>
```

Example

```text
uq_users_email
```

---

## Foreign Keys

Convention

```text
fk_<table>_<referenced_table>
```

Example

```text
fk_users_companies
```

---

# 5. UUID Strategy

Every business table uses UUID.

Benefits

* Better distributed systems
* Safer APIs
* Harder to enumerate records
* Easier future replication

No auto-increment integer IDs.

---

# 6. Common Columns

Every business table should include the following standard fields unless there is a valid documented exception.

```text
id

created_at

updated_at

created_by

updated_by

deleted_at

deleted_by

is_deleted
```

These provide:

* Auditing
* Soft Delete
* Traceability
* Accountability

---

# 7. Audit Columns

Every critical business entity must track who created and modified it.

Minimum audit fields:

```text
created_at

created_by

updated_at

updated_by
```

Financial and security tables may require additional audit information.

---

# 8. Soft Delete Policy

Business data should not normally be physically deleted.

Instead:

```text
is_deleted = true

deleted_at = timestamp

deleted_by = user_id
```

Soft delete preserves historical records for reporting and auditing.

Physical deletion is allowed only for temporary or disposable data where explicitly approved.

---

# 9. Timestamp Standard

Use timezone-aware UTC timestamps.

Examples:

```text
created_at

updated_at

deleted_at

expires_at

last_login_at
```

All timestamps should be stored in UTC.

Timezone conversion belongs to the frontend.

---

# 10. Multi-Tenant Rules

Every tenant-owned table must include:

```text
company_id
```

Examples:

* products
* customers
* suppliers
* invoices
* payments
* inventory
* journal_entries

Global tables (e.g., system configuration) are exempt.

Every query involving tenant-owned data must filter by company_id.

---

# 11. Relationship Standards

Relationships should be explicit.

Examples:

One Company

↓

Many Users

One Customer

↓

Many Sales

One Supplier

↓

Many Purchases

One Product

↓

Many Inventory Transactions

Avoid ambiguous relationships.

---

# 12. Foreign Key Rules

All relationships must enforce referential integrity.

Every foreign key must reference an existing parent record.

Deletion behavior (CASCADE, RESTRICT, SET NULL) must be explicitly defined based on business rules.

Never rely on implicit defaults.

---

# 13. Unique Constraints

Examples:

* Email Address
* Username
* Company Slug
* SKU (per company if applicable)

Business uniqueness must always be enforced at the database level.

---

# 14. Indexing Strategy

Indexes should be added for:

* Primary Keys
* Foreign Keys
* Frequently searched columns
* Login fields (email)
* SKU
* Invoice Number
* Customer Code
* Supplier Code

Composite indexes should be used where beneficial.

Example:

```text
(company_id, sku)

(company_id, email)

(company_id, invoice_number)
```

---

# 15. Check Constraints

Use database constraints where appropriate.

Examples:

Quantity ≥ 0

Price ≥ 0

Discount ≥ 0

Percentage between 0–100

Business validation still remains in the Service Layer.

---

# 16. Enum Strategy

Use PostgreSQL ENUM only for stable values.

Examples:

* User Status
* Gender
* Token Type

Frequently changing business values should be stored in lookup tables instead.

---

# 17. Lookup Tables

Use lookup tables for configurable business data.

Examples:

* Categories
* Brands
* Units
* Payment Methods
* Tax Types

Avoid hardcoding business values.

---

# 18. Financial Data Rules

Financial tables must never lose historical accuracy.

Records should be corrected through reversing entries or adjustment transactions rather than destructive updates.

---

# 19. Inventory Rules

Inventory quantities must always remain traceable.

Every stock movement should have a corresponding transaction record.

Current stock should be derivable from transaction history where appropriate.

---

# 20. Authentication Tables

Authentication-related tables include:

* users
* user_credentials
* refresh_tokens
* sessions
* password_reset_tokens
* email_verification_tokens
* audit_logs

These tables follow stricter security and retention policies.

---

# 21. Migration Standards

Every schema change must use Alembic.

Migration rules:

* One logical change per migration.
* Never edit an applied migration.
* Use descriptive messages.
* Test migrations before release.

Database schema changes must never bypass Alembic.

---

# 22. Data Integrity

The database should enforce:

* Primary Keys
* Foreign Keys
* Unique Constraints
* Check Constraints
* Not Null Constraints

Critical integrity rules must exist at both the database and application layers.

---

# 23. Performance Guidelines

To ensure scalability:

* Index frequently queried columns.
* Avoid unnecessary joins.
* Use pagination.
* Optimize large reports.
* Prevent N+1 query problems.
* Use eager loading only where appropriate.

Performance optimizations must not compromise correctness.

---

# 24. Backup & Recovery

The production database should support:

* Scheduled Backups
* Point-in-Time Recovery (PITR)
* Disaster Recovery Procedures
* Backup Verification

Backup strategy is an operational requirement and must be documented separately.

---

# 25. Future Expansion

The schema must be designed to support future modules without major redesign.

Potential future modules include:

* POS
* HRM
* Payroll
* Manufacturing
* Warehouse Management
* AI Analytics
* Mobile Applications
* Third-Party Integrations

Database evolution should occur through additive, backward-compatible migrations whenever possible.

---

# 26. Database Standards Summary

The DevSphere ERP database follows these core principles:

* PostgreSQL as the primary database.
* UUID primary keys.
* SQLAlchemy 2.x ORM.
* Alembic migrations.
* Multi-tenant isolation using company_id.
* Standard audit fields.
* Soft delete for business entities.
* Strong referential integrity.
* Proper indexing.
* Explicit constraints.
* UTC timestamps.
* Extensible schema design.

---

# 27. Single Source of Truth

This document is the official database design specification for DevSphere ERP.

All current and future database models, migrations, and schema changes must conform to these standards.
